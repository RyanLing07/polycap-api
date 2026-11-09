from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Grade, Kit, KitRelease, Universe
from app.schemas import KitOut

router = APIRouter(prefix="/v1/kits", tags=["kits"])


@router.get("", response_model=List[KitOut])
def list_kits(
    grade: Optional[str] = Query(None, description="Grade code, e.g. HG, MG, RG"),
    universe: Optional[str] = Query(None, description="Universe name, e.g. Cosmic Era"),
    q: Optional[str] = Query(None, description="Search kit names (English or Japanese)"),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(Kit).order_by(Kit.id).limit(limit)
    if grade:
        query = query.join(Grade, Kit.grade_id == Grade.id).where(
            Grade.code == grade.upper()
        )
    if universe:
        query = query.join(Universe, Kit.universe_id == Universe.id).where(
            Universe.name.ilike(universe)
        )
    if q:
        like = f"%{q}%"
        query = query.where(Kit.name.ilike(like) | Kit.name_jp.ilike(like))
    return db.scalars(query).unique().all()


# Defined before "/{kit_id}" so "barcode" is never read as an id.
@router.get("/barcode/{jan}", response_model=KitOut)
def get_kit_by_barcode(jan: str, db: Session = Depends(get_db)):
    release = db.scalars(select(KitRelease).where(KitRelease.jan_code == jan)).first()
    if release is None:
        raise HTTPException(status_code=404, detail="No kit with that barcode")
    return release.kit


@router.get("/{kit_id}", response_model=KitOut)
def get_kit(kit_id: int, db: Session = Depends(get_db)):
    kit = db.get(Kit, kit_id)
    if kit is None:
        raise HTTPException(status_code=404, detail="Kit not found")
    return kit
