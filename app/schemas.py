from datetime import date
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class _FromORM(BaseModel):
    # Lets Pydantic read values from SQLAlchemy objects, not just dicts.
    model_config = ConfigDict(from_attributes=True)


class GradeOut(_FromORM):
    code: str
    name: str


class ProductLineOut(_FromORM):
    name: str


class UniverseOut(_FromORM):
    name: str


class ManufacturerOut(_FromORM):
    name: str


class ReleaseOut(_FromORM):
    id: int
    region: str
    jan_code: Optional[str] = None
    price: Optional[int] = None
    currency: str
    release_date: Optional[date] = None
    date_precision: str
    exclusive_to: Optional[str] = None
    is_limited: bool
    status: str
    source_url: Optional[str] = None


class KitOut(_FromORM):
    id: int
    name: str
    name_jp: Optional[str] = None
    grade: GradeOut
    product_line: Optional[ProductLineOut] = None
    universe: Optional[UniverseOut] = None
    manufacturer: ManufacturerOut
    scale: Optional[str] = None
    parent_kit_id: Optional[int] = None
    variant_label: Optional[str] = None
    notes: Optional[str] = None
    tags: List[str] = Field(default_factory=list, validation_alias="tag_names")
    releases: List[ReleaseOut] = Field(default_factory=list)
