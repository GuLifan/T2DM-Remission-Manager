"""v0.4可追溯资料：记录只追加；临床事件保存引用与当时快照。"""
from datetime import date, datetime

from sqlalchemy import JSON, Date, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ClinicalRecord(Base):
    __tablename__ = "clinical_records"
    __table_args__ = (UniqueConstraint("source_event_id", "kind", "source_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    operator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    source_event_id: Mapped[int | None] = mapped_column(ForeignKey("events.id"), nullable=True)
    source_index: Mapped[int] = mapped_column(default=0)
    kind: Mapped[str] = mapped_column(String(32))
    clinical_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    data: Mapped[dict] = mapped_column(JSON)
    supersedes_id: Mapped[int | None] = mapped_column(ForeignKey("clinical_records.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
