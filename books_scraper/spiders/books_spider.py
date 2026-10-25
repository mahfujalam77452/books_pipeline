"""Spider that crawls random categories and extracts random books."""

import logging
from typing import Iterator, List

import scrapy
from scrapy.http import Response
from twisted.python.failure import Failure

from books_scraper.items import BookItem
from books_scraper.parsers import BookListingParser, CategoryParser
from books_scraper.selection import RandomSelector


class BooksSpider(scrapy.Spider):
    """Crawl books.toscrape.com.

    Flow:
        1. Open the homepage and discover all categories dynamically.
        2. Randomly select 5-10 categories.
        3. For each category, walk through every pagination page and
           collect all books.
        4. Randomly select 5 books per category and yield them.
    """

    name = "books"
    allowed_domains = ["books.toscrape.com"]
    start_urls = ["https://books.toscrape.com/index.html"]

    def __init__(self, *args, **kwargs) -> None:
        """Initialise the spider and its random selector."""
        super().__init__(*args, **kwargs)
        self.selector = None  # created in parse() once settings are available

    
    # Step 1: homepage -> categories
    
    def parse(self, response: Response) -> Iterator[scrapy.Request]:
        """Discover categories and schedule a random subset of them.

        """
        self.selector = RandomSelector(self.settings.get("RANDOM_SEED"))

        categories = CategoryParser.parse_categories(response)
        if not categories:
            self.logger.error("No categories found on %s", response.url)
            return
        self.logger.info("Discovered %d categories", len(categories))

        count = self.selector.pick_count(
            self.settings.getint("CATEGORY_COUNT_MIN", 5),
            self.settings.getint("CATEGORY_COUNT_MAX", 10),
            len(categories),
        )
        chosen = self.selector.sample(categories, count)
        self.logger.info(
            "Selected %d categories: %s", len(chosen), [c.name for c in chosen]
        )

        for category in chosen:
            yield scrapy.Request(
                category.url,
                callback=self.parse_category,
                errback=self.handle_category_error,
                cb_kwargs={"category_name": category.name, "collected": []},
            )

    
    # Step 2: category pages (with pagination)
   
    def parse_category(
        self, response: Response, category_name: str, collected: List[BookItem]
    ) -> Iterator:
        """Collect books from one category page and follow pagination."""
        category_name = CategoryParser.parse_category_title(response, category_name)
        books = collected + BookListingParser.parse_books(response, category_name)
        self.logger.debug(
            "%s: %d books collected so far (%s)", category_name, len(books), response.url
        )

        next_url = CategoryParser.parse_next_page(response)
        if next_url:
            yield scrapy.Request(
                next_url,
                callback=self.parse_category,
                errback=self.handle_category_error,
                cb_kwargs={"category_name": category_name, "collected": books},
            )
        else:
            yield from self._select_books(category_name, books)

    
    # Error handling
    
    def handle_category_error(self, failure: Failure) -> Iterator[BookItem]:
        """Handle a failed category/pagination request. """
        request = failure.request
        self.logger.error("Request failed: %s -> %s", request.url, failure.value)
        kwargs = request.cb_kwargs or {}
        collected = kwargs.get("collected", [])
        if collected:
            self.logger.warning(
                "Using %d partially collected books for '%s'",
                len(collected),
                kwargs.get("category_name"),
            )
            yield from self._select_books(kwargs["category_name"], collected)

    
    # Helpers
    
    def _select_books(
        self, category_name: str, books: List[BookItem]
    ) -> Iterator[BookItem]:
        """Randomly select books for a category and yield them."""
        per_category = self.settings.getint("BOOKS_PER_CATEGORY", 5)
        selected = self.selector.sample(books, per_category)
        self.logger.info(
            "Category '%s': %d books found, %d selected",
            category_name,
            len(books),
            len(selected),
        )
        yield from selected