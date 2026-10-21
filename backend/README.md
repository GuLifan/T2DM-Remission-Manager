# ETMMS backend / 后端 0.4.3

FastAPI + SQLAlchemy + SQLite, Python 3.13. Use uv and the project-local `.venv`, install from `uv.lock`, and run one Uvicorn worker. Configure `.env` before starting. Existing upgrades preserve data/key and do not run `init-admin` again.

使用 FastAPI、SQLAlchemy、SQLite 和 Python 3.13。通过 uv 与项目内 `.venv` 按 `uv.lock` 安装，运行单 Uvicorn worker。启动前配置 `.env`；已有环境升级保留数据和密钥，不重复执行 `init-admin`。

[Sealos setup / 安装](../docs/DEPLOY_SEALOS.md) · [Patch / 补丁](../docs/UPDATE_0.4.3.md) · [Specifications / 约束](../_SPEC/README.md) · [Evidence / 依据](../docs/EVIDENCE.md)
