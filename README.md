# hoopy

[Scrapy](https://scrapy.org) spiders that collect NBA player and game stats from
[basketball-reference.com](https://www.basketball-reference.com).

| Spider        | What it collects                                                      | One item per                          |
|---------------|-----------------------------------------------------------------------|---------------------------------------|
| `playerlist`  | Every player in the site's player index                               | player                                |
| `playerstats` | Season stats from player pages: per game, totals and advanced         | player × season × team × season type  |
| `playergames` | Game logs for specific players, built from box scores                 | player × game                         |
| `games`       | Every player's box score line for whole seasons                       | player × game                         |

## Setup

Requires Python 3.10+.

```sh
python -m venv .venv
source .venv/bin/activate        # fish: source .venv/bin/activate.fish
pip install -e '.[dev]'
```

## Usage

Run from the project root. `-O file.json` writes a JSON array (use `.jsonl` or
`.csv` for other formats). Seasons are named by the year they end in, as on
basketball-reference: `2025` is the 2024-25 season.

```sh
# All players (~5,500 players, 26 requests, about 2 minutes)
scrapy crawl playerlist -O data/playerlist.json

# Career season-by-season stats
scrapy crawl playerstats -a players=jamesle01,hardeja01 -O stats.json
scrapy crawl playerstats -a playerlist=data/playerlist.json -a active=1 -O active-stats.json

# Game logs: one or more players, optionally limited to some seasons
scrapy crawl playergames -a players=jamesle01 -a seasons=2004 -O lebron-rookie.json
scrapy crawl playergames -a players=curryst01 -a seasons=2015-2017 -O steph.json

# Every game in a season (or just some months of it)
scrapy crawl games -a seasons=2025 -O games-2025.json
scrapy crawl games -a seasons=2025 -a months=october,november -O fall-2024.json
scrapy crawl games -a seasons=1972 -a league=ABA -O aba-1972.json
```

Player ids are the slugs in player URLs (`/players/j/jamesle01.html` → `jamesle01`);
`data/playerlist.json` has all of them.

### Output fields

Columns are taken from each table's `data-stat` attributes, so names match the
site's CSV exports (`fg`, `fga`, `fg3_pct`, `trb`, `ts_pct`, `bpm`, …). Numbers
are converted to ints/floats and blank cells become `null`. Older seasons have
fewer columns (no minutes, rebounds or advanced stats in early box scores).

**`playergames` / `games`**: `game_id`, `date`, `season`, `season_type`
(`regular`, `playoffs` or `play-in`), `game_label` (e.g. `2016 NBA Finals Game 7`),
`team`, `opponent`, `is_home`, `team_pts`, `opp_pts`, `result`, `player_id`,
`player`, `starter`, `reason`, `mp` (`"MM:SS"`), `seconds_played`, then the basic
and advanced box score stats. Players who were on the roster but didn't play are
included with `reason` set (`"Did Not Play"`, `"Inactive"`, …) and no stats.

**`playerstats`**: `player_id`, `player`, `season`, `season_label`, `season_type`,
`team`, `league`, `partial`, `team_url`, `age`, `pos`, `games`, `games_started`, then
per-game (`*_per_g`), totals and advanced columns. A player traded mid-season has a
combined row (`team` like `"2TM"`, no `team_url`) plus one row per team
(`partial: true`), the same as on the site.

**`playerlist`**: `player_id`, `player`, `start_year`, `end_year`, `position`,
`height`, `weight`, `birth_date` (ISO), `colleges`, `is_active`, `hall_of_fame`, `url`.

## Crawling politely

Sports Reference [limits bots](https://www.sports-reference.com/bot-traffic.html)
to about 20 requests a minute and blocks clients that go faster. The site's
`robots.txt` asks for a 3-second crawl delay. The settings in `hoopy/settings.py`
follow both:

- one request at a time, 3-5 seconds apart
- `robots.txt` is obeyed
- an HTTP 429 response stops the crawl straight away instead of retrying
- pages are cached in `.scrapy/httpcache` for 24 hours, so re-runs and spiders
  that share pages don't download them again (`-s HTTPCACHE_ENABLED=0` to bypass)

That makes big crawls slow: a full season with `games` is ~1,300 box scores, about
1.5 hours. A player's career with `playergames` is roughly one request per game.
Long crawls can be paused and resumed with
`-s JOBDIR=.scrapy/jobs/<name>` (stop with a single Ctrl-C, then run the same
command again).

Please don't lower the delay. Also read Sports Reference's
[data use terms](https://www.sports-reference.com/data_use.html) before
publishing anything built on this data.

### Why game logs come from box scores

The site's own game log pages (`/players/<x>/<id>/gamelog/<season>/`) are now
disallowed by `robots.txt`. `playergames` builds the same logs from pages that
are allowed: player page → each team/season the player appeared for → that
team's schedule → each box score.

## Tests

```sh
pytest
```

The tests run offline against trimmed copies of real pages in `tests/fixtures/`.
If the site changes its markup and a spider starts returning nothing, save a fresh
copy of the page, trim it, and update the fixture and tests.
