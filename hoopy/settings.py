# Scrapy settings for hoopy.
# https://docs.scrapy.org/en/latest/topics/settings.html

BOT_NAME = "hoopy"

SPIDER_MODULES = ["hoopy.spiders"]
NEWSPIDER_MODULE = "hoopy.spiders"

# --- Being a good citizen ---------------------------------------------------
# basketball-reference.com's robots.txt asks for "Crawl-delay: 3", and Sports
# Reference blocks clients that make more than ~20 requests a minute. One
# request at a time, 3-5 seconds apart, stays under both.
ROBOTSTXT_OBEY = True
CONCURRENT_REQUESTS_PER_DOMAIN = 1
DOWNLOAD_DELAY = 4
DOWNLOAD_DELAY_JITTER = 0.25  # actual delay is 3-5 seconds

# A 429 means we're being blocked; retrying only makes it worse.
RETRY_HTTP_CODES = [408, 500, 502, 503, 504, 522, 524]
DOWNLOADER_MIDDLEWARES = {
    "hoopy.middlewares.StopOnRateLimitMiddleware": 560,
}

# Cache pages locally (in .scrapy/httpcache) so re-running a spider, or several
# spiders that share pages, doesn't hit the site again. Cached pages skip the
# download delay. Entries expire after a day so current-season data stays fresh;
# pass -s HTTPCACHE_ENABLED=0 to bypass the cache entirely.
HTTPCACHE_ENABLED = True
HTTPCACHE_EXPIRATION_SECS = 24 * 60 * 60
HTTPCACHE_DIR = "httpcache"
HTTPCACHE_IGNORE_HTTP_CODES = [429, 500, 502, 503, 504]

# --- Output -------------------------------------------------------------------
FEED_EXPORT_ENCODING = "utf-8"
