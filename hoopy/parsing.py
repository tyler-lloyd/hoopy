"""Helpers for turning basketball-reference HTML tables into plain dicts.

Every stat cell on basketball-reference carries a ``data-stat`` attribute, so
rows are parsed generically: each cell becomes ``{data_stat: value}`` with the
value coerced to int/float where that is unambiguous. This keeps the spiders
working across eras (1950 box scores have far fewer columns than 2025 ones).
"""

import json
import re
from pathlib import Path

BASE_URL = "https://www.basketball-reference.com"

_INT_RE = re.compile(r"^[+-]?\d+$")
_THOUSANDS_RE = re.compile(r"^\d{1,3}(,\d{3})+$")
_FLOAT_RE = re.compile(r"^[+-]?(\d+)?\.\d+$")
_PLAYER_ID_RE = re.compile(r"/players/[a-z]/([a-z0-9]+)\.html")
_TEAM_SEASON_RE = re.compile(r"/teams/([A-Z0-9]+)/(\d{4})\.html")
_BOX_ID_RE = re.compile(r"/boxscores/(\d{8}0[A-Z0-9]{3})\.html")


def clean_value(text):
    """Strip a cell's text and coerce it to int/float when it is clearly numeric.

    ``''`` -> ``None``, ``'.417'`` -> ``0.417``, ``'+23'`` -> ``23``,
    ``'19,156'`` -> ``19156``. Anything else (``'6-6'``, ``'30:31'``, ``'SG'``)
    stays a string.
    """
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    if _INT_RE.match(text):
        return int(text)
    if _THOUSANDS_RE.match(text):
        return int(text.replace(",", ""))
    if _FLOAT_RE.match(text):
        return float(text)
    return text


def cell_text(cell):
    return "".join(cell.xpath(".//text()").getall())


def parse_row(row, skip=()):
    """Return ``{data-stat: value}`` for every ``th``/``td`` cell in a table row."""
    out = {}
    for cell in row.xpath("./th[@data-stat] | ./td[@data-stat]"):
        stat = cell.attrib["data-stat"]
        if stat in skip:
            continue
        out[stat] = clean_value(cell_text(cell))
    return out


def data_rows(table):
    """Body rows of a table, without the repeated header/spacer rows."""
    return table.xpath(
        './tbody/tr[not(contains(concat(" ", @class, " "), " thead "))'
        ' and not(contains(concat(" ", @class, " "), " spacer "))]'
    )


def player_id_from_url(url):
    """``/players/j/jamesle01.html`` -> ``jamesle01`` (``None`` if not a player URL)."""
    match = _PLAYER_ID_RE.search(url or "")
    return match.group(1) if match else None


def player_url(player_id):
    return f"{BASE_URL}/players/{player_id[0]}/{player_id}.html"


def team_season_from_url(url):
    """``/teams/CLE/2004.html`` -> ``('CLE', 2004)`` (``None`` if not a team-season URL)."""
    match = _TEAM_SEASON_RE.search(url or "")
    return (match.group(1), int(match.group(2))) if match else None


def boxscore_id_from_url(url):
    match = _BOX_ID_RE.search(url or "")
    return match.group(1) if match else None


def csk_date(value):
    """``'20011113'`` -> ``'2001-11-13'``."""
    if value and len(value) == 8 and value.isdigit():
        return f"{value[:4]}-{value[4:6]}-{value[6:]}"
    return None


def split_arg(value):
    """Split a comma-separated spider argument (``-a players=a,b``) into a list."""
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [part.strip() for part in str(value).split(",") if part.strip()]


def parse_seasons(value):
    """Parse ``'2004,2010-2012'`` into ``[2004, 2010, 2011, 2012]``.

    Seasons are named by the year they end in, as on basketball-reference
    (``2025`` is the 2024-25 season).
    """
    seasons = []
    for part in split_arg(value):
        if "-" in part:
            start, end = (int(p) for p in part.split("-", 1))
            seasons.extend(range(start, end + 1))
        else:
            seasons.append(int(part))
    return seasons


def player_ids_from_args(players=None, playerlist=None, active=None):
    """Resolve the ``players`` / ``playerlist`` / ``active`` spider arguments to ids.

    ``players`` may hold ids (``jamesle01``) or player URLs. ``playerlist`` is
    the path of a JSON feed written by the ``playerlist`` spider.
    """
    ids = []
    for value in split_arg(players):
        ids.append(player_id_from_url(value) or value)
    if playerlist:
        with Path(playerlist).open(encoding="utf-8") as fh:
            records = json.load(fh)
        only_active = str(active or "").lower() in {"1", "true", "yes"}
        for record in records:
            if only_active and not record.get("is_active"):
                continue
            ids.append(record.get("player_id") or player_id_from_url(record.get("url")))
    # Keep order, drop duplicates/empties.
    return [pid for pid in dict.fromkeys(ids) if pid]


# --------------------------------------------------------------------------- #
# Box scores
# --------------------------------------------------------------------------- #

_PLAYOFF_WORDS = ("Round", "Finals", "Semifinals", "Playoffs", "Division")


def season_type_from_label(label):
    """Classify a box score from the prefix of its ``<h1>``.

    Regular season box scores have no prefix; playoff ones read like
    ``2025 NBA Western Conference First Round Game 1``.
    """
    if not label:
        return "regular"
    if "Play-In" in label:
        return "play-in"
    if "Cup" in label or "In-Season" in label:
        return "regular"
    if any(word in label for word in _PLAYOFF_WORDS):
        return "playoffs"
    return "regular"


def parse_boxscore(response, season=None, player_ids=None):
    """Yield one dict per player per team from a box score page.

    If ``player_ids`` is given, only those players' lines are returned.
    Players who did not play are included with a ``reason`` (e.g.
    ``"Did Not Play"``) and no stats.
    """
    game_id = boxscore_id_from_url(response.url)
    if not game_id:
        return

    title = cell_text(response.xpath("//h1")[0]).strip() if response.xpath("//h1") else ""
    label = title.split(":", 1)[0].strip() if ":" in title else None

    basic_tables = response.xpath(
        '//table[re:test(@id, "^box-[A-Z0-9]+-game-basic$")]',
        namespaces={"re": "http://exslt.org/regular-expressions"},
    )
    teams = [t.attrib["id"].split("-")[1] for t in basic_tables]
    scores = [
        clean_value(s) for s in response.xpath('//div[@class="scorebox"]//div[@class="score"]/text()').getall()
    ]
    if len(teams) != 2:
        return

    game = {
        "game_id": game_id,
        "date": csk_date(game_id[:8]),
        "season": season,
        "season_type": season_type_from_label(label),
        "game_label": label,
    }

    for index, table in enumerate(basic_tables):
        team, opponent = teams[index], teams[1 - index]
        team_pts = scores[index] if len(scores) == 2 else None
        opp_pts = scores[1 - index] if len(scores) == 2 else None
        result = None
        if isinstance(team_pts, int) and isinstance(opp_pts, int):
            result = "W" if team_pts > opp_pts else "L"

        advanced = {}
        adv_table = response.xpath(f'//table[@id="box-{team}-game-advanced"]')
        if adv_table:
            for row in data_rows(adv_table[0]):
                pid = row.xpath("./th/@data-append-csv").get()
                if pid:
                    advanced[pid] = parse_row(row, skip=("player", "mp", "reason"))

        has_split = bool(table.xpath('./tbody/tr[contains(concat(" ", @class, " "), " thead ")]'))
        starter = True if has_split else None
        for row in table.xpath("./tbody/tr"):
            if "thead" in (row.attrib.get("class") or "").split():
                starter = False
                continue
            pid = row.xpath("./th/@data-append-csv").get()
            if not pid or (player_ids and pid not in player_ids):
                continue

            stats = parse_row(row, skip=("player",))
            reason = stats.pop("reason", None)
            minutes_csk = row.xpath('./td[@data-stat="mp"]/@csk').get()

            line = {
                **game,
                "team": team,
                "opponent": opponent,
                "is_home": game_id.endswith(team),
                "team_pts": team_pts,
                "opp_pts": opp_pts,
                "result": result,
                "player_id": pid,
                "player": cell_text(row.xpath("./th")[0]).strip(),
                "starter": starter,
                "reason": reason,
                "seconds_played": int(minutes_csk) if minutes_csk and minutes_csk.isdigit() else None,
            }
            line.update(stats)
            line.update(advanced.get(pid, {}))
            yield line
