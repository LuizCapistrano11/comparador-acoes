import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from datetime import date, timedelta

from utils import (
    IBOVESPA_TICKERS, SP500_TOP50, SMLL_TICKERS,
    nome_amigavel, baixar_dados, baixar_cdi, baixar_cdi_diario,
    baixar_selic, baixar_cambio, baixar_juro_longo, baixar_taxa_yf,
)

st.title("Análise de Ativos")

DATA_INICIO_MAX = "2000-01-01"

BOLSA_BR = sorted(set(IBOVESPA_TICKERS + SMLL_TICKERS))

UNIVERSOS = {
    "Ibovespa": IBOVESPA_TICKERS,
    "Small Caps (SMLL)": SMLL_TICKERS,
    "Bolsa brasileira (Ibov + SMLL)": BOLSA_BR,
    "S&P 500 (Top 50)": SP500_TOP50,
}

METRICAS = {
    "Retorno de preço": "retorno_preco",
    "Retorno total (com dividendos)": "retorno_total",
    "Retorno vs CDI (alpha)": "alpha_cdi",
    "Retorno vs Ibovespa (alpha)": "alpha_ibov",
    "Volatilidade anualizada": "volatilidade",
    "Drawdown máximo": "drawdown_max",
    "Sharpe (retorno / volatilidade)": "sharpe",
    "Liquidez (volume médio 3 meses, R$)": "liquidez",
}

# --- Sidebar: período do ranking ---
st.sidebar.header("Período do ranking")

PERIODOS = {
    "1 mês": 30, "3 meses": 90, "6 meses": 180,
    "1 ano": 365, "2 anos": 730, "3 anos": 1095,
    "5 anos": 1825, "10 anos": 3650, "15 anos": 5475,
    "20 anos": 7300, "25 anos": 9125,
}

periodo_nome = st.sidebar.selectbox("Período", list(PERIODOS.keys()), index=3)
dias = PERIODOS[periodo_nome]
data_fim = date.today()
data_inicio = data_fim - timedelta(days=dias)

st.sidebar.caption(
    f"Ranking calculado de {data_inicio.strftime('%d/%m/%Y')} "
    f"a {data_fim.strftime('%d/%m/%Y')}"
)

# --- Sidebar: visualização ---
st.sidebar.markdown("---")
st.sidebar.subheader("Visualização")

preco_em_dolar = st.sidebar.toggle(
    "Converter para dólar (USD)", value=False,
    help="Converte os preços para dólar usando o câmbio USDBRL.",
    key="analise_dolar",
)

# --- Sidebar: benchmarks ---
st.sidebar.markdown("---")
st.sidebar.subheader("Benchmarks")

mostrar_cdi = st.sidebar.toggle(
    "CDI acumulado", value=False,
    help="Rendimento acumulado do CDI no período (base 100).",
    key="analise_cdi",
)

# --- Sidebar: indicadores macro ---
st.sidebar.markdown("---")
st.sidebar.subheader("Indicadores macro")

mostrar_cambio = st.sidebar.toggle(
    "Câmbio (USD/BRL)", value=False,
    help="Cotação do dólar em reais — eixo secundário.",
    key="analise_cambio",
)
mostrar_selic = st.sidebar.toggle(
    "Selic Meta", value=False,
    help="Taxa Selic Meta definida pelo Copom — eixo secundário.",
    key="analise_selic",
)
mostrar_juro_longo = st.sidebar.toggle(
    "Juro longo Brasil (Swap Pré 5a)", value=False,
    help="Swap DI x Pré 5 anos — interpolado para frequência diária.",
    key="analise_juro_longo",
)
mostrar_fed_curto = st.sidebar.toggle(
    "Fed Rate (T-Bill 13 semanas)", value=False,
    help="Taxa de juros de curto prazo dos EUA.",
    key="analise_fed_curto",
)
mostrar_fed_longo = st.sidebar.toggle(
    "Treasury 5 anos (EUA)", value=False,
    help="Yield do título de 5 anos americano.",
    key="analise_fed_longo",
)


# =====================================================================
# Helpers
# =====================================================================

def _slider_janela(df_full, data_inicio_ranking, data_fim_ranking, key):
    """
    Exibe slider cobrindo todo o histórico disponível.
    Default = janela do ranking. Retorna (dt_ini, dt_end) como Timestamps.
    """
    datas = df_full.dropna(how="all").index
    if len(datas) < 2:
        return pd.Timestamp(data_inicio_ranking), pd.Timestamp(data_fim_ranking)

    data_min = datas[0].date()
    data_max = datas[-1].date()

    # Default: recortar ao período do ranking (mas slider vai do máximo disponível)
    default_ini = max(data_min, data_inicio_ranking)
    default_fim = min(data_max, data_fim_ranking)

    janela = st.slider(
        "Ajuste a janela do gráfico",
        min_value=data_min,
        max_value=data_max,
        value=(default_ini, default_fim),
        format="DD/MM/YYYY",
        key=key,
    )
    return pd.Timestamp(janela[0]), pd.Timestamp(janela[1])


def plotar_base100_com_macro(df_precos_janela, titulo_chart, chart_inicio, chart_fim, key_prefix):
    """
    Plota base 100 com indicadores macro.
    df_precos_janela: DataFrame já fatiado pela janela do slider.
    chart_inicio/fim: strings de data para baixar macro nessa janela.
    """
    inicio_str = str(chart_inicio.date()) if hasattr(chart_inicio, "date") else str(chart_inicio)
    fim_str = str(chart_fim.date()) if hasattr(chart_fim, "date") else str(chart_fim)

    cambio = None
    if preco_em_dolar or mostrar_cambio:
        cambio = baixar_cambio(inicio_str, fim_str)

    cdi_acum = None
    if mostrar_cdi:
        cdi_acum = baixar_cdi(inicio_str, fim_str)

    selic = None
    if mostrar_selic:
        selic = baixar_selic(inicio_str, fim_str)

    juro_longo = None
    if mostrar_juro_longo:
        juro_longo = baixar_juro_longo(inicio_str, fim_str)

    fed_curto = None
    if mostrar_fed_curto:
        fed_curto = baixar_taxa_yf("^IRX", inicio_str, fim_str)

    fed_longo = None
    if mostrar_fed_longo:
        fed_longo = baixar_taxa_yf("^FVX", inicio_str, fim_str)

    df_top = df_precos_janela.dropna(how="all").copy()
    if df_top.empty:
        st.error("Sem dados para plotar.")
        return

    # Converter para dólar
    if preco_em_dolar and cambio is not None:
        cambio_al = cambio.reindex(df_top.index, method="ffill")
        df_top = df_top.div(cambio_al, axis=0).dropna(how="all")
        if cdi_acum is not None:
            cambio_cdi = cambio.reindex(cdi_acum.index, method="ffill")
            cdi_em_usd = cdi_acum / cambio_cdi
            cdi_acum = cdi_em_usd / cdi_em_usd.dropna().iloc[0] * 100

    # Base 100
    df_base100 = (df_top / df_top.iloc[0]) * 100
    if cdi_acum is not None:
        cdi_acum = cdi_acum / cdi_acum.dropna().iloc[0] * 100

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
        nome = nome_amigavel(col)
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
    fig.update_layout(
        title=f"{titulo_chart} (Base 100, {moeda})",
        xaxis_title="Data", yaxis_title="Base 100",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        height=500, dragmode="pan",
    )
    st.plotly_chart(
        fig, use_container_width=True,
        config={"scrollZoom": False, "modeBarButtonsToRemove": ["zoom2d", "select2d", "lasso2d"]},
    )


def _calcular_metricas(ticker, serie, cdi_para_analise, ibov_para_analise,
                       data_inicio_r, data_fim_r):
    serie = serie.dropna()
    if len(serie) < 20:
        return None

    nome = nome_amigavel(ticker)
    retorno_pct = (serie.iloc[-1] / serie.iloc[0] - 1) * 100
    retornos_diarios = serie.pct_change().dropna()
    vol = retornos_diarios.std() * (252 ** 0.5) * 100

    pico = serie.cummax()
    dd_max = (((serie - pico) / pico) * 100).min()

    try:
        df_vol = yf.download(
            ticker, start=data_inicio_r, end=data_fim_r,
            progress=False, auto_adjust=False,
        )
        if isinstance(df_vol.columns, pd.MultiIndex):
            df_vol.columns = df_vol.columns.get_level_values(0)
        if not df_vol.empty and "Volume" in df_vol.columns and "Close" in df_vol.columns:
            liquidez_3m = (df_vol["Volume"] * df_vol["Close"]).tail(63).mean()
        else:
            liquidez_3m = 0
    except Exception:
        liquidez_3m = 0

    alpha_cdi_val = None
    if cdi_para_analise is not None and len(cdi_para_analise) >= 2:
        cdi_ret = (cdi_para_analise.iloc[-1] / cdi_para_analise.iloc[0] - 1) * 100
        alpha_cdi_val = retorno_pct - cdi_ret

    alpha_ibov_val = None
    if ibov_para_analise is not None and len(ibov_para_analise) >= 2:
        ibov_ret = (ibov_para_analise.iloc[-1] / ibov_para_analise.iloc[0] - 1) * 100
        alpha_ibov_val = retorno_pct - ibov_ret

    sharpe_val = None
    if cdi_para_analise is not None and len(cdi_para_analise) >= 2 and vol > 0:
        cdi_ret = (cdi_para_analise.iloc[-1] / cdi_para_analise.iloc[0] - 1) * 100
        sharpe_val = (retorno_pct - cdi_ret) / vol

    return {
        "ticker": ticker,
        "Ativo": nome,
        "Retorno (%)": retorno_pct,
        "Volatilidade (% a.a.)": vol,
        "Drawdown Máx. (%)": dd_max,
        "Sharpe": sharpe_val,
        "Alpha vs CDI (%)": alpha_cdi_val,
        "Alpha vs Ibov (%)": alpha_ibov_val,
        "Liquidez Média 3M (R$)": liquidez_3m,
    }


def _formatar_tabela(df_resultados):
    df_display = df_resultados[["Ativo"]].copy()
    df_display["Retorno"] = df_resultados["Retorno (%)"].map(lambda x: f"{x:+.2f}%")
    df_display["Volatilidade"] = df_resultados["Volatilidade (% a.a.)"].map(lambda x: f"{x:.2f}%")
    df_display["Drawdown Máx."] = df_resultados["Drawdown Máx. (%)"].map(lambda x: f"{x:.2f}%")
    if df_resultados["Sharpe"].notna().any():
        df_display["Sharpe"] = df_resultados["Sharpe"].map(
            lambda x: f"{x:.2f}" if pd.notna(x) else "—"
        )
    if df_resultados["Alpha vs CDI (%)"].notna().any():
        df_display["Alpha vs CDI"] = df_resultados["Alpha vs CDI (%)"].map(
            lambda x: f"{x:+.2f}%" if pd.notna(x) else "—"
        )
    if df_resultados["Alpha vs Ibov (%)"].notna().any():
        df_display["Alpha vs Ibov"] = df_resultados["Alpha vs Ibov (%)"].map(
            lambda x: f"{x:+.2f}%" if pd.notna(x) else "—"
        )
    df_display["Liquidez 3M (R$)"] = df_resultados["Liquidez Média 3M (R$)"].map(
        lambda x: f"{x:,.0f}".replace(",", ".") if x else "—"
    )
    return df_display


# =====================================================================
# Abas
# =====================================================================
tab_ranking, tab_cdi = st.tabs(["Ranking de ativos", "Ações que bateram o CDI"])

# =====================================================================
# ABA 1 — Ranking de ativos
# =====================================================================
with tab_ranking:
    col_a1, col_a2 = st.columns(2)
    universo_nome = col_a1.selectbox("Universo de ativos", list(UNIVERSOS.keys()))
    metrica_nome = col_a2.selectbox("Métrica de ranking", list(METRICAS.keys()))

    col_a3, col_a4 = st.columns(2)
    top_n = col_a3.slider("Quantidade de ativos", min_value=3, max_value=20, value=5)
    direcao = col_a4.radio("Ordenação", ["Melhores", "Piores"], horizontal=True)

    if st.button("Rodar análise", key="btn_ranking"):
        metrica_key = METRICAS[metrica_nome]
        universo = UNIVERSOS[universo_nome]

        with st.spinner(f"Analisando {len(universo)} ativos..."):
            use_adj = metrica_key == "retorno_total"

            # Baixar dados para o período do ranking
            dados_rank, _ = baixar_dados(
                tuple(universo), data_inicio, data_fim, use_adj,
            )
            if not dados_rank:
                st.error("Não foi possível baixar dados do universo selecionado.")
                st.stop()

            cdi_para_analise = None
            if metrica_key in ("alpha_cdi", "sharpe"):
                cdi_para_analise = baixar_cdi(str(data_inicio), str(data_fim))

            ibov_para_analise = None
            if metrica_key == "alpha_ibov":
                df_ibov = yf.download(
                    "^BVSP", start=data_inicio, end=data_fim,
                    progress=False, auto_adjust=use_adj,
                )
                if not df_ibov.empty:
                    if isinstance(df_ibov.columns, pd.MultiIndex):
                        df_ibov.columns = df_ibov.columns.get_level_values(0)
                    ibov_para_analise = df_ibov["Close"]

            # Calcular métricas e ranking
            resultados = []
            for ticker, serie in dados_rank.items():
                r = _calcular_metricas(
                    ticker, serie, cdi_para_analise, ibov_para_analise,
                    data_inicio, data_fim,
                )
                if r is None:
                    continue

                if metrica_key in ("retorno_preco", "retorno_total"):
                    r["_ranking"] = r["Retorno (%)"]
                elif metrica_key == "alpha_cdi":
                    r["_ranking"] = r["Alpha vs CDI (%)"] if r["Alpha vs CDI (%)"] is not None else -9999
                elif metrica_key == "alpha_ibov":
                    r["_ranking"] = r["Alpha vs Ibov (%)"] if r["Alpha vs Ibov (%)"] is not None else -9999
                elif metrica_key == "volatilidade":
                    r["_ranking"] = r["Volatilidade (% a.a.)"]
                elif metrica_key == "drawdown_max":
                    r["_ranking"] = r["Drawdown Máx. (%)"]
                elif metrica_key == "sharpe":
                    r["_ranking"] = r["Sharpe"] if r["Sharpe"] is not None else -9999
                elif metrica_key == "liquidez":
                    r["_ranking"] = r["Liquidez Média 3M (R$)"]
                else:
                    r["_ranking"] = r["Retorno (%)"]
                resultados.append(r)

            if not resultados:
                st.error("Nenhum ativo com dados suficientes no período.")
                st.stop()

            df_resultados = pd.DataFrame(resultados)
            ascendente = direcao == "Piores"
            if metrica_key == "volatilidade":
                ascendente = direcao == "Melhores"
            if metrica_key == "drawdown_max":
                ascendente = direcao == "Piores"

            df_resultados = df_resultados.sort_values("_ranking", ascending=ascendente).head(top_n)

            label = "Top" if direcao == "Melhores" else "Bottom"
            st.subheader(f"{label} {top_n} — {metrica_nome}")
            st.dataframe(_formatar_tabela(df_resultados), use_container_width=True, hide_index=True)

            # --- Gráfico com slider de histórico máximo ---
            st.subheader("Performance comparada")
            tickers_top = df_resultados["ticker"].tolist()

            dados_full, _ = baixar_dados(
                tuple(tickers_top), DATA_INICIO_MAX, str(data_fim), use_adj,
            )
            df_full = pd.DataFrame(
                {t: dados_full[t] for t in tickers_top if t in dados_full}
            ).dropna(how="all")

            if not df_full.empty:
                dt_ini, dt_end = _slider_janela(df_full, data_inicio, data_fim, "slider_ranking")
                df_janela = df_full.loc[dt_ini:dt_end]

                if not df_janela.empty and len(df_janela) >= 2:
                    plotar_base100_com_macro(
                        df_janela,
                        f"{label} {top_n} — {metrica_nome}",
                        dt_ini, dt_end,
                        key_prefix="ranking",
                    )

# =====================================================================
# ABA 2 — Ações que bateram o CDI
# =====================================================================
with tab_cdi:
    st.markdown(
        "Lista todas as ações brasileiras (Ibovespa + Small Caps) cujo retorno "
        "superou o CDI acumulado no período selecionado na barra lateral."
    )

    col_c1, col_c2 = st.columns(2)
    usar_retorno_total = col_c1.toggle(
        "Considerar dividendos", value=False,
        help="Usa retorno total (com dividendos reinvestidos).",
        key="cdi_dividendos",
    )
    top_n_chart = col_c2.slider(
        "Ativos no gráfico (top alpha)",
        min_value=3, max_value=30, value=10,
        help="Quantos ativos exibir no gráfico (ordenados por maior alpha vs CDI).",
        key="cdi_top_chart",
    )

    if st.button("Buscar ações que bateram o CDI", key="btn_cdi"):
        with st.spinner(f"Analisando {len(BOLSA_BR)} ações contra o CDI..."):
            cdi_acum_ref = baixar_cdi(str(data_inicio), str(data_fim))
            if cdi_acum_ref is None or len(cdi_acum_ref) < 2:
                st.error("Não foi possível baixar dados do CDI para o período.")
                st.stop()

            cdi_retorno_pct = (cdi_acum_ref.iloc[-1] / cdi_acum_ref.iloc[0] - 1) * 100

            dados_br, _ = baixar_dados(
                tuple(BOLSA_BR), data_inicio, data_fim, usar_retorno_total,
            )
            if not dados_br:
                st.error("Não foi possível baixar dados das ações.")
                st.stop()

            vencedores = []
            perdedores_count = 0
            sem_dados_count = 0

            for ticker, serie in dados_br.items():
                serie = serie.dropna()
                if len(serie) < 20:
                    sem_dados_count += 1
                    continue

                retorno_pct = (serie.iloc[-1] / serie.iloc[0] - 1) * 100
                alpha = retorno_pct - cdi_retorno_pct
                retornos_diarios = serie.pct_change().dropna()
                vol = retornos_diarios.std() * (252 ** 0.5) * 100
                pico = serie.cummax()
                dd_max = (((serie - pico) / pico) * 100).min()

                if retorno_pct > cdi_retorno_pct:
                    vencedores.append({
                        "ticker": ticker,
                        "Ativo": nome_amigavel(ticker),
                        "Retorno (%)": retorno_pct,
                        "CDI (%)": cdi_retorno_pct,
                        "Alpha vs CDI (%)": alpha,
                        "Volatilidade (% a.a.)": vol,
                        "Drawdown Máx. (%)": dd_max,
                    })
                else:
                    perdedores_count += 1

            total_analisados = len(vencedores) + perdedores_count
            st.markdown(
                f"**{len(vencedores)}** de **{total_analisados}** ações bateram o CDI "
                f"(**{cdi_retorno_pct:+.2f}%**) no período.  \n"
                f"{perdedores_count} ficaram abaixo do CDI"
                + (f" e {sem_dados_count} não tinham dados suficientes." if sem_dados_count else ".")
            )

            if not vencedores:
                st.info("Nenhuma ação bateu o CDI no período selecionado.")
                st.stop()

            df_venc = pd.DataFrame(vencedores).sort_values("Alpha vs CDI (%)", ascending=False)

            df_show = df_venc[["Ativo"]].copy()
            df_show["Retorno"] = df_venc["Retorno (%)"].map(lambda x: f"{x:+.2f}%")
            df_show["CDI"] = df_venc["CDI (%)"].map(lambda x: f"{x:+.2f}%")
            df_show["Alpha vs CDI"] = df_venc["Alpha vs CDI (%)"].map(lambda x: f"{x:+.2f}%")
            df_show["Volatilidade"] = df_venc["Volatilidade (% a.a.)"].map(lambda x: f"{x:.2f}%")
            df_show["Drawdown Máx."] = df_venc["Drawdown Máx. (%)"].map(lambda x: f"{x:.2f}%")
            st.dataframe(df_show, use_container_width=True, hide_index=True)

            # --- Gráfico com slider de histórico máximo ---
            st.subheader("Performance comparada (top alpha vs CDI)")
            tickers_chart = df_venc["ticker"].head(top_n_chart).tolist()

            dados_full, _ = baixar_dados(
                tuple(tickers_chart), DATA_INICIO_MAX, str(data_fim), usar_retorno_total,
            )
            df_full = pd.DataFrame(
                {t: dados_full[t] for t in tickers_chart if t in dados_full}
            ).dropna(how="all")

            if not df_full.empty:
                dt_ini, dt_end = _slider_janela(df_full, data_inicio, data_fim, "slider_cdi")
                df_janela = df_full.loc[dt_ini:dt_end]

                if not df_janela.empty and len(df_janela) >= 2:
                    plotar_base100_com_macro(
                        df_janela,
                        f"Top {min(top_n_chart, len(tickers_chart))} ações que bateram o CDI",
                        dt_ini, dt_end,
                        key_prefix="cdi",
                    )
