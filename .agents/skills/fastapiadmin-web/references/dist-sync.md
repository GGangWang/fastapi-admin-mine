# 前端构建产物（dist）重建 / 同步 / 核对

**源码改对 ≠ 部署改对。** dist 是生成物不入 git（`.gitignore`），但仓库存在多份预构建副本直接随部署走。前端源码改完必须重建 + 同步，否则线上仍跑旧行为（AI 聊天重复"连接成功"曾因此被误判一轮：源码已修对，但三份 dist 还是修复前的包）。

## 三份产物与各自服务入口

| 产物 | 服务入口 |
| --- | --- |
| `frontend/web/dist` | 构建输出（`pnpm build:prod` 的 outDir） |
| `docker/nginx/web/dist` | docker 部署的 `/web`（nginx.conf `alias /usr/share/nginx/html/web/dist`） |
| `backend/dist` | 一体化部署的 `app.frontend("/")` 托管（`path_conf.FRONTEND_DIST_DIR`） |

移动端：`docker/nginx/app/dist/build/h5`（nginx `/app`；注意真实入口在 `build/h5` 下一层）。

## 重建 + 同步

```bash
cd frontend/web && pnpm build:prod          # 输出到 frontend/web/dist
cd ../.. && rsync -a --delete frontend/web/dist/ docker/nginx/web/dist/ \
              && rsync -a --delete frontend/web/dist/ backend/dist/
```

- `--delete` 必须：产物文件带内容 hash，不删旧文件会残留
- 产物只发服务器（无源码、无构建）的发布通道由根目录 `deploy-artifacts.sh` 负责（见 `fastapiadmin-deploy` 技能）：服务端同步走 `push_dir`（staging 解包 → 校验 index.html → 备份旧目录 → 原子替换）

## 核对：对产物 grep，别只看 src/

minify 后函数名/注释没了，但属性访问（`WebSocket.CLOSED`）与提示文案字符串仍在：

```bash
grep -l "ai/chat/ws" docker/nginx/web/dist/js/*.js                    # 定位 chunk
grep -oE '.{0,60}readyState.{0,60}' <chunk> | grep -i websocket      # 确认守卫（-oE 重复上限 255）
```

示例：旧包是 `if (ws?.readyState === WebSocket.OPEN) return;`（`CLOSED` 命中 0 次）；修复后为 `if (ws && ws.readyState !== WebSocket.CLOSED) return;`。

**线上反馈"没生效"时，第一步先核对 dist 产物里有没有特征串**，再回源码；docker 部署还需重新出镜像 / 重新上传 docker 目录才生效。

## 后端一体化托管坑（owner：本文件）

`register_frontend`（`backend/app/__init__.py`）的探测与挂载必须用**同一个** `path_conf.FRONTEND_DIST_DIR`（backend/dist）。历史上探测用 path_conf 但挂载硬编码 `frontend/web/dist`，导致 500：`check_dir=False` 时启动不报错、**首请求才炸**，只能靠 loguru 日志（`backend/logs/fastapiadmin.log`）定位。
