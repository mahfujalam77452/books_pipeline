# Books Data Engineering Pipeline

A production-style Scrapy application that crawls [books.toscrape.com](https://books.toscrape.com/index.html),
randomly selects categories and books, cleans the data through item pipelines, exports it to
JSON / CSV / XML, stores it in SQLite, and runs inside Docker with Scrapyd.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Features](#features)
3. [Tech Stack](#tech-stack)
4. [Installation Guide](#installation-guide)
5. [Environment Setup](#environment-setup)
6. [Running the Spider](#running-the-spider)
7. [Docker Setup Guide](#docker-setup-guide)
8. [Scrapyd Deployment Guide](#scrapyd-deployment-guide)
9. [Output Format Description](#output-format-description)
10. [Database Configuration](#database-configuration)
11. [Architecture Diagram](#architecture-diagram)
12. [Folder Structure](#folder-structure)
13. [Design Decisions](#design-decisions)
14. [Known Limitations](#known-limitations)

---

## Project Overview

On every run the spider:

1. Opens the homepage and **discovers all categories dynamically** (no hardcoded names or URLs).
2. Randomly selects **5-10 categories**.
3. Crawls every page of each selected category and collects **all** books.
4. Randomly selects **5 books per category**.
5. Cleans and validates each book through Scrapy item pipelines.
6. Writes the result to **JSON, CSV, XML** (Scrapy Feed Exports) and **SQLite** (item pipeline).

Extracted fields: `title`, `price`, `availability`, `product_url`, `image_url`, `category`.

## Features

- Dynamic category discovery and full pagination handling
- Reproducible random selection through an optional seed
- Pipeline-based cleaning: whitespace trimming, text normalisation, currency removal,
  numeric price, boolean availability
- Validation and duplicate filtering
- Feed exports configured entirely in `settings.py`
- SQLite storage through an item pipeline, consistent with the exported files
- Consistency verification script (database vs JSON vs CSV vs XML)
- Docker image with Scrapyd; the project is deployed automatically on container start
- Structured logging for crawling, processing and errors
- OOP / SOLID / DRY design with docstrings on all classes and methods

## Tech Stack

| Area | Technology |
|---|---|
| Language | Python 3.12 |
| Crawling | Scrapy |
| Scheduling / API | Scrapyd, scrapyd-client |
| Database | SQLite (`sqlite3` from the standard library) |
| Containerisation | Docker, Docker Compose |

## Installation Guide

Requirements: Python 3.10+ and pip (Docker is only needed for the container setup).

```bash
git clone https://github.com/mahfujalam77452/books_pipeline
cd books_pipeline

python -m venv venv
# Windows (CMD):         venv\Scripts\activate
# Windows (PowerShell):  .\venv\Scripts\Activate.ps1
# Linux / macOS:         source venv/bin/activate

pip install -r requirements.txt
```

## Environment Setup

All settings live in `books_scraper/settings.py`. They can be overridden from the command
line with `-s NAME=value`, or through the environment variable below.

| Setting / variable | Default | Description |
|---|---|---|
| `BOOKS_OUTPUT_DIR` (env) | `output` | Directory for feeds and the SQLite database |
| `CATEGORY_COUNT_MIN` | `5` | Minimum number of categories to crawl |
| `CATEGORY_COUNT_MAX` | `10` | Maximum number of categories to crawl |
| `BOOKS_PER_CATEGORY` | `5` | Books selected from each category |
| `RANDOM_SEED` | `None` | Integer seed for a reproducible crawl |
| `SQLITE_DB_PATH` | `<output>/books.db` | Database file location |
| `SQLITE_RESET_ON_START` | `True` | Recreate the table on every run |
| `DOWNLOAD_DELAY` | `0.25` | Delay between requests (seconds) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Running the Spider

```bash
scrapy crawl books
```

Reproducible run:

```bash
scrapy crawl books -s RANDOM_SEED=42
```

Verify that the database and all exported files contain identical data:

```bash
python scripts/verify_consistency.py
```

The script exits with code `0` when everything matches and `1` otherwise.

## Docker Setup Guide

### Docker Compose (recommended)

```bash
docker compose up --build -d
docker compose logs -f          # Ctrl+C to leave the logs; the container keeps running
```

The container starts Scrapyd on port **6800** and deploys the project automatically.

Stop the container (data is kept in volumes):

```bash
docker compose down
```

Remove the container and its data:

```bash
docker compose down -v
```

### Plain Docker

```bash
docker build -t books-scrapyd .
docker run -d --name books-scrapyd -p 6800:6800 \
  -v books_output:/app/output -v scrapyd_data:/var/lib/scrapyd \
  books-scrapyd
```

### Getting the generated files out of the container

```bash
docker cp books-scrapyd:/app/output ./output_docker
```

Run the consistency check inside the container:

```bash
docker exec books-scrapyd python scripts/verify_consistency.py
```

## Scrapyd Deployment Guide

When the container starts, `docker/entrypoint.sh`:

1. starts Scrapyd in the foreground,
2. waits until `daemonstatus.json` responds,
3. runs `scrapyd-deploy`, which builds an egg and uploads it using `scrapy.cfg`.

Scrapyd itself is configured in `scrapyd.conf` (`bind_address = 0.0.0.0` is required so the
API is reachable from outside the container).

> On Windows PowerShell use `curl.exe` instead of `curl`.

Check the deployment:

```bash
curl http://localhost:6800/daemonstatus.json
curl http://localhost:6800/listprojects.json
curl "http://localhost:6800/listspiders.json?project=books_scraper"
```

Run the spider through the API:

```bash
curl http://localhost:6800/schedule.json -d project=books_scraper -d spider=books
```

Pass a setting to a job:

```bash
curl http://localhost:6800/schedule.json -d project=books_scraper -d spider=books -d setting=RANDOM_SEED=42
```

Monitor jobs and logs:

```bash
curl "http://localhost:6800/listjobs.json?project=books_scraper"
# Web UI and logs: http://localhost:6800
```

Cancel a job:

```bash
curl http://localhost:6800/cancel.json -d project=books_scraper -d job=<jobid>
```

### Deploying without Docker

```bash
scrapyd                # terminal 1 (keep running)
scrapyd-deploy         # terminal 2, from the folder containing scrapy.cfg
```

## Output Format Description

Files are written to the output directory (`output/` locally, `/app/output` in Docker).
They are overwritten on every run.

| Field | Type | Description |
|---|---|---|
| `title` | string | Full book title |
| `price` | float | Price without currency symbol |
| `availability` | boolean | `true` only when the status is exactly "In stock" |
| `product_url` | string | Absolute URL of the product page |
| `image_url` | string | Absolute URL of the book cover |
| `category` | string | Category name |

**books.json**

```json
[
    {
        "title": "It's Only the Himalayas",
        "price": 45.17,
        "availability": true,
        "product_url": "https://books.toscrape.com/catalogue/its-only-the-himalayas_981/index.html",
        "image_url": "https://books.toscrape.com/media/cache/27/a5/27a53d0bb95bdd88288eaf66c9230d7e.jpg",
        "category": "Travel"
    }
]
```

**books.csv**: header `title,price,availability,product_url,image_url,category`, one book per row
(availability is written as `True` / `False`).

**books.xml**: root element `<books>`, one `<book>` element per record containing one child
element per field.

## Database Configuration

SQLite is used (`output/books.db`, configurable with `SQLITE_DB_PATH`). The `SQLitePipeline`
creates this table automatically:

```sql
CREATE TABLE books (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT    NOT NULL,
    price        REAL    NOT NULL,
    availability INTEGER NOT NULL CHECK (availability IN (0, 1)),
    product_url  TEXT    NOT NULL UNIQUE,
    image_url    TEXT    NOT NULL,
    category     TEXT    NOT NULL
);
```

`availability` is stored as `1` (in stock) or `0` (not in stock).

Inspect the data:

```bash
sqlite3 output/books.db "SELECT category, COUNT(*) FROM books GROUP BY category;"
```

No SQLite client? Use Python:

```bash
python -c "import sqlite3; print(sqlite3.connect('output/books.db').execute('SELECT COUNT(*) FROM books').fetchone())"
```

**Consistency guarantee:** the database pipeline runs *after* cleaning and validation. If an
insert fails, the item is dropped, so it never reaches the feed exporters either. Both storages
therefore always contain the same records.

## Architecture Diagram

```
                     scrapy crawl books  /  Scrapyd schedule.json
                                   |
                                   v
                          +-----------------+
                          |   BooksSpider   |   (orchestrates the crawl)
                          +--------+--------+
                                   |
     +-----------------------------+------------------------------+
     |                             |                              |
     v                             v                              v
+----------------+      +---------------------+        +-------------------+
| CategoryParser |      |  BookListingParser  |        |  RandomSelector   |
| categories,    |      |  book cards -> Item |        | pick N categories |
| title, next pg |      +---------------------+        | pick 5 books      |
+----------------+                                     +-------------------+
                                   |
                                   v  BookItem (raw values)
        +-----------------------------------------------------------+
        |                     Item Pipelines                        |
        | 100 TextNormalization -> 200 Price -> 300 Availability -> |
        | 400 Validation -> 500 Duplicates -> 600 SQLite            |
        +--------------------------+--------------------------------+
                                   |
                  +----------------+-----------------+
                  v                                  v
          Feed Exports (settings.py)           SQLite database
          books.json / .csv / .xml              books.db
```

Crawl flow:

```
Homepage -> discover categories -> choose 5-10 -> for each category:
  page 1 -> page 2 -> ... -> last page (all books collected) -> choose 5 -> yield items
```

## Folder Structure

```
books_pipeline/
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .gitignore
├── .gitattributes
├── README.md
├── requirements.txt
├── scrapy.cfg                  # project + Scrapyd deploy target
├── scrapyd.conf                # Scrapyd server configuration
├── docker/
│   └── entrypoint.sh           # starts Scrapyd and auto-deploys the project
├── scripts/
│   └── verify_consistency.py   # DB vs JSON/CSV/XML comparison
└── books_scraper/
    ├── items.py                # BookItem definition
    ├── parsers.py              # CSS selectors and HTML parsing
    ├── selection.py            # RandomSelector
    ├── pipelines.py            # cleaning, validation, duplicates, SQLite
    ├── settings.py             # settings, feeds, pipeline order
    └── spiders/
        └── books_spider.py     # BooksSpider
```

## Design Decisions

- **Single Responsibility:** the spider only controls the crawl flow. Parsing lives in
  `parsers.py`, randomness in `selection.py`, and every cleaning step is its own pipeline.
- **Open/Closed and DRY:** `FieldPipeline` is an abstract base class that applies a `clean`
  method to a list of fields. A new cleaning step only needs a subclass.
- **Selectors in one place:** a website layout change requires edits only in `parsers.py`.
- **Data from listing pages:** the listing page already contains every required field, so no
  extra request per book is needed. It also exposes the exact status "In stock", whereas the
  detail page says "In stock (19 available)", which would be `False` under the required rule.
- **Full title from the `title` attribute:** the visible link text on listing pages is truncated.
- **Selection after pagination:** books are collected from all pages first, so every book has
  an equal chance of being selected.
- **Robust price parsing:** a regex extracts the number, so it works even if the currency symbol
  is mis-decoded or the price contains thousands separators.
- **Database before feeds:** pipelines run before feed exporters, so a failed database insert
  drops the item everywhere and keeps all storages identical.
- **Absolute output path in Docker:** Scrapyd runs spiders as separate processes, so the
  output directory is provided through `BOOKS_OUTPUT_DIR`.
- **Auto-deploy at container start:** the container works without any manual step.
- **Non-root container user and named volumes** for safer, persistent deployments.

## Known Limitations

- Categories with fewer than 5 books produce fewer than 5 records (all their books are used and
  a warning is logged). "Exactly 5" is impossible there.
- Output files and the database are overwritten on every run. Two Scrapyd jobs running at the
  same time would write to the same files; keep `max_proc` effectively at one running job of
  this spider, or give each job its own `BOOKS_OUTPUT_DIR`.
- Only listing-page data is extracted: the exact stock count and the full-size cover image
  from the detail page are not collected.
- Selection is random, so two runs differ unless `RANDOM_SEED` is set.
- No proxy or user-agent rotation. Not needed for this sandbox site, but required for
  sites with anti-bot protection.
- CSS selectors depend on the current website layout.
- Every container start deploys a new egg version into Scrapyd's volume.
- SQLite supports a single writer, which is sufficient for this workload.