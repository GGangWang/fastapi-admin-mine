import os
from typing import Annotated

import typer
import uvicorn
from alembic import command
from alembic.config import Config
from typer.main import Typer

from app.common.enums import EnvironmentEnum

resnexus_cli: Typer = typer.Typer()
alembic_cfg: Config = Config(file_="alembic.ini")


@resnexus_cli.command(
    name="run",
    help="启动 ResNexus 服务, 运行 python(或uv run) main.py run --env=dev 不加参数默认 dev 环境",
)
def run(
    env: Annotated[EnvironmentEnum, typer.Option("--env", help="运行环境 (dev, prod)")] = EnvironmentEnum.DEV,
) -> None:
    """按指定环境加载配置并启动 Uvicorn（dev 环境 DEBUG=True 自动开启 reload）。

    参数:
    - env (EnvironmentEnum): 运行环境，对应 `--env`。

    返回:
    - None
    """
    os.environ["ENVIRONMENT"] = env.value

    from app.utils.banner import worship
    typer.secho(message=f"{worship()}", fg=typer.colors.GREEN)
    from app.config.setting import settings
    from app.core.event_loop import requires_selector_loop

    uvicorn.run(
        app="app:create_app",
        factory=True,
        loop="app.core.event_loop:database_event_loop" if requires_selector_loop() else "auto",
        host=settings.SERVER_HOST,
        port=settings.SERVER_PORT,
        reload=settings.DEBUG,
        workers=settings.WORKERS,
        log_config=None,
        timeout_graceful_shutdown=5,
    )


@resnexus_cli.command(
    name="revision",
    help="生成新的 Alembic 迁移脚本, 运行 python(或uv run) main.py revision --env=dev",
)
def revision(
    env: Annotated[EnvironmentEnum, typer.Option("--env", help="运行环境 (dev, prod)")] = EnvironmentEnum.DEV,
    message: Annotated[str, typer.Option("--message", "-m", help="迁移说明（进入迁移文件名 slug）")] = "迁移脚本",
) -> None:
    """使用 Alembic 自动生成迁移脚本（autogenerate）。

    参数:
    - env (EnvironmentEnum): 运行环境，用于加载对应数据库模型元数据。
    - message (str): 迁移说明，写入迁移文件 message 与文件名 slug。

    返回:
    - None
    """
    os.environ["ENVIRONMENT"] = env.value
    command.revision(config=alembic_cfg, autogenerate=True, message=message)
    typer.echo(message="迁移脚本已生成")


@resnexus_cli.command(
    name="upgrade",
    help="应用最新的 Alembic 迁移, 运行 python(或uv run) main.py upgrade --env=dev",
)
def upgrade(
    env: Annotated[EnvironmentEnum, typer.Option("--env", help="运行环境 (dev, prod)")] = EnvironmentEnum.DEV,
) -> None:
    """将数据库升级到 Alembic 最新版本（head）。

    参数:
    - env (EnvironmentEnum): 运行环境。

    返回:
    - None
    """
    os.environ["ENVIRONMENT"] = env.value
    command.upgrade(config=alembic_cfg, revision="head")
    typer.echo(message="所有迁移已应用。")


@resnexus_cli.command(name="migrate-audit-logs", help="停服后按月迁移历史登录/操作日志，保留原表；可重复执行")
def migrate_audit_logs(
    env: Annotated[EnvironmentEnum, typer.Option("--env")] = EnvironmentEnum.DEV,
    batch_size: Annotated[int, typer.Option("--batch-size", min=1)] = 1000,
) -> None:
    import asyncio
    import json
    os.environ["ENVIRONMENT"] = env.value
    from app.core.database import databases
    from app.scripts.migrate_audit_logs import migrate

    async def execute():
        try:
            return await migrate(databases.engine("logs"), batch_size)
        finally:
            await databases.dispose()

    from app.core.event_loop import database_event_loop

    with asyncio.Runner(loop_factory=database_event_loop) as runner:
        typer.echo(json.dumps(runner.run(execute()), ensure_ascii=False))


@resnexus_cli.command(name="upgrade-log-ids", help="停服后将日志库现有登录/操作日志主键升级为 VARCHAR(32)")
def upgrade_log_ids(env: Annotated[EnvironmentEnum, typer.Option("--env")] = EnvironmentEnum.DEV):
    import asyncio
    import json
    os.environ["ENVIRONMENT"] = env.value
    from app.core.database import databases
    from app.modules.system.log.upgrade import upgrade_ids
    async def execute():
        try:
            return await upgrade_ids(databases.engine("logs"))
        finally:
            await databases.dispose()
    typer.echo(json.dumps(asyncio.run(execute()), ensure_ascii=False))


if __name__ == "__main__":
    resnexus_cli()
