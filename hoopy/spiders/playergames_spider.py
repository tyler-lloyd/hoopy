import scrapy

from hoopy.parsing import (
    BASE_URL,
    boxscore_id_from_url,
    parse_boxscore,
    parse_seasons,
    player_id_from_url,
    player_ids_from_args,
    player_url,
    team_season_from_url,
)


class PlayerGameSpider(scrapy.Spider):
    """Game-by-game logs for one or more players.

    basketball-reference's own game log pages (``/players/.../gamelog/``) are
    disallowed by its robots.txt, so the logs are built from box scores
    instead: player page -> each team/season the player appeared for -> that
    team's schedule -> each box score -> the player's line.

    One item per game the player was on the roster for, including games they
    sat out (``reason`` is set and the stat fields are absent).

    Usage::

        scrapy crawl playergames -a players=jamesle01 -a seasons=2004,2012 -O lebron.json
        scrapy crawl playergames -a players=curryst01 -a seasons=2015-2017 -O steph.json
    """

    name = "playergames"

    def __init__(self, players=None, playerlist=None, active=None, seasons=None, **kwargs):
        super().__init__(**kwargs)
        self.player_ids = player_ids_from_args(players, playerlist, active)
        if not self.player_ids:
            raise ValueError("pass -a players=<id>[,<id>...] or -a playerlist=<path to playerlist JSON>")
        self.seasons = set(parse_seasons(seasons))
        # Teammates share team schedules and box scores, so these requests use
        # dont_filter and are de-duplicated per player here instead.
        self._seen = set()

    async def start(self):
        for pid in self.player_ids:
            yield scrapy.Request(player_url(pid), callback=self.parse)

    def _once(self, *key):
        if key in self._seen:
            return False
        self._seen.add(key)
        return True

    def parse(self, response):
        pid = player_id_from_url(response.url)
        team_links = response.xpath(
            '//table[@id="per_game_stats" or @id="per_game_stats_post"]'
            '/tbody/tr/td[@data-stat="team_name_abbr"]/a/@href'
        ).getall()
        for link in team_links:
            team_season = team_season_from_url(link)
            if not team_season:
                continue
            team, season = team_season
            if self.seasons and season not in self.seasons:
                continue
            if not self._once("team", pid, team, season):
                continue
            yield scrapy.Request(
                f"{BASE_URL}/teams/{team}/{season}_games.html",
                callback=self.parse_team_games,
                cb_kwargs={"player_id": pid, "season": season},
                dont_filter=True,
            )

    def parse_team_games(self, response, player_id, season):
        # Regular season ("games") and, if the team made it, playoffs ("games_playoffs").
        links = response.xpath(
            '//table[starts-with(@id, "games")]/tbody/tr/td[@data-stat="box_score_text"]/a/@href'
        ).getall()
        for link in links:
            game_id = boxscore_id_from_url(link)
            if not game_id or not self._once("game", player_id, game_id):
                continue
            yield response.follow(
                link,
                callback=self.parse_boxscore,
                cb_kwargs={"player_id": player_id, "season": season},
                dont_filter=True,
            )

    def parse_boxscore(self, response, player_id, season):
        yield from parse_boxscore(response, season=season, player_ids={player_id})
