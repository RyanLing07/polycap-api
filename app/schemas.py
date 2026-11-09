from typing import Optional

from pydantic import BaseModel, ConfigDict


class KitOut(BaseModel):
    # Lets Pydantic read values from SQLAlchemy objects, not just dicts.
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    grade: str
    series: str
    scale: str
    release_year: Optional[int] = None
