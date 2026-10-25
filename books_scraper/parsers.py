"""HTML parsers for books.toscrape.com.
All CSS selectors live here so that a layout change on the website only
requires edits in this single module.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from scrapy.http import Response

from books_scraper.items import BookItem

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CategoryLink:
    """A category discovered on the website."""

    name: str
    url: str


class CategoryParser:
    """Extracts category-level information from pages."""

    # Direct children only: this skips the root "Books" link.
    CATEGORY_LINKS_CSS = "div.side_categories ul.nav-list > li > ul > li > a"
    CATEGORY_TITLE_CSS = "div.page-header h1::text"
    NEXT_PAGE_CSS = "li.next a::attr(href)"

    @classmethod
    def parse_categories(cls, response: Response) -> List[CategoryLink]:
        """Discover every category from the sidebar menu."""
        categories = []
        for link in response.css(cls.CATEGORY_LINKS_CSS):
            name = " ".join(link.css("::text").getall()).strip()
            href = link.attrib.get("href")
            if not name or not href:
                logger.warning("Skipping malformed category link: %s", link.get())
                continue
            categories.append(CategoryLink(name=name, url=response.urljoin(href)))
        return categories

    @classmethod
    def parse_category_title(cls, response: Response, fallback: str) -> str:
        """Read the category title from a category page."""
        title = response.css(cls.CATEGORY_TITLE_CSS).get()
        return title.strip() if title and title.strip() else fallback

    @classmethod
    def parse_next_page(cls, response: Response) -> Optional[str]:
        """Return the absolute URL of the next pagination page, if any."""
        href = response.css(cls.NEXT_PAGE_CSS).get()
        return response.urljoin(href) if href else None


class BookListingParser:
    """Extracts book data from a category listing page."""

    BOOK_CARD_CSS = "article.product_pod"

    @classmethod
    def parse_books(cls, response: Response, category: str) -> List[BookItem]:
        """Extract every book shown on one listing page.

        Values are kept raw; cleaning is the job of the item pipelines.
        """
        books = []
        for card in response.css(cls.BOOK_CARD_CSS):
            # The visible text is truncated ("A Light in the ..."),
            # the title attribute holds the full title.
            title = card.css("h3 a::attr(title)").get()
            href = card.css("h3 a::attr(href)").get()
            if not title or not href:
                logger.warning("Skipping malformed book card on %s", response.url)
                continue

            image_src = card.css("div.image_container img::attr(src)").get()
            books.append(
                BookItem(
                    title=title,
                    price=card.css("p.price_color::text").get(),
                    availability=" ".join(
                        card.css("p.availability::text").getall()
                    ),
                    product_url=response.urljoin(href),
                    image_url=response.urljoin(image_src) if image_src else None,
                    category=category,
                )
            )
        return books