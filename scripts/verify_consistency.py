"""Verify that the SQLite database and all exported files hold the same data."""

import argparse
import csv
import json
import sqlite3
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from typing import Dict, List

FIELDS = ["title", "price", "availability", "product_url", "image_url", "category"]
Record = Dict[str, object]


def to_bool(value: object) -> bool:
    """Convert bool / 0 / 1 / 'True' / 'false' style values to bool."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1"}


def normalize(raw: Dict[str, object]) -> Record:
    """Convert a raw record into a comparable canonical form."""
    return {
        "title": str(raw["title"]).strip(),
        "price": round(float(raw["price"]), 2),
        "availability": to_bool(raw["availability"]),
        "product_url": str(raw["product_url"]).strip(),
        "image_url": str(raw["image_url"]).strip(),
        "category": str(raw["category"]).strip(),
    }


def load_db(path: Path) -> List[Record]:
    """Load every row from the SQLite ``books`` table."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(f"SELECT {', '.join(FIELDS)} FROM books").fetchall()
    finally:
        conn.close()
    return [normalize(dict(row)) for row in rows]


def load_json(path: Path) -> List[Record]:
    """Load records from the JSON export."""
    with open(path, encoding="utf-8") as handle:
        return [normalize(item) for item in json.load(handle)]


def load_csv(path: Path) -> List[Record]:
    """Load records from the CSV export."""
    with open(path, encoding="utf-8", newline="") as handle:
        return [normalize(row) for row in csv.DictReader(handle)]


def load_xml(path: Path) -> List[Record]:
    """Load records from the XML export."""
    root = ET.parse(path).getroot()
    return [
        normalize({child.tag: (child.text or "") for child in book})
        for book in root
    ]


def index_by_url(records: List[Record]) -> Dict[str, Record]:
    """Index records by ``product_url`` (the unique key)."""
    return {record["product_url"]: record for record in records}


def compare(name: str, reference: Dict[str, Record], other: Dict[str, Record]) -> int:
    """Compare one source against the reference (database)."""
    problems = 0
    for url in sorted(reference.keys() - other.keys()):
        print(f"  [{name}] missing record: {url}")
        problems += 1
    for url in sorted(other.keys() - reference.keys()):
        print(f"  [{name}] extra record not in DB: {url}")
        problems += 1
    for url in reference.keys() & other.keys():
        for field in FIELDS:
            if reference[url][field] != other[url][field]:
                print(
                    f"  [{name}] {url} -> {field}: "
                    f"db={reference[url][field]!r} vs {other[url][field]!r}"
                )
                problems += 1
    return problems


def main() -> int:
    """Run all consistency checks."""
    parser = argparse.ArgumentParser(description="Verify DB / export consistency")
    parser.add_argument("--output-dir", default="output", type=Path)
    parser.add_argument("--db", default=None, type=Path)
    args = parser.parse_args()

    db_path = args.db or args.output_dir / "books.db"
    sources = {
        "database": (load_db, db_path),
        "json": (load_json, args.output_dir / "books.json"),
        "csv": (load_csv, args.output_dir / "books.csv"),
        "xml": (load_xml, args.output_dir / "books.xml"),
    }

    loaded: Dict[str, List[Record]] = {}
    for name, (loader, path) in sources.items():
        if not path.exists():
            print(f"ERROR: {name} file not found: {path}")
            return 1
        loaded[name] = loader(path)

    print("Record counts:")
    for name, records in loaded.items():
        print(f"  {name:<9}: {len(records)} records, "
              f"{len(index_by_url(records))} unique URLs")

    reference = index_by_url(loaded["database"])
    problems = 0
    for name in ("json", "csv", "xml"):
        problems += compare(name, reference, index_by_url(loaded[name]))

    per_category = Counter(record["category"] for record in loaded["database"])
    print(f"\nCategories crawled: {len(per_category)}")
    for category, count in sorted(per_category.items()):
        print(f"  {category:<20} {count} books")

    if problems:
        print(f"\nFAILED: {problems} inconsistencies found")
        return 1
    print("\nOK: database, JSON, CSV and XML are fully consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())