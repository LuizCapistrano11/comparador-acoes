import streamlit as st

st.set_page_config(page_title="O Investidor Crítico", layout="wide")

comparador = st.Page("pages/comparador.py", title="Comparador de Ações", icon="📊", default=True)
analise = st.Page("pages/analise.py", title="Análise de Ativos", icon="🔍")

nav = st.navigation([comparador, analise])
nav.run()
