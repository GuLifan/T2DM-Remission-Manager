"""profile import and reference data

迁移编号：4f8e1c2d9a70
修订内容：增加开放注册科室、患者档案扩展、资料完善门禁与科室字典
生成时间：2026-09-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4f8e1c2d9a70"
down_revision: str | None = "9c4a2f1b7e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


DEPARTMENTS: tuple[str, ...] = (
    "创伤骨科",
    "胆道外科",
    "胆胰内镜外科",
    "耳鼻咽喉-头颈外科",
    "儿科",
    "儿童保健科",
    "儿童重症医学科",
    "风湿免疫科",
    "腹部外科",
    "妇产科",
    "肝胆外科",
    "感染性疾病科",
    "肝移植外科",
    "肝脏外科",
    "骨科",
    "骨肿瘤科",
    "呼吸与危重症医学科",
    "健康医学科",
    "健苑五病区.涉外病房",
    "减重与代谢外科",
    "结构性心脏病科",
    "结直肠外科",
    "精神心理卫生科",
    "急诊科",
    "急诊内科",
    "急诊外科",
    "急诊重症医学科（EICU）",
    "脊柱外科",
    "康复医学科",
    "口腔科",
    "老年内二科",
    "老年内一科",
    "麻醉科",
    "泌尿外科",
    "内分泌科",
    "皮肤科",
    "普通外科",
    "全科医学科",
    "乳腺外科",
    "疝和腹膜后肿瘤外科",
    "生殖医学科",
    "神经内科",
    "神经外科",
    "肾移植科",
    "肾脏内科",
    "疼痛科",
    "外科重症医学科",
    "胃外科",
    "腺体和综合外科",
    "小儿外科",
    "消化内镜微创治疗亚专科",
    "消化内科",
    "新生儿科",
    "心血管内科",
    "心血管外科",
    "胸外科",
    "血管外科",
    "血液净化科",
    "血液内科",
    "眼科",
    "胰腺外科",
    "运动医学与关节外科",
    "整形美容•颌面外科",
    "肿瘤放疗科",
    "肿瘤内科",
    "肿瘤外科",
    "中医科",
    "重症医学科",
    "周围血管科",
)


def upgrade() -> None:
    """增加第二批数据结构并安全回填现有开发数据。"""
    op.add_column("users", sa.Column("department", sa.String(length=128), nullable=True))

    # SQLite 不能原地添加外键约束，统一用 batch 重建患者表
    with op.batch_alter_table("patients") as batch_op:
        batch_op.add_column(
            sa.Column("department", sa.String(length=128), nullable=False, server_default="内分泌科")
        )
        batch_op.add_column(sa.Column("contact_phone", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("created_by", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_patients_created_by_users", "users", ["created_by"], ["id"])
        batch_op.create_index("ix_patients_created_by", ["created_by"], unique=False)
        batch_op.add_column(sa.Column("profile_complete", sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column("height_cm", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("weight_kg", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("bmi", sa.Float(), nullable=True))

    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
        sa.UniqueConstraint("sort_order"),
    )
    department_table = sa.table(
        "departments",
        sa.column("name", sa.String),
        sa.column("sort_order", sa.Integer),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        department_table,
        [
            {"name": name, "sort_order": index, "is_active": True}
            for index, name in enumerate(DEPARTMENTS, start=1)
        ],
    )

    # 既有患者均已人工建档，因此资料视为已完善；创建者精确回填为 admin（存在时）
    op.execute(sa.text("UPDATE patients SET profile_complete = 1, department = '内分泌科'"))
    op.execute(
        sa.text(
            "UPDATE patients SET created_by = (SELECT id FROM users WHERE username = 'admin' LIMIT 1) "
            "WHERE EXISTS (SELECT 1 FROM users WHERE username = 'admin')"
        )
    )


def downgrade() -> None:
    """移除第二批档案与参考字典结构。"""
    op.drop_table("departments")
    with op.batch_alter_table("patients") as batch_op:
        batch_op.drop_column("bmi")
        batch_op.drop_column("weight_kg")
        batch_op.drop_column("height_cm")
        batch_op.drop_column("profile_complete")
        batch_op.drop_index("ix_patients_created_by")
        batch_op.drop_constraint("fk_patients_created_by_users", type_="foreignkey")
        batch_op.drop_column("created_by")
        batch_op.drop_column("contact_phone")
        batch_op.drop_column("department")
    op.drop_column("users", "department")
