import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import requests
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

NOMES = {"^BVSP": "IBOVESPA"}

# --- Estado persistente dos tickers ---
if "tickers_ativos" not in st.session_state:
    st.session_state.tickers_ativos = ["^BVSP"]
if "nomes_cache" not in st.session_state:
    st.session_state.nomes_cache = {}


def adicionar_ticker(ticker, nome=None):
    if ticker not in st.session_state.tickers_ativos:
        st.session_state.tickers_ativos.append(ticker)
    if nome:
        st.session_state.nomes_cache[ticker] = nome


def remover_ticker(ticker):
    if ticker in st.session_state.tickers_ativos:
        st.session_state.tickers_ativos.remove(ticker)


# --- Sidebar ---
st.sidebar.header("Configurações")

# Busca por nome ou ticker
st.sidebar.subheader("Adicionar ativos")
busca = st.sidebar.text_input(
    "Buscar por nome ou ticker",
    placeholder="Ex: Petrobras, Apple, MGLU3...",
    key="busca_ticker",
)
if busca:
    try:
        resultados = yf.Search(busca.strip(), max_results=8)
        for q in resultados.quotes:
            if q.get("isYahooFinance"):
                simbolo = q["symbol"]
                nome = q.get("shortname", simbolo)
                bolsa = q.get("exchDisp", "")
                label = f"{simbolo} — {nome} ({bolsa})"
                ja_adicionado = simbolo in st.session_state.tickers_ativos
                st.sidebar.button(
                    f"{'\\u2705' if ja_adicionado else '\\u2795'} {label}",
                    key=f"add_{simbolo}",
                    on_click=adicionar_ticker,
                    args=(simbolo, nome),
                    disabled=ja_adicionado,
                )
    except Exception:
        st.sidebar.caption("Erro na busca. Tente novamente.")

# Atalhos para tickers populares
with st.sidebar.expander("Tickers populares"):
    for ticker in TICKERS_POPULARES:
        nome_display = NOMES.get(ticker, ticker.replace(".SA", ""))
        ja_adicionado = ticker in st.session_state.tickers_ativos
        st.button(
            f"{'\\u2705' if ja_adicionado else '\\u2795'} {nome_display} ({ticker})",
            key=f"pop_{ticker}",
            on_click=adicionar_ticker,
            args=(ticker,),
            disabled=ja_adicionado,
        )

st.sidebar.markdown("---")

# Ativos no gráfico (com remoção)
st.sidebar.subheader("Ativos no gráfico")
if st.session_state.tickers_ativos:
    for ticker in list(st.session_state.tickers_ativos):
        nome_display = (
            st.session_state.nomes_cache.get(ticker)
            or NOMES.get(ticker)
            or ticker.replace(".SA", "")
        )
        st.sidebar.button(
            f"\\u274c {nome_display} ({ticker})",
            key=f"rem_{ticker}",
            on_click=remover_ticker,
            args=(ticker,),
        )
else:
    st.sidebar.caption("Nenhum ativo selecionado.")

tickers_selecionados = list(st.session_state.tickers_ativos)

st.sidebar.markdown("---")

ajuste_dividendos = st.sidebar.toggle(
    "Incluir dividendos (retorno total)",
    value=False,
    help="Ativado: retorno total com dividendos reinvestidos. "
    "Desativado: apenas variação de preço (como Google Finance).",
)

mostrar_cdi = st.sidebar.toggle(
    "Comparar com CDI",
    value=True,
    help="Exibe o rendimento acumulado do CDI no período.",
)

preco_em_dolar = st.sidebar.toggle(
    "Preços em dólar (USD)",
    value=False,
    help="Converte os preços dos ativos para dólar usando o câmbio USDBRL.",
)

mostrar_cambio = st.sidebar.toggle(
    "Exibir câmbio USDBRL",
    value=False,
    help="Adiciona a curva do câmbio USDBRL ao gráfico.",
)

mostrar_juro_longo = st.sidebar.toggle(
    "Exibir juro longo (Swap Pré 5 anos)",
    value=False,
    help="Adiciona a curva de juros (Swap DI x Pré 1800 dias) em eixo secundário. "
    "Dados mensais do BCB interpolados para frequência diária.",
)

mostrar_fed_curto = st.sidebar.toggle(
    "Exibir Fed Funds Rate (curto)",
    value=False,
    help="T-Bill 13 semanas (^IRX) — proxy da taxa básica do Fed, comparável ao CDI.",
)

mostrar_fed_longo = st.sidebar.toggle(
    "Exibir Treasury 5 anos (EUA)",
    value=False,
    help="Yield do Treasury de 5 anos (^FVX) — comparável ao juro longo brasileiro.",
)

st.sidebar.markdown("---")

periodo_opcoes = {
    "1 mês": 30,
    "3 meses": 90,
    "6 meses": 180,
    "1 ano": 365,
    "2 anos": 730,
    "5 anos": 1825,
    "10 anos": 3650,
    "15 anos": 5475,
    "20 anos": 7300,
    "25 anos": 9125,
    "Máximo": 9999,
    "Personalizado": None,
}

periodo = st.sidebar.selectbox("Período", list(periodo_opcoes.keys()), index=8)

if periodo == "Personalizado":
    col1, col2 = st.sidebar.columns(2)
    data_inicio = col1.date_input(
        "Início",
        value=date.today() - timedelta(days=365),
        min_value=date(2000, 1, 1),
    )
    data_fim = col2.date_input("Fim", value=date.today())
else:
    dias = periodo_opcoes[periodo]
    data_fim = date.today()
    data_inicio = data_fim - timedelta(days=dias)

# Garantir que as datas são strings para consistência com o cache
data_inicio = str(data_inicio)
data_fim = str(data_fim)

# --- Funções auxiliares ---
if not tickers_selecionados:
    st.warning("Selecione ao menos um ticker na barra lateral.")
    st.stop()


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


def _baixar_serie_bcb(serie, inicio_str, fim_str):
    """Baixa série do BCB em blocos de 10 anos (limite da API)."""
    dt_inicio = pd.to_datetime(inicio_str)
    dt_fim = pd.to_datetime(fim_str)
    frames = []
    cursor = dt_inicio
    while cursor < dt_fim:
        bloco_fim = min(cursor + timedelta(days=3650), dt_fim)
        url = (
            f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados"
            f"?formato=json"
            f"&dataInicial={cursor.strftime('%d/%m/%Y')}"
            f"&dataFinal={bloco_fim.strftime('%d/%m/%Y')}"
        )
        r = requests.get(url, timeout=30)
        if r.status_code == 200:
            data = r.json()
            if isinstance(data, list) and data:
                frames.append(pd.DataFrame(data))
        cursor = bloco_fim + timedelta(days=1)
    if not frames:
        return None
    df = pd.concat(frames, ignore_index=True)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = df["valor"].astype(float)
    df = df.set_index("data").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df["valor"]


@st.cache_data(ttl=3600)
def baixar_cdi(inicio, fim):
    """Baixa taxa CDI diária do BCB (série 12) e retorna série acumulada base 100."""
    serie = _baixar_serie_bcb(12, inicio, fim)
    if serie is None:
        return None
    fator = 1 + serie / 100
    acum = fator.cumprod() * 100 / fator.iloc[0]
    acum.name = "cdi_acum"
    return acum


@st.cache_data(ttl=3600)
def baixar_cambio(inicio, fim):
    """Baixa câmbio USDBRL via yfinance."""
    df = yf.download("USDBRL=X", start=inicio, end=fim, progress=False)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df["Close"]


@st.cache_data(ttl=3600)
def baixar_juro_longo(inicio, fim):
    """Baixa Swap DI x Pré 5 anos (série 7815 do BCB), interpolado para diário."""
    serie = _baixar_serie_bcb(7815, inicio, fim)
    if serie is None:
        return None
    # Interpolar dados mensais para frequência diária (dias úteis)
    idx_diario = pd.bdate_range(start=serie.index[0], end=serie.index[-1])
    serie = serie.reindex(idx_diario).interpolate(method="linear")
    serie.name = "juro_longo"
    return serie


@st.cache_data(ttl=3600)
def baixar_taxa_yf(ticker, inicio, fim):
    """Baixa yield/taxa via yfinance (ex: ^IRX, ^FVX)."""
    df = yf.download(ticker, start=inicio, end=fim, progress=False)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df["Close"]


# --- Download e processamento ---
with st.spinner("Baixando dados..."):
    dados, erros = baixar_dados(
        tuple(tickers_selecionados), data_inicio, data_fim, ajuste_dividendos,
    )

    cambio = None
    if preco_em_dolar or mostrar_cambio:
        cambio = baixar_cambio(data_inicio, data_fim)

    cdi_acum = None
    if mostrar_cdi:
        cdi_acum = baixar_cdi(data_inicio, data_fim)

    juro_longo = None
    if mostrar_juro_longo:
        juro_longo = baixar_juro_longo(data_inicio, data_fim)

    fed_curto = None
    if mostrar_fed_curto:
        fed_curto = baixar_taxa_yf("^IRX", data_inicio, data_fim)

    fed_longo = None
    if mostrar_fed_longo:
        fed_longo = baixar_taxa_yf("^FVX", data_inicio, data_fim)

if erros:
    for erro in erros:
        st.warning(erro)

if not dados:
    st.error("Não foi possível baixar dados para os tickers selecionados.")
    st.stop()

# Montar DataFrame de preços
df_precos = pd.DataFrame(dados)
df_precos = df_precos.dropna(how="all")

# Ajustar janela: começar na data do dado mais recente entre todos os ativos
# para garantir que todos tenham dados desde o início e base 100 seja comparável
data_inicio_efetiva = df_precos.apply(lambda col: col.dropna().index[0]).max()
df_precos = df_precos.loc[data_inicio_efetiva:]
df_precos = df_precos.dropna(how="all")

if df_precos.empty:
    st.error("Não há dados suficientes para o período e ativos selecionados.")
    st.stop()

# Recortar CDI, câmbio e juro longo para a mesma janela
if cdi_acum is not None:
    cdi_acum = cdi_acum.loc[cdi_acum.index >= data_inicio_efetiva]
    if not cdi_acum.empty:
        cdi_acum = cdi_acum / cdi_acum.iloc[0] * 100
    else:
        cdi_acum = None

if cambio is not None:
    cambio = cambio.loc[cambio.index >= data_inicio_efetiva]
    if cambio.empty:
        cambio = None

if juro_longo is not None:
    juro_longo = juro_longo.loc[juro_longo.index >= data_inicio_efetiva]
    if juro_longo.empty:
        juro_longo = None

if fed_curto is not None:
    fed_curto = fed_curto.loc[fed_curto.index >= data_inicio_efetiva]
    if fed_curto.empty:
        fed_curto = None

if fed_longo is not None:
    fed_longo = fed_longo.loc[fed_longo.index >= data_inicio_efetiva]
    if fed_longo.empty:
        fed_longo = None

# Converter para dólar se necessário
if preco_em_dolar and cambio is not None:
    cambio_alinhado = cambio.reindex(df_precos.index, method="ffill")
    df_precos = df_precos.div(cambio_alinhado, axis=0)
    df_precos = df_precos.dropna(how="all")
    # Converter CDI acumulado para dólar também
    if cdi_acum is not None:
        cambio_cdi = cambio.reindex(cdi_acum.index, method="ffill")
        cdi_em_usd = cdi_acum / cambio_cdi
        cdi_acum = cdi_em_usd / cdi_em_usd.dropna().iloc[0] * 100

# --- Slider de ajuste fino da janela ---
datas_disponiveis = df_precos.index
data_min = datas_disponiveis[0].date()
data_max = datas_disponiveis[-1].date()

if data_min < data_max:
    janela = st.slider(
        "Ajuste a janela de análise",
        min_value=data_min,
        max_value=data_max,
        value=(data_min, data_max),
        format="DD/MM/YYYY",
    )
    # Filtrar todos os dados pela janela selecionada
    dt_ini = pd.Timestamp(janela[0])
    dt_end = pd.Timestamp(janela[1])
    df_precos = df_precos.loc[dt_ini:dt_end]

    if cdi_acum is not None:
        cdi_acum = cdi_acum.loc[
            (cdi_acum.index >= dt_ini) & (cdi_acum.index <= dt_end)
        ]
        if not cdi_acum.empty:
            cdi_acum = cdi_acum / cdi_acum.iloc[0] * 100
        else:
            cdi_acum = None

    if cambio is not None:
        cambio = cambio.loc[(cambio.index >= dt_ini) & (cambio.index <= dt_end)]
        if cambio.empty:
            cambio = None

    if juro_longo is not None:
        juro_longo = juro_longo.loc[
            (juro_longo.index >= dt_ini) & (juro_longo.index <= dt_end)
        ]
        if juro_longo.empty:
            juro_longo = None

    if fed_curto is not None:
        fed_curto = fed_curto.loc[
            (fed_curto.index >= dt_ini) & (fed_curto.index <= dt_end)
        ]
        if fed_curto.empty:
            fed_curto = None

    if fed_longo is not None:
        fed_longo = fed_longo.loc[
            (fed_longo.index >= dt_ini) & (fed_longo.index <= dt_end)
        ]
        if fed_longo.empty:
            fed_longo = None

if df_precos.empty or len(df_precos) < 2:
    st.warning("Janela muito curta — selecione um intervalo maior.")
    st.stop()

# Converter para base 100
df_base100 = (df_precos / df_precos.iloc[0]) * 100

# --- Gráfico ---
tem_cambio_eixo = mostrar_cambio and cambio is not None
tem_juro_eixo = mostrar_juro_longo and juro_longo is not None
tem_fed_curto_eixo = mostrar_fed_curto and fed_curto is not None
tem_fed_longo_eixo = mostrar_fed_longo and fed_longo is not None
usar_secundario = tem_cambio_eixo or tem_juro_eixo or tem_fed_curto_eixo or tem_fed_longo_eixo

if usar_secundario:
    fig = make_subplots(specs=[[{"secondary_y": True}]])
else:
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
        ),
        secondary_y=False if usar_secundario else None,
    )

# CDI acumulado
if mostrar_cdi and cdi_acum is not None:
    fig.add_trace(
        go.Scatter(
            x=cdi_acum.index,
            y=cdi_acum,
            mode="lines",
            name="CDI",
            line=dict(dash="dot", color="gold", width=2),
            hovertemplate="<b>CDI</b><br>"
            + "Data: %{x|%d/%m/%Y}<br>"
            + "Base 100: %{y:.2f}<extra></extra>",
        ),
        secondary_y=False if usar_secundario else None,
    )

# Câmbio USDBRL (valor real, eixo secundário)
if tem_cambio_eixo:
    fig.add_trace(
        go.Scatter(
            x=cambio.index,
            y=cambio,
            mode="lines",
            name="USDBRL",
            line=dict(dash="dash", color="green", width=2),
            hovertemplate="<b>USDBRL</b><br>"
            + "Data: %{x|%d/%m/%Y}<br>"
            + "R$ %{y:.2f}<extra></extra>",
        ),
        secondary_y=True,
    )

# Juro longo (eixo secundário)
if tem_juro_eixo:
    fig.add_trace(
        go.Scatter(
            x=juro_longo.index,
            y=juro_longo,
            mode="lines",
            name="Juro Longo (Swap Pré 5a)",
            line=dict(dash="dashdot", color="red", width=2),
            hovertemplate="<b>Juro Longo</b><br>"
            + "Data: %{x|%d/%m/%Y}<br>"
            + "Taxa: %{y:.2f}% a.a.<extra></extra>",
        ),
        secondary_y=True,
    )

# Fed Funds Rate curto (eixo secundário)
if tem_fed_curto_eixo:
    fig.add_trace(
        go.Scatter(
            x=fed_curto.index,
            y=fed_curto,
            mode="lines",
            name="Fed Rate (T-Bill 13w)",
            line=dict(dash="dot", color="orange", width=2),
            hovertemplate="<b>Fed Rate (curto)</b><br>"
            + "Data: %{x|%d/%m/%Y}<br>"
            + "Taxa: %{y:.2f}%<extra></extra>",
        ),
        secondary_y=True,
    )

# Treasury 5 anos (eixo secundário)
if tem_fed_longo_eixo:
    fig.add_trace(
        go.Scatter(
            x=fed_longo.index,
            y=fed_longo,
            mode="lines",
            name="Treasury 5Y (EUA)",
            line=dict(dash="dot", color="purple", width=2),
            hovertemplate="<b>Treasury 5Y</b><br>"
            + "Data: %{x|%d/%m/%Y}<br>"
            + "Taxa: %{y:.2f}%<extra></extra>",
        ),
        secondary_y=True,
    )

# Label do eixo secundário
if usar_secundario:
    labels = []
    if tem_cambio_eixo:
        labels.append("USDBRL (R$)")
    if tem_juro_eixo or tem_fed_curto_eixo or tem_fed_longo_eixo:
        labels.append("Taxa (% a.a.)")
    fig.update_yaxes(title_text=" / ".join(labels), secondary_y=True)

fig.add_hline(y=100, line_dash="dash", line_color="gray", opacity=0.5)

moeda = "USD" if preco_em_dolar else "BRL"
titulo = f"Performance Comparada — Base 100 ({moeda})"
if ajuste_dividendos:
    titulo += " — com dividendos"

fig.update_layout(
    title=titulo,
    xaxis_title="Data",
    yaxis_title="Base 100",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=600,
    dragmode="pan",
)

st.plotly_chart(
    fig,
    use_container_width=True,
    config={"scrollZoom": False, "modeBarButtonsToRemove": ["zoom2d", "select2d", "lasso2d"]},
)

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

# CDI na tabela
if mostrar_cdi and cdi_acum is not None and len(cdi_acum) >= 2:
    retorno_cdi = cdi_acum.iloc[-1] - 100
    resumo.append(
        {
            "Ativo": "CDI",
            "Retorno (%)": f"{retorno_cdi:+.2f}%",
            "Máx. (%)": f"{cdi_acum.max() - 100:+.2f}%",
            "Mín. (%)": f"{cdi_acum.min() - 100:+.2f}%",
            "Último Valor": f"{cdi_acum.iloc[-1]:.2f}",
        }
    )

if resumo:
    st.dataframe(pd.DataFrame(resumo), use_container_width=True, hide_index=True)
