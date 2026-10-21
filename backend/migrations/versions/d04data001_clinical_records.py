"""v0.4资料记录与旧快照可追踪投影，保留所有原事件。"""
import json
from datetime import date

import sqlalchemy as sa
from alembic import op

revision = "d04data001"
down_revision = "d03demo001"
branch_labels = None
depends_on = None


def upgrade():
    table = op.create_table(
        "clinical_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("patient_id", sa.Integer(), sa.ForeignKey("patients.id"), nullable=False),
        sa.Column("operator_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_event_id", sa.Integer(), sa.ForeignKey("events.id")),
        sa.Column("source_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("clinical_date", sa.Date()),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("supersedes_id", sa.Integer(), sa.ForeignKey("clinical_records.id")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("source_event_id", "kind", "source_index"),
    )
    op.create_index("ix_clinical_records_patient_id", "clinical_records", ["patient_id"])
    conn = op.get_bind()
    # 只读原JSON，能确定的资料按事件来源投影；未知测量日绝不改成评估日。
    events = sa.table("events", sa.column("id"), sa.column("patient_id"), sa.column("operator_id"),
                      sa.column("payload"), sa.column("created_at", sa.DateTime()))
    for e in conn.execute(sa.select(events).order_by(events.c.id)).mappings():
        try:
            p = json.loads(e["payload"] or "{}")
        except (ValueError, TypeError):
            continue
        if not isinstance(p, dict):
            continue
        records = []
        m = p.get("measurement_snapshot")
        if isinstance(m, dict) and m.get("weight_kg") is not None:
            records.append(("measurement", {**m, "measured_on": None, "date_basis": "旧记录未单独记录测量日"}))
        if "f016_medications" in p:
            meds = p.get("f016_medications") or []
            records.append(("medication_regimen", {"medications": meds, "complete": bool(p.get("f016_no_medication_confirmed") or meds), "legacy": True}))
        for key in ("recent_examination", "f058_examination"):
            if isinstance(p.get(key), dict):
                records.append(("examination", p[key]))
        for index, (kind, data) in enumerate(records):
            raw = data.get("test_date") or data.get("report_end_date") if kind == "examination" else p.get("clinical_date")
            try:
                clinical_date = date.fromisoformat(raw) if raw else None
            except ValueError:
                clinical_date = None
            conn.execute(table.insert().values(patient_id=e["patient_id"], operator_id=e["operator_id"],
                         source_event_id=e["id"], source_index=index, kind=kind, data=data,
                         clinical_date=clinical_date, created_at=e["created_at"]))


def downgrade():
    # 回退先用维护说明恢复一致性备份，禁止迁移命令直接销毁临床新增记录。
    raise RuntimeError("请按v0.4回退说明恢复匹配的数据库备份，不能直接删除资料记录")
