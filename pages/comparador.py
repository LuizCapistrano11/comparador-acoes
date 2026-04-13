import io
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import date, timedelta

from utils import (
    TICKERS_POPULARES, nome_amigavel,
    baixar_dados, baixar_cdi, baixar_cdi_diario, baixar_selic,
    baixar_cambio, baixar_juro_longo, baixar_taxa_yf,
)

DATA_INICIO_MAX = "2000-01-01"

st.title("Comparador de Ações — Base 100")

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


def _display_name(ticker):
    return nome_amigavel(ticker, st.session_state.nomes_cache.get(ticker))


# --- Sidebar ---
st.sidebar.header("Configurações")

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
                nome_raw = q.get("shortname", simbolo)
                bolsa = q.get("exchDisp", "")
                nome_limpo = nome_amigavel(simbolo, nome_raw)
                label = f"{simbolo} — {nome_limpo} ({bolsa})"
                ja_adicionado = simbolo in st.session_state.tickers_ativos
                st.sidebar.button(
                    f"{'✅' if ja_adicionado else '➕'} {label}",
                    key=f"add_{simbolo}",
                    on_click=adicionar_ticker,
                    args=(simbolo, nome_raw),
                    disabled=ja_adicionado,
                )
    except Exception:
        st.sidebar.caption("Erro na busca. Tente novamente.")

with st.sidebar.expander("Tickers populares"):
    for ticker in TICKERS_POPULARES:
        nome_display = _display_name(ticker)
        ja_adicionado = ticker in st.session_state.tickers_ativos
        st.button(
            f"{'✅' if ja_adicionado else '➕'} {nome_display} ({ticker})",
            key=f"pop_{ticker}",
            on_click=adicionar_ticker,
            args=(ticker,),
            disabled=ja_adicionado,
        )

st.sidebar.markdown("---")

st.sidebar.subheader("Ativos no gráfico")
if st.session_state.tickers_ativos:
    for ticker in list(st.session_state.tickers_ativos):
        nome_display = _display_name(ticker)
        st.sidebar.button(
            f"❌ {nome_display} ({ticker})",
            key=f"rem_{ticker}",
            on_click=remover_ticker,
            args=(ticker,),
        )
else:
    st.sidebar.caption("Nenhum ativo selecionado.")

tickers_selecionados = list(st.session_state.tickers_ativos)

st.sidebar.markdown("---")

# --- Opções de visualização ---
st.sidebar.subheader("Visualização")

ajuste_dividendos = st.sidebar.toggle(
    "Retorno total (com dividendos)", value=False,
    help="Inclui dividendos reinvestidos. Desativado: apenas variação de preço.",
)
preco_em_dolar = st.sidebar.toggle(
    "Converter para dólar (USD)", value=False,
    help="Converte os preços dos ativos para dólar usando o câmbio USDBRL.",
)

st.sidebar.markdown("---")

# --- Benchmarks ---
st.sidebar.subheader("Benchmarks")
mostrar_cdi = st.sidebar.toggle(
    "CDI acumulado", value=True,
    help="Rendimento acumulado do CDI no período (base 100).",
)

st.sidebar.markdown("---")

# --- Indicadores macro ---
st.sidebar.subheader("Indicadores macro")
mostrar_cambio = st.sidebar.toggle(
    "Câmbio (USD/BRL)", value=False,
    help="Cotação do dólar em reais — eixo secundário.",
)
mostrar_selic = st.sidebar.toggle(
    "Selic Meta", value=False,
    help="Taxa Selic Meta definida pelo Copom — eixo secundário.",
)
mostrar_juro_longo = st.sidebar.toggle(
    "Juro longo Brasil (Swap Pré 5a)", value=False,
    help="Swap DI x Pré 5 anos — dados mensais interpolados para diário.",
)
mostrar_fed_curto = st.sidebar.toggle(
    "Fed Rate (T-Bill 13 semanas)", value=False,
    help="Taxa de juros de curto prazo dos EUA — eixo secundário.",
)
mostrar_fed_longo = st.sidebar.toggle(
    "Treasury 5 anos (EUA)", value=False,
    help="Yield do título de 5 anos americano — eixo secundário.",
)

st.sidebar.markdown("---")

# --- Período padrão do slider ---
st.sidebar.subheader("Período padrão")

periodo_opcoes = {
    "1 mês": 30, "3 meses": 90, "6 meses": 180,
    "1 ano": 365, "2 anos": 730, "5 anos": 1825,
    "10 anos": 3650, "15 anos": 5475, "20 anos": 7300,
    "25 anos": 9125, "Máximo": 0,
}

periodo = st.sidebar.selectbox("Período padrão do gráfico", list(periodo_opcoes.keys()), index=8)

# --- Verificação de tickers ---
if not tickers_selecionados:
    st.warning("Selecione ao menos um ticker na barra lateral.")
    st.stop()

# --- Download de TODOS os dados desde 2000 ---
hoje = date.today()

with st.spinner("Baixando dados..."):
    dados, erros = baixar_dados(
        tuple(tickers_selecionados), DATA_INICIO_MAX, str(hoje), ajuste_dividendos,
    )
    cambio_full = None
    if preco_em_dolar or mostrar_cambio:
        cambio_full = baixar_cambio(DATA_INICIO_MAX, str(hoje))

    cdi_full = None
    cdi_diario_full = None
    if mostrar_cdi:
        cdi_diario_full = baixar_cdi_diario(DATA_INICIO_MAX, str(hoje))
        cdi_full = baixar_cdi(DATA_INICIO_MAX, str(hoje))

    selic_full = None
    if mostrar_selic:
        selic_full = baixar_selic(DATA_INICIO_MAX, str(hoje))

    juro_longo_full = None
    if mostrar_juro_longo:
        juro_longo_full = baixar_juro_longo(DATA_INICIO_MAX, str(hoje))

    fed_curto_full = None
    if mostrar_fed_curto:
        fed_curto_full = baixar_taxa_yf("^IRX", DATA_INICIO_MAX, str(hoje))

    fed_longo_full = None
    if mostrar_fed_longo:
        fed_longo_full = baixar_taxa_yf("^FVX", DATA_INICIO_MAX, str(hoje))

if erros:
    for erro in erros:
        st.warning(erro)

if not dados:
    st.error("Não foi possível baixar dados para os tickers selecionados.")
    st.stop()

# Montar DataFrame e ajustar início ao dado mais antigo disponível
df_precos_full = pd.DataFrame(dados).dropna(how="all")
data_inicio_efetiva = df_precos_full.apply(lambda col: col.dropna().index[0]).max()
df_precos_full = df_precos_full.loc[data_inicio_efetiva:].dropna(how="all")

if df_precos_full.empty:
    st.error("Não há dados suficientes para o período e ativos selecionados.")
    st.stop()

# --- Slider com histórico máximo disponível ---
data_min = df_precos_full.index[0].date()
data_max = df_precos_full.index[-1].date()

dias_padrao = periodo_opcoes[periodo]
if dias_padrao == 0:
    default_ini = data_min
else:
    default_ini = max(data_min, hoje - timedelta(days=dias_padrao))
default_fim = data_max

janela = st.slider(
    "Ajuste a janela de análise",
    min_value=data_min,
    max_value=data_max,
    value=(default_ini, default_fim),
    format="DD/MM/YYYY",
)
dt_ini = pd.Timestamp(janela[0])
dt_end = pd.Timestamp(janela[1])

# --- Fatiar tudo pela janela do slider ---
def _slice(serie):
    if serie is None:
        return None
    s = serie.loc[(serie.index >= dt_ini) & (serie.index <= dt_end)]
    return s if not s.empty else None

df_precos = df_precos_full.loc[dt_ini:dt_end]
cambio = _slice(cambio_full)
cdi_diario = _slice(cdi_diario_full)
cdi_acum = _slice(cdi_full)
selic = _slice(selic_full)
juro_longo = _slice(juro_longo_full)
fed_curto = _slice(fed_curto_full)
fed_longo = _slice(fed_longo_full)

if cdi_acum is not None and len(cdi_acum) >= 2:
    cdi_acum = cdi_acum / cdi_acum.iloc[0] * 100

if df_precos.empty or len(df_precos) < 2:
    st.warning("Janela muito curta — selecione um intervalo maior.")
    st.stop()

# --- Converter para dólar ---
if preco_em_dolar and cambio is not None:
    cambio_al = cambio.reindex(df_precos.index, method="ffill")
    df_precos = df_precos.div(cambio_al, axis=0).dropna(how="all")
    if cdi_acum is not None:
        cambio_cdi = cambio.reindex(cdi_acum.index, method="ffill")
        cdi_em_usd = cdi_acum / cambio_cdi
        cdi_acum = cdi_em_usd / cdi_em_usd.dropna().iloc[0] * 100

# --- Base 100 ---
df_base100 = (df_precos / df_precos.iloc[0]) * 100

# --- Gráfico ---
tem_cambio_eixo = mostrar_cambio and cambio is not None
tem_selic_eixo = mostrar_selic and selic is not None
tem_juro_eixo = mostrar_juro_longo and juro_longo is not None
tem_fed_curto_eixo = mostrar_fed_curto and fed_curto is not None
tem_fed_longo_eixo = mostrar_fed_longo and fed_longo is not None
usar_secundario = (
    tem_cambio_eixo or tem_selic_eixo or tem_juro_eixo
    or tem_fed_curto_eixo or tem_fed_longo_eixo
)

fig = make_subplots(specs=[[{"secondary_y": True}]]) if usar_secundario else go.Figure()

for col in df_base100.columns:
    nome = nome_amigavel(col, st.session_state.nomes_cache.get(col))
    fig.add_trace(
        go.Scatter(
            x=df_base100.index, y=df_base100[col],
            mode="lines", name=nome,
            hovertemplate=f"<b>{nome}</b><br>Data: %{{x|%d/%m/%Y}}<br>Base 100: %{{y:.2f}}<extra></extra>",
        ),
        secondary_y=False if usar_secundario else None,
    )

if mostrar_cdi and cdi_acum is not None:
    fig.add_trace(
        go.Scatter(
            x=cdi_acum.index, y=cdi_acum, mode="lines", name="CDI",
            line=dict(dash="dot", color="gold", width=2),
            hovertemplate="<b>CDI</b><br>Data: %{x|%d/%m/%Y}<br>Base 100: %{y:.2f}<extra></extra>",
        ),
        secondary_y=False if usar_secundario else None,
    )

if tem_cambio_eixo:
    fig.add_trace(
        go.Scatter(
            x=cambio.index, y=cambio, mode="lines", name="Câmbio USD/BRL",
            line=dict(dash="dash", color="green", width=2),
            hovertemplate="<b>USD/BRL</b><br>Data: %{x|%d/%m/%Y}<br>R$ %{y:.2f}<extra></extra>",
        ),
        secondary_y=True,
    )
if tem_selic_eixo:
    fig.add_trace(
        go.Scatter(
            x=selic.index, y=selic, mode="lines", name="Selic Meta",
            line=dict(dash="dot", color="darkgoldenrod", width=2),
            hovertemplate="<b>Selic Meta</b><br>Data: %{x|%d/%m/%Y}<br>Taxa: %{y:.2f}% a.a.<extra></extra>",
        ),
        secondary_y=True,
    )
if tem_juro_eixo:
    fig.add_trace(
        go.Scatter(
            x=juro_longo.index, y=juro_longo, mode="lines", name="Juro Longo BR (Swap 5a)",
            line=dict(dash="dashdot", color="red", width=2),
            hovertemplate="<b>Juro Longo BR</b><br>Data: %{x|%d/%m/%Y}<br>Taxa: %{y:.2f}% a.a.<extra></extra>",
        ),
        secondary_y=True,
    )
if tem_fed_curto_eixo:
    fig.add_trace(
        go.Scatter(
            x=fed_curto.index, y=fed_curto, mode="lines", name="Fed Rate (curto)",
            line=dict(dash="dot", color="orange", width=2),
            hovertemplate="<b>Fed Rate</b><br>Data: %{x|%d/%m/%Y}<br>Taxa: %{y:.2f}%<extra></extra>",
        ),
        secondary_y=True,
    )
if tem_fed_longo_eixo:
    fig.add_trace(
        go.Scatter(
            x=fed_longo.index, y=fed_longo, mode="lines", name="Treasury 5Y (EUA)",
            line=dict(dash="dot", color="purple", width=2),
            hovertemplate="<b>Treasury 5Y</b><br>Data: %{x|%d/%m/%Y}<br>Taxa: %{y:.2f}%<extra></extra>",
        ),
        secondary_y=True,
    )

if usar_secundario:
    labels = []
    if tem_cambio_eixo:
        labels.append("USD/BRL (R$)")
    if tem_selic_eixo or tem_juro_eixo or tem_fed_curto_eixo or tem_fed_longo_eixo:
        labels.append("Taxa (% a.a.)")
    fig.update_yaxes(title_text=" / ".join(labels), secondary_y=True)

fig.add_hline(y=100, line_dash="dash", line_color="gray", opacity=0.5)

moeda = "USD" if preco_em_dolar else "BRL"
titulo = f"Performance Comparada — Base 100 ({moeda})"
if ajuste_dividendos:
    titulo += " — com dividendos"

fig.update_layout(
    title=titulo, xaxis_title="Data", yaxis_title="Base 100",
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    height=600, dragmode="pan",
)

st.plotly_chart(
    fig, use_container_width=True,
    config={"scrollZoom": False, "modeBarButtonsToRemove": ["zoom2d", "select2d", "lasso2d"]},
)

# --- Download dos dados ---
moeda_label = "USD" if preco_em_dolar else "BRL"

df_b100_dl = pd.DataFrame()
for col in df_base100.columns:
    nome = nome_amigavel(col, st.session_state.nomes_cache.get(col))
    df_b100_dl[f"{nome} (base 100)"] = df_base100[col]
if mostrar_cdi and cdi_acum is not None:
    df_b100_dl["CDI (base 100)"] = cdi_acum
if tem_cambio_eixo:
    cambio_b100 = (cambio / cambio.dropna().iloc[0]) * 100
    df_b100_dl["Câmbio USD/BRL (base 100)"] = cambio_b100

df_precos_dl = pd.DataFrame()
for col in df_precos.columns:
    nome = nome_amigavel(col, st.session_state.nomes_cache.get(col))
    df_precos_dl[f"{nome} ({moeda_label})"] = df_precos[col]

df_ind = pd.DataFrame()
if mostrar_cdi and cdi_diario is not None:
    df_ind["CDI (taxa diária %)"] = cdi_diario
if tem_cambio_eixo:
    df_ind["Câmbio USD/BRL (R$)"] = cambio
if tem_selic_eixo:
    df_ind["Selic Meta (% a.a.)"] = selic
if tem_juro_eixo:
    df_ind["Juro Longo BR — Swap Pré 5a (% a.a.)"] = juro_longo
if tem_fed_curto_eixo:
    df_ind["Fed Rate — T-Bill 13w (%)"] = fed_curto
if tem_fed_longo_eixo:
    df_ind["Treasury 5Y EUA (%)"] = fed_longo

df_download = pd.concat([df_b100_dl, df_precos_dl, df_ind], axis=1)
df_download.index.name = "Data"

col_csv, col_xlsx, _ = st.columns([1, 1, 6], gap="small")

csv_buffer = df_download.to_csv(decimal=",", sep=";")
col_csv.download_button(
    label="Baixar CSV", data=csv_buffer,
    file_name="comparador_acoes.csv", mime="text/csv",
)

xlsx_buffer = io.BytesIO()
with pd.ExcelWriter(xlsx_buffer, engine="openpyxl") as writer:
    df_download.to_excel(writer, sheet_name="Dados")
xlsx_buffer.seek(0)
col_xlsx.download_button(
    label="Baixar Excel", data=xlsx_buffer,
    file_name="comparador_acoes.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# --- Resumo ---
st.subheader("Resumo do Período")

resumo = []
for col in df_base100.columns:
    nome = nome_amigavel(col, st.session_state.nomes_cache.get(col))
    serie = df_base100[col].dropna()
    if len(serie) < 2:
        continue
    resumo.append({
        "Ativo": nome,
        "Retorno (%)": f"{serie.iloc[-1] - 100:+.2f}%",
        "Máx. (%)": f"{serie.max() - 100:+.2f}%",
        "Mín. (%)": f"{serie.min() - 100:+.2f}%",
        "Último Valor": f"{serie.iloc[-1]:.2f}",
    })

if mostrar_cdi and cdi_acum is not None and len(cdi_acum) >= 2:
    resumo.append({
        "Ativo": "CDI",
        "Retorno (%)": f"{cdi_acum.iloc[-1] - 100:+.2f}%",
        "Máx. (%)": f"{cdi_acum.max() - 100:+.2f}%",
        "Mín. (%)": f"{cdi_acum.min() - 100:+.2f}%",
        "Último Valor": f"{cdi_acum.iloc[-1]:.2f}",
    })

if resumo:
    st.dataframe(pd.DataFrame(resumo), use_container_width=True, hide_index=True)
