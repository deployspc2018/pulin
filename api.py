import requests
from datetime import datetime
import difflib
import streamlit as st

API_KEY = st.secrets.get("bet_api_key", "")
EVENTS_URL = st.secrets.get("events_api_url", "")
ODDS_URL = st.secrets.get("odds_api_url", "")

def get_events_by_date(data_str_streamlit, bookmaker):
    """
    Busca a lista de jogos do dia para uma casa específica.
    """
    try:
        ano_atual = datetime.now().year
        data_limpa = data_str_streamlit.split('-')[0].strip() 
        
        dt_inicio = datetime.strptime(f"{data_limpa}/{ano_atual}", "%d/%m/%Y")
        
        from_param = dt_inicio.strftime("%Y-%m-%dT00:00:00Z")
        to_param = dt_inicio.strftime("%Y-%m-%dT23:59:59Z")

        params = {
            'apiKey': API_KEY,
            'league': 'usa-nba',
            'sport': 'basketball',
            'bookmaker': bookmaker,
            'from': from_param,
            'to': to_param
        }

        response = requests.get(EVENTS_URL, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erro API ({bookmaker}): {response.status_code}")
            return []

    except Exception as e:
        print(f"Erro no parsing de data/request: {e}")
        return []

def fuzzy_match_event(poly_title, bookmaker_events, threshold=0.8):
    """
    Tenta encontrar o jogo da Polymarket na lista retornada pela casa de aposta.
    Retorna o dicionário do evento se encontrar, ou None.
    """
    poly_clean = poly_title.lower()
    best_match = None
    best_ratio = 0

    for ev in bookmaker_events:
        home = ev.get('home', '').lower()
        away = ev.get('away', '').lower()
        
        # 1. FAST-TRACK NBA (Match pelo sobrenome do time)
        # Ex: "Pelicans" e "Jazz" in "Pelicans vs. Jazz"
        home_last = home.split()[-1] if home else ""
        away_last = away.split()[-1] if away else ""
        
        if home_last and away_last and (home_last in poly_clean and away_last in poly_clean):
            return ev # Match perfeito

        # 2. TESTE FUZZY MATEMÁTICO (Caso o fast-track falhe)
        # A Polymarket pode escrever "A vs B" ou "B vs A"
        str1 = f"{home} vs {away}"
        str2 = f"{away} vs {home}"
        
        ratio1 = difflib.SequenceMatcher(None, poly_clean, str1).ratio()
        ratio2 = difflib.SequenceMatcher(None, poly_clean, str2).ratio()
        
        max_ratio = max(ratio1, ratio2)
        
        if max_ratio > best_ratio:
            best_ratio = max_ratio
            best_match = ev

    # Retorna o match se a similaridade for maior que a tolerância (80%)
    if best_ratio >= threshold:
        return best_match
        
    return None

def get_odds_from_event(event_id, bookmaker):
    """
    Busca o JSON de odds usando o padrão query param exigido pela API.
    """
    params = {
        'apiKey': API_KEY,
        'eventId': event_id,
        'bookmakers': bookmaker # O endpoint deles permite filtrar a casa aqui também!
    }
    
    try:
        response = requests.get(ODDS_URL, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Erro {response.status_code} ao buscar odd do evento {event_id}")
            
    except Exception as e:
        print(f"Erro na requisição da odd para {event_id}: {e}")
    
    return None

def extract_ml_odds(json_evento, bookmaker):
    """
    Extrai as odds Moneyline (ML) do JSON de retorno da API de Odds.
    """
    try:
        # A resposta que você me mandou antes vinha numa lista de tamanho 1
        # Se a estrutura do endpoint /odds for igual a do /events, iteramos:
        if isinstance(json_evento, list) and len(json_evento) > 0:
            evento_dados = json_evento[0]
        else:
            evento_dados = json_evento

        mercados = evento_dados.get('bookmakers', {}).get(bookmaker, [])
        for mercado in mercados:
            if mercado['name'] == 'ML':
                odds = mercado['odds'][0]
                return float(odds['home']), float(odds['away'])
    except Exception as e:
        print(f"Mercado ML não encontrado para {bookmaker}: {e}")
        
    return None, None