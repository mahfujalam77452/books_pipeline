"""Item pipelines: cleaning, validation and de-duplication."""

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