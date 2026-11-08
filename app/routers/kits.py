from fastapi import APIRouter, HTTPException
from app.models import Kit
from typing import Optional

router = APIRouter(prefix="/kits", tags=["kits"])

KITS = [
    Kit(id=1, name="RX-78-2 Gundam", grade="RG", series="Mobile Suit Gundam", scale="1/144", release_year=2010),
    Kit(id=2, name="Zaku II", grade="HG", series="Mobile Suit Gundam", scale="1/144"),
]

@router.get("/", response_model=list[Kit])
def list_kits(grade: Optional[str] = None):
    if grade:
        return [k for k in KITS if k.grade.upper() == grade.upper()]
    return KITS

@router.get("/{kit_id}", response_model=Kit)
def get_kit(kit_id: int):
    for kit in KITS:
        if kit.id == kit_id:
            return kit
    raise HTTPException(status_code=404, detail="Kit not found")