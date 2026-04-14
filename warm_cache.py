"""
Script de pré-aquecimento do cache.

Baixa e armazena em disco todos os dados usados pelo app,
para que o carregamento seja instantâneo ao abrir no celular ou web.

Como executar manualmente:
    python warm_cache.py

Como agendar (rodar todo dia às 7h no Windows):
    1. Abra o Agendador de Tarefas (Task Scheduler)
    2. Criar Tarefa Básica
    3. Disparador: Diário, 07:00
    4. Ação: Iniciar Programa
       Programa: python
       Argumentos: warm_cache.py
       Iniciar em: C:\\Users\\l-ota\\Desktop\\O Investidor Crítico\\comparador-acoes
"""

import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from utils import (
    IBOVESPA_TICKERS, SP500_TOP50, SMLL_TICKERS,
    baixar_dados, baixar_volume_financeiro,
    baixar_cdi, baixar_cdi_diario,
    baixar_selic, baixar_cambio,
    baixar_juro_longo, baixar_taxa_yf,
)

HOJE = str(date.today())
DATA_INICIO = "2000-01-01"
BOLSA_BR = sorted(set(IBOVESPA_TICKERS + SMLL_TICKERS))


def step(label):
    print(f"\n{'─' * 55}")
    print(f"  {label}")
    print(f"{'─' * 55}")


def ok(label, t0):
    print(f"  ✓ {label} ({time.time() - t0:.1f}s)")


print("=" * 55)
print("  Pré-aquecimento do cache — O Investidor Crítico")
print(f"  {HOJE}")
print("=" * 55)

t_total = time.time()

# ------------------------------------------------------------------
step("Bolsa brasileira — preços (139 ativos, desde 2000)")
t = time.time()
baixar_dados(tuple(BOLSA_BR), DATA_INICIO, HOJE, False)   # preço
ok("Preços (sem dividendos)", t)

t = time.time()
baixar_dados(tuple(BOLSA_BR), DATA_INICIO, HOJE, True)    # retorno total
ok("Preços (com dividendos)", t)

# ------------------------------------------------------------------
step("Bolsa brasileira — volume financeiro")
t = time.time()
baixar_volume_financeiro(tuple(BOLSA_BR), DATA_INICIO, HOJE)
ok("Volume financeiro", t)

# ------------------------------------------------------------------
step("S&P 500 (Top 50) — preços")
t = time.time()
baixar_dados(tuple(SP500_TOP50), DATA_INICIO, HOJE, False)
ok("S&P 500 preços", t)

# ------------------------------------------------------------------
step("Séries do BCB (CDI, Selic, Juro Longo)")
t = time.time()
baixar_cdi(DATA_INICIO, HOJE)
baixar_cdi_diario(DATA_INICIO, HOJE)
ok("CDI", t)

t = time.time()
baixar_selic(DATA_INICIO, HOJE)
ok("Selic Meta", t)

t = time.time()
baixar_juro_longo(DATA_INICIO, HOJE)
ok("Juro Longo (Swap Pré 5a)", t)

# ------------------------------------------------------------------
step("Câmbio e taxas americanas")
t = time.time()
baixar_cambio(DATA_INICIO, HOJE)
ok("Câmbio USD/BRL", t)

t = time.time()
baixar_taxa_yf("^IRX", DATA_INICIO, HOJE)
ok("Fed Rate (T-Bill 13w)", t)

t = time.time()
baixar_taxa_yf("^FVX", DATA_INICIO, HOJE)
ok("Treasury 5Y", t)

# ------------------------------------------------------------------
print(f"\n{'=' * 55}")
print(f"  ✅ Cache pré-aquecido em {time.time() - t_total:.0f}s")
print(f"{'=' * 55}\n")
