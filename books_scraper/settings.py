"""Scrapy settings for the books_scraper project."""

BOT_NAME = "books_scraper"

SPIDER_MODULES = ["books_scraper.spiders"]
NEWSPIDER_MODULE = "books_scraper.spiders"

# --- Crawling behaviour ----------------------------------------------
ROBOTSTXT_OBEY = True
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
CONCURRENT_REQUESTS = 8
DOWNLOAD_DELAY = 0.25
DOWNLOAD_TIMEOUT = 15
COOKIES_ENABLED = False

RETRY_ENABLED = True
RETRY_TIMES = 3

AUTOTHROTTLE_ENABLED = True

# --- Logging ----------------------------------------------------------
LOG_LEVEL = "INFO"

# --- Project specific settings ---------------------------------------
CATEGORY_COUNT_MIN = 5       # minimum number of categories to crawl
CATEGORY_COUNT_MAX = 10      # maximum number of categories to crawl
BOOKS_PER_CATEGORY = 5       # books selected from each category
RANDOM_SEED = None           # set an int for a reproducible crawl

# Use the modern, future-proof default
FEED_EXPORT_ENCODING = "utf-8"