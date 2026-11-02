from bs4 import BeautifulSoup
from pathlib import Path
from urllib3 import PoolManager
import time
import pandas as pd
import re
import json

http = PoolManager()

OUT_DIR = Path(__file__).resolve().parent / 'raw'
SEASON = 22
ARCHIVE_URL = f"https://www.j-archive.com/showseason.php?season={SEASON}"

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
        ('Double Jeopardy!', '#double_jeopardy_round')
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
                    "value": value,
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
            "value": 0,
            "is_daily_double": False,
            "question": question,
            "answer": answer,
            "external_links": external_links
        })

    return all_clues

def main():
    if not OUT_DIR.exists():
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        
    print(f"Fetching season {SEASON}...")
    html = request_handler(ARCHIVE_URL)
    game_ids = scan_game_id(html)
    
    if not game_ids:
        print("Gagal menemukan game_id.")
        return

    df = pd.DataFrame({'game_id': game_ids})
    df.to_csv(OUT_DIR / 'jeopardy_game_id.csv', index=False, index_label='index')

    datas = []
    for game_id in game_ids:
        print(f"Fetching Show ID {game_id}...")
        show_html = request_handler(get_show_url(game_id))

        if show_html:
            show_data = scan_show(show_html)
            datas.extend(show_data) 

        time.sleep(2) 
            
    out_file = OUT_DIR / f'jeopardy_season_{SEASON}.json'
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(datas, f, indent=4, ensure_ascii=False)
        
    print(f"Berhasil ekstrak {len(datas)} clues. Tersimpan di {out_file}")

if __name__ == '__main__':
    main()