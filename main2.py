import streamlit as st
import requests
import pandas as pd
import ast
import api # Importando seu arquivo api.py

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Arbitragem NBA Pro", page_icon="🏀", layout="wide")

# ARQUITETURA MODULAR DE CASAS (Adicione futuras casas aqui)
BOOKMAKERS_ATIVOS = ["Novibet"]

# --- CSS AVANÇADO ---
st.markdown("""
    <style>
    .lucro-positivo { color: #00ff00; font-weight: bold; font-size: 20px; }
    .lucro-negativo { color: #ff4b4b; font-weight: bold; }
    div[data-testid="stMetric"]:contains("Alvo") div[data-testid="stMetricValue"] {
        color: #ffca28 !important; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- CONSTANTES ---
GAMMA_URL = "https://gamma-api.polymarket.com/events"
NBA_SERIES_ID = 10345

# --- FUNÇÕES ---
def to_decimal(price):
    try:
        p = float(price)
        return round(1/p, 2) if p > 0 else 0
    except: return 0

def calcular_stakes(o1, o2, banca_total):
    if o1 <= 0 or o2 <= 0: return 0, 0, 0, 0, False

    inversao = (1/o1) + (1/o2)
    is_surebet = inversao < 1

    stake1 = (banca_total * (1/o1)) / inversao
    stake2 = (banca_total * (1/o2)) / inversao

    retorno_final = stake1 * o1
    lucro_prejuizo = retorno_final - banca_total
    lucro_pct = (lucro_prejuizo / banca_total) * 100

    return round(stake1, 2), round(stake2, 2), round(lucro_pct, 2), round(lucro_prejuizo, 2), is_surebet

def calc_alvo_necessario(odd_atual):
    try:
        if odd_atual <= 1: return 0
        p_atual = 1 / odd_atual
        p_necessaria = 1 - p_atual
        if p_necessaria <= 0: return 0
        return round(1 / p_necessaria, 2)
    except: return 0

@st.cache_data(ttl=20)
def get_polymarket_data():
    params = {"series_id": NBA_SERIES_ID, "active": "true", "closed": "false", "order": "id", "ascending": "false", "limit": 100}
    try:
        r = requests.get(GAMMA_URL, params=params)
        return r.json()
    except: return []

def agrupar_por_data(data):
    agrupado = {}
    for event in data:
        raw_time = event.get('gameStartTime') or event.get('endDate')
        try:
            dt = pd.to_datetime(raw_time)
            chave_data = dt.strftime('%d/%m - %A')
            if chave_data not in agrupado: agrupado[chave_data] = []
            agrupado[chave_data].append(event)
        except: continue
    return agrupado

# --- INTERFACE (SIDEBAR) ---
st.sidebar.header("💰 Gestão de Banca")
banca_total = st.sidebar.number_input("Valor Total (R$)", min_value=10.0, value=1000.0)

st.sidebar.markdown("---")
st.sidebar.header("📅 Filtro de Data")

raw_data = get_polymarket_data()
agenda = agrupar_por_data(raw_data)

if not agenda:
    st.warning("Nenhum jogo disponível.")
else:
    data_escolhida = st.sidebar.selectbox("Escolha o Dia:", list(agenda.keys()))
    
    if st.sidebar.button("Atualizar Odds Polymarket"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("🔍 Radar de Arbitragem")
    # Botão Mestre que busca as listas de jogos de todas as casas de uma vez
    if st.sidebar.button(f"Sincronizar Casas ({data_escolhida})"):
        with st.spinner("Buscando eventos nas casas..."):
            if 'dados_casas' not in st.session_state:
                st.session_state['dados_casas'] = {}
            
            for bookie in BOOKMAKERS_ATIVOS:
                eventos = api.get_events_by_date(data_escolhida, bookmaker=bookie)
                st.session_state['dados_casas'][bookie] = eventos
            st.sidebar.success("✅ Eventos sincronizados!")

    # --- CORPO PRINCIPAL ---
    st.title(f"🏀 Jogos de {data_escolhida}")

    for event in agenda[data_escolhida]:
        with st.expander(f"PARTIDA: {event['title']}", expanded=True):
            for market in event.get('markets', []):
                # 1. Filtro rápido para pular mercados secundários da Polymarket
                tipo_mercado = market.get('sportsMarketType', '').lower()
                if 'spread' in tipo_mercado or 'total' in tipo_mercado or 'over' in tipo_mercado:
                    continue # Pula para o próximo mercado se não for o Moneyline

                # 2. Parsing das odds e nomes
                outcomes = ast.literal_eval(market['outcomes']) if isinstance(market['outcomes'], str) else market['outcomes']
                prices = ast.literal_eval(market['outcomePrices']) if isinstance(market['outcomePrices'], str) else market['outcomePrices']

                # Só queremos mercados de confronto direto (2 opções)
                if len(outcomes) != 2: 
                    continue

                # 3. Faz o cálculo de stakes
                o1, o2 = to_decimal(prices[0]), to_decimal(prices[1])
                s1, s2, lucro_pct, lucro_rs, is_surebet = calcular_stakes(o1, o2, banca_total)

                # Definição de Base e Alvo (Base é sempre a maior Odd)
                if o1 >= o2:
                    maior_odd = o1
                    nome_base, nome_alvo = outcomes[0], outcomes[1]
                    odd_alvo_atual = o2
                    stake_alvo = s2
                else:
                    maior_odd = o2
                    nome_base, nome_alvo = outcomes[1], outcomes[0]
                    odd_alvo_atual = o1
                    stake_alvo = s1

                alvo_necessario = calc_alvo_necessario(maior_odd)

                # --- VISUALIZAÇÃO ---
                if is_surebet:
                    st.success(f" Possibilidade de Sure só na Polymarket, lucro de {lucro_pct}% ")

                c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.5])

                with c1:
                    tipo_formatado = market.get('sportsMarketType', 'Moneyline').replace('_', ' ').title()
                    st.write(f"**{tipo_formatado}**")
                    st.caption(f"Base: {nome_base} ({maior_odd}x)")

                with c2:
                    st.metric(f"{outcomes[0]}", f"{o1}x")
                    st.write(f"Apostar: R$ {s1}")

                with c3:
                    st.metric(f"{outcomes[1]}", f"{o2}x")
                    st.write(f"Apostar: R$ {s2}")

                with c4:
                    st.metric(label=f"🎯 Alvo: {nome_alvo}", value=f"\\> {alvo_necessario}x")
                    if lucro_pct > 0:
                        st.markdown(f"<span class='lucro-positivo'>Lucro: +{lucro_pct}% (+R$ {lucro_rs})</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<span class='lucro-negativo'>Spread: {lucro_pct}% (R$ {lucro_rs})</span>", unsafe_allow_html=True)

                # O PULO DO GATO: Se chegou até aqui e renderizou o mercado principal, para o loop!
                break

            # --- SESSÃO DAS CASAS TRADICIONAIS (Nova Feature) ---
            st.markdown("---")
            
            # Só renderiza a parte de baixo se o usuário tiver clicado no botão lateral
            if 'dados_casas' in st.session_state:
                st.markdown("Odds nas Casas")
                
                # Cria N colunas de acordo com o número de casas configuradas
                colunas_casas = st.columns(len(BOOKMAKERS_ATIVOS))
                
                for idx, bookie in enumerate(BOOKMAKERS_ATIVOS):
                    with colunas_casas[idx]:
                        eventos_desta_casa = st.session_state['dados_casas'].get(bookie, [])
                        
                        # Tenta fazer o Match Fuzzy
                        match = api.fuzzy_match_event(event['title'], eventos_desta_casa)
                        
                        if match:
                            event_id = match['id']
                            st.success(f"✅ {bookie}: Match!")
                            
                            # Botão individual para chamar as odds DENTRO do match encontrado
                            if st.button(f"Extrair Odds {bookie}", key=f"btn_{bookie}_{event_id}"):
                                with st.spinner("Batendo na API..."):
                                    json_odds = api.get_odds_from_event(event_id, bookie)
                                    print(f"json odds {json_odds}")
                                    if json_odds:
                                        odd_home, odd_away = api.extract_ml_odds(json_odds, bookie)
                                        
                                        if odd_home and odd_away:
                                            # Aqui você pode chamar calcular_stakes de novo cruzando Poly x Casa
                                            st.info(f"**{match['home']}**: {odd_home}x | **{match['away']}**: {odd_away}x")
                                            # TODO: Implementar a exibição da Surebet Poly x Casa aqui!
                                        else:
                                            st.warning("Mercado ML indisponível agora.")
                        else:
                            st.error(f"❌ {bookie}: Sem evento")
            else:
                st.caption("👈 Use o botão 'Sincronizar Casas' no menu lateral para buscar eventos.")