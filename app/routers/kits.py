from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Kit
from app.schemas import KitOut

router = APIRouter(prefix="/v1/kits", tags=["kits"])


@router.get("", response_model=list[KitOut])
def list_kits(grade: Optional[str] = None, db: Session = Depends(get_db)):
    query = select(Kit).order_by(Kit.id)
    if grade:
        query = query.where(Kit.grade == grade.upper())
    return db.scalars(query).all()


@router.get("/{kit_id}", response_model=KitOut)
def get_kit(kit_id: int, db: Session = Depends(get_db)):
    kit = db.get(Kit, kit_id)
    if kit is None:
        raise HTTPException(status_code=404, detail="Kit not found")
    return kit
