"""Item pipelines: cleaning, validation and de-duplication."""
import sqlite3
from pathlib import Path
import logging
import re
import unicodedata
from abc import ABC, abstractmethod
from typing import Any, Optional, Set, Tuple

from itemadapter import ItemAdapter
from scrapy import Spider
from scrapy.exceptions import DropItem

logger = logging.getLogger(__name__)


class FieldPipeline(ABC):
    """Base class for pipelines that transform specific item fields."""

    fields: Tuple[str, ...] = ()

    def process_item(self, item: Any, spider: Spider) -> Any:
        """Apply ``clean`` to every configured field of the item."""
        adapter = ItemAdapter(item)
        for field in self.fields:
            if field in adapter:
                adapter[field] = self.clean(adapter[field])
        return item

    @abstractmethod
    def clean(self, value: Any) -> Any:
        """Clean a single value."""


class TextNormalizationPipeline(FieldPipeline):
    """Trim and normalise every text field."""

    fields = ("title", "availability", "category", "product_url", "image_url")

    def clean(self, value: Any) -> Optional[str]:
        """Strip, unicode-normalise and collapse repeated whitespace."""
        if value is None:
            return None
        text = unicodedata.normalize("NFKC", str(value))
        text = re.sub(r"\s+", " ", text).strip()
        return text or None


class PricePipeline(FieldPipeline):
    """Convert a price string such as ``"£45.17"`` into a float."""

    fields = ("price",)
    _NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")

    def clean(self, value: Any) -> Optional[float]:
        """Remove currency symbols and parse the number."""
        if value is None:
            return None
        text = str(value).replace(",", "")  # thousands separator
        match = self._NUMBER_RE.search(text)
        if not match:
            logger.warning("Could not parse price from %r", value)
            return None
        return round(float(match.group()), 2)


class AvailabilityPipeline(FieldPipeline):
    """Convert availability text into a boolean."""

    fields = ("availability",)

    def clean(self, value: Any) -> bool:
        """Map ``"In stock"`` to ``True`` and anything else to ``False``."""
        return isinstance(value, str) and value.strip().lower() == "in stock"


class ValidationPipeline:
    """Drop items that miss required data."""

    REQUIRED_FIELDS = (
        "title",
        "price",
        "availability",
        "product_url",
        "image_url",
        "category",
    )

    def process_item(self, item: Any, spider: Spider) -> Any:
        """Ensure all required fields are present."""
        adapter = ItemAdapter(item)
        missing = [f for f in self.REQUIRED_FIELDS if adapter.get(f) is None]
        if missing:
            raise DropItem(f"Missing fields {missing} in item: {adapter.get('product_url')}")
        return item


class DuplicatesPipeline:
    """Drop items whose ``product_url`` was already processed."""

    def __init__(self) -> None:
        """Initialise the set of seen URLs."""
        self._seen: Set[str] = set()

    def process_item(self, item: Any, spider: Spider) -> Any:
        """Reject duplicates."""
        url = ItemAdapter(item)["product_url"]
        if url in self._seen:
            raise DropItem(f"Duplicate item: {url}")
        self._seen.add(url)
        return item

class SQLitePipeline:
    """Persist validated items into a SQLite database. """

    CREATE_TABLE_SQL = """
        CREATE TABLE IF NOT EXISTS books (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            title        TEXT    NOT NULL,
            price        REAL    NOT NULL,
            availability INTEGER NOT NULL CHECK (availability IN (0, 1)),
            product_url  TEXT    NOT NULL UNIQUE,
            image_url    TEXT    NOT NULL,
            category     TEXT    NOT NULL
        )
    """
    INSERT_SQL = """
        INSERT INTO books (title, price, availability, product_url, image_url, category)
        VALUES (:title, :price, :availability, :product_url, :image_url, :category)
    """
    COMMIT_EVERY = 50

    def __init__(self, db_path: str, reset_on_start: bool = True) -> None:
        """Store configuration; the connection is opened in ``open_spider``. """
        self.db_path = db_path
        self.reset_on_start = reset_on_start
        self.connection: Optional[sqlite3.Connection] = None
        self._inserted = 0
        self._pending = 0

    @classmethod
    def from_crawler(cls, crawler) -> "SQLitePipeline":
        """Build the pipeline from project settings."""
        settings = crawler.settings
        return cls(
            db_path=settings.get("SQLITE_DB_PATH", "output/books.db"),
            reset_on_start=settings.getbool("SQLITE_RESET_ON_START", True),
        )

    def open_spider(self, spider: Spider) -> None:
        """Open the database connection and prepare the table."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.db_path)
        if self.reset_on_start:
            self.connection.execute("DROP TABLE IF EXISTS books")
        self.connection.execute(self.CREATE_TABLE_SQL)
        self.connection.commit()
        logger.info("SQLite database ready at %s", self.db_path)

    def process_item(self, item: Any, spider: Spider) -> Any:
        """Insert one item into the ``books`` table."""
        row = dict(ItemAdapter(item))
        row["availability"] = int(bool(row["availability"]))
        try:
            self.connection.execute(self.INSERT_SQL, row)
        except sqlite3.IntegrityError as exc:
            raise DropItem(f"Integrity error for {row['product_url']}: {exc}")
        except sqlite3.Error as exc:
            logger.error("Database error for %s: %s", row["product_url"], exc)
            raise DropItem(f"Database error for {row['product_url']}: {exc}")

        self._inserted += 1
        self._pending += 1
        if self._pending >= self.COMMIT_EVERY:
            self.connection.commit()
            self._pending = 0
        return item

    def close_spider(self, spider: Spider) -> None:
        """Commit remaining rows and close the connection. """
        if self.connection is None:
            return
        self.connection.commit()
        self.connection.close()
        logger.info("SQLite: %d rows stored in %s", self._inserted, self.db_path)