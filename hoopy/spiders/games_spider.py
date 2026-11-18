import scrapy

from hoopy.parsing import BASE_URL, parse_boxscore, parse_seasons, split_arg


class GamesSpider(scrapy.Spider):
    """Every player's box score line for every game in one or more seasons.

    League schedule -> month pages -> box scores. A full NBA season is ~1,300
    box scores, which takes well over an hour at the site's allowed request
    rate (see README).

    Usage::

        scrapy crawl games -a seasons=2025 -O games-2025.json
        scrapy crawl games -a seasons=2025 -a months=october,november -O fall-2024.json
        scrapy crawl games -a seasons=1972 -a league=ABA -O aba-1972.json
    """

    name = "games"

    def __init__(self, seasons=None, months=None, league="NBA", **kwargs):
        super().__init__(**kwargs)
        self.seasons = parse_seasons(seasons)
        if not self.seasons:
            raise ValueError("pass -a seasons=<year>[,<year>...] (2025 = the 2024-25 season)")
        self.months = {m.lower() for m in split_arg(months)}
        self.league = league

    async def start(self):
        for season in self.seasons:
            yield scrapy.Request(
                f"{BASE_URL}/leagues/{self.league}_{season}_games.html",
                callback=self.parse,
                cb_kwargs={"season": season},
            )

    def parse(self, response, season):
        month_links = response.xpath('//div[contains(@class, "filter")]//a/@href').getall()
        if not month_links:
            # Some older seasons fit on a single page with no month filter.
            yield from self.parse_month(response, season)
            return
        for link in month_links:
            month = link.rsplit("-", 1)[-1].removesuffix(".html")
            if self.months and month not in self.months:
                continue
            yield response.follow(link, callback=self.parse_month, cb_kwargs={"season": season})

    def parse_month(self, response, season):
        # Games that haven't been played yet have no box score link and are skipped.
        for link in response.xpath(
            '//table[@id="schedule"]/tbody/tr/td[@data-stat="box_score_text"]/a/@href'
        ).getall():
            yield response.follow(link, callback=self.parse_boxscore, cb_kwargs={"season": season})

    def parse_boxscore(self, response, season):
        yield from parse_boxscore(response, season=season)
