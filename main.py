"""ARPE · Relatórios de Fiscalização v2.0 – ponto de entrada (interface gráfica e linha de comando)."""
from __future__ import annotations

import argparse
import sys
import threading
import time
import webbrowser

from arpe_relatorios.config import Config, app_dir
from arpe_relatorios.models import Periodo


def cli(args) -> int:
    from arpe_relatorios.server import App
    cfg = Config.carregar(excel_path=args.planilha, saida_dir=args.saida, assets_dir=args.assets)
    app = App(cfg)
    if app.erro:
        print("Erro:", app.erro)
        return 1
    if args.comando == "status":
        s = app.snapshot()
        print(f"Planilha: {s['arquivo']}\nPróximo relatório: {s['proximo_nome'] or '—'}"
              + ("\n(sem histórico: informe o último mês entregue com --baseline MM/AAAA)" if s["sem_historico"] else ""))
        for p in s["periodos"][:12]:
            print(f"  {p['label']}  {p['status_txt']:<22} {p['n_fisc']:>4} fisc.  {p['n_nc']:>3} NC")
        return 0
    if args.baseline:
        app.baseline({"periodo": args.baseline})
    if args.comando == "gerar":
        alvo = args.periodo or app.snapshot()["proximo"]
        if not alvo:
            print("Nenhum relatório pendente.")
            return 0
        r = app.gerar({"periodo": alvo, "pa": args.pa, "sei": args.sei, "fotos_sinteticas": args.sinteticas})
        print(f"Gerado: {r['caminho']}")
        for a in r["avisos"]:
            print(" aviso:", a)
    return 0


def gui(args):
    from arpe_relatorios.server import iniciar
    cfg = Config.carregar(excel_path=args.planilha, saida_dir=args.saida, assets_dir=args.assets)
    srv, url, _ = iniciar(cfg)
    try:
        import webview  # type: ignore
        webview.create_window("ARPE · Relatórios de Fiscalização", url, width=1400, height=900, min_size=(1000, 700))
        webview.start()
    except ImportError:
        print(f"Aplicativo em {url}  (Ctrl+C para encerrar)")
        webbrowser.open(url)
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            pass
    srv.shutdown()


def main():
    ap = argparse.ArgumentParser(description="ARPE · Relatórios de Fiscalização 2.0")
    ap.add_argument("comando", nargs="?", default="gui", choices=["gui", "status", "gerar"])
    ap.add_argument("--planilha"), ap.add_argument("--saida"), ap.add_argument("--assets")
    ap.add_argument("--periodo", help="MM/AAAA (padrão: próximo pendente)")
    ap.add_argument("--baseline", help="último mês já entregue, MM/AAAA")
    ap.add_argument("--pa", default=""), ap.add_argument("--sei", default="")
    ap.add_argument("--sinteticas", action="store_true", help="gera fotos ilustrativas sintéticas quando faltarem")
    a = ap.parse_args()
    sys.exit(cli(a)) if a.comando != "gui" else gui(a)


if __name__ == "__main__":
    main()
