import streamlit as st
import requests
import pandas as pd
import ast
from datetime import datetime
import api

st.set_page_config(page_title="Arbitragem NBA", page_icon="🏀", layout="wide")

BOOKMAKERS_ATIVOS = ["Bet365", "KTO", "Esportiva"]

st.markdown("""
    <style>
    .lucro-positivo { color: #00ff00; font-weight: bold; font-size: 20px; }
    .lucro-negativo { color: #ff4b4b; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

GAMMA_URL = "https://gamma-api.polymarket.com/events"
NBA_SERIES_ID = 10345

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

def check_cross_arb(outcomes, o1, o2, bookie_home, bookie_away, oh, oa, banca):
    if not all(x and x > 1 for x in [o1, o2, oh, oa]):
        return None
    last0 = outcomes[0].lower().split()[-1]
    poly0_is_home = last0 == bookie_home.lower().split()[-1] or last0 in bookie_home.lower()
    combos = (
        [(o1, oa, outcomes[0], bookie_away), (o2, oh, outcomes[1], bookie_home)]
        if poly0_is_home else
        [(o1, oh, outcomes[0], bookie_home), (o2, oa, outcomes[1], bookie_away)]
    )
    best = None
    for op, ob, team_poly, team_bookie in combos:
        inv = 1/op + 1/ob
        if inv < 1 and (best is None or inv < best['inv']):
            best = {
                'inv': inv,
                'odd_poly': op,
                'odd_bookie': ob,
                'odd_target': round(op / (op - 1), 2),
                'team_poly': team_poly,
                'stake_poly': round((banca * (1/op)) / inv, 2),
                'team_bookie': team_bookie,
                'stake_bookie': round((banca * (1/ob)) / inv, 2),
                'lucro_pct': round((1/inv - 1) * 100, 2),
                'lucro_rs': round(banca * (1/inv - 1), 2),
            }
    return best

@st.dialog("Arbitragem Disponível")
def show_arb_modal(arb, bookie):
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Odd Polymarket", f"{arb['odd_poly']}x")
    with c2:
        st.metric("Alvo Casa", f"> {arb['odd_target']}x")
    with c3:
        st.metric(f"Odd {bookie}", f"{arb['odd_bookie']}x", delta=f"{round(arb['odd_bookie'] - arb['odd_target'], 2):+}")
    st.divider()
    c4, c5 = st.columns(2)
    with c4:
        st.metric(f"Polymarket — {arb['team_poly']}", f"R$ {arb['stake_poly']}")
    with c5:
        st.metric(f"{bookie} — {arb['team_bookie']}", f"R$ {arb['stake_bookie']}")
    st.divider()
    c6, c7 = st.columns(2)
    with c6:
        st.metric("Spread", f"+{arb['lucro_pct']}%")
    with c7:
        st.metric("Lucro Estimado", f"R$ {arb['lucro_rs']}")

def calc_alvo_necessario(odd_atual):
    try:
        if odd_atual <= 1: return 0
        p_necessaria = 1 - (1 / odd_atual)
        if p_necessaria <= 0: return 0
        return round(1 / p_necessaria, 2)
    except: return 0

@st.cache_data(ttl=20)
def get_polymarket_data():
    params = {"series_id": NBA_SERIES_ID, "active": "true", "closed": "false",
              "order": "id", "ascending": "false", "limit": 100}
    try:
        r = requests.get(GAMMA_URL, params=params)
        return r.json()
    except: return []

def agrupar_por_data(data):
    agrupado = {}
    for event in data:
        raw_time = event.get('gameStartTime') or event.get('endDate')
        try:
            dt = pd.to_datetime(raw_time, utc=True).tz_convert('America/Sao_Paulo')
            chave = dt.strftime('%d/%m - %A')
            if chave not in agrupado: agrupado[chave] = []
            agrupado[chave].append(event)
        except: continue
    sorted_keys = sorted(agrupado.keys(), key=lambda k: datetime.strptime(
        k.split(' - ')[0] + f'/{datetime.now().year}', '%d/%m/%Y'))
    return {k: agrupado[k] for k in sorted_keys}

st.sidebar.header("💰 Gestão de Banca")
banca_total = st.sidebar.number_input("Valor Total (R$)", min_value=10.0, value=1000.0)

st.sidebar.markdown("---")
st.sidebar.header("📅 Filtro de Data")

raw_data = get_polymarket_data()
agenda = agrupar_por_data(raw_data)

if not agenda:
    st.warning("Nenhum jogo disponível.")
else:
    datas = list(agenda.keys())
    hoje = datetime.now().strftime('%d/%m - %A')
    default_idx = datas.index(hoje) if hoje in datas else 0
    data_escolhida = st.sidebar.selectbox("Escolha o Dia:", datas, index=default_idx)

    if st.sidebar.button("Atualizar Odds Polymarket"):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.header("🔍 Radar de Arbitragem")

    if st.sidebar.button(f"Sincronizar Casas ({data_escolhida})"):
        with st.spinner("Buscando eventos nas casas..."):
            if 'dados_casas' not in st.session_state:
                st.session_state['dados_casas'] = {}
            for bookie in BOOKMAKERS_ATIVOS:
                st.session_state['dados_casas'][bookie] = api.get_events_by_date(data_escolhida, bookie)
            st.sidebar.success("✅ Eventos sincronizados!")

    st.title(f"🏀 Jogos de {data_escolhida}")

    if st.button("Fechar todos"):
        st.session_state['expanders_abertos'] = False
    if 'expanders_abertos' not in st.session_state:
        st.session_state['expanders_abertos'] = True

    for event in agenda[data_escolhida]:
        with st.expander(f"PARTIDA: {event['title']}", expanded=st.session_state['expanders_abertos']):
            outcomes, o1, o2 = None, 0, 0
            for market in event.get('markets', []):
                tipo_mercado = market.get('sportsMarketType', '').lower()
                if 'spread' in tipo_mercado or 'total' in tipo_mercado or 'over' in tipo_mercado:
                    continue

                outcomes = ast.literal_eval(market['outcomes']) if isinstance(market['outcomes'], str) else market['outcomes']
                prices = ast.literal_eval(market['outcomePrices']) if isinstance(market['outcomePrices'], str) else market['outcomePrices']

                if len(outcomes) != 2:
                    continue

                o1, o2 = to_decimal(prices[0]), to_decimal(prices[1])
                s1, s2, _, _, _ = calcular_stakes(o1, o2, banca_total)

                alvo1 = calc_alvo_necessario(o1)
                alvo2 = calc_alvo_necessario(o2)

                c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.5])
                with c1:
                    st.write(f"**{market.get('sportsMarketType', 'Moneyline').replace('_', ' ').title()}**")
                with c2:
                    st.metric(f"{outcomes[0]}", f"{o1}x")
                    st.write(f"Apostar: R$ {s1}")
                with c3:
                    st.metric(f"{outcomes[1]}", f"{o2}x")
                    st.write(f"Apostar: R$ {s2}")
                with c4:
                    st.caption(f"🎯 Casa precisa de **> {alvo1}x** em {outcomes[1]}")
                    st.caption(f"🎯 Casa precisa de **> {alvo2}x** em {outcomes[0]}")
                break

            st.markdown("---")

            if 'dados_casas' in st.session_state:
                st.markdown("Odds nas Casas")

                for bookie in BOOKMAKERS_ATIVOS:
                    eventos_desta_casa = st.session_state['dados_casas'].get(bookie, [])
                    match = api.fuzzy_match_event(event['title'], eventos_desta_casa, bookie)
                    col_status, col_btn, col_odds = st.columns([1.5, 1, 3])

                    if match:
                        with col_status:
                            st.success(f"✅ {bookie}")

                        if api.is_direct_source(bookie):
                            result = api.get_ml_odds(match, bookie)
                            with col_odds:
                                if result:
                                    home, away, oh, oa = result
                                    arb = check_cross_arb(outcomes, o1, o2, home, away, oh, oa, banca_total) if outcomes else None
                                    c_info, c_arb = st.columns([2, 1])
                                    with c_info:
                                        st.info(f"**{home}**: {oh}x | **{away}**: {oa}x")
                                    with c_arb:
                                        if arb and st.button("Ver Arbitragem", key=f"arb_{bookie}_{event['id']}"):
                                            show_arb_modal(arb, bookie)
                                else:
                                    st.warning("ML indisponível.")
                        else:
                            odds_key = f"odds_{bookie}_{match.get('id')}_{event['id']}"
                            with col_btn:
                                if st.button("Extrair Odds", key=f"btn_{bookie}_{match.get('id')}_{event['id']}"):
                                    with st.spinner(""):
                                        st.session_state[odds_key] = api.get_ml_odds(match, bookie)
                            with col_odds:
                                if odds_key in st.session_state:
                                    result = st.session_state[odds_key]
                                    if result:
                                        home, away, oh, oa = result
                                        arb = check_cross_arb(outcomes, o1, o2, home, away, oh, oa, banca_total) if outcomes else None
                                        c_info, c_arb = st.columns([2, 1])
                                        with c_info:
                                            st.info(f"**{home}**: {oh}x | **{away}**: {oa}x")
                                        with c_arb:
                                            if arb and st.button("Ver Arbitragem", key=f"arb_{bookie}_{event['id']}"):
                                                show_arb_modal(arb, bookie)
                                    else:
                                        st.warning("ML indisponível.")
                    else:
                        with col_status:
                            st.error(f"❌ {bookie}")
            else:
                st.caption("👈 Use o botão 'Sincronizar Casas' no menu lateral para buscar eventos.")
