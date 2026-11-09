"""Insert a couple of kits by hand. Safe to re-run.

Run from the project root:  python -m app.seed
"""
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Kit

Base.metadata.create_all(bind=engine)

with SessionLocal() as db:
    if db.scalars(select(Kit)).first():
        print("Kits already present, nothing to do.")
    else:
        db.add_all([
            Kit(name="RX-78-2 Gundam", grade="RG", series="Mobile Suit Gundam",
                scale="1/144", release_year=2010),
            Kit(name="Zaku II", grade="HG", series="Mobile Suit Gundam",
                scale="1/144"),
        ])
        db.commit()
        print("Seeded 2 kits.")
