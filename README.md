# Polycap API

A public REST API for Gundam model kits (Gunpla): which kits exist, when they came out, and (eventually) which ones you own or have built.

Named after the polycap, the tiny joint piece that holds every Gunpla together... and also causes most of its headaches.

This is an unofficial fan project, not affiliated with Bandai. It's built with FastAPI, SQLAlchemy 2.0 and Pydantic v2, and it's meant to power a mobile app down the line.

**Status:** VERY early development. The read-only catalog works locally with a SQLite database, and it isn't deployed yet.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/v1/health` | Health check |
| GET | `/v1/kits` | List kits. Filters: `?grade=HG`, `?universe=Cosmic Era`, `?q=zaku`, `?limit=20` |
| GET | `/v1/kits/{id}` | Get one kit (404 if not found) |
| GET | `/v1/kits/barcode/{jan}` | Look up a kit by the barcode on its box |

A **kit** is one design (one set of parts and colors). Each kit has one or more **releases**: the boxes that went on sale, with their own barcode, price and date. A new-colors variant is its own kit that points to the original through `parent_kit_id`.

Interactive docs are generated automatically at `/docs`.

## Run it locally

Requires Python 3.9+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed          # creates gunpla.db with sample kits
fastapi dev app/main.py
```

Then open http://127.0.0.1:8000/docs.

## Sample request

```bash
curl "http://127.0.0.1:8000/v1/kits?grade=HG"
```

```json
[
  {
    "id": 2,
    "name": "Zaku II",
    "name_jp": null,
    "grade": { "code": "HG", "name": "High Grade" },
    "product_line": { "name": "HGUC" },
    "universe": { "name": "Universal Century" },
    "manufacturer": { "name": "Bandai Spirits" },
    "scale": "1/144",
    "parent_kit_id": null,
    "variant_label": null,
    "notes": null,
    "tags": [],
    "releases": [
      {
        "id": 2,
        "region": "JP",
        "jan_code": null,
        "price": null,
        "currency": "JPY",
        "release_date": null,
        "date_precision": "day",
        "exclusive_to": null,
        "is_limited": false,
        "status": "released",
        "source_url": null
      }
    ]
  }
]
```

## Project layout

```
app/
  main.py        app setup and health endpoint
  database.py    database connection and sessions
  models.py      SQLAlchemy tables
  schemas.py     Pydantic response shapes
  seed.py        inserts lookup data and sample kits
  routers/
    kits.py      /v1/kits endpoints
```

## Data

Kit data is entered by hand and sticks to facts (names, grades, scales, release dates). I don't host any images, since the official art and names belong to Bandai.

## Roadmap

- More kits and fields (release date, price, barcode lookup)
- Filtering, search and pagination
- Tests and deployment
- User accounts and personal collections

## License

MIT (covers the code only, not the data).
