# Polycap API

A public REST API for Gundam model kits (Gunpla): which kits exist, when they came out, and (eventually) which ones you own or have built.

Named after the polycap, the tiny joint piece that holds every Gunpla together... and also causes most of its headaches.

This is an unofficial fan project, not affiliated with Bandai. It's built with FastAPI, SQLAlchemy 2.0 and Pydantic v2, and it's meant to power a mobile app down the line.

**Status:** VERY early development. The read-only catalog works locally with a SQLite database, and it isn't deployed yet.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/v1/health` | Health check |
| GET | `/v1/kits` | List kits (paged). Filters: `grade`, `universe`, `mobile_suit`, `q`, `release_after`, `updated_since` |
| GET | `/v1/kits/{id}` | Get one kit (404 if not found) |
| GET | `/v1/kits/slug/{slug}` | Get one kit by its permanent slug, like `rg-sazabi` |
| GET | `/v1/kits/barcode/{jan}` | Look up a kit by the barcode on its box |

Lists come back as `{ "items": [...], "next_cursor": "..." }`. To get the next page, pass `next_cursor` as `?cursor=`. When `next_cursor` is `null` you have reached the end. `updated_since` is for apps that sync: it returns only kits that changed (including changes to their releases) after a given time.

A **kit** is one design (one set of parts and colors). Each kit has one or more **releases**: the boxes that went on sale, with their own barcode, price and date. A new-colors variant is its own kit that points to the original through `parent_kit_id`.

Interactive docs are generated automatically at `/docs`.

## Run it locally

Requires Python 3.9+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed          # creates gunpla.db with grades, universes, etc.
python -m app.load_csv data/kits.csv   # loads the kits
fastapi dev app/main.py
```

Then open http://127.0.0.1:8000/docs.

## Adding kits

Kits go in a CSV file, one row per release (one box on sale). See `data/kits.example.csv` for the format, add rows to `data/kits.csv`, then:

```bash
python -m app.load_csv data/kits.csv --dry-run   # check for mistakes, saves nothing
python -m app.load_csv data/kits.csv             # save
```

- Every kit needs a unique `slug` (lowercase, hyphens, like `rg-rx-78-2-gundam`). It is the kit's permanent key.
- Rows with the same `slug` are extra releases of the same kit (a reprint, a new barcode).
- A color or parts variant is its own kit, with `variant_of` set to the **original** kit's slug.
- `line_number` is the kit's number within its product line (like 29 for RG 29). Leave it blank if you don't know it.
- `mobile_suit` is just a name used to group kits of the same machine.
- Dates can be `2024-03-16`, `2024-03` or `2024`. Barcodes must be valid 13-digit JAN codes.
- Re-running updates whatever changed and prints each change. A blank cell never erases existing data, so you only fill the cells you want to set.
- If any row has a problem, nothing is saved and every problem is listed with its line number.
- Put the page you got each fact from in `source_url`.

## Sample request

```bash
curl "http://127.0.0.1:8000/v1/kits?q=sazabi"
```

```json
{
  "items": [
    {
      "id": 7,
      "slug": "rg-sazabi",
      "name": "Sazabi",
      "name_jp": null,
      "grade": { "code": "RG", "name": "Real Grade" },
      "product_line": { "name": "RG" },
      "universe": { "name": "Universal Century" },
      "mobile_suit": { "name": "MSN-04 Sazabi", "slug": "msn-04-sazabi" },
      "manufacturer": { "name": "Bandai Spirits" },
      "scale": "1/144",
      "parent_kit_id": null,
      "variant_label": null,
      "line_number": 29,
      "notes": null,
      "updated_at": "2026-11-09T01:46:17",
      "tags": [],
      "releases": [
        {
          "id": 7,
          "region": "JP",
          "jan_code": "4573102616050",
          "price": null,
          "currency": "JPY",
          "release_date": "2025-10-31",
          "date_precision": "day",
          "exclusive_to": null,
          "is_limited": false,
          "status": "released",
          "source_url": "https://www.hlj.com/1-144-scale-rg-sazabi-banh616050-up"
        }
      ]
    }
  ],
  "next_cursor": null
}
```

## Tests

```bash
pip install -r requirements-dev.txt
pytest
```

The tests use a throwaway database, so they never touch your real `gunpla.db`.

## Project layout

```
app/
  main.py        app setup and health endpoint
  database.py    database connection and sessions
  models.py      SQLAlchemy tables
  schemas.py     Pydantic response shapes
  seed.py        inserts lookup data (grades, universes, ...)
  load_csv.py    loads and updates kits from a CSV file
  slugs.py       slug helpers
  routers/
    kits.py      /v1/kits endpoints
```

## Data

Kit data is entered by hand and sticks to facts (names, grades, scales, release dates). I don't host any images, since the official art and names belong to Bandai.

## Roadmap

- More kits and prices
- Tests and deployment
- User accounts and personal collections

## License

MIT (covers the code only, not the data).
