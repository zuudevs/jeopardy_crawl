from bs4 import BeautifulSoup
from pathlib import Path
from urllib3 import PoolManager
import pandas as pd

http = PoolManager()

OUT_DIR = Path(__file__).resolve().parent / 'raw'
TARGET_SEASON = 22
TARGET_URL = f"https://www.j-archive.com/showseason.php?season={TARGET_SEASON}"

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

def main():
    if not OUT_DIR.exists():
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        
    html = request_handler(TARGET_URL)
    scan_result = scan_game_id(html)
    
    if scan_result:
        df = pd.DataFrame({'game_id': scan_result})
        df.to_csv(OUT_DIR / 'jeopardy_game_id.csv', index=False)

if __name__ == '__main__':
    main()