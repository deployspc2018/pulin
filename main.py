import streamlit as st
import requests
import pandas as pd
import ast

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Arbitragem NBA Pro", page_icon="🏀", layout="wide")

api_key = st.secrets["bet_api_key"]

# --- CSS AVANÇADO ---
st.markdown("""
    <style>
    /* Estilo para Lucro Positivo (Verde Neon) */
    .lucro-positivo {
        color: #00ff00;
        font-weight: bold;
        font-size: 20px;
    }
    /* Estilo para Prejuízo (Vermelho/Laranja) */
    .lucro-negativo {
        color: #ff4b4b;
        font-weight: bold;
    }
    /* Alvo sempre destacado */
    div[data-testid="stMetric"]:contains("Alvo") div[data-testid="stMetricValue"] {
        color: #ffca28 !important; /* Amarelo Ouro para o Alvo */
        font-weight: bold;
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

    # Cálculo das Stakes (sempre proporcional para igualar o resultado)
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

@st.cache_data(ttl=60)
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

# --- INTERFACE ---
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
    if st.sidebar.button("Atualizar Odds"):
        st.cache_data.clear()
        st.rerun()

    st.title(f"🏀 Jogos de {data_escolhida}")

    for event in agenda[data_escolhida]:
        with st.expander(f"PARTIDA: {event['title']}", expanded=True):
            for market in event.get('markets', []):
                outcomes = ast.literal_eval(market['outcomes']) if isinstance(market['outcomes'], str) else market['outcomes']
                prices = ast.literal_eval(market['outcomePrices']) if isinstance(market['outcomePrices'], str) else market['outcomePrices']

                if len(outcomes) < 2: continue

                o1, o2 = to_decimal(prices[0]), to_decimal(prices[1])
                s1, s2, lucro_pct, lucro_rs, is_surebet = calcular_stakes(o1, o2, banca_total)

                # Definição de Base e Alvo (Base é sempre a maior Odd para calcularmos o hedge)
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

                # Se for Surebet, damos um destaque visual antes das colunas
                if is_surebet:
                    st.success(f" Possibilidade de Sure só na Polymarket, lucro de {lucro_pct}% ")

                c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.5])

                with c1:
                    tipo = market.get('sportsMarketType', 'Mercado').replace('_', ' ').title()
                    st.write(f"**{tipo}**")
                    st.caption(f"Base: {nome_base} ({maior_odd}x)")

                with c2:
                    st.metric(f"{outcomes[0]}", f"{o1}x")
                    st.write(f"Apostar: R$ {s1}")

                with c3:
                    st.metric(f"{outcomes[1]}", f"{o2}x")
                    st.write(f"Apostar: R$ {s2}")

                with c4:
                    # Lógica de exibição unificada

                    # 1. O Alvo (Sempre visível)
                    st.metric(
                        label=f"🎯 Alvo: {nome_alvo}",
                        value=f"\\> {alvo_necessario}x",
                    )

                    # 2. O Lucro (Sempre visível, muda a cor)
                    if lucro_pct > 0:
                        st.markdown(f"<span class='lucro-positivo'>Lucro: +{lucro_pct}% (+R$ {lucro_rs})</span>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<span class='lucro-negativo'>Spread: {lucro_pct}% (R$ {lucro_rs})</span>", unsafe_allow_html=True)

        st.divider()
