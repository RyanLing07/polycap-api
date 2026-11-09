from typing import Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Kit(Base):
    __tablename__ = "kits"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    grade: Mapped[str] = mapped_column(String(10))
    series: Mapped[str] = mapped_column(String(200))
    scale: Mapped[str] = mapped_column(String(10))
    release_year: Mapped[Optional[int]] = mapped_column(default=None)
