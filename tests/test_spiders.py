import asyncio

import pytest
from scrapy import Request

from hoopy.spiders.games_spider import GamesSpider
from hoopy.spiders.playergames_spider import PlayerGameSpider
from hoopy.spiders.playerlist_spider import PlayerListSpider
from hoopy.spiders.playerstats_spider import PlayerStatsSpider

BR = "https://www.basketball-reference.com"


def collect_start(spider):
    async def run():
        return [request async for request in spider.start()]

    return asyncio.run(run())


def test_playerlist_start_covers_alphabet():
    urls = [r.url for r in collect_start(PlayerListSpider())]
    assert len(urls) == 26
    assert urls[0] == f"{BR}/players/a/"
    assert urls[-1] == f"{BR}/players/z/"


def test_playerlist_parse(page):
    items = list(PlayerListSpider().parse(page("players_j.html", f"{BR}/players/j/")))
    by_id = {item["player_id"]: item for item in items}

    assert by_id["jabalwa01"] == {
        "player_id": "jabalwa01",
        "player": "Warren Jabali",
        "start_year": 1969,
        "end_year": 1975,
        "position": "G-F",
        "height": "6-2",
        "weight": 200,
        "birth_date": "1946-08-29",
        "colleges": ["Wichita State"],
        "is_active": False,
        "hall_of_fame": False,
        "url": f"{BR}/players/j/jabalwa01.html",
    }
    assert by_id["jacksan01"]["is_active"] is True
    assert by_id["jacksph01"]["hall_of_fame"] is True
    assert by_id["jacksph01"]["player"] == "Phil Jackson"
    assert any(len(item["colleges"]) > 1 for item in items)


def test_playerstats_requires_players():
    with pytest.raises(ValueError):
        PlayerStatsSpider()


def test_playerstats_parse(page):
    spider = PlayerStatsSpider(players="hardeja01")
    response = page("player_hardeja01.html", f"{BR}/players/h/hardeja01.html")
    items = list(spider.parse(response))

    regular = [i for i in items if i["season_type"] == "regular"]
    playoffs = [i for i in items if i["season_type"] == "playoffs"]
    assert [(i["season"], i["team"], i["partial"]) for i in regular] == [
        (2019, "HOU", False),
        (2020, "HOU", False),
        (2021, "2TM", False),
        (2021, "HOU", True),
        (2021, "BRK", True),
    ]
    assert playoffs and all(i["team"] in {"HOU", "BRK"} for i in playoffs)

    season = regular[0]
    assert season["player"] == "James Harden"
    assert season["season_label"] == "2018-19"
    assert season["league"] == "NBA"
    assert season["team_url"] == f"{BR}/teams/HOU/2019.html"
    # Per-game, totals and advanced columns are all present on one item.
    assert season["pts_per_g"] == pytest.approx(36.1)
    assert season["pts"] == 2818
    assert isinstance(season["per"], float)
    assert "team_url" not in regular[2]  # the 2TM row has no single team


def test_playergames_flow(page):
    spider = PlayerGameSpider(players="hardeja01", seasons="2021")

    team_requests = list(spider.parse(page("player_hardeja01.html", f"{BR}/players/h/hardeja01.html")))
    assert sorted(r.url for r in team_requests) == [
        f"{BR}/teams/BRK/2021_games.html",
        f"{BR}/teams/HOU/2021_games.html",
    ]
    assert all(r.cb_kwargs == {"player_id": "hardeja01", "season": 2021} for r in team_requests)

    box_requests = list(spider.parse_team_games(
        page("team_CLE_2004_games.html", f"{BR}/teams/CLE/2004_games.html"),
        player_id="jamesle01",
        season=2004,
    ))
    assert [r.url for r in box_requests] == [
        f"{BR}/boxscores/200310290SAC.html",
        f"{BR}/boxscores/200310300PHO.html",
        f"{BR}/boxscores/200311010POR.html",
    ]
    # Requesting the same team page again for the same player is a no-op...
    again = spider.parse_team_games(
        page("team_CLE_2004_games.html", f"{BR}/teams/CLE/2004_games.html"),
        player_id="jamesle01",
        season=2004,
    )
    assert list(again) == []
    # ...but a teammate still gets their own requests.
    teammate = spider.parse_team_games(
        page("team_CLE_2004_games.html", f"{BR}/teams/CLE/2004_games.html"),
        player_id="ilgauzy01",
        season=2004,
    )
    assert len(list(teammate)) == 3

    lines = list(spider.parse_boxscore(
        page("boxscore_202410220BOS.html", f"{BR}/boxscores/202410220BOS.html"),
        player_id="holidjr01",
        season=2025,
    ))
    assert len(lines) == 1 and lines[0]["pts"] == 18


def test_games_requires_seasons():
    with pytest.raises(ValueError):
        GamesSpider()


def test_games_flow(page):
    spider = GamesSpider(seasons="2025", months="october,november")
    [start] = collect_start(spider)
    assert start.url == f"{BR}/leagues/NBA_2025_games.html"

    schedule = page("schedule_NBA_2025_october.html", f"{BR}/leagues/NBA_2025_games.html")
    months = [r.url for r in spider.parse(schedule, season=2025)]
    assert months == [
        f"{BR}/leagues/NBA_2025_games-october.html",
        f"{BR}/leagues/NBA_2025_games-november.html",
    ]

    boxes = list(spider.parse_month(schedule, season=2025))
    assert all(isinstance(r, Request) for r in boxes)
    assert boxes[0].url == f"{BR}/boxscores/202410220BOS.html"
    assert len(boxes) == 3

    lines = list(spider.parse_boxscore(
        page("boxscore_202410220BOS.html", f"{BR}/boxscores/202410220BOS.html"), season=2025
    ))
    assert len(lines) == 25
