

import scrapy


class BookItem(scrapy.Item):
    """Data model describing a single scraped book."""

    title = scrapy.Field()
    price = scrapy.Field()
    availability = scrapy.Field()
    product_url = scrapy.Field()
    image_url = scrapy.Field()
    category = scrapy.Field()