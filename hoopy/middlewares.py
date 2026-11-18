import logging

from scrapy.exceptions import IgnoreRequest
from scrapy.utils.defer import deferred_from_coro

logger = logging.getLogger(__name__)


class StopOnRateLimitMiddleware:
    """Stop the crawl as soon as the site answers 429 Too Many Requests.

    Sports Reference blocks clients that exceed its rate limit for a while
    (an hour, per their docs), and every further request extends the block.
    Retrying is pointless, so close the spider instead.
    """

    def __init__(self, crawler):
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_response(self, request, response, spider=None):
        if response.status != 429:
            return response
        logger.error(
            "Rate limited (HTTP 429) on %s (Retry-After: %s). Stopping the crawl; "
            "wait before trying again, and consider raising DOWNLOAD_DELAY.",
            request.url,
            response.headers.get("Retry-After", b"?").decode(errors="replace"),
        )
        # "fast" drops requests already queued in the downloader instead of
        # sending them to a site that is currently blocking us.
        deferred_from_coro(
            self.crawler.engine.close_spider_async(reason="rate_limited", mode="fast", error=True)
        )
        raise IgnoreRequest("rate limited")
