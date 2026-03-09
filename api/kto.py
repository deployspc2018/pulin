import requests
import difflib
import streamlit as st
from datetime import datetime
import pytz

KTO_URL = st.secrets.get("kto_url", "")
KTO_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://www.kto.bet.br/",
    "Origin": "https://www.kto.bet.br",
}
KTO_PARAMS = {"channel_id": 1, "client_id": 200, "lang": "pt_BR", "market": "BR"}

@st.cache_data(ttl=60)
def get_all_events():
    try:
        r = requests.get(KTO_URL, params=KTO_PARAMS, headers=KTO_HEADERS, timeout=8)
        if r.status_code == 200:
            return r.json().get('events', [])
    except Exception as e:
        print(f"KTO fetch error: {e}")
    return []

def get_events_by_date(date_str):
    BRT = pytz.timezone("America/Sao_Paulo")
    UTC = pytz.utc
    ano = datetime.now().year
    data_limpa = date_str.split(' - ')[0].strip()

    dt_start = BRT.localize(datetime.strptime(f"{data_limpa}/{ano}", "%d/%m/%Y"))
    dt_end = BRT.localize(datetime.strptime(f"{data_limpa}/{ano} 23:59:59", "%d/%m/%Y %H:%M:%S"))

    result = []
    for ev in get_all_events():
        start_str = ev.get('event', {}).get('start', '')
        try:
            start_utc = UTC.localize(datetime.strptime(start_str[:19], "%Y-%m-%dT%H:%M:%S"))
            start_brt = start_utc.astimezone(BRT)
            if dt_start <= start_brt <= dt_end:
                result.append(ev)
        except:
            continue
    return result

def fuzzy_match_event(poly_title, kto_events, threshold=0.8):
    poly_clean = poly_title.lower()
    best_match = None
    best_ratio = 0

    for ev in kto_events:
        english_name = ev.get('event', {}).get('englishName', '')
        parts = english_name.split(' - ')
        if len(parts) != 2:
            continue
        home = parts[0].strip().lower()
        away = parts[1].strip().lower()

        home_last = home.split()[-1] if home else ""
        away_last = away.split()[-1] if away else ""

        if home_last and away_last and home_last in poly_clean and away_last in poly_clean:
            return ev

        ratio = max(
            difflib.SequenceMatcher(None, poly_clean, f"{home} vs {away}").ratio(),
            difflib.SequenceMatcher(None, poly_clean, f"{away} vs {home}").ratio()
        )
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = ev

    return best_match if best_ratio >= threshold else None

def extract_ml_odds(kto_event):
    try:
        ml = next((b for b in kto_event.get('betOffers', [])
                   if 'Moneyline' in b.get('criterion', {}).get('englishLabel', '')), None)
        if ml:
            outcomes = ml['outcomes']
            return round(outcomes[0]['odds'] / 1000, 2), round(outcomes[1]['odds'] / 1000, 2)
    except Exception as e:
        print(f"KTO ML extraction error: {e}")
    return None, None

def get_home_away_names(kto_event):
    english_name = kto_event.get('event', {}).get('englishName', '')
    parts = english_name.split(' - ')
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return '', ''
