# ETMMS 0.4.3 backend / 后端

FastAPI, SQLAlchemy, Alembic and SQLite on Python3.13 with uv and project-local backend/.venv. Application source, migrations and isolated regression tests are included. Current clinical contractv0.3, inputv0.4 and database headd04data001 remain unchanged.

使用Python3.13、FastAPI、SQLAlchemy、Alembic和SQLite，uv管理项目内backend/.venv。包含应用源码、迁移及隔离回归；临床v0.3、输入v0.4和数据库d04data001保持。

Run `uv sync --frozen` and `uv run --no-sync pytest` here. Existing cloud replacement retains its own configuration/environment/data and never initializes the administrator again. See [fresh install](../docs/FRESH_INSTALL.md), [complete replacement](../docs/DEPLOY_SEALOS.md) and [current constraints](../_SPEC/CURRENT_SPEC.md).

在此运行上述命令准备开发环境和回归。既有云端完整替换保留配置/环境/数据，不重新初始化管理员。详见[全新安装](../docs/FRESH_INSTALL.md)、[完整替换](../docs/DEPLOY_SEALOS.md)及[约束](../_SPEC/CURRENT_SPEC.md)。
