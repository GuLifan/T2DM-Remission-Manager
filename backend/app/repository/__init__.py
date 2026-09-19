"""
包名称：repository
所属层级：数据访问层
功能说明：封装数据库连接、事务边界与查询。上层（services/api）不直接使用 ORM 会话，
          一律通过本层访问数据，便于统一处理事务与审计。

模块划分：
    - database：引擎、会话工厂、FastAPI 依赖。
    - migrations：启动时执行 Alembic 迁移。
    - users：账号与登录防护。
    - patients：患者档案。
    - events：临床事件流水（只增不改）。
    - audit：系统审计日志。
"""
