import csv
from datetime import date, datetime

import pytest
from sqlalchemy import func, select

from app.load_csv import (
    COLUMNS,
    load,
    main,
    parse_bool,
    parse_release_date,
    read_rows,
    valid_jan,
)
from app.models import Kit, KitRelease
from tests.helpers import jan, row

ALPHA = dict(
    slug="rg-alpha", name="Alpha", grade="RG", universe="Universal Century",
    mobile_suit="Alpha Suit", jan_code=jan("457310200001"), price="1000",
    release_date="2020-05-01",
)


def run(db, *rows):
    """Load rows and commit, the way the command-line tool does."""
    result = load(db, list(rows))
    db.commit()
    return result


def count(db, model):
    return db.scalar(select(func.count()).select_from(model))


def write_csv(path, rows):
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        for r in rows:
            writer.writerow({k: v or "" for k, v in r.items()})


# --- Loading new data ---------------------------------------------------------


def test_loads_a_new_kit_with_sensible_defaults(db):
    counts, problems, _ = run(db, row(**ALPHA))

    assert problems == []
    assert counts["kits_new"] == 1 and counts["releases_new"] == 1
    kit = db.scalars(select(Kit)).one()
    assert kit.slug == "rg-alpha"
    assert kit.manufacturer.name == "Bandai Spirits"  # default maker
    assert kit.scale == "1/144"  # taken from the grade
    assert kit.mobile_suit.slug == "alpha-suit"
    release = kit.releases[0]
    assert release.price == 1000
    assert release.release_date == date(2020, 5, 1)
    assert release.date_precision == "day"
    assert release.region == "JP" and release.currency == "JPY"


def test_rows_with_the_same_slug_are_releases_of_one_kit(db):
    second = row(slug="rg-alpha", name="Alpha", grade="RG", release_date="2023-01-15", price="1500")
    counts, problems, _ = run(db, row(**ALPHA), second)

    assert problems == []
    assert counts["kits_new"] == 1 and counts["releases_new"] == 2
    assert len(db.scalars(select(Kit)).one().releases) == 2


def test_month_and_year_dates_record_their_precision(db):
    run(
        db,
        row(slug="a", name="A", grade="HG", release_date="2024-03"),
        row(slug="b", name="B", grade="HG", release_date="2024"),
    )
    precision = {
        k.slug: (k.releases[0].release_date, k.releases[0].date_precision)
        for k in db.scalars(select(Kit))
    }
    assert precision["a"] == (date(2024, 3, 1), "month")
    assert precision["b"] == (date(2024, 1, 1), "year")


def test_tags_are_created_and_attached(db):
    run(db, row(**ALPHA, tags="Transformation; clear parts"))
    kit = db.scalars(select(Kit)).one()
    assert kit.tag_names == ["clear parts", "transformation"]


def test_line_number_is_saved_and_can_be_updated(db):
    run(db, row(**ALPHA, line_number="7"))
    assert db.scalars(select(Kit)).one().line_number == 7

    _, _, changes = run(db, row(**ALPHA, line_number="8"))
    assert any("line_number" in c for c in changes)
    assert db.scalars(select(Kit)).one().line_number == 8


def test_a_blank_line_number_does_not_erase_an_existing_one(db):
    run(db, row(**ALPHA, line_number="7"))
    run(db, row(**ALPHA))
    assert db.scalars(select(Kit)).one().line_number == 7


# --- Re-running and updating --------------------------------------------------


def test_rerunning_the_same_rows_changes_nothing(db):
    run(db, row(**ALPHA))
    counts, problems, changes = run(db, row(**ALPHA))

    assert problems == [] and changes == []
    assert counts["kits_unchanged"] == 1 and counts["releases_unchanged"] == 1
    assert counts["kits_new"] == 0 and counts["releases_new"] == 0
    assert count(db, Kit) == 1 and count(db, KitRelease) == 1


def test_changed_price_updates_and_is_reported(db):
    run(db, row(**ALPHA))
    counts, _, changes = run(db, row(**{**ALPHA, "price": "1200"}))

    assert counts["releases_updated"] == 1
    assert any("price" in c and "1200" in c for c in changes)
    assert db.scalars(select(KitRelease)).one().price == 1200


def test_blank_cells_never_erase_existing_data(db):
    run(db, row(**ALPHA))
    sparse = row(slug="rg-alpha", name="Alpha", grade="RG", jan_code=ALPHA["jan_code"])
    _, problems, changes = run(db, sparse)

    assert problems == [] and changes == []
    release = db.scalars(select(KitRelease)).one()
    assert release.price == 1000 and release.release_date == date(2020, 5, 1)
    assert db.scalars(select(Kit)).one().mobile_suit is not None


def test_kit_changes_are_reported(db):
    run(db, row(**ALPHA))
    counts, _, changes = run(db, row(**{**ALPHA, "notes": "Hello"}))

    assert counts["kits_updated"] == 1
    assert any("notes" in c for c in changes)


def test_adding_a_missing_barcode_updates_the_release_instead_of_duplicating(db):
    no_barcode = row(slug="a", name="A", grade="HG", release_date="2020-05-01")
    run(db, no_barcode)
    counts, problems, _ = run(db, {**no_barcode, "jan_code": jan("457310200009")})

    assert problems == []
    assert counts["releases_updated"] == 1 and counts["releases_new"] == 0
    assert count(db, KitRelease) == 1
    assert db.scalars(select(KitRelease)).one().jan_code == jan("457310200009")


def test_changing_a_release_bumps_the_kit_updated_at(db):
    run(db, row(**ALPHA))
    kit = db.scalars(select(Kit)).one()
    kit.updated_at = datetime(2000, 1, 1)
    db.commit()

    run(db, row(**{**ALPHA, "price": "1300"}))
    db.refresh(kit)
    assert kit.updated_at > datetime(2020, 1, 1)


# --- Variants ----------------------------------------------------------------


def test_variant_points_at_the_original_kit(db):
    clear = row(
        slug="rg-alpha-clear", name="Alpha Clear", grade="RG", variant_of="rg-alpha",
        variant_label="Clear", exclusive_to="event", is_limited="yes",
    )
    _, problems, _ = run(db, row(**ALPHA), clear)

    assert problems == []
    original = db.scalars(select(Kit).where(Kit.slug == "rg-alpha")).one()
    variant = db.scalars(select(Kit).where(Kit.slug == "rg-alpha-clear")).one()
    assert variant.parent_kit_id == original.id
    assert variant.releases[0].exclusive_to == "event"
    assert variant.releases[0].is_limited is True


@pytest.mark.parametrize(
    "rows, message",
    [
        ([row(slug="b", name="B", grade="HG", variant_of="nope")], "not a known kit slug"),
        ([row(slug="a", name="A", grade="HG", variant_of="a")], "cannot be a variant of itself"),
        (
            [
                row(slug="a", name="A", grade="HG"),
                row(slug="b", name="B", grade="HG", variant_of="a"),
                row(slug="c", name="C", grade="HG", variant_of="b"),
            ],
            "itself a variant",
        ),
    ],
)
def test_bad_variant_links_are_reported(db, rows, message):
    _, problems, _ = load(db, rows)
    assert any(message in p for p in problems)


# --- Validation ----------------------------------------------------------------


def test_problems_are_reported_with_csv_line_numbers(db):
    good = jan("457310200001")
    wrong_check_digit = good[:-1] + str((int(good[-1]) + 1) % 10)
    rows = [
        row(slug="ok-1", name="Fine", grade="HG"),                              # line 2
        row(slug="a", name="A", grade="ZZ"),                                    # line 3
        row(slug="Bad Slug", name="B", grade="HG"),                             # line 4
        row(slug="c", name="C", grade="HG", jan_code=wrong_check_digit),        # line 5
        row(slug="d", name="D", grade="HG", release_date="2020-13-45"),         # line 6
        row(slug="e", name="E", grade="HG", universe="Nowhere"),                # line 7
        row(slug="f", name="F", grade="HG", price="abc"),                       # line 8
        row(slug="g", name="G", grade="HG", exclusive_to="sale"),               # line 9
        row(slug="h", name="H", grade="HG", line_number="0"),                   # line 10
        row(slug="i", name="I", grade="HG", line_number="two"),                 # line 11
    ]
    _, problems, _ = load(db, rows)

    def has(line, text):
        return any(p.startswith(f"line {line}:") and text in p for p in problems)

    assert has(3, "unknown grade")
    assert has(4, "slug")
    assert has(5, "not a valid 13-digit barcode")
    assert has(6, "release_date")
    assert has(7, "unknown universe")
    assert has(8, "price")
    assert has(9, "exclusive_to")
    assert has(10, "line_number")
    assert has(11, "line_number")
    assert not any(p.startswith("line 2:") for p in problems)


def test_a_barcode_cannot_belong_to_two_kits(db):
    run(db, row(**ALPHA))
    other = row(slug="other", name="Other", grade="RG", jan_code=ALPHA["jan_code"])
    _, problems, _ = load(db, [other])
    assert any("already belongs to a different kit" in p for p in problems)


# --- The command-line tool (all-or-nothing) -----------------------------------


def test_a_file_with_any_bad_row_saves_nothing(db, tmp_path, capsys):
    path = tmp_path / "kits.csv"
    write_csv(path, [
        row(slug="good", name="Good", grade="HG"),
        row(slug="bad", name="Bad", grade="ZZ"),
    ])

    assert main([str(path)]) == 1
    assert "Nothing was saved" in capsys.readouterr().out
    db.expire_all()
    assert count(db, Kit) == 0


def test_a_clean_file_is_saved(db, tmp_path):
    path = tmp_path / "kits.csv"
    write_csv(path, [row(slug="good", name="Good", grade="HG")])

    assert main([str(path)]) == 0
    db.expire_all()
    assert count(db, Kit) == 1


def test_dry_run_saves_nothing(db, tmp_path):
    path = tmp_path / "kits.csv"
    write_csv(path, [row(slug="good", name="Good", grade="HG")])

    assert main([str(path), "--dry-run"]) == 0
    db.expire_all()
    assert count(db, Kit) == 0


def test_read_rows_rejects_unknown_and_missing_columns(tmp_path):
    path = tmp_path / "kits.csv"
    path.write_text("slug,name,bogus\nx,X,1\n")
    _, problems = read_rows(str(path))
    assert any("unknown column 'bogus'" in p for p in problems)
    assert any("missing required column 'grade'" in p for p in problems)


def test_read_rows_rejects_empty_required_cells(tmp_path):
    path = tmp_path / "kits.csv"
    path.write_text("slug,name,grade\nx,,HG\n")
    _, problems = read_rows(str(path))
    assert any("line 2: name is empty" in p for p in problems)


# --- Small parsing functions -----------------------------------------------------


def test_valid_jan():
    assert valid_jan(jan("457310200001"))
    assert not valid_jan("4573102000012")  # wrong check digit
    assert not valid_jan("12345")  # too short
    assert not valid_jan("45731020000A1")  # not all digits


def test_parse_release_date():
    assert parse_release_date("2024-03-16") == (date(2024, 3, 16), "day")
    assert parse_release_date("2024-03") == (date(2024, 3, 1), "month")
    assert parse_release_date("2024") == (date(2024, 1, 1), "year")
    with pytest.raises(ValueError):
        parse_release_date("2024-13-01")
    with pytest.raises(ValueError):
        parse_release_date("soon")


def test_parse_bool():
    assert parse_bool("Yes") is True and parse_bool("no") is False
    with pytest.raises(ValueError):
        parse_bool("maybe")
