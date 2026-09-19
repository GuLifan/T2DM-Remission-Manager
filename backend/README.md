# backend — ETMMS 后端

> FastAPI + SQLAlchemy + SQLite（Alembic 迁移）。虚拟环境位于本目录 `.venv`（uv 管理，**不改动全局 Python 环境**）。

## 启动（开发态）

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8080
```

## 测试

```bash
uv run pytest
```

## 结构

```txt
app/
├─ main.py        应用装配与静态资源挂载
├─ config.py      配置（数据库路径、端口、会话时长）
├─ core/          时钟注入、结构化日志、异常体系
├─ api/           路由层（不含临床判断）
├─ services/      临床服务层（纯函数，最严格）
├─ domain/        状态机、分支优先级、输出模板、枚举（单一数据源）
├─ repository/    数据访问封装
├─ models/        ORM 模型与 Pydantic 模式
└─ evidence/      医学依据抽取与检索
```

分层与实现约定见 `_SPEC/07_技术架构与数据模型_v1.0.md`。
