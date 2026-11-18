import json

import pytest

from hoopy.parsing import (
    clean_value,
    csk_date,
    parse_boxscore,
    parse_seasons,
    player_id_from_url,
    player_ids_from_args,
    season_type_from_label,
    team_season_from_url,
)

BR = "https://www.basketball-reference.com"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", None),
        ("   ", None),
        (None, None),
        ("42", 42),
        ("+23", 23),
        ("-7", -7),
        (".417", 0.417),
        ("19.5", 19.5),
        ("19,156", 19156),
        ("30:31", "30:31"),
        ("6-6", "6-6"),
        ("SG", "SG"),
        ("2003-04", "2003-04"),
    ],
)
def test_clean_value(text, expected):
    assert clean_value(text) == expected


def test_url_helpers():
    assert player_id_from_url("/players/j/jamesle01.html") == "jamesle01"
    assert player_id_from_url(f"{BR}/players/j/jamesle01.html") == "jamesle01"
    assert player_id_from_url("/teams/CLE/2004.html") is None
    assert team_season_from_url("/teams/CLE/2004.html") == ("CLE", 2004)
    assert team_season_from_url("/leagues/NBA_2004.html") is None
    assert csk_date("20011113") == "2001-11-13"
    assert csk_date("") is None


def test_parse_seasons():
    assert parse_seasons("2004, 2010-2012") == [2004, 2010, 2011, 2012]
    assert parse_seasons(None) == []


def test_player_ids_from_args(tmp_path):
    playerlist = tmp_path / "players.json"
    playerlist.write_text(json.dumps([
        {"player_id": "jamesle01", "is_active": True},
        {"player_id": "jordami01", "is_active": False},
        {"url": "/players/c/curryst01.html", "is_active": True},  # pre-2026 format
    ]))
    assert player_ids_from_args("jamesle01, /players/h/hardeja01.html") == ["jamesle01", "hardeja01"]
    assert player_ids_from_args(playerlist=str(playerlist)) == ["jamesle01", "jordami01", "curryst01"]
    assert player_ids_from_args("jamesle01", str(playerlist), active="1") == ["jamesle01", "curryst01"]


@pytest.mark.parametrize(
    ("label", "expected"),
    [
        (None, "regular"),
        ("2025 NBA Western Conference First Round Game 1", "playoffs"),
        ("2016 NBA Finals Game 7", "playoffs"),
        ("1977 ABA Semifinals Game 2", "playoffs"),
        ("2025 NBA Play-In Tournament", "play-in"),
        ("2024 NBA Cup Championship", "regular"),
    ],
)
def test_season_type_from_label(label, expected):
    assert season_type_from_label(label) == expected


def test_parse_boxscore_modern(page):
    response = page("boxscore_202410220BOS.html", f"{BR}/boxscores/202410220BOS.html")
    lines = list(parse_boxscore(response, season=2025))

    assert {line["team"] for line in lines} == {"NYK", "BOS"}
    assert len(lines) == 12 + 13  # each tbody also has a "Reserves" header row

    holiday = next(line for line in lines if line["player_id"] == "holidjr01")
    assert holiday == {
        **holiday,
        "game_id": "202410220BOS",
        "date": "2024-10-22",
        "season": 2025,
        "season_type": "regular",
        "game_label": None,
        "team": "BOS",
        "opponent": "NYK",
        "is_home": True,
        "team_pts": 132,
        "opp_pts": 109,
        "result": "W",
        "player": "Jrue Holiday",
        "starter": True,
        "reason": None,
        "mp": "30:31",
        "seconds_played": 1831,
        "fg": 7,
        "fga": 9,
        "fg_pct": 0.778,
        "ft_pct": None,
        "pts": 18,
        "plus_minus": 23,
    }
    # Advanced box score stats are merged into the same line.
    assert isinstance(holiday["ts_pct"], float)
    assert "bpm" in holiday

    knicks = [line for line in lines if line["team"] == "NYK"]
    assert all(line["result"] == "L" and not line["is_home"] for line in knicks)
    assert sum(line["starter"] for line in knicks) == 5

    dnp = next(line for line in lines if line["player_id"] == "sprinja01")
    assert dnp["reason"] == "Did Not Play"
    assert dnp["starter"] is False
    assert "pts" not in dnp


def test_parse_boxscore_filters_players(page):
    response = page("boxscore_202410220BOS.html", f"{BR}/boxscores/202410220BOS.html")
    lines = list(parse_boxscore(response, player_ids={"holidjr01"}))
    assert [line["player_id"] for line in lines] == ["holidjr01"]


def test_parse_boxscore_playoffs(page):
    response = page("boxscore_202504190LAL.html", f"{BR}/boxscores/202504190LAL.html")
    lines = list(parse_boxscore(response))
    assert lines
    assert {line["season_type"] for line in lines} == {"playoffs"}
    assert lines[0]["game_label"] == "2025 NBA Western Conference First Round Game 1"
    assert {(line["team"], line["result"]) for line in lines} == {("MIN", "W"), ("LAL", "L")}


def test_parse_boxscore_1950(page):
    """Early box scores have no minutes, rebounds, starters or advanced stats."""
    response = page("boxscore_195011010BLB.html", f"{BR}/boxscores/195011010BLB.html")
    lines = list(parse_boxscore(response))
    mikan = next(line for line in lines if line["player_id"] == "mikange01")
    assert mikan["team"] == "MNL"
    assert mikan["is_home"] is False
    assert mikan["pts"] == 34
    assert mikan["mp"] is None
    assert mikan["seconds_played"] is None
    assert mikan["starter"] is None
    assert (mikan["team_pts"], mikan["opp_pts"], mikan["result"]) == (71, 81, "L")
