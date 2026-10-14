---
name: res-nexus-web
description: "Use for ResNexus admin frontend (frontend/web, Vue3 + Vite + TS + Element Plus + Tailwind + Pinia) page creation, CRUD screens, API layer wiring, routing/menu/permission changes. Invoke before writing or modifying frontend/web code, or when debugging KeepAlive cache, duplicate-connection, or build-artifact-not-updated issues. Keywords: Vue3, FaTable, FaSearchBar, FaDialog, useTable, useCrudDialog, useCrudForm, useTableColumns, useImportExport, v-hasPerm, api/module_x, views/module_x, defineOptions, KeepAlive, worktab, dist, rsync."
metadata:
  argument-hint: "page/route name, API module name, or issue description"
---

# ResNexus Web 技能

适用 `frontend/web/`（小程序端 `frontend/app` 归其自身技能）。后端接口改动看 `res-nexus-backend`。

## 何时使用

- 新建/修改 `views/module_x/` 业务页面、对应 `api/module_x/xxx.ts`
- 做 CRUD 屏（列表 + 搜索 + 弹窗 + 权限）
- 改路由 / 菜单 / 权限联动
- 排查"重复弹窗 / 重复连接 / 重复请求"、页面缓存（KeepAlive）问题
- 源码改动后确认构建产物（dist）已重建同步

## 目录

| 位置                  | 说明                                                                                                        |
| --------------------- | ----------------------------------------------------------------------------------------------------------- |
| `api/module_x/xxx.ts` | API 层，与后端模块一一对应                                                                                  |
| `views/module_x/`     | 业务页面；页面私有组件放同目录 `components/`                                                                |
| `components/`         | 公共组件 `FaXxx`——写页面先找现成的                                                                          |
| `hooks/core/`         | 开发套件：useTable / useCrudForm / useCrudDialog / useTableColumns / useAuth / useImportExport / useConfirm |
| `router/`             | `routes.ts` 静态壳 + 动态路由管线（guards → MenuProcessor → RouteRegistry）                                 |
| `store/modules/`      | pinia store（user / worktab / menu / setting / dict…）                                                      |
| `locales/langs/`      | i18n `zh.json` / `en.json`（必须双写）                                                                      |
| `utils/`              | http（request 封装）、auth、storage、navigation、download、sse                                              |

## 核心约定

- **API 层**：`import { request } from "@utils"`；对象字面量方法；泛型用全局 `ApiResponse<T>` / `PageResult<T>`；URL 对齐后端 controller（如 `/system/dict/type/list`）。完整模板见 [crud-suite](./references/crud-suite.md)
- **页面**：优先复用套件（FaSearchBar / FaTable / FaDialog / FaForm），不手写 ElTable / ElDialog
- **权限**：按钮级 `v-hasPerm="'module_x:res:op'"`（可传数组）；代码内 `useAuth().hasAuth(...)`；标识三段式与后端一致
- **路由/菜单**：业务路由来自后端菜单（动态 addRoute）；新页面要同时在管理端"菜单管理"配 route_path / route_name / component_path / keep_alive；页面 `defineOptions({ name })` 必须等于菜单 route_name，否则缓存/排除失效
- **i18n**：文案走 `$t('key')`，zh.json 与 en.json 都要加
- **自动导入**：Vue API（ref/computed/watch…）无需 import；Element Plus 组件模板中直接用
- **有副作用的页面**（WebSocket / 定时器 / 全局监听）必须写 `onActivated` / `onDeactivated`：deactivated 释放、activated 恢复——`onUnmounted` 只在缓存被清空时触发，不能做唯一清理点
- **环境变量**：公共 `.env`（`VITE_APP_BASE_API=/api/v1`、`VITE_PORT=5180`）；`.env.development`（`VITE_API_BASE_URL` 代理目标；AI WebSocket `VITE_APP_WS_ENDPOINT` 直连后端绕过代理）
- **改完必跑**：`pnpm ts:check`；提交时 husky/commitlint + lint-staged 自动过，勿绕过钩子

## KeepAlive 与连接类资源（坑，本节 owner，勿回退）

> 本段（及本技能内其他坑内容）为 owner：根 SKILL.md 只留指针，不重复全文。

- KeepAlive 的 `include` 来自 worktab 的 `opened`（`layouts/fa-page-content/index.vue`）；`opened` 为空时 include 是 `undefined`——**undefined 时 KeepAlive 不清理**，别假设"清空页签即清缓存"
- KeepAlive 内部缓存**无法从外部直接清空**，唯一抓手是改 `include` / `exclude` 触发内部 prune。退出登录时 `worktab.store.ts` 的 `clearAll()` 把被移除页签的组件名写入 `keepAliveExclude` 清掉旧实例（下次 `openTab` 的 `removeKeepAliveExclude` 自动摘除）——改 store 时别删这段
- WebSocket 守卫必须覆盖握手期：`if (ws && ws.readyState !== WebSocket.CLOSED) return`。只挡 `OPEN` 会在 CONNECTING 期间重入时新建连接、旧引用被覆盖，泄漏的旧连接仍会完成握手弹提示（AI 聊天曾出现退出→登录后多 ws 实例 + 多条"连接成功"提示）
- 主动断开时先摘 `onopen/onmessage/onerror/onclose` 再 `close()`，防 close 竞态触发提示或状态回调
- 路由出口 KeepAlive **只挂一层**且**不许加 `:max`**：动态目录路由的 `component` 保持 `undefined`（`MenuProcessor.mapMenuNode` / `RouteTransformer.handleNormalRoute`），靠 vue-router RouterView depth 跳层直达叶子页面。历史上目录挂壳组件（`NestedRouterParent`）导致壳实例随缓存保留多份、同一页面被重复挂载、菜单切换时接口重复调用；`KeepAlive :max` 做 LRU 会顶掉仍开着的页签导致切回莫名重挂载。缓存集合只用 `include` / `exclude` 表达
- "重复弹窗 / 重复连接 / 重复请求"类问题排查顺序：先全仓 grep 提示文案定位唯一来源（弹 N 次 = N 实例或 N 次重入）→ 查 KeepAlive include/exclude 计算与退出→登录跳转链（登录守卫的 404 → replace 重定向叠了竞态窗口）→ 查 `backend/sql/sys_menu.json` 菜单配置（route_name 唯一、keep_alive）排除后端
- 路由视图缓存 key 是叶子路由 `path`（query 变化不重挂载；keying 逻辑见 `layouts/fa-page-content/index.vue` 的 `routeViewCacheKey`）

## 构建产物（dist）

**源码改对 ≠ 部署改对。** 仓库存在多份预构建 dist 副本直接随部署走；前端源码改完必须重建 + 同步 + 核对产物。三份产物表、rsync 命令（必须 `--delete`）与 grep 核对法见 [dist-sync](./references/dist-sync.md)（owner）。

## 引用

- [crud-suite.md](./references/crud-suite.md) — API 层模板 + CRUD 页面套件拆解（dict 样例）
- [dist-sync.md](./references/dist-sync.md) — 构建产物表、重建/同步、核对技巧、后端托管坑
