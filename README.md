# ResNexus

ResNexus提供资源管理业务的基础框架，包含统一认证、角色权限、组织管理、操作审计、系统监控和代码生成能力。具体资源模型与纳管流程可在现有模块体系中扩展。

## 技术栈

- 后端：FastAPI、SQLAlchemy、Redis、Alembic、uv。
- 管理端：Vue 3、TypeScript、Element Plus、Pinia、Vite。
- 移动端：UniApp；文档站：VitePress。

## 本地开发

1. 按 `backend/env/` 的环境配置准备数据库和 Redis。
2. 在 `backend` 目录运行 `uv sync`，然后运行 `uv run main.py run --env=dev`。
3. 在 `frontend/web` 目录运行 `pnpm install` 和 `pnpm dev`。
4. 部署配置见 `DEPLOYMENT.md` 与 `docker/README.md`。

## 已有环境升级

系统名称、Logo、页脚与链接由数据库系统参数提供。已有数据库不会因修改种子文件自动更新，可执行 `backend/sql/upgrade_resource_branding.sql`（仅替换上游默认值），重启后端刷新 Redis 缓存；也可在“系统管理 → 参数管理”中按 `backend/sql/sys_param.json` 更新相应参数，再退出登录并重新登录以刷新缓存。

生产环境请通过环境变量设置实际域名白名单、跨域来源和 OAuth 回调地址。数据库名、Redis 前缀、现有日志路径等兼容标识保留，避免影响已有数据和部署。

## 许可

本项目基于 MIT 许可的软件进行定制，原始版权和许可声明保留在根目录及各子项目的 `LICENSE` 文件中；第三方依赖遵循各自许可证。
