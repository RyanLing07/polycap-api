"""Fill the database with lookup data and a few SAMPLE kits. Safe to re-run.

Run from the project root:  python -m app.seed

The lookup data (grades, universes, ...) is real. The sample kits exist to show
the structure (a re-release and a variant). Check names, dates and flags against
a real source before treating them as facts. The 0000000000000 barcode is a
placeholder for testing, not a real JAN code.
"""
from datetime import date

from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Grade, Kit, KitRelease, Manufacturer, ProductLine, Tag, Universe

Base.metadata.create_all(bind=engine)

UNIVERSES = [
    "Universal Century", "Future Century", "After Colony", "After War",
    "Cosmic Era", "Anno Domini", "Advanced Generation", "Post Disaster",
    "Regild Century", "Build Series",
]

GRADES = [  # code, name, typical scale
    ("SD", "Super Deformed", None),
    ("EG", "Entry Grade", "1/144"),
    ("HG", "High Grade", "1/144"),
    ("RG", "Real Grade", "1/144"),
    ("MG", "Master Grade", "1/100"),
    ("PG", "Perfect Grade", "1/60"),
]

PRODUCT_LINES = [  # name, grade code
    ("HGUC", "HG"),
    ("RG", "RG"),
    ("MG", "MG"),
]

TAGS = ["transformation", "clear parts", "metallic finish"]


def get_or_create(db, model, lookup, **extra):
    obj = db.scalars(select(model).filter_by(**lookup)).first()
    if obj is None:
        obj = model(**lookup, **extra)
        db.add(obj)
        db.flush()
    return obj


with SessionLocal() as db:
    universes = {n: get_or_create(db, Universe, {"name": n}) for n in UNIVERSES}
    grades = {
        code: get_or_create(db, Grade, {"code": code}, name=name, typical_scale=scale)
        for code, name, scale in GRADES
    }
    lines = {
        name: get_or_create(db, ProductLine, {"name": name}, grade_id=grades[g].id)
        for name, g in PRODUCT_LINES
    }
    bandai = get_or_create(db, Manufacturer, {"name": "Bandai Spirits"}, country="Japan")
    tags = {n: get_or_create(db, Tag, {"name": n}) for n in TAGS}

    if db.scalars(select(Kit)).first():
        print("Lookup data ensured. Kits already present, nothing else to do.")
    else:
        # An original kit with one release.
        rg_gundam = Kit(
            name="RX-78-2 Gundam", grade_id=grades["RG"].id,
            product_line_id=lines["RG"].id,
            universe_id=universes["Universal Century"].id,
            manufacturer_id=bandai.id, scale="1/144",
        )
        rg_gundam.releases.append(KitRelease(
            region="JP", release_date=date(2010, 1, 1), date_precision="year",
            jan_code="0000000000000",  # placeholder, not a real barcode
        ))

        # An original kit with TWO releases (a re-release is a new release row).
        hg_zaku = Kit(
            name="Zaku II", grade_id=grades["HG"].id,
            product_line_id=lines["HGUC"].id,
            universe_id=universes["Universal Century"].id,
            manufacturer_id=bandai.id, scale="1/144",
        )
        hg_zaku.releases.extend([
            KitRelease(region="JP", status="released"),
            KitRelease(region="JP", status="released"),  # the re-release
        ])
        db.add_all([rg_gundam, hg_zaku])
        db.flush()

        # A variant (new colors): its own kit, pointing at the original.
        clear = Kit(
            name="RX-78-2 Gundam [Clear Color]", grade_id=grades["RG"].id,
            product_line_id=lines["RG"].id,
            universe_id=universes["Universal Century"].id,
            manufacturer_id=bandai.id, scale="1/144",
            parent_kit_id=rg_gundam.id, variant_label="Clear Color",
        )
        clear.tags.append(tags["clear parts"])
        clear.releases.append(KitRelease(
            region="JP", exclusive_to="event", is_limited=True,
        ))
        db.add(clear)
        db.commit()
        print("Seeded lookup data and 3 sample kits.")
