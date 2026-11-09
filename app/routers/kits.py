import base64
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Grade, Kit, KitRelease, MobileSuit, Universe
from app.schemas import KitOut, KitPage
from app.slugs import slugify

router = APIRouter(prefix="/v1/kits", tags=["kits"])


def encode_cursor(kit_id: int) -> str:
    return base64.urlsafe_b64encode(str(kit_id).encode()).decode()


def decode_cursor(cursor: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid cursor")


@router.get("", response_model=KitPage)
def list_kits(
    grade: Optional[str] = Query(None, description="Grade code, e.g. HG, MG, RG"),
    universe: Optional[str] = Query(None, description="Universe name, e.g. Cosmic Era"),
    mobile_suit: Optional[str] = Query(None, description="Mobile suit name or slug"),
    q: Optional[str] = Query(None, description="Search kit names (English or Japanese)"),
    release_after: Optional[date] = Query(
        None, description="Kits with a release on or after this date (YYYY-MM-DD)"
    ),
    updated_since: Optional[datetime] = Query(
        None, description="Kits changed since this time (for app sync), e.g. 2026-11-01T00:00:00"
    ),
    limit: int = Query(50, ge=1, le=100),
    cursor: Optional[str] = Query(None, description="next_cursor from the previous page"),
    db: Session = Depends(get_db),
):
    query = select(Kit).order_by(Kit.id)
    if cursor:
        query = query.where(Kit.id > decode_cursor(cursor))
    if grade:
        query = query.where(Kit.grade.has(Grade.code == grade.upper()))
    if universe:
        query = query.where(Kit.universe.has(Universe.name.ilike(universe)))
    if mobile_suit:
        query = query.where(Kit.mobile_suit.has(MobileSuit.slug == slugify(mobile_suit)))
    if q:
        like = f"%{q}%"
        query = query.where(Kit.name.ilike(like) | Kit.name_jp.ilike(like))
    if release_after:
        query = query.where(Kit.releases.any(KitRelease.release_date >= release_after))
    if updated_since:
        query = query.where(Kit.updated_at >= updated_since)

    # Ask for one extra row: if it exists, there is a next page.
    rows = db.scalars(query.limit(limit + 1)).unique().all()
    items = rows[:limit]
    next_cursor = encode_cursor(items[-1].id) if len(rows) > limit else None
    return KitPage(items=items, next_cursor=next_cursor)


# The fixed paths below are defined before "/{kit_id}" so they are never read as an id.
@router.get("/barcode/{jan}", response_model=KitOut)
def get_kit_by_barcode(jan: str, db: Session = Depends(get_db)):
    release = db.scalars(select(KitRelease).where(KitRelease.jan_code == jan)).first()
    if release is None:
        raise HTTPException(status_code=404, detail="No kit with that barcode")
    return release.kit


@router.get("/slug/{slug}", response_model=KitOut)
def get_kit_by_slug(slug: str, db: Session = Depends(get_db)):
    kit = db.scalars(select(Kit).where(Kit.slug == slug)).first()
    if kit is None:
        raise HTTPException(status_code=404, detail="Kit not found")
    return kit


@router.get("/{kit_id}", response_model=KitOut)
def get_kit(kit_id: int, db: Session = Depends(get_db)):
    kit = db.get(Kit, kit_id)
    if kit is None:
        raise HTTPException(status_code=404, detail="Kit not found")
    return kit
