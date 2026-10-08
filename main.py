"""Ponto de entrada: interface gráfica (padrão) ou linha de comando.

  python main.py                         -> abre o dashboard
  python main.py relatorio               -> gera o próximo relatório pendente
  python main.py relatorio --mes 05/2026 --fotos-sinteticas
  python main.py fotos --mes 05/2026     -> gera fotos ilustrativas do período
  python main.py painel-png --ano 2026   -> exporta os gráficos do dashboard em PNG
  python main.py marcar 01/2026 02/2026  -> marca períodos como já gerados
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from arpe_relatorios.analytics import DashboardAnalytics
from arpe_relatorios.charts import ChartFactory
from arpe_relatorios.config import Config
from arpe_relatorios.models import Periodo
from arpe_relatorios.photos import SyntheticPhotoGenerator
from arpe_relatorios.repository import ExcelRepository
from arpe_relatorios.report import ReportBuilder
from arpe_relatorios.state import ReportStateStore


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--excel", type=Path)
    ap.add_argument("--assets", type=Path)
    ap.add_argument("--saida", type=Path)
    sub = ap.add_subparsers(dest="cmd")
    r = sub.add_parser("relatorio"); r.add_argument("--mes"); r.add_argument("--fotos-sinteticas", action="store_true")
    f = sub.add_parser("fotos"); f.add_argument("--mes", required=True); f.add_argument("--sobrescrever", action="store_true")
    g = sub.add_parser("painel-png"); g.add_argument("--ano", type=int)
    m = sub.add_parser("marcar"); m.add_argument("meses", nargs="+")
    a = ap.parse_args(argv)

    cfg = Config(excel_path=a.excel, assets_dir=a.assets, saida_dir=a.saida)
    if not a.cmd:
        from arpe_relatorios.gui import executar
        executar(cfg)
        return 0

    ds = ExcelRepository(cfg).load()
    estado = ReportStateStore(cfg)
    if a.cmd == "relatorio":
        p = Periodo.parse(a.mes) if a.mes else estado.proximo_pendente(ds)
        if not p:
            print("Nenhum relatório pendente.")
            return 0
        if a.fotos_sinteticas:
            SyntheticPhotoGenerator(cfg).gerar_periodo(ds, p)
        destino = ReportBuilder(cfg, ds).build(p)
        estado.marcar(p, str(destino))
        print(f"Relatório {p.label} gerado em {destino}")
    elif a.cmd == "fotos":
        novas = SyntheticPhotoGenerator(cfg).gerar_periodo(ds, Periodo.parse(a.mes), a.sobrescrever)
        print(f"{len(novas)} fotos ilustrativas criadas em {cfg.assets_dir}")
    elif a.cmd == "painel-png":
        ano = a.ano or ds.periodos()[-1].ano
        cf = ChartFactory(DashboardAnalytics(ds, ano, cfg))
        cfg.saida_dir.mkdir(parents=True, exist_ok=True)
        for nome in ("mensal", "acumulado", "segmentos", "municipios", "nc_evolucao", "nc_frequencia"):
            (cfg.saida_dir / f"painel_{nome}.png").write_bytes(ChartFactory.para_png(getattr(cf, nome)()).read())
        print(f"Gráficos exportados em {cfg.saida_dir}")
    elif a.cmd == "marcar":
        for txt in a.meses:
            estado.marcar(Periodo.parse(txt), "(marcado manualmente)")
        print("Períodos marcados.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
