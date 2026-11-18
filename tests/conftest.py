from pathlib import Path

import pytest
from scrapy.http import HtmlResponse, Request

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def page():
    """Build a Scrapy response from a saved fixture, as if fetched from ``url``."""

    def _page(name, url):
        return HtmlResponse(
            url=url,
            body=(FIXTURES / name).read_bytes(),
            encoding="utf-8",
            request=Request(url),
        )

    return _page
