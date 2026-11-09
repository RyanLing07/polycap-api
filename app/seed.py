"""Fill the database with lookup data (grades, universes, ...). Safe to re-run.

Run from the project root:  python -m app.seed

Kits themselves come from data/kits.csv:  python -m app.load_csv data/kits.csv
"""
from sqlalchemy import select

from app.database import Base, SessionLocal, engine
from app.models import Grade, Manufacturer, ProductLine, Tag, Universe

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
    for name in UNIVERSES:
        get_or_create(db, Universe, {"name": name})
    grades = {
        code: get_or_create(db, Grade, {"code": code}, name=name, typical_scale=scale)
        for code, name, scale in GRADES
    }
    for name, grade_code in PRODUCT_LINES:
        get_or_create(db, ProductLine, {"name": name}, grade_id=grades[grade_code].id)
    get_or_create(db, Manufacturer, {"name": "Bandai Spirits"}, country="Japan")
    for name in TAGS:
        get_or_create(db, Tag, {"name": name})
    db.commit()
    print("Lookup data ready.")
