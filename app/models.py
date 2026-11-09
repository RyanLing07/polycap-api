from datetime import date, datetime
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    String,
    Table,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# --- Lookup tables -----------------------------------------------------------


class Universe(Base):
    """Which continuity a kit belongs to. The only lore we track."""

    __tablename__ = "universes"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)  # "Universal Century"


class MobileSuit(Base):
    """Just a name to group kits of the same machine. No lore, no pilots."""

    __tablename__ = "mobile_suits"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)  # "RX-78-2 Gundam"
    slug: Mapped[str] = mapped_column(String(200), unique=True)  # "rx-78-2-gundam"


class Grade(Base):
    __tablename__ = "grades"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True)  # "HG", "MG", ...
    name: Mapped[str] = mapped_column(String(100))  # "High Grade"
    typical_scale: Mapped[Optional[str]] = mapped_column(String(10), default=None)


class ProductLine(Base):
    __tablename__ = "product_lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)  # "HGUC"
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id"), index=True)

    grade: Mapped[Grade] = relationship(lazy="joined")


class Manufacturer(Base):
    __tablename__ = "manufacturers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    country: Mapped[Optional[str]] = mapped_column(String(50), default=None)


# --- Tags (many-to-many with kits) -------------------------------------------

kit_tags = Table(
    "kit_tags",
    Base.metadata,
    Column("kit_id", ForeignKey("kits.id"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id"), primary_key=True),
)


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(50), unique=True)


# --- Kits and releases -------------------------------------------------------


class Kit(Base):
    """A distinct design: one set of parts and colors.

    A plain re-release is another KitRelease on the same kit.
    A real variant (new colors or parts) is a new Kit pointing at the
    original through parent_kit_id.

    The slug is the permanent human-readable key (e.g. "rg-rx-78-2-gundam").
    It is what the CSV files use, so rebuilding or updating never depends on
    row order.
    """

    __tablename__ = "kits"

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    name_jp: Mapped[Optional[str]] = mapped_column(String(200), default=None)
    grade_id: Mapped[int] = mapped_column(ForeignKey("grades.id"), index=True)
    product_line_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("product_lines.id"), default=None, index=True
    )
    universe_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("universes.id"), default=None, index=True
    )
    mobile_suit_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("mobile_suits.id"), default=None, index=True
    )
    manufacturer_id: Mapped[int] = mapped_column(
        ForeignKey("manufacturers.id"), index=True
    )
    scale: Mapped[Optional[str]] = mapped_column(String(10), default=None)
    # Always points at the ORIGINAL kit, never at another variant.
    parent_kit_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("kits.id"), default=None, index=True
    )
    variant_label: Mapped[Optional[str]] = mapped_column(String(100), default=None)
    notes: Mapped[Optional[str]] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Bumped on any change to the kit OR its releases (the app syncs on this).
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), index=True
    )

    grade: Mapped[Grade] = relationship(lazy="joined")
    product_line: Mapped[Optional[ProductLine]] = relationship(lazy="joined")
    universe: Mapped[Optional[Universe]] = relationship(lazy="joined")
    mobile_suit: Mapped[Optional[MobileSuit]] = relationship(lazy="joined")
    manufacturer: Mapped[Manufacturer] = relationship(lazy="joined")
    releases: Mapped[List["KitRelease"]] = relationship(
        back_populates="kit", lazy="selectin", order_by="KitRelease.release_date"
    )
    tags: Mapped[List[Tag]] = relationship(secondary=kit_tags, lazy="selectin")

    @property
    def tag_names(self) -> List[str]:
        return sorted(tag.name for tag in self.tags)


class KitRelease(Base):
    """One time a kit went on sale: a box with its own barcode, price, date."""

    __tablename__ = "kit_releases"

    id: Mapped[int] = mapped_column(primary_key=True)
    kit_id: Mapped[int] = mapped_column(ForeignKey("kits.id"), index=True)
    region: Mapped[str] = mapped_column(String(10), default="JP")
    # Text, not integer: JAN codes can have leading zeros. Unique when present.
    jan_code: Mapped[Optional[str]] = mapped_column(
        String(13), unique=True, default=None
    )
    price: Mapped[Optional[int]] = mapped_column(default=None)  # whole currency units
    currency: Mapped[str] = mapped_column(String(3), default="JPY")
    release_date: Mapped[Optional[date]] = mapped_column(Date, default=None, index=True)
    # "day", "month" or "year": announced kits often only have a month.
    date_precision: Mapped[str] = mapped_column(String(5), default="day")
    # None, "premium_bandai", "gundam_base", "event" or "retailer"
    exclusive_to: Mapped[Optional[str]] = mapped_column(String(30), default=None)
    is_limited: Mapped[bool] = mapped_column(Boolean, default=False)
    # "announced", "released" or "cancelled": rows are never deleted.
    status: Mapped[str] = mapped_column(String(10), default="released")
    source_url: Mapped[Optional[str]] = mapped_column(String(500), default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    kit: Mapped[Kit] = relationship(back_populates="releases", lazy="joined")
