import string

import scrapy

from hoopy.parsing import BASE_URL, cell_text, clean_value, csk_date, data_rows


class PlayerListSpider(scrapy.Spider):
    """Every player listed in basketball-reference's player index (/players/a/ ... /players/z/).

    Usage::

        scrapy crawl playerlist -O data/playerlist.json
    """

    name = "playerlist"

    async def start(self):
        for letter in string.ascii_lowercase:
            yield scrapy.Request(f"{BASE_URL}/players/{letter}/", callback=self.parse)

    def parse(self, response):
        table = response.xpath('//table[@id="players"]')
        if not table:
            return
        for row in data_rows(table[0]):
            name_cell = row.xpath('./th[@data-stat="player"]')
            if not name_cell:
                continue
            name_cell = name_cell[0]
            url = name_cell.xpath(".//a/@href").get()
            colleges = [c.strip() for c in row.xpath('./td[@data-stat="colleges"]/a/text()').getall()]

            yield {
                "player_id": name_cell.attrib.get("data-append-csv"),
                "player": name_cell.xpath(".//a/text()").get(),
                "start_year": clean_value(cell_text(row.xpath('./td[@data-stat="year_min"]')[0])),
                "end_year": clean_value(cell_text(row.xpath('./td[@data-stat="year_max"]')[0])),
                "position": clean_value(cell_text(row.xpath('./td[@data-stat="pos"]')[0])),
                "height": clean_value(cell_text(row.xpath('./td[@data-stat="height"]')[0])),
                "weight": clean_value(cell_text(row.xpath('./td[@data-stat="weight"]')[0])),
                "birth_date": csk_date(row.xpath('./td[@data-stat="birth_date"]/@csk').get()),
                "colleges": colleges,
                # Active players are bolded in the index; Hall of Famers get a trailing '*'.
                "is_active": bool(name_cell.xpath("./strong")),
                "hall_of_fame": cell_text(name_cell).strip().endswith("*"),
                "url": response.urljoin(url) if url else None,
            }
