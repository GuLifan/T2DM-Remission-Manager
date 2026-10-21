# ETMMS backend 0.4.2

FastAPI + SQLAlchemy + SQLite. Use Python 3.13 with uv and this directory's `.venv`; install from `uv.lock`. Runtime deployment uses one Uvicorn worker.

See [Sealos setup](../docs/DEPLOY_SEALOS.md), [specifications](../_SPEC/README.md), [private evidence](../docs/EVIDENCE.md), and [verification](../docs/VALIDATION.md). Configure `.env` before starting; existing installations must preserve their data and signing key and must not reinitialize the administrator.
