import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
from datetime import date, timedelta

st.set_page_config(page_title="Comparador de Ações", layout="wide")
st.title("Comparador de Ações — Base 100")

TICKERS_POPULARES = [
    "^BVSP",   # IBOVESPA
    "PETR4.SA",
    "VALE3.SA",
    "ITUB4.SA",
    "BBDC4.SA",
    "ABEV3.SA",
    "WEGE3.SA",
    "RENT3.SA",
    "BBAS3.SA",
    "SUZB3.SA",
    "AAPL",
    "MSFT",
    "GOOGL",
    "AMZN",
    "TSLA",
]

# --- Sidebar ---
st.sidebar.header("Configurações")

tickers_selecionados = st.sidebar.multiselect(
    "Selecione os tickers",
    options=TICKERS_POPULARES,
    default=["^BVSP", "PETR4.SA"],
    help="Escolha um ou mais ativos para comparar",
)

ticker_custom = st.sidebar.text_input(
    "Adicionar ticker manualmente",
    placeholder="Ex: MGLU3.SA",
    help="Digite o ticker do Yahoo Finance e pressione Enter",
)
if ticker_custom:
    ticker_custom = ticker_custom.strip().upper()
    if ticker_custom not in tickers_selecionados:
        tickers_selecionados.append(ticker_custom)

st.sidebar.markdown("---")

ajuste_dividendos = st.sidebar.toggle(
    "Incluir dividendos (retorno total)",
    value=False,
    help="Ativado: retorno total com dividendos reinvestidos. "
    "Desativado: apenas variação de preço (como Google Finance).",
)

periodo_opcoes = {
    "1 mês": 30,
    "3 meses": 90,
    "6 meses": 180,
    "1 ano": 365,
    "2 anos": 730,
    "5 anos": 1825,
    "Personalizado": None,
}

periodo = st.sidebar.selectbox("Período", list(periodo_opcoes.keys()), index=3)

if periodo == "Personalizado":
    col1, col2 = st.sidebar.columns(2)
    data_inicio = col1.date_input("Início", value=date.today() - timedelta(days=365))
    data_fim = col2.date_input("Fim", value=date.today())
else:
    dias = periodo_opcoes[periodo]
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=dias)

# Garantir que as datas são strings para consistência com o cache
data_inicio = str(data_inicio)
data_fim = str(data_fim)

# --- Download e processamento ---
if not tickers_selecionados:
    st.warning("Selecione ao menos um ticker na barra lateral.")
    st.stop()

NOMES = {"^BVSP": "IBOVESPA"}


@st.cache_data(ttl=3600)
def baixar_dados(tickers, inicio, fim, auto_adjust):
    dados = {}
    erros = []
    for ticker in tickers:
        try:
            df = yf.download(
                ticker, start=inicio, end=fim,
                progress=False, auto_adjust=auto_adjust,
            )
            if not df.empty:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                dados[ticker] = df["Close"]
            else:
                erros.append(f"{ticker}: sem dados para o período")
        except Exception as e:
            erros.append(f"{ticker}: {e}")
    return dados, erros


with st.spinner("Baixando dados..."):
    dados, erros = baixar_dados(
        tuple(tickers_selecionados), data_inicio, data_fim, ajuste_dividendos,
    )

if erros:
    for erro in erros:
        st.warning(erro)

if not dados:
    st.error("Não foi possível baixar dados para os tickers selecionados.")
    st.stop()

# Montar DataFrame e converter para base 100
df_precos = pd.DataFrame(dados)
df_precos = df_precos.dropna(how="all")
df_base100 = (df_precos / df_precos.iloc[0]) * 100

# --- Gráfico ---
fig = go.Figure()

for col in df_base100.columns:
    nome = NOMES.get(col, col.replace(".SA", ""))
    fig.add_trace(
        go.Scatter(
            x=df_base100.index,
            y=df_base100[col],
            mode="lines",
            name=nome,
            hovertemplate=f"<b>{nome}</b><br>"
            + "Data: %{x|%d/%m/%Y}<br>"
            + "Base 100: %{y:.2f}<extra></extra>",
        )
    )

fig.add_hline(y=100, line_dash="dash", line_color="gray", opacity=0.5)

fig.update_layout(
    title="Performance Comparada — Base 100"
    + (" (com dividendos)" if ajuste_dividendos else " (apenas preço)"),
    xaxis_title="Data",
    yaxis_title="Base 100",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=600,
)

st.plotly_chart(fig, use_container_width=True)

# --- Tabela de resumo ---
st.subheader("Resumo do Período")

resumo = []
for col in df_base100.columns:
    nome = NOMES.get(col, col.replace(".SA", ""))
    serie = df_base100[col].dropna()
    if len(serie) < 2:
        continue
    retorno = serie.iloc[-1] - 100
    maximo = serie.max() - 100
    minimo = serie.min() - 100
    resumo.append(
        {
            "Ativo": nome,
            "Retorno (%)": f"{retorno:+.2f}%",
            "Máx. (%)": f"{maximo:+.2f}%",
            "Mín. (%)": f"{minimo:+.2f}%",
            "Último Valor": f"{serie.iloc[-1]:.2f}",
        }
    )

if resumo:
    st.dataframe(pd.DataFrame(resumo), use_container_width=True, hide_index=True)
