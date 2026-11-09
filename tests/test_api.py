from datetime import datetime

import pytest
from sqlalchemy import update

from app.load_csv import load
from app.models import Kit
from tests.helpers import jan, row

UC = "Universal Century"

ALPHA = row(
    slug="rg-alpha", name="Alpha", grade="RG", universe=UC, mobile_suit="Alpha Suit",
    tags="transformation", jan_code=jan("457310200001"), release_date="2010-07-22",
)
ALPHA_V2 = row(
    slug="rg-alpha-ver-2", name="Alpha Ver.2.0", grade="RG", universe=UC,
    mobile_suit="Alpha Suit", jan_code=jan("457310200002"), release_date="2024-08",
)
BETA = row(
    slug="hg-beta", name="Beta", name_jp="ベータ", grade="HG", universe="After Colony",
    mobile_suit="Beta Suit", jan_code=jan("457310200003"), release_date="2025-10-31",
)
BETA_CLEAR = row(
    slug="hg-beta-clear", name="Beta [Clear]", grade="HG", universe="After Colony",
    mobile_suit="Beta Suit", variant_of="hg-beta", variant_label="Clear",
    exclusive_to="event", is_limited="yes", release_date="2025-11",
)
GAMMA = row(slug="mg-gamma", name="Gamma", grade="MG", universe="Cosmic Era")

ALL_SLUGS = ["rg-alpha", "rg-alpha-ver-2", "hg-beta", "hg-beta-clear", "mg-gamma"]


@pytest.fixture
def catalog(db):
    """Five kits (ids 1 to 5, in that order) loaded into the test database."""
    _, problems, _ = load(db, [ALPHA, ALPHA_V2, BETA, BETA_CLEAR, GAMMA])
    assert problems == []
    db.commit()
    return db


def slugs(client, **params):
    response = client.get("/v1/kits", params=params)
    assert response.status_code == 200
    return [kit["slug"] for kit in response.json()["items"]]


# --- Basics ----------------------------------------------------------------------


def test_health(client):
    assert client.get("/v1/health").json() == {"status": "healthy"}


def test_openapi_docs_build(client):
    assert client.get("/openapi.json").status_code == 200


def test_empty_catalog_returns_an_empty_page(client):
    assert client.get("/v1/kits").json() == {"items": [], "next_cursor": None}


# --- Listing and paging -----------------------------------------------------------


def test_list_returns_every_kit_in_id_order(catalog, client):
    body = client.get("/v1/kits").json()
    assert [k["slug"] for k in body["items"]] == ALL_SLUGS
    assert body["next_cursor"] is None


def test_paging_visits_every_kit_exactly_once(catalog, client):
    seen, cursor, pages = [], None, 0
    while True:
        params = {"limit": 2, **({"cursor": cursor} if cursor else {})}
        body = client.get("/v1/kits", params=params).json()
        seen += [k["slug"] for k in body["items"]]
        pages += 1
        cursor = body["next_cursor"]
        if cursor is None:
            break
    assert seen == ALL_SLUGS
    assert pages == 3


def test_a_page_that_ends_exactly_on_the_last_kit_has_no_next_cursor(catalog, client):
    assert client.get("/v1/kits", params={"limit": 5}).json()["next_cursor"] is None


def test_garbage_cursor_is_rejected(catalog, client):
    assert client.get("/v1/kits", params={"cursor": "!!!"}).status_code == 400


@pytest.mark.parametrize("limit", [0, 101])
def test_limit_must_be_between_1_and_100(catalog, client, limit):
    assert client.get("/v1/kits", params={"limit": limit}).status_code == 422


# --- Filters --------------------------------------------------------------------------


def test_filter_by_grade_ignores_case(catalog, client):
    assert slugs(client, grade="hg") == ["hg-beta", "hg-beta-clear"]
    assert slugs(client, grade="MG") == ["mg-gamma"]


def test_filter_by_universe_ignores_case(catalog, client):
    assert slugs(client, universe="cosmic era") == ["mg-gamma"]


def test_filter_by_mobile_suit_accepts_name_or_slug(catalog, client):
    expected = ["rg-alpha", "rg-alpha-ver-2"]
    assert slugs(client, mobile_suit="Alpha Suit") == expected
    assert slugs(client, mobile_suit="alpha-suit") == expected


def test_search_matches_english_and_japanese_names(catalog, client):
    assert slugs(client, q="alp") == ["rg-alpha", "rg-alpha-ver-2"]
    assert slugs(client, q="ベータ") == ["hg-beta"]
    assert slugs(client, q="no-such-kit") == []


def test_filter_by_release_after(catalog, client):
    assert slugs(client, release_after="2025-01-01") == ["hg-beta", "hg-beta-clear"]
    assert slugs(client, release_after="2025-11-01") == ["hg-beta-clear"]
    assert slugs(client, release_after="2030-01-01") == []


def test_filters_combine(catalog, client):
    assert slugs(client, grade="hg", universe="after colony", q="clear") == ["hg-beta-clear"]
    assert slugs(client, grade="rg", universe="cosmic era") == []


def test_updated_since_returns_only_changed_kits(catalog, client):
    catalog.execute(update(Kit).values(updated_at=datetime(2000, 1, 1)))
    catalog.commit()
    load(catalog, [{**ALPHA, "price": "1200"}])  # changes alpha's release only
    catalog.commit()

    assert slugs(client, updated_since="2001-01-01T00:00:00") == ["rg-alpha"]
    assert slugs(client, updated_since="1999-01-01T00:00:00") == ALL_SLUGS


# --- Single kits ---------------------------------------------------------------------------


def test_get_by_id(catalog, client):
    kit = client.get("/v1/kits/1").json()
    assert kit["slug"] == "rg-alpha"
    assert kit["id"] == 1


def test_get_by_id_missing_is_404(catalog, client):
    assert client.get("/v1/kits/999").status_code == 404


def test_get_by_slug(catalog, client):
    assert client.get("/v1/kits/slug/hg-beta").json()["name"] == "Beta"
    assert client.get("/v1/kits/slug/nope").status_code == 404


def test_get_by_barcode(catalog, client):
    kit = client.get(f"/v1/kits/barcode/{ALPHA['jan_code']}").json()
    assert kit["slug"] == "rg-alpha"
    assert client.get("/v1/kits/barcode/0000000000000").status_code == 404


def test_a_kit_includes_its_nested_details(catalog, client):
    kit = client.get("/v1/kits/slug/rg-alpha").json()
    assert kit["grade"] == {"code": "RG", "name": "Real Grade"}
    assert kit["universe"] == {"name": UC}
    assert kit["mobile_suit"] == {"name": "Alpha Suit", "slug": "alpha-suit"}
    assert kit["manufacturer"] == {"name": "Bandai Spirits"}
    assert kit["tags"] == ["transformation"]
    assert kit["parent_kit_id"] is None
    (release,) = kit["releases"]
    assert release["jan_code"] == ALPHA["jan_code"]
    assert release["release_date"] == "2010-07-22"
    assert release["date_precision"] == "day"


def test_a_variant_links_to_its_original_and_carries_release_flags(catalog, client):
    original = client.get("/v1/kits/slug/hg-beta").json()
    variant = client.get("/v1/kits/slug/hg-beta-clear").json()
    assert variant["parent_kit_id"] == original["id"]
    assert variant["variant_label"] == "Clear"
    assert variant["releases"][0]["exclusive_to"] == "event"
    assert variant["releases"][0]["is_limited"] is True
    assert variant["releases"][0]["date_precision"] == "month"
