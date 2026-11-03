from bs4 import BeautifulSoup
from pathlib import Path
from urllib3 import PoolManager
import time
import re
import json

http = PoolManager()
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}
OUT_DIR = Path(__file__).resolve().parent / 'raw'
ARCHIVE_URL = 'https://www.j-archive.com/listseasons.php'

MONTHS_TABLE = { 
    month : idx for idx, month in enumerate(
        iterable=[
            'January', 'February', 'March', 'April', 'May', 'June',
            'July', 'August', 'September', 'October', 'November', 'December'
        ],
        start=1
    )
}

def get_show_url(game_id: int) -> str:
    return f"https://www.j-archive.com/showgame.php?game_id={game_id}"

def get_archive_url(season: str) -> str:
    return f"https://www.j-archive.com/showseason.php?season={season}"

def request_handler(target_url: str) -> str | None:
    response = http.request('GET', target_url, headers=HEADERS)
    if response.status == 200:
        return response.data.decode('utf-8')
    return None

def scan_season(html: str) -> list[str] | None:
    parser = BeautifulSoup(html, 'html.parser')
    rows = parser.select('table tr')
    
    season_data = []
    
    for row in rows:
        link = row.select_one('td:nth-child(1) a')
        date_col = row.select_one('.left_padded')
        
        if link and date_col:
            href = link.get('href', '')
            if 'season=' in href:
                season = href.split('season=')[-1]
                
                pattern = r'(\d{4})-(\d{2})-(\d{2})\sto\s(\d{4})-(\d{2})-(\d{2})'
                matched = re.search(pattern, date_col.text)
                
                if matched:
                    end_date = f"{matched.group(4)}-{matched.group(5)}-{matched.group(6)}"
                    season_data.append({
                        'season': season,
                        'end_date': end_date
                    })

    if not season_data:
        return None

    latest_end_date = max([s['end_date'] for s in season_data])
    filtered_seasons = [s['season'] for s in season_data if s['end_date'] != latest_end_date]
    
    return filtered_seasons

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

def scan_show(html: str) -> list[dict]:
    parser = BeautifulSoup(html, 'html.parser')
    all_clues = []
    
    header = parser.find('h1')
    header_text = header.text if header else ""
    
    pattern = r'Show\s#(\d+)\s-\s\w+,\s(\w+)\s(\d+),\s(\d{4})'
    matched = re.search(pattern, header_text)
    
    if matched:
        show_number = int(matched.group(1))
        month_idx = MONTHS_TABLE.get(matched.group(2), 1)
        day = int(matched.group(3))
        year = matched.group(4)
        air_date = f"{year}-{month_idx:02d}-{day:02d}"
    else:
        show_number = 0
        air_date = "1970-01-01"

    rounds_info = [
        ('Jeopardy!', '#jeopardy_round'),
        ('Double Jeopardy!', '#double_jeopardy_round'),
        ('Final Jeopardy!', '#final_jeopardy_round')
    ]

    for round_name, div_id in rounds_info:
        round_div = parser.select_one(div_id)
        if not round_div:
            continue
            
        all_rows = round_div.select('table.round > tr')
        if not all_rows:
            all_rows = round_div.select('table.round > tbody > tr')
            
        if not all_rows:
            continue

        categories = [td.text.strip() for td in all_rows[0].select('.category_name')]

        for row in all_rows[1:]:
            for col_index, td_clue in enumerate(row.select('td.clue')):
                question_td = td_clue.select_one('.clue_text:not([id$="_r"])')
                
                if not question_td or not question_td.text.strip():
                    continue

                question = question_td.text.strip()
                
                val_td = td_clue.select_one('.clue_value, .clue_value_daily_double')
                is_dd = bool(td_clue.select_one('.clue_value_daily_double'))
                
                value = 0
                if val_td:
                    val_str = val_td.text.replace('$', '').replace(',', '').replace('DD: ', '').strip()
                    if val_str.isdigit():
                        value = int(val_str)

                ans_em = td_clue.select_one('.correct_response')
                answer = ans_em.text.strip() if ans_em else ""
                
                external_links = [a.get('href') for a in question_td.select('a')]

                all_clues.append({
                    "show_number": show_number,
                    "air_date": air_date,
                    "round": round_name,
                    "category": categories[col_index] if col_index < len(categories) else "",
                    "value": f"${value}",
                    "is_daily_double": is_dd,
                    "question": question,
                    "answer": answer,
                    "external_links": external_links
                })

    fj_div = parser.select_one('#final_jeopardy_round')
    if fj_div:
        cat_td = fj_div.select_one('.category_name')
        category = cat_td.text.strip() if cat_td else ""
        
        q_td = fj_div.select_one('.clue_text')
        question = q_td.text.strip() if q_td else ""
        
        a_em = fj_div.select_one('.correct_response')
        answer = a_em.text.strip() if a_em else ""
        
        external_links = [a.get('href') for a in q_td.select('a')] if q_td else []

        all_clues.append({
            "show_number": show_number,
            "air_date": air_date,
            "round": "Final Jeopardy!",
            "category": category,
            "value": f"${0}",
            "is_daily_double": False,
            "question": question,
            "answer": answer,
            "external_links": external_links
        })

    return all_clues

def main():
    if not OUT_DIR.exists():
        OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print("Scanning list of seasons...")
    seasons = scan_season(request_handler(ARCHIVE_URL))
    
    if not seasons:
        print("Failed to fetching list of seasons.")
        return

    with open(OUT_DIR / 'jeopardy_seasons.csv', 'w', encoding='utf-8') as w:
        w.write('index,season\n')
        for idx, season in enumerate(seasons):
            w.write(f"{idx},{season}\n")
    
    all_jeopardy_data = []
    
    for season in seasons:
        print(f"Fetching season {season}...")
        
        html = request_handler(get_archive_url(season))
        game_ids = scan_game_id(html)
        
        if not game_ids:
            print(f"Failed to find game_id for season {season}. Skipping to the next season.")
            continue
        
        with open(OUT_DIR / 'jeopardy_games.csv', 'w', encoding='utf-8') as w:
            w.write('index,game_id\n')
            for idx, game_id in enumerate(game_ids):
                w.write(f"{idx},{game_id}\n")

        for game_id in game_ids:
            print(f"Fetching Show ID {game_id} (Season {season})...")
            show_html = request_handler(get_show_url(game_id))

            if show_html:
                show_data = scan_show(show_html)
                all_jeopardy_data.extend(show_data) 

            time.sleep(2) 
            
        print(f"Finished extracting season {season}. Current total data: {len(all_jeopardy_data)} clues.")
            
    out_file = OUT_DIR / 'jeopardy.json'
    print(f"\nAll seasons have finished processing! Saving to {out_file}...")
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(all_jeopardy_data, f, indent=4, ensure_ascii=False)
        
    print(f"Success! A total of {len(all_jeopardy_data)} clues have been neatly saved to jeopardy.json.")

if __name__ == '__main__':
    main()