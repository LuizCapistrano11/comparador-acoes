import hashlib
import pickle
import time
from pathlib import Path

import streamlit as st
import yfinance as yf
import pandas as pd
import requests
from datetime import timedelta

# ---------------------------------------------------------------------------
# Cache em disco — sobrevive a restarts do Streamlit
# ---------------------------------------------------------------------------
_CACHE_DIR = Path(__file__).parent / ".cache"
_CACHE_DIR.mkdir(exist_ok=True)

_TTL_PRECO = 4 * 3600       # preços de ativos: 4 horas
_TTL_BCB   = 12 * 3600      # séries do BCB: 12 horas


def _chave(*args):
    return hashlib.md5(str(args).encode()).hexdigest()


def _disk_get(chave):
    path = _CACHE_DIR / f"{chave}.pkl"
    if path.exists() and (time.time() - path.stat().st_mtime) < _TTL_BCB:
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    return None


def _disk_get_preco(chave):
    path = _CACHE_DIR / f"{chave}.pkl"
    if path.exists() and (time.time() - path.stat().st_mtime) < _TTL_PRECO:
        try:
            with open(path, "rb") as f:
                return pickle.load(f)
        except Exception:
            pass
    return None


def _disk_set(chave, valor):
    path = _CACHE_DIR / f"{chave}.pkl"
    try:
        with open(path, "wb") as f:
            pickle.dump(valor, f)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
NOMES = {
    "^BVSP": "Ibovespa",
    "^GSPC": "S&P 500",
    "^DJI": "Dow Jones",
    "^IXIC": "Nasdaq",
    "^RUT": "Russell 2000",
    "^FTSE": "FTSE 100",
    "^N225": "Nikkei 225",
    "^STOXX50E": "Euro Stoxx 50",
    "^HSI": "Hang Seng",
    "USDBRL=X": "Dólar/Real",
    "EURBRL=X": "Euro/Real",
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "GC=F": "Ouro",
    "CL=F": "Petróleo WTI",
    "SI=F": "Prata",
}

TICKERS_POPULARES = [
    "^BVSP", "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA",
    "ABEV3.SA", "WEGE3.SA", "RENT3.SA", "BBAS3.SA", "SUZB3.SA",
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
]

IBOVESPA_TICKERS = [
    "ABEV3.SA", "ALPA4.SA", "AMOB3.SA", "ASAI3.SA", "AZUL4.SA",
    "B3SA3.SA", "BBAS3.SA", "BBDC4.SA", "BBSE3.SA", "BEEF3.SA",
    "BPAC11.SA", "BRAV3.SA", "BRFS3.SA", "BRKM5.SA", "CCRO3.SA",
    "CMIN3.SA", "CMIG4.SA", "COGN3.SA", "CPFE3.SA", "CPLE6.SA",
    "CRFB3.SA", "CSAN3.SA", "CSNA3.SA", "CYRE3.SA", "DXCO3.SA",
    "ELET3.SA", "ELET6.SA", "EMBR3.SA", "ENEV3.SA", "ENGI11.SA",
    "EQTL3.SA", "GGBR4.SA", "GOAU4.SA", "HAPV3.SA", "HYPE3.SA",
    "IGTI11.SA", "IRBR3.SA", "ISAE4.SA", "ITSA4.SA", "ITUB4.SA",
    "JBSS3.SA", "KLBN11.SA", "LREN3.SA", "LWSA3.SA", "MGLU3.SA",
    "MRFG3.SA", "MRVE3.SA", "MULT3.SA", "NTCO3.SA", "PCAR3.SA",
    "PETR3.SA", "PETR4.SA", "PETZ3.SA", "PRIO3.SA", "RADL3.SA",
    "RAIZ4.SA", "RAIL3.SA", "RDOR3.SA", "RENT3.SA", "SANB11.SA",
    "SBSP3.SA", "SLCE3.SA", "SMTO3.SA", "SUZB3.SA", "TAEE11.SA",
    "TIMS3.SA", "TOTS3.SA", "UGPA3.SA", "USIM5.SA", "VALE3.SA",
    "VBBR3.SA", "VIVT3.SA", "WEGE3.SA", "YDUQ3.SA",
]

SP500_TOP50 = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
    "UNH", "JNJ", "V", "XOM", "JPM", "PG", "MA", "HD", "CVX", "MRK",
    "ABBV", "LLY", "PEP", "KO", "COST", "AVGO", "WMT", "MCD", "CSCO",
    "ACN", "TMO", "ABT", "DHR", "CRM", "NFLX", "AMD", "INTC", "CMCSA",
    "VZ", "ADBE", "NKE", "TXN", "PM", "NEE", "UPS", "RTX", "LOW",
    "ORCL", "QCOM", "BA", "CAT", "GS",
]

SMLL_TICKERS = [
    "AERI3.SA", "AESB3.SA", "ALPA4.SA", "ANIM3.SA", "ARZZ3.SA",
    "AZUL4.SA", "BHIA3.SA", "BMOB3.SA", "BPAN4.SA", "BRSR6.SA",
    "CAML3.SA", "CASH3.SA", "CBAV3.SA", "CEAB3.SA", "CIEL3.SA",
    "COGN3.SA", "CPLE6.SA", "CSED3.SA", "CURY3.SA", "CYRE3.SA",
    "DXCO3.SA", "ECOR3.SA", "ELET6.SA", "ENAT3.SA", "EVEN3.SA",
    "EZTC3.SA", "FRAS3.SA", "GMAT3.SA", "GRND3.SA", "HYPE3.SA",
    "IFCM3.SA", "INTB3.SA", "IRBR3.SA", "ITSA4.SA", "JHSF3.SA",
    "KEPL3.SA", "LAVV3.SA", "LEVE3.SA", "LJQQ3.SA", "LOGG3.SA",
    "LUPA3.SA", "LWSA3.SA", "MATD3.SA", "MBLY3.SA", "MDNE3.SA",
    "MEGA3.SA", "MILS3.SA", "MLAS3.SA", "MOVI3.SA", "MRFG3.SA",
    "MRVE3.SA", "MULT3.SA", "MYPK3.SA", "NTCO3.SA", "ODPV3.SA",
    "ONCO3.SA", "ORVR3.SA", "PCAR3.SA", "PETZ3.SA", "PLPL3.SA",
    "PNVL3.SA", "POMO4.SA", "QUAL3.SA", "RAIZ4.SA", "RCSL3.SA",
    "RECV3.SA", "RENT3.SA", "SANB11.SA", "SAPR11.SA", "SEER3.SA",
    "SIMH3.SA", "SLCE3.SA", "SMFT3.SA", "SOMA3.SA", "SQIA3.SA",
    "STBP3.SA", "TEND3.SA", "TGMA3.SA", "TIMS3.SA", "TOTS3.SA",
    "TRIS3.SA", "TTEN3.SA", "TUPY3.SA", "USIM5.SA", "VAMO3.SA",
    "VIVA3.SA", "VLID3.SA", "VULC3.SA", "YDUQ3.SA", "ZAMP3.SA",
]


# ---------------------------------------------------------------------------
# Funções auxiliares
# ---------------------------------------------------------------------------
def nome_amigavel(ticker, nome_busca=None):
    if ticker in NOMES:
        return NOMES[ticker]
    if nome_busca:
        nome = nome_busca
        for sufixo in [" S.A.", " SA", " S/A", " Corp.", " Corporation",
                       " Inc.", " Inc", " Ltd.", " Ltd", " Holdings",
                       " Holding", " - ", " N2", " NM", " ON", " PN",
                       " EDJ", " EJ", " DR3", " UNT"]:
            nome = nome.split(sufixo)[0]
        return nome.strip()
    return ticker.replace(".SA", "")


# ---------------------------------------------------------------------------
# Download de preços — batch (todos os tickers de uma vez)
# ---------------------------------------------------------------------------
@st.cache_data(ttl=_TTL_PRECO)
def baixar_dados(tickers, inicio, fim, auto_adjust):
    """Baixa preços de fechamento em lote via yfinance."""
    chave = _chave("dados", tickers, inicio, fim, auto_adjust)
    cached = _disk_get_preco(chave)
    if cached is not None:
        return cached

    dados = {}
    erros = []
    lista = list(tickers)

    if not lista:
        return dados, erros

    try:
        # Download em lote — muito mais rápido que um por um
        raw = yf.download(
            lista, start=inicio, end=fim,
            progress=False, auto_adjust=auto_adjust,
            group_by="ticker",
        )

        if raw.empty:
            erros.append("Sem dados para o período.")
            return dados, erros

        if len(lista) == 1:
            # yfinance retorna colunas simples quando só há 1 ticker
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            serie = raw["Close"].dropna()
            if not serie.empty:
                dados[lista[0]] = serie
            else:
                erros.append(f"{lista[0]}: sem dados para o período")
        else:
            for ticker in lista:
                try:
                    serie = raw[ticker]["Close"].dropna()
                    if not serie.empty:
                        dados[ticker] = serie
                    else:
                        erros.append(f"{ticker}: sem dados para o período")
                except Exception:
                    erros.append(f"{ticker}: sem dados para o período")

    except Exception as e:
        # Fallback: download individual se o lote falhar
        for ticker in lista:
            try:
                df = yf.download(
                    ticker, start=inicio, end=fim,
                    progress=False, auto_adjust=auto_adjust,
                )
                if not df.empty:
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    dados[ticker] = df["Close"].dropna()
                else:
                    erros.append(f"{ticker}: sem dados para o período")
            except Exception as e2:
                erros.append(f"{ticker}: {e2}")

    resultado = (dados, erros)
    _disk_set(chave, resultado)
    return resultado


# ---------------------------------------------------------------------------
# Séries do BCB — com cache em disco (12 h)
# ---------------------------------------------------------------------------
def _baixar_serie_bcb(serie, inicio_str, fim_str):
    """Baixa série do BCB em blocos de 10 anos com cache em disco."""
    chave = _chave("bcb", serie, inicio_str, fim_str)
    cached = _disk_get(chave)
    if cached is not None:
        return cached

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
        for tentativa in range(3):
            try:
                r = requests.get(url, timeout=60)
                if r.status_code == 200:
                    data = r.json()
                    if isinstance(data, list) and data:
                        frames.append(pd.DataFrame(data))
                break
            except requests.exceptions.ReadTimeout:
                if tentativa == 2:
                    pass
        cursor = bloco_fim + timedelta(days=1)

    if not frames:
        return None

    df = pd.concat(frames, ignore_index=True)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = df["valor"].astype(float)
    df = df.set_index("data").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    resultado = df["valor"]

    _disk_set(chave, resultado)
    return resultado


@st.cache_data(ttl=_TTL_BCB)
def baixar_cdi(inicio, fim):
    serie = _baixar_serie_bcb(12, inicio, fim)
    if serie is None:
        return None
    fator = 1 + serie / 100
    acum = fator.cumprod() * 100 / fator.iloc[0]
    acum.name = "cdi_acum"
    return acum


@st.cache_data(ttl=_TTL_BCB)
def baixar_cdi_diario(inicio, fim):
    return _baixar_serie_bcb(12, inicio, fim)


@st.cache_data(ttl=_TTL_BCB)
def baixar_selic(inicio, fim):
    serie = _baixar_serie_bcb(432, inicio, fim)
    if serie is None:
        return None
    serie.name = "selic"
    return serie


@st.cache_data(ttl=_TTL_PRECO)
def baixar_cambio(inicio, fim):
    df = yf.download("USDBRL=X", start=inicio, end=fim, progress=False)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df["Close"]


@st.cache_data(ttl=_TTL_BCB)
def baixar_juro_longo(inicio, fim):
    serie = _baixar_serie_bcb(7815, inicio, fim)
    if serie is None:
        return None
    idx_diario = pd.bdate_range(start=serie.index[0], end=serie.index[-1])
    serie = serie.reindex(idx_diario).interpolate(method="linear")
    serie.name = "juro_longo"
    return serie


@st.cache_data(ttl=_TTL_PRECO)
def baixar_taxa_yf(ticker, inicio, fim):
    df = yf.download(ticker, start=inicio, end=fim, progress=False)
    if df.empty:
        return None
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    return df["Close"]
