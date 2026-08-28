from __future__ import annotations

from datetime import time

from sqlalchemy import Boolean, ForeignKey, Integer, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


class WorkingSchedule(Base):
    __tablename__ = "working_schedules"
    __table_args__ = (
        UniqueConstraint("master_id", "weekday", name="uq_schedule_master_weekday"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    master_id: Mapped[int] = mapped_column(ForeignKey("masters.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    is_working: Mapped[bool] = mapped_column(Boolean, default=True)

    master: Mapped[Master] = relationship(back_populates="schedules")
