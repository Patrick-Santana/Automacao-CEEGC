"""ARPE · Relatórios de Fiscalização v2.0 – ponto de entrada (interface gráfica e linha de comando)."""
from __future__ import annotations

import argparse
import os
import shutil
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
    if app.problema:
        pr = app.problema
        print(f"{pr['titulo']}\n{pr['mensagem']}\n{pr['dica']}\n(Arquivo: {cfg.excel_path})")
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
        cfg.incluir_mapas = args.com_mapas
        r = app.gerar({"periodo": alvo, "pa": args.pa, "sei": args.sei, "fotos_sinteticas": args.sinteticas})
        print(f"Gerado: {r['caminho']}")
        for a in r["avisos"]:
            print(" aviso:", a)
    return 0


VERSAO = "2.3.1"


def _log(cfg, texto: str):
    from arpe_relatorios.log import registrar
    registrar(cfg.dados_dir, texto)


def _caixa_mensagem(titulo: str, msg: str):
    """Programa sem console (--windowed): erros precisam aparecer numa janela, senão o programa 'não abre' sem explicação."""
    try:
        if sys.platform.startswith("win"):
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, titulo, 0x10)
            return
    except Exception:  # noqa: BLE001
        pass
    print(f"{titulo}\n{msg}", file=sys.stderr)


def _caixa_info(titulo: str, msg: str):
    try:
        if sys.platform.startswith("win"):
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, titulo, 0x40)
            return
    except Exception:  # noqa: BLE001
        pass
    print(msg)


def _porta_ativa(cfg) -> int | None:
    """Se já existe uma instância do usuário rodando, devolve a porta dela (evita abrir o programa duas vezes)."""
    import urllib.request
    try:
        porta = int((cfg.dados_dir / "porta.txt").read_text().strip())
        with urllib.request.urlopen(f"http://127.0.0.1:{porta}/api/ping", timeout=1.5) as r:
            return porta if b'"arpe"' in r.read() else None
    except Exception:  # noqa: BLE001
        return None


def _verificar_carga_interrompida(cfg) -> dict | None:
    """Se sobrou o 'carga.lock', a última carga de planilha derrubou o programa: volta à última planilha que funcionou."""
    trava = cfg.dados_dir / "carga.lock"
    if not trava.exists():
        return None
    try:
        suspeita = trava.read_text(encoding="utf-8").strip()
        trava.unlink()
    except OSError:
        return None
    _log(cfg, f"ATENÇÃO: a carga anterior de '{suspeita}' não terminou (programa fechou durante a carga)")
    if suspeita and str(cfg.excel_path) == suspeita:
        anterior = cfg.planilha_ok if cfg.planilha_ok and cfg.planilha_ok != suspeita else ""
        cfg.excel_path = type(cfg.excel_path)(anterior) if anterior else cfg.base_dir / "DadosFiscalização.xlsx"
        cfg.salvar()
        return dict(codigo="carga_falhou", titulo="A última planilha escolhida travou o programa",
                    mensagem=f"O programa fechou ao carregar “{suspeita}”. " + (
                        f"Voltei para a planilha anterior: {anterior}." if anterior else "Escolha outra planilha."),
                    dica="Se o problema for o arquivo, abra-o no Excel, salve uma cópia nova (.xlsx) e carregue de novo.",
                    detalhe=suspeita)
    return None


def gui(args):
    import faulthandler
    from arpe_relatorios.config import em_rede
    cfg = Config.carregar(excel_path=args.planilha, saida_dir=args.saida, assets_dir=args.assets)
    os.environ.setdefault("MPLCONFIGDIR", str(cfg.dados_dir / "mpl"))
    rede = em_rede(cfg.base_dir)
    _log(cfg, f"v{VERSAO} iniciando · exe={sys.executable} · pasta={cfg.base_dir} · rede={rede} · dados={cfg.dados_dir}")
    try:   # falhas nativas (crash do .NET/WebView2) e travamentos > 90 s deixam a pilha no log
        _fh = open(cfg.dados_dir / "arpe_crash.txt", "w")
        faulthandler.enable(_fh)
        faulthandler.dump_traceback_later(90, file=_fh, exit=False)
    except Exception:  # noqa: BLE001
        _fh = None

    existente = _porta_ativa(cfg)
    if existente:
        _log(cfg, f"instância já aberta na porta {existente}; abrindo o navegador")
        webbrowser.open(f"http://127.0.0.1:{existente}/")
        return

    aviso = _verificar_carga_interrompida(cfg)
    # Executável em pasta de rede: a janela própria (pywebview/.NET) costuma falhar ao carregar DLLs de \\servidor;
    # o navegador padrão é o caminho robusto. --janela força a janela própria.
    modo = "janela" if (args.janela or (not rede and not args.navegador)) else "navegador"
    from arpe_relatorios.server import iniciar
    srv, url, app = iniciar(cfg, modo=modo)
    if aviso:
        app.aviso_inicial = aviso
    _log(cfg, f"servidor local em {url} (a planilha carrega em segundo plano)")
    try:
        (cfg.dados_dir / "porta.txt").write_text(str(srv.server_address[1]))
    except OSError:
        pass

    aberto_em_janela = False
    if modo == "janela":
        storage = None
        try:
            import tempfile
            import webview  # type: ignore
            _log(cfg, f"pywebview {getattr(webview, '__version__', '?')} importado")
            janela = webview.create_window("ARPE · Relatórios de Fiscalização", url, width=1400, height=900, min_size=(1000, 700))
            app.janela = janela
            carregou = threading.Event()
            janela.events.loaded += lambda: carregou.set()

            def vigia_janela():
                # a janela nova pode ficar em branco/oculta (perfil do WebView2 preso por um processo antigo): cai para o navegador
                if not carregou.wait(25):
                    _log(cfg, "a janela não carregou em 25 s; abrindo também no navegador")
                    app.modo = "navegador"
                    app.janela = None
                    app.ultimo_ping = time.time()
                    webbrowser.open(url)
                else:
                    _log(cfg, "janela carregada")
                    if _fh:
                        faulthandler.cancel_dump_traceback_later()
            threading.Thread(target=vigia_janela, daemon=True).start()
            storage = tempfile.mkdtemp(prefix="arpe_wv_")      # perfil novo a cada execução: não colide com processos antigos
            _log(cfg, "abrindo janela própria (pywebview)")
            try:
                webview.start(private_mode=True, storage_path=storage)
            except TypeError:
                webview.start()
            aberto_em_janela = True
            if app.modo == "navegador":                    # caiu para o navegador: segue vivo até a aba fechar
                aberto_em_janela = False
        except Exception as e:  # noqa: BLE001 - qualquer falha da janela cai para o navegador, nunca fecha em silêncio
            import traceback
            _log(cfg, f"janela própria indisponível ({type(e).__name__}: {e}); usando o navegador\n{traceback.format_exc()}")
        finally:
            if storage:
                shutil.rmtree(storage, ignore_errors=True)
    if not aberto_em_janela:
        app.modo = "navegador"
        app.janela = None
        _log(cfg, f"abrindo no navegador: {url}")
        webbrowser.open(url)
        app.ultimo_ping = time.time()
        app.encerrar.wait()          # termina quando a aba é fechada ou o botão "Encerrar" é usado
    srv.shutdown()
    try:
        (cfg.dados_dir / "porta.txt").unlink()
    except OSError:
        pass
    _log(cfg, "encerrado")


def escolher_tk(tipo: str, resultado: str):
    """Processo auxiliar: mostra o seletor do tkinter e grava o caminho escolhido em 'resultado'."""
    caminho = ""
    try:
        import tkinter
        from tkinter import filedialog
        raiz = tkinter.Tk()
        raiz.withdraw()
        raiz.attributes("-topmost", True)
        if tipo == "arquivo":
            caminho = filedialog.askopenfilename(title="Selecione a planilha",
                                                 filetypes=[("Planilha Excel", "*.xlsx *.xlsm"), ("Todos", "*.*")])
        else:
            caminho = filedialog.askdirectory(title="Selecione a pasta")
        raiz.destroy()
    finally:
        with open(resultado, "w", encoding="utf-8") as f:
            f.write(caminho or "")


def main():
    ap = argparse.ArgumentParser(description="ARPE · Relatórios de Fiscalização 2.0")
    ap.add_argument("comando", nargs="?", default="gui", choices=["gui", "status", "gerar"])
    ap.add_argument("--planilha"), ap.add_argument("--saida"), ap.add_argument("--assets")
    ap.add_argument("--periodo", help="MM/AAAA (padrão: próximo pendente)")
    ap.add_argument("--baseline", help="último mês já entregue, MM/AAAA")
    ap.add_argument("--pa", default=""), ap.add_argument("--sei", default="")
    ap.add_argument("--com-mapas", action="store_true", help="inclui as Figuras 01 a 04 (mapas) no relatório")
    ap.add_argument("--janela", action="store_true", help="força a janela própria (pywebview)")
    ap.add_argument("--navegador", action="store_true", help="abre no navegador padrão")
    ap.add_argument("--escolher", choices=["arquivo", "pasta"], help=argparse.SUPPRESS)
    ap.add_argument("--resultado", help=argparse.SUPPRESS)
    ap.add_argument("--criar-atalho", action="store_true", help="cria o atalho na Área de Trabalho e sai")
    ap.add_argument("--sinteticas", action="store_true", help="gera fotos ilustrativas sintéticas quando faltarem")
    a = ap.parse_args()
    if getattr(sys, "frozen", False):                      # --windowed: stdout/stderr não existem
        if sys.stdout is None or sys.stderr is None:
            sys.stdout = sys.stderr = open(os.devnull, "w")
    if a.escolher:
        escolher_tk(a.escolher, a.resultado or os.devnull)
        return
    try:
        if a.criar_atalho:
            from arpe_relatorios.atalho import criar_atalho
            caminho = criar_atalho()
            _caixa_info("ARPE · Relatórios", f"Atalho criado na Área de Trabalho:\n{caminho}")
            return
        sys.exit(cli(a)) if a.comando != "gui" else gui(a)
    except SystemExit:
        raise
    except BaseException as e:  # noqa: BLE001
        import traceback
        cfg = Config.carregar()
        _log(cfg, "ERRO FATAL\n" + traceback.format_exc())
        _caixa_mensagem("ARPE · Relatórios – não foi possível abrir",
                        f"{type(e).__name__}: {e}\n\nDetalhes gravados em:\n{cfg.dados_dir / 'arpe_log.txt'}")
        sys.exit(1)


if __name__ == "__main__":
    main()
