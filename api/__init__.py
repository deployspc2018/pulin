import requests
import difflib
import pytz
import streamlit as st
from datetime import datetime
from . import kto, esportiva

API_KEY = st.secrets.get("bet_api_key", "")
EVENTS_URL = st.secrets.get("events_api_url", "")
ODDS_URL = st.secrets.get("odds_api_url", "")

DIRECT_SOURCES = {"KTO", "Esportiva"}

def is_direct_source(bookmaker):
    return bookmaker in DIRECT_SOURCES

def get_events_by_date(date_str, bookmaker):
    if bookmaker == "KTO":
        return kto.get_events_by_date(date_str)
    if bookmaker == "Esportiva":
        return esportiva.get_events_by_date(date_str)
    return _odds_api_get_events(date_str, bookmaker)

def fuzzy_match_event(poly_title, events, bookmaker):
    if bookmaker == "KTO":
        return kto.fuzzy_match_event(poly_title, events)
    if bookmaker == "Esportiva":
        return esportiva.fuzzy_match_event(poly_title, events)
    return _odds_api_fuzzy_match(poly_title, events)

def get_ml_odds(match, bookmaker):
    if bookmaker == "KTO":
        home, away = kto.get_home_away_names(match)
        oh, oa = kto.extract_ml_odds(match)
        return (home, away, oh, oa) if oh and oa else None
    if bookmaker == "Esportiva":
        home, away = esportiva.get_home_away_names(match)
        oh, oa = esportiva.extract_ml_odds(match)
        return (home, away, oh, oa) if oh and oa else None
    return _odds_api_get_ml_odds(match, bookmaker)

def _odds_api_get_events(date_str, bookmaker):
    try:
        BRT = pytz.timezone("America/Sao_Paulo")
        UTC = pytz.utc
        ano = datetime.now().year
        data_limpa = date_str.split(' - ')[0].strip()
        dt_start = BRT.localize(datetime.strptime(f"{data_limpa}/{ano}", "%d/%m/%Y"))
        dt_end = BRT.localize(datetime.strptime(f"{data_limpa}/{ano} 23:59:59", "%d/%m/%Y %H:%M:%S"))
        params = {
            'apiKey': API_KEY, 'league': 'usa-nba', 'sport': 'basketball',
            'bookmaker': bookmaker,
            'from': dt_start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            'to': dt_end.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        r = requests.get(EVENTS_URL, params=params)
        return r.json() if r.status_code == 200 else []
    except Exception as e:
        print(f"Odds API events error ({bookmaker}): {e}")
        return []

def _odds_api_fuzzy_match(poly_title, events, threshold=0.8):
    poly_clean = poly_title.lower()
    best_match = None
    best_ratio = 0
    for ev in events:
        home = ev.get('home', '').lower()
        away = ev.get('away', '').lower()
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

def _odds_api_get_ml_odds(match, bookmaker):
    try:
        event_id = match.get('id')
        r = requests.get(ODDS_URL, params={'apiKey': API_KEY, 'eventId': event_id, 'bookmakers': bookmaker})
        if r.status_code != 200:
            return None
        data = r.json()
        if isinstance(data, list) and data:
            data = data[0]
        markets = data.get('bookmakers', {}).get(bookmaker, [])
        for m in markets:
            if m['name'] == 'ML':
                odds = m['odds'][0]
                return match.get('home', ''), match.get('away', ''), float(odds['home']), float(odds['away'])
    except Exception as e:
        print(f"Odds API ML error ({bookmaker}): {e}")
    return None
