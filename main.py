import re

from bs4 import BeautifulSoup
from pathlib import Path
from urllib3 import PoolManager
import pandas as pd

http = PoolManager()

OUT_DIR = Path(__file__).resolve().parent / 'raw'
SEASON = 22
ARCHIVE_URL = f"https://www.j-archive.com/showseason.php?season={SEASON}"
ROUNDS = ["Jeopardy!", "Double Jeopardy!"]
JSON_SCHEMA = {
    "show_number": None,
    "air_date": None,
    "round": None,
    "category": None,
    "value": None,
    "question": None,
    "answer": None,
    "external_links": None
}
MONTHS_TABLE = { 
    month : idx for idx, month in enumerate(
        iterable=[
            'January',
            'February',
            'March',
            'April',
            'May',
            'June',
            'July',
            'August',
            'September',
            'October',
            'November',
            'December'
        ],
        start=1
    )
}

def get_show_url(game_id: int) -> str:
    return f"https://www.j-archive.com/showgame.php?game_id={game_id}"

def request_handler(target_url: str) -> str | None:
    response = http.request('GET', target_url)
 
    if response.status == 200:
        return response.data.decode('utf-8')
    return None

def scan_game_id(html: str) -> list[int] | None:
    parser = BeautifulSoup(html, 'html.parser')
    links = parser.select('table tr td:nth-child(1) a')
    game_ids = []
    for link in links:
        href = link.get('href', '')
        target_param = 'game_id='
        if target_param in href:
            id_str = href.split(target_param)[-1]
            
            if id_str.isdigit():
                game_ids.append(int(id_str))
                
    return game_ids if game_ids else None

def scan_show(html: str) -> dict:
    parser = BeautifulSoup(html, 'html.parser')
    show_data = JSON_SCHEMA
    
    def parse_date(text: str):
        pattern = r'\w+\s\#\d+\s-\s\w+\,\s(\w+)\s(\d{2})\,\s(\d{4})'
        matched = re.search(pattern, text)
        if matched:
            return f"{matched.group(2)}-{MONTHS_TABLE[matched.group(1)]:02}-{matched.group(3)}"
        return None
    # TODO: Parse round
    # TODO: Parse category
    # TODO: Parse value / bounty
    # TODO: Parse question
    # TODO: Parse answer
    # TODO: Parse external_links
    aired_date = parse_date(parser.find('h1').text)

def main():
    if not OUT_DIR.exists():
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        
    html = request_handler(ARCHIVE_URL)
    scan_result = scan_game_id(html)
    html = request_handler(get_show_url(487))
    show_result = scan_show(html)
    
    if scan_result:
        df = pd.DataFrame({'game_id': scan_result})
        df.to_csv(OUT_DIR / 'jeopardy_game_id.csv', index=False)

if __name__ == '__main__':
    main()