# 公共 HTTP 客户端

使用 `from app.common.http import http_clients, http_context, iter_sse`。

```python
http = http_clients.get("default")
data = await http.post_json(url, json=payload, business="资源同步")
# 大 JSON 按业务关闭正文采集；两个方向可独立设置。
data = await http.get_json(url, log_response_body=False)
with http_context(business="模型调用", operator="admin", log_request_body=False):
    async with http_clients.get("ai").stream("POST", url, json=payload) as response:
        async for event in iter_sse(response.aiter_bytes()):
            print(event["data"])
await http_clients.get("download").download_file("POST", url, destination, json=payload)
```

普通 JSON 正文及请求头原样记录、不脱敏、不截断；文件及流式正文默认不记录。
SDK 注入 `http_clients.get("ai").raw`，重试由 SDK 显式设置为 0。
命名客户端：default、download、ai、wechat、oauth。独立后台进程须自行 start/close。
异常沿用 HTTPX 原始异常，业务服务负责映射业务提示。

日志表 `sys_http_log_YYYYMM` 按上海时区的请求开始月份归属。
`sys_http_log_month` 登记月份和结构版本；模板版本目前为 1。
未来升级先通过 Alembic 遍历登记月份修改历史表，再同步模板；禁止修改已执行迁移。
列表与详情不查询正文；正文按 UTF-8 字节分页，完整下载经 60 秒一次性凭据交给浏览器。
接口均位于 `/api/v1/system/http-log`，单月查询，拒绝跨月时间范围。

正文不设应用上限，但数据库 `max_allowed_packet`、字段容量、驱动及写入内存仍有限。
元数据先写入，正文独立更新；写入失败标记 failed 并告警，不影响业务。
正文队列最多 256 项，正文暂存系统临时目录，结束/失败清理；停服最多等待 15 秒。
本期不自动清理历史月表。日志权限由超级管理员分配给需要查看的角色。

## 本地验收

- 数据库已升级到 `20261014_http_log`，准备 `202610`、`202611` 月表；菜单位于系统管理的 HTTP 调用日志。
- 实际 MySQL 验证 JSON 请求、响应原文写入及正文分页；当前 `max_allowed_packet` 为 64 MiB。
- 隔离库演练迁移升级/降级、失败正文保留元数据、单月过滤和权限检查。
- 后端完整测试 138 项通过，含静态资源托管及 OAuth/微信模拟适配回归；前端日志/字典相关测试 10 项通过。
- 三份静态产物 208 个文件哈希一致；服务健康检查、首页、新接口及失效下载凭据状态正常。
- 演示页主键从 UUID 改为后端要求的数字 ID，原有 3 处 TS2352 已消除，全量类型检查通过。
- 修复一体化托管首页资源引用 `/web/js/…` 返回 404 的问题；`/web` 与根路径共享同一份生产产物。
- 用户确认后，通过正常滑块验证码登录真实后台；验证日志筛选、单月切换、空月份、详情、请求/响应切换及按需读取。
- 真实浏览器验证 120,036 字节中文正文：第一页在 65,535 字节字符边界结束，第二页包含结束标记，无乱码；完整下载还原 40,000 个中文字，原值全部一致。
- OAuth、微信缺少测试配置，按用户确认保留真实授权联调待配置；已有模拟合同回归通过。
- 真实模型请求已尝试：当前地址返回 404，版本化兼容路径发生超时。用户确认网关暂不可用，保留真实模型联调待恢复；未擅自改写模型地址或密钥。
- AI SDK 客户端注入及分项超时继承已通过本地测试。首次并发前端测试因工作进程启动超时未执行，串行重跑 10 项全部通过。
- 最终生产构建成功，后端托管及 Docker 副本均为 208 个文件，逐文件哈希无差异；入口脚本及 16 个直接依赖返回 200。
- 最终浏览器刷新验证通过，日志详情结果使用后端字典翻译，默认不读取正文；页面保留供用户查看。所有改动留在工作区，未提交或推送。
