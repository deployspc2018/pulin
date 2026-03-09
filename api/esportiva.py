import requests
import difflib
import streamlit as st
from datetime import datetime
import pytz

BASE_API = st.secrets.get("esportiva_api_url", "")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Referer": "https://esportiva.bet.br/",
    "Origin": "https://esportiva.bet.br",
    "Accept": "application/json",
}
PARAMS_BASE = {
    "culture": "pt-BR",
    "timezoneOffset": 180,
    "integration": "esportiva",
    "deviceType": 1,
    "numFormat": "en-GB",
    "countryCode": "BR",
}
NBA_CHAMP_ID = int(st.secrets.get("esportiva_nba_champ_id", 2980))

@st.cache_data(ttl=60)
def get_all_events():
    all_events, all_markets, all_odds, all_competitors = [], [], [], []

    for endpoint, extra in [
        ("widget/GetLiveEvents", {}),
        ("widget/GetEvents", {"eventCount": 100}),
    ]:
        params = {**PARAMS_BASE, "sportId": 67, "catIds": 0, "champIds": NBA_CHAMP_ID, **extra}
        try:
            r = requests.get(f"{BASE_API}/{endpoint}", params=params, headers=HEADERS, timeout=8)
            if r.status_code == 200:
                result = r.json().get("Result", r.json())
                all_events += result.get("events", [])
                all_markets += result.get("markets", [])
                all_odds += result.get("odds", [])
                all_competitors += result.get("competitors", [])
        except Exception as e:
            print(f"Esportiva fetch error ({endpoint}): {e}")

    seen = set()
    unique_events = [e for e in all_events if not (e["id"] in seen or seen.add(e["id"]))]

    return {
        "events": unique_events,
        "markets": all_markets,
        "odds": {o["id"]: o for o in all_odds},
        "competitors": {c["id"]: c["name"] for c in all_competitors},
    }

def get_events_by_date(date_str):
    BRT = pytz.timezone("America/Sao_Paulo")
    UTC = pytz.utc
    ano = datetime.now().year
    data_limpa = date_str.split(' - ')[0].strip()

    dt_start = BRT.localize(datetime.strptime(f"{data_limpa}/{ano}", "%d/%m/%Y"))
    dt_end = BRT.localize(datetime.strptime(f"{data_limpa}/{ano} 23:59:59", "%d/%m/%Y %H:%M:%S"))

    result = []
    for ev in get_all_events()["events"]:
        start_str = ev.get("startDate", "")
        try:
            start_utc = UTC.localize(datetime.strptime(start_str[:19], "%Y-%m-%dT%H:%M:%S"))
            start_brt = start_utc.astimezone(BRT)
            if dt_start <= start_brt <= dt_end:
                result.append(ev)
        except:
            continue
    return result

def fuzzy_match_event(poly_title, esportiva_events, threshold=0.8):
    poly_clean = poly_title.lower()
    best_match = None
    best_ratio = 0

    for ev in esportiva_events:
        name = ev.get("name", "")
        parts = name.split(" vs. ")
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

def extract_ml_odds(esportiva_event):
    try:
        data = get_all_events()
        markets = data["markets"]
        odds_map = data["odds"]

        ml = next((m for m in markets
                   if m["id"] in esportiva_event.get("marketIds", [])
                   and "Vencedor" in m.get("name", "")), None)
        if ml:
            odd_objs = [odds_map[oid] for oid in ml["oddIds"] if oid in odds_map]
            if len(odd_objs) >= 2:
                return round(odd_objs[0]["price"], 2), round(odd_objs[1]["price"], 2)
    except Exception as e:
        print(f"Esportiva ML extraction error: {e}")
    return None, None

def get_home_away_names(esportiva_event):
    name = esportiva_event.get("name", "")
    parts = name.split(" vs. ")
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return "", ""
