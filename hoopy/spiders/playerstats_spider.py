import scrapy

from hoopy.parsing import (
    cell_text,
    data_rows,
    parse_row,
    player_id_from_url,
    player_ids_from_args,
    player_url,
    team_season_from_url,
)

# (table id, season type). Tables are merged row-by-row into one item per season/team.
TABLES = {
    "regular": ("per_game_stats", "totals_stats", "advanced"),
    "playoffs": ("per_game_stats_post", "totals_stats_post", "advanced_post"),
}


class PlayerStatsSpider(scrapy.Spider):
    """Season-by-season stats (per game, totals and advanced) from player pages.

    One item per player, season, team and season type. Players traded mid-season
    get a combined row (``team`` like ``"2TM"``, ``partial`` false) plus one row
    per team (``partial`` true), as on the site.

    Usage::

        scrapy crawl playerstats -a players=jamesle01,hardeja01 -O stats.json
        scrapy crawl playerstats -a playerlist=data/playerlist.json -a active=1 -O stats.json
    """

    name = "playerstats"

    def __init__(self, players=None, playerlist=None, active=None, **kwargs):
        super().__init__(**kwargs)
        self.player_ids = player_ids_from_args(players, playerlist, active)
        if not self.player_ids:
            raise ValueError("pass -a players=<id>[,<id>...] or -a playerlist=<path to playerlist JSON>")

    async def start(self):
        for pid in self.player_ids:
            yield scrapy.Request(player_url(pid), callback=self.parse)

    def parse(self, response):
        pid = player_id_from_url(response.url)
        name = cell_text(response.xpath("//h1")[0]).strip() if response.xpath("//h1") else None

        for season_type, table_ids in TABLES.items():
            merged = {}
            for table_id in table_ids:
                table = response.xpath(f'//table[@id="{table_id}"]')
                if not table:
                    continue
                for position, row in enumerate(data_rows(table[0])):
                    stats = parse_row(row)
                    season = row.xpath('./th[@data-stat="year_id"]/@csk').get()
                    # The tables list the same rows in the same order; season and
                    # team are part of the key so a mismatch can't silently merge.
                    key = (position, season, stats.get("team_name_abbr"))
                    item = merged.setdefault(key, {
                        "player_id": pid,
                        "player": name,
                        "season": int(season) if season and season.isdigit() else None,
                        "season_type": season_type,
                        "partial": "partial_table" in (row.attrib.get("class") or ""),
                    })
                    team_link = row.xpath('./td[@data-stat="team_name_abbr"]/a/@href').get()
                    if team_link and team_season_from_url(team_link):
                        item["team_url"] = response.urljoin(team_link)
                    item.update(stats)

            for item in merged.values():
                item["season_label"] = item.pop("year_id", None)
                item["team"] = item.pop("team_name_abbr", None)
                item["league"] = item.pop("comp_name_abbr", None)
                yield item
