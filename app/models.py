from typing import Optional
from pydantic import BaseModel

class Kit(BaseModel):
    id: int
    name: str
    grade: str
    series: str
    scale: str
    release_year: Optional[int] = None