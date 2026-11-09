"""Load or update kits and releases from a CSV file. One row per release.

Run from the project root:

    python -m app.load_csv data/kits.csv
    python -m app.load_csv data/kits.csv --dry-run     # check without saving

Rules:
- Every kit has a unique `slug` (like rg-rx-78-2-gundam). Rows that share a slug
  are releases of the SAME kit; the kit columns are read from its first row.
- A variant row sets `variant_of` to the ORIGINAL kit's slug.
- Re-running UPDATES what changed and prints every change. A blank cell never
  erases existing data, so you only need to fill the cells you want to set.
- All-or-nothing: if any row has a problem, nothing is saved and every problem
  is printed with its CSV line number.
- Grades and universes must already exist (python -m app.seed adds them).
  Product lines, manufacturers, mobile suits and tags are created on the fly.
"""
import argparse
import csv
import sys
from datetime import date, datetime
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import Base, SessionLocal, engine
from app.models import (
    Grade,
    Kit,
    KitRelease,
    Manufacturer,
    MobileSuit,
    ProductLine,
    Tag,
    Universe,
)
from app.slugs import is_valid_slug, slugify

COLUMNS = [
    "slug", "name", "name_jp", "grade", "product_line", "universe", "mobile_suit",
    "manufacturer", "scale", "variant_of", "variant_label", "tags", "notes",
    "region", "jan_code", "price", "currency", "release_date", "exclusive_to",
    "is_limited", "status", "source_url",
]
REQUIRED = ["slug", "name", "grade"]
EXCLUSIVE_TO = {"premium_bandai", "gundam_base", "event", "retailer"}
STATUSES = {"announced", "released", "cancelled"}
DEFAULT_MANUFACTURER = "Bandai Spirits"
MAX_CHANGES_SHOWN = 60


# --- Parsing helpers (no database needed) ------------------------------------


def parse_bool(text: str) -> bool:
    value = text.strip().lower()
    if value in ("1", "true", "yes", "y"):
        return True
    if value in ("0", "false", "no", "n"):
        return False
    raise ValueError("use yes or no")


def parse_release_date(text: str) -> Tuple[date, str]:
    """Accepts YYYY-MM-DD, YYYY-MM or YYYY. Returns (date, precision)."""
    parts = text.strip().split("-")
    try:
        numbers = [int(p) for p in parts]
        if len(numbers) == 3:
            return date(numbers[0], numbers[1], numbers[2]), "day"
        if len(numbers) == 2:
            return date(numbers[0], numbers[1], 1), "month"
        if len(numbers) == 1:
            return date(numbers[0], 1, 1), "year"
    except ValueError:
        pass
    raise ValueError("use YYYY-MM-DD, YYYY-MM or YYYY")


def valid_jan(code: str) -> bool:
    """13 digits with a correct check digit (catches most typos)."""
    if len(code) != 13 or not code.isdigit():
        return False
    digits = [int(c) for c in code]
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:12]))
    return (10 - total % 10) % 10 == digits[12]


def clean_row(raw: Dict[str, Optional[str]]) -> Dict[str, Optional[str]]:
    """Trim whitespace; turn empty cells into None."""
    out = {}
    for key, value in raw.items():
        value = (value or "").strip()
        out[key] = value or None
    return out


def parse_release(row: Dict[str, Optional[str]]) -> Tuple[dict, List[str]]:
    """Read the release columns. Returns ONLY the cells that were filled in."""
    problems: List[str] = []
    provided: dict = {}

    if row.get("region"):
        region = row["region"].upper()
        if not (2 <= len(region) <= 3 and region.isalpha()):
            problems.append("region should be a short code like JP or US")
        provided["region"] = region

    if row.get("jan_code"):
        if not valid_jan(row["jan_code"]):
            problems.append(f"jan_code {row['jan_code']!r} is not a valid 13-digit barcode")
        provided["jan_code"] = row["jan_code"]

    if row.get("price"):
        try:
            price = int(row["price"].replace(",", ""))
            if price < 0:
                raise ValueError
            provided["price"] = price
        except ValueError:
            problems.append("price must be a whole number like 1500")

    if row.get("currency"):
        currency = row["currency"].upper()
        if len(currency) != 3 or not currency.isalpha():
            problems.append("currency should be a 3-letter code like JPY")
        provided["currency"] = currency

    if row.get("release_date"):
        try:
            provided["release_date"], provided["date_precision"] = parse_release_date(
                row["release_date"]
            )
        except ValueError as exc:
            problems.append(f"release_date: {exc}")

    if row.get("exclusive_to"):
        exclusive = row["exclusive_to"].lower()
        if exclusive not in EXCLUSIVE_TO:
            problems.append(
                f"exclusive_to must be one of: {', '.join(sorted(EXCLUSIVE_TO))}"
            )
        provided["exclusive_to"] = exclusive

    if row.get("is_limited"):
        try:
            provided["is_limited"] = parse_bool(row["is_limited"])
        except ValueError as exc:
            problems.append(f"is_limited: {exc}")

    if row.get("status"):
        status = row["status"].lower()
        if status not in STATUSES:
            problems.append(f"status must be one of: {', '.join(sorted(STATUSES))}")
        provided["status"] = status

    if row.get("source_url"):
        provided["source_url"] = row["source_url"]
    return provided, problems


# --- Database helpers ---------------------------------------------------------


def get_or_create(db: Session, model, lookup: dict, **extra):
    obj = db.scalars(select(model).filter_by(**lookup)).first()
    if obj is None:
        obj = model(**lookup, **extra)
        db.add(obj)
        db.flush()
    return obj


def set_field(obj, attr: str, value, ident: str, changes: List[str]) -> bool:
    """Set obj.attr if it differs, and record the change. Returns True if changed."""
    old = getattr(obj, attr)
    if old == value:
        return False
    setattr(obj, attr, value)
    changes.append(f"{ident}: {attr} {old!r} -> {value!r}")
    return True


def load(db: Session, rows: List[Dict[str, Optional[str]]]) -> Tuple[dict, List[str], List[str]]:
    """Insert or update the rows. Returns (counts, problems, changes).

    The caller commits or rolls back.
    """
    problems: List[str] = []
    changes: List[str] = []
    counts = {
        "kits_new": 0, "kits_updated": 0, "kits_unchanged": 0,
        "releases_new": 0, "releases_updated": 0, "releases_unchanged": 0,
    }

    grades = {g.code: g for g in db.scalars(select(Grade))}
    universes = {u.name.lower(): u for u in db.scalars(select(Universe))}
    kits_seen: Dict[str, Kit] = {}
    kit_state: Dict[str, str] = {}  # slug -> "new" | "changed" | "same"
    variant_requests: List[Tuple[int, Kit, str]] = []
    release_rows: List[Tuple[int, Kit, dict]] = []
    touched: Set[Kit] = set()

    # Pass 1: kits.
    for index, row in enumerate(rows):
        line = index + 2  # line 1 is the header
        row_problems: List[str] = []

        slug = row["slug"]
        if not is_valid_slug(slug):
            row_problems.append(
                f"slug {slug!r} should be lowercase letters, digits and hyphens "
                "(like rg-rx-78-2-gundam)"
            )
        grade = grades.get(row["grade"].upper())
        if grade is None:
            row_problems.append(
                f"unknown grade {row['grade']!r} (known: {', '.join(sorted(grades))})"
            )
        universe = None
        if row.get("universe"):
            universe = universes.get(row["universe"].lower())
            if universe is None:
                row_problems.append(f"unknown universe {row['universe']!r}")
        provided, release_problems = parse_release(row)
        row_problems += release_problems
        if row_problems:
            problems += [f"line {line}: {p}" for p in row_problems]
            continue

        kit = kits_seen.get(slug)
        if kit is None:
            values: dict = {"name": row["name"], "grade_id": grade.id}
            for column in ("name_jp", "scale", "variant_label", "notes"):
                if row.get(column):
                    values[column] = row[column]
            if universe:
                values["universe_id"] = universe.id
            if row.get("manufacturer"):
                values["manufacturer_id"] = get_or_create(
                    db, Manufacturer, {"name": row["manufacturer"]}
                ).id
            if row.get("product_line"):
                product_line = get_or_create(
                    db, ProductLine, {"name": row["product_line"]}, grade_id=grade.id
                )
                if product_line.grade_id != grade.id:
                    problems.append(
                        f"line {line}: product line {row['product_line']!r} "
                        "already belongs to a different grade"
                    )
                    continue
                values["product_line_id"] = product_line.id
            if row.get("mobile_suit"):
                suit_slug = slugify(row["mobile_suit"])
                suit = get_or_create(
                    db, MobileSuit, {"slug": suit_slug}, name=row["mobile_suit"]
                )
                values["mobile_suit_id"] = suit.id

            kit = db.scalars(select(Kit).where(Kit.slug == slug)).first()
            tag_names = [t.strip().lower() for t in (row.get("tags") or "").split(";")]
            tag_names = [t for t in tag_names if t]
            if kit is None:
                values.setdefault(
                    "manufacturer_id",
                    get_or_create(db, Manufacturer, {"name": DEFAULT_MANUFACTURER}).id,
                )
                if "scale" not in values and grade.typical_scale:
                    values["scale"] = grade.typical_scale
                kit = Kit(slug=slug, **values)
                for tag_name in tag_names:
                    kit.tags.append(get_or_create(db, Tag, {"name": tag_name}))
                db.add(kit)
                db.flush()
                kit_state[slug] = "new"
            else:
                changed = False
                for attr, value in values.items():
                    changed |= set_field(kit, attr, value, slug, changes)
                have = {t.name for t in kit.tags}
                for tag_name in tag_names:
                    if tag_name not in have:
                        kit.tags.append(get_or_create(db, Tag, {"name": tag_name}))
                        changes.append(f"{slug}: tag added {tag_name!r}")
                        changed = True
                kit_state[slug] = "changed" if changed else "same"
            kits_seen[slug] = kit
            if row.get("variant_of"):
                variant_requests.append((line, kit, row["variant_of"]))
        release_rows.append((line, kit, provided))

    # Pass 2: link variants to their original kit.
    for line, kit, original_slug in variant_requests:
        parent = db.scalars(select(Kit).where(Kit.slug == original_slug)).first()
        if parent is None:
            problems.append(f"line {line}: variant_of {original_slug!r} is not a known kit slug")
        elif parent.id == kit.id:
            problems.append(f"line {line}: a kit cannot be a variant of itself")
        elif parent.parent_kit_id is not None:
            problems.append(
                f"line {line}: {original_slug!r} is itself a variant; "
                "point at the ORIGINAL kit instead"
            )
        elif kit.parent_kit_id != parent.id:
            if kit_state.get(kit.slug) != "new":
                kit_state[kit.slug] = "changed"
                changes.append(f"{kit.slug}: parent kit set to {original_slug!r}")
            kit.parent_kit_id = parent.id

    # Pass 3: releases.
    for line, kit, provided in release_rows:
        jan = provided.get("jan_code")
        existing = None
        if jan:
            existing = db.scalars(select(KitRelease).where(KitRelease.jan_code == jan)).first()
            if existing is not None and existing.kit_id != kit.id:
                problems.append(
                    f"line {line}: barcode {jan} already belongs to a different kit "
                    f"(id {existing.kit_id})"
                )
                continue
        if existing is None:
            query = select(KitRelease).where(
                KitRelease.kit_id == kit.id,
                KitRelease.region == provided.get("region", "JP"),
                KitRelease.release_date == provided.get("release_date"),
                KitRelease.exclusive_to == provided.get("exclusive_to"),
            )
            if jan:  # filling in a barcode that was missing before
                query = query.where(KitRelease.jan_code.is_(None))
            existing = db.scalars(query).first()
        if existing is None:
            db.add(KitRelease(kit_id=kit.id, **provided))
            db.flush()
            counts["releases_new"] += 1
            if kit_state[kit.slug] != "new":
                touched.add(kit)
            continue
        ident = f"{kit.slug} release {existing.jan_code or existing.id}"
        changed = False
        for attr, value in provided.items():
            changed |= set_field(existing, attr, value, ident, changes)
        if changed:
            counts["releases_updated"] += 1
            touched.add(kit)
        else:
            counts["releases_unchanged"] += 1

    # The app syncs on kit.updated_at, so a release change must bump the kit too.
    now = datetime.utcnow()
    for kit in touched:
        kit.updated_at = now

    for state in kit_state.values():
        key = {"new": "kits_new", "changed": "kits_updated", "same": "kits_unchanged"}[state]
        counts[key] += 1
    return counts, problems, changes


def read_rows(path: str) -> Tuple[List[Dict[str, Optional[str]]], List[str]]:
    problems = []
    with open(path, newline="", encoding="utf-8-sig") as handle:  # utf-8-sig: Excel files
        reader = csv.DictReader(handle)
        header = reader.fieldnames or []
        for column in REQUIRED:
            if column not in header:
                problems.append(f"missing required column {column!r}")
        for column in header:
            if column not in COLUMNS:
                problems.append(f"unknown column {column!r}")
        rows = [clean_row(r) for r in reader]
    for index, row in enumerate(rows):
        for column in REQUIRED:
            if column in row and not row[column]:
                problems.append(f"line {index + 2}: {column} is empty")
    return rows, problems


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Load or update kits from a CSV file.")
    parser.add_argument("csv_path")
    parser.add_argument("--dry-run", action="store_true", help="check only, save nothing")
    args = parser.parse_args(argv)

    rows, problems = read_rows(args.csv_path)
    if problems:
        print("Fix these first:\n  " + "\n  ".join(problems))
        return 1

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        counts, problems, changes = load(db, rows)
        if problems:
            db.rollback()
            print("Nothing was saved. Fix these:\n  " + "\n  ".join(problems))
            return 1
        if args.dry_run:
            db.rollback()
        else:
            db.commit()

    if changes:
        print("Changes to existing data:")
        for text in changes[:MAX_CHANGES_SHOWN]:
            print("  " + text)
        if len(changes) > MAX_CHANGES_SHOWN:
            print(f"  ... and {len(changes) - MAX_CHANGES_SHOWN} more")
    prefix = "Dry run (nothing saved): " if args.dry_run else "Done: "
    print(
        f"{prefix}kits {counts['kits_new']} new, {counts['kits_updated']} updated, "
        f"{counts['kits_unchanged']} unchanged; releases {counts['releases_new']} new, "
        f"{counts['releases_updated']} updated, {counts['releases_unchanged']} unchanged."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
