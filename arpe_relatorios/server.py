"""Servidor local (somente 127.0.0.1) que alimenta a interface web do aplicativo."""
from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import numpy as np
import pandas as pd

from .analytics import DashboardAnalytics
from .config import MESES_ABREV, MESES_NOME, Config, em_rede, resource_dir
from .log import registrar
from .models import Dataset, Periodo
from .relatorio import Opcoes, RelatorioBuilder
from .repository import ExcelRepository
from .state import ReportStateStore

WEB = resource_dir() / "arpe_relatorios" / "web"
STATUS_TXT = {"gerado": "Gerado", "historico": "Já entregue", "planilha": "Concluído na planilha", "pendente": "Pendente"}


def _jsonable(v):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if np.isnan(v) else float(v)
    return v


def df_json(df: pd.DataFrame) -> dict:
    return {"colunas": [str(c) for c in df.columns], "linhas": [
        {"nome": str(i), "valores": [_jsonable(x) for x in r]} for i, r in zip(df.index, df.itertuples(index=False))]}


def traduzir_erro(exc: BaseException, caminho=None) -> dict:
    """Converte exceções técnicas em mensagens compreensíveis (título, mensagem, dica) + detalhe técnico."""
    det = f"{type(exc).__name__}: {exc}"
    if isinstance(exc, FileNotFoundError):
        return dict(codigo="sem_arquivo", titulo="Nenhuma planilha carregada",
                    mensagem="Ainda não há dados para mostrar. Carregue a planilha de fiscalizações (DadosFiscalização.xlsx) "
                             "para ver o painel e gerar os relatórios.",
                    dica="Clique em “Carregar planilha…” e escolha o arquivo Excel.", detalhe=det)
    if type(exc).__name__ in ("BadZipFile", "InvalidFileException") or "Excel file format" in str(exc):
        return dict(codigo="formato", titulo="Este arquivo não é uma planilha Excel válida",
                    mensagem="Não consegui interpretar o arquivo. Ele pode estar corrompido ou não ser um .xlsx.",
                    dica="Abra-o no Excel, salve como “Pasta de Trabalho do Excel (.xlsx)” e carregue novamente.", detalhe=det)
    if isinstance(exc, OSError) and "atalho" in str(exc).lower():
        return dict(codigo="atalho", titulo="Não consegui criar o atalho", mensagem=str(exc),
                    dica="Crie manualmente: botão direito no ARPE_Relatorios.exe › Enviar para › Área de trabalho.", detalhe=det)
    if isinstance(exc, PermissionError):
        return dict(codigo="arquivo_aberto", titulo="Não consegui abrir o arquivo",
                    mensagem="O arquivo está aberto em outro programa (provavelmente o Excel ou o Word) ou está protegido.",
                    dica="Salve e feche o arquivo e clique em “Tentar novamente”.", detalhe=det)
    if isinstance(exc, LookupError) and "Template" in str(exc):
        return dict(codigo="template", titulo="O Template do relatório mudou",
                    mensagem="Não encontrei no Template.docx um trecho que o aplicativo usa como referência: "
                             f"{str(exc).split(':', 1)[-1].strip()}.",
                    dica="Restaure o trecho no Template (ou use uma cópia anterior) e tente de novo.", detalhe=det)
    if isinstance(exc, ValueError) and ("Aba não encontrada" in str(exc) or "precisa das colunas" in str(exc)
                                        or "precisa de ID" in str(exc)):
        return dict(codigo="formato", titulo="A planilha não está no formato esperado",
                    mensagem=str(exc), dica="Confira os nomes das abas e das colunas ou carregue outra planilha.", detalhe=det)
    if isinstance(exc, ValueError) and "Nenhuma planilha" in str(exc):
        return dict(codigo="sem_arquivo", titulo="Nenhuma planilha carregada", mensagem=str(exc),
                    dica="Carregue a planilha antes de gerar o relatório.", detalhe=det)
    return dict(codigo="outro", titulo="Algo não saiu como esperado",
                mensagem="Não foi possível concluir a operação. Os detalhes técnicos estão abaixo e podem ser enviados ao suporte.",
                dica="Tente recarregar a planilha.", detalhe=det)


def escolher_externo(tipo: str, dados_dir) -> dict:
    """Abre o seletor (tkinter) em OUTRO processo e lê o caminho escolhido de um arquivo temporário."""
    import tempfile
    saida = Path(tempfile.gettempdir()) / f"arpe_escolha_{os.getpid()}_{int(time.time())}.txt"
    cmd = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(Path(sys.argv[0]).resolve())]
    cmd += ["--escolher", tipo, "--resultado", str(saida)]
    try:
        r = subprocess.run(cmd, timeout=900, creationflags=0x08000000 if sys.platform.startswith("win") else 0,
                           capture_output=True)
        caminho = saida.read_text(encoding="utf-8").strip() if saida.exists() else ""
        if r.returncode != 0:
            registrar(dados_dir, f"seletor externo terminou com código {r.returncode}: {r.stderr.decode(errors='ignore')[-400:]}")
            return dict(caminho="", erro="Não consegui abrir a janela de seleção. Digite o caminho completo do arquivo.")
        return dict(caminho=caminho)
    except Exception as e:  # noqa: BLE001
        registrar(dados_dir, f"seletor externo falhou: {type(e).__name__}: {e}")
        return dict(caminho="", erro="Não consegui abrir a janela de seleção. Digite o caminho completo do arquivo.")
    finally:
        try:
            saida.unlink()
        except OSError:
            pass


class App:
    """Estado da aplicação (planilha carregada, configuração, controle de relatórios gerados)."""

    def __init__(self, cfg: Config, background: bool = False):
        self.cfg = cfg
        self.janela = None                   # janela pywebview (quando existir): usada para os seletores de arquivo
        self.carregando = False
        self.carga_inicio = 0.0
        self.aviso_inicial: dict | None = None
        self.lock = threading.RLock()
        self.ds: Dataset | None = None
        self.erro: str | None = None
        self.problema: dict | None = None
        self.modo = "janela"                 # "janela" (pywebview) ou "navegador"
        self.ultimo_ping = time.time()
        self.saindo_desde: float | None = None
        self.encerrar = threading.Event()
        self.estado = ReportStateStore(cfg)
        self.recarregar(background=background)

    def recarregar(self, background: bool = False):
        """Lê a planilha. Em segundo plano a janela abre na hora e mostra 'Carregando…' (a carga pode demorar)."""
        with self.lock:
            self.estado = ReportStateStore(self.cfg)
            self.carregando, self.carga_inicio = True, time.time()
        if background:
            threading.Thread(target=self._carregar, daemon=True).start()
        else:
            self._carregar()

    def _carregar(self):
        trava = self.cfg.dados_dir / "carga.lock"      # existe só durante a carga: se sobrar, a carga derrubou o programa
        try:
            trava.write_text(str(self.cfg.excel_path), encoding="utf-8")
        except OSError:
            pass
        registrar(self.cfg.dados_dir, f"carga da planilha: {self.cfg.excel_path}")
        try:
            ds = ExcelRepository(self.cfg).load()
            problema = None
            if not ds.fiscalizacoes:
                problema = dict(codigo="vazia", titulo="A planilha não tem fiscalizações",
                                mensagem="Encontrei a planilha, mas ela não possui linhas de fiscalização com ID e Data.",
                                dica="Preencha a aba de fiscalizações e clique em “Tentar novamente”.", detalhe="")
            with self.lock:
                self.ds, self.erro, self.problema = ds, None, problema
            if not problema and self.cfg.planilha_ok != str(self.cfg.excel_path):
                self.cfg.planilha_ok = str(self.cfg.excel_path)
                self.cfg.salvar()
            registrar(self.cfg.dados_dir, f"planilha carregada em {time.time() - self.carga_inicio:.1f}s "
                                          f"({len(ds.fiscalizacoes)} fiscalizações, {len(ds.ncs)} NC)")
        except Exception as e:  # noqa: BLE001
            with self.lock:
                self.ds, self.problema = None, traduzir_erro(e)
                self.erro = self.problema["detalhe"]
            registrar(self.cfg.dados_dir, "FALHA na carga: " + self.problema["detalhe"])
        finally:
            self.carregando = False
            try:
                trava.unlink()
            except OSError:
                pass

    # ------------------------------------------------------------------ estado para a UI
    def snapshot(self, ano: int | None = None) -> dict:
        cfg = self.cfg
        aviso, self.aviso_inicial = (self.aviso_inicial, None) if not self.carregando else (None, self.aviso_inicial)
        base = dict(aviso_inicial=aviso, carregando=self.carregando, carregando_seg=int(time.time() - self.carga_inicio) if self.carregando else 0,
                    modo=self.modo, em_rede=em_rede(cfg.base_dir), problema=self.problema, arquivo=str(cfg.excel_path), assets=str(cfg.assets_dir), saida=str(cfg.saida_dir),
                    template=str(cfg.template_efetivo()), meses=MESES_ABREV,
                    config=dict(pa=cfg.ultimo_pa, sei=cfg.ultimo_sei, fotos_sinteticas=cfg.gerar_fotos_sinteticas,
                                condicoes_gerais=cfg.incluir_condicoes_gerais, tema=cfg.tema))
        if self.carregando or not self.ds or not self.ds.fiscalizacoes or self.problema:
            return base | dict(anos=[], ano=None)
        ds, st = self.ds, self.estado
        anos = sorted({p.ano for p in ds.periodos()})
        ano = ano if ano in anos else anos[-1]
        an = DashboardAnalytics(ds, ano, cfg)
        prox = st.proximo_pendente(ds)
        sug = st.sugerir_baseline(ds)
        pers = []
        for p in sorted(ds.periodos(), reverse=True):
            fs = ds.do_periodo(p)
            info = st.info(p)
            stt = st.status(p, ds)
            pers.append(dict(label=p.label, ano=p.ano, mes=p.mes, nome=f"{p.nome_mes.capitalize()} de {p.ano}",
                             status=stt, status_txt=STATUS_TXT[stt], n_fisc=len(fs), n_nc=sum(len(f.ncs) for f in fs),
                             arquivo=(info or {}).get("arquivo", ""), gerado_em=(info or {}).get("gerado_em", "")))
        bl = st.baseline
        return base | dict(
            ano=ano, anos=anos, kpis=an.kpis(), series=an.series_web(),
            avisos=[a for a in an.avisos() if a not in st.alertas_dispensados],
            avisos_dispensados=len([a for a in an.avisos() if a in st.alertas_dispensados]),
            tabelas={k: df_json(v) for k, v in an.tabelas().items()},
            periodos=pers, proximo=prox.label if prox else None,
            proximo_nome=f"{prox.nome_mes.capitalize()} de {prox.ano}" if prox else None,
            sem_historico=st.sem_historico(ds), baseline=bl.label if bl else None,
            baseline_sugerido=sug.label if sug else None,
        )

    # ------------------------------------------------------------------ ações
    def gerar(self, d: dict) -> dict:
        with self.lock:
            if not self.ds:
                raise ValueError("Nenhuma planilha carregada. Carregue a planilha de fiscalizações antes de gerar o relatório.")
            p = Periodo.parse(d["periodo"])
            cfg = self.cfg
            cfg.ultimo_pa, cfg.ultimo_sei = str(d.get("pa", "")), str(d.get("sei", ""))
            cfg.gerar_fotos_sinteticas = bool(d.get("fotos_sinteticas"))
            cfg.incluir_condicoes_gerais = bool(d.get("condicoes_gerais"))
            cfg.salvar()
            op = Opcoes(pa=cfg.ultimo_pa, sei=cfg.ultimo_sei, incluir_condicoes_gerais=cfg.incluir_condicoes_gerais,
                        gerar_fotos_sinteticas=cfg.gerar_fotos_sinteticas)
            r = RelatorioBuilder(cfg, self.ds).build(p, opcoes=op)
            self.estado.marcar(p, r.caminho.name)
            return dict(arquivo=r.caminho.name, caminho=str(r.caminho), periodo=p.label, n_fisc=r.n_fiscalizacoes,
                        n_nc=r.n_nc, n_fotos=r.n_fotos,
                        avisos=[a for a in r.avisos if a not in self.estado.alertas_dispensados])

    def config(self, d: dict):
        with self.lock:
            for k in ("excel_path", "assets_dir", "saida_dir", "template_path"):
                if d.get(k):
                    self.cfg.definir(k, d[k])
            if "tema" in d:
                self.cfg.tema = d["tema"]
            self.cfg.salvar()
        self.recarregar(background=True)

    def baseline(self, d: dict):
        with self.lock:
            self.estado.definir_baseline(Periodo.parse(d["periodo"]) if d.get("periodo") else None)

    def ping(self):
        self.ultimo_ping, self.saindo_desde = time.time(), None

    def vigiar(self):
        """No modo navegador não há janela para fechar: encerra sozinho quando a aba é fechada."""
        while not self.encerrar.wait(2):
            if self.modo != "navegador":
                continue
            agora = time.time()
            if (self.saindo_desde and agora - self.saindo_desde > 8) or agora - self.ultimo_ping > 180:
                self.encerrar.set()

    def atalho(self) -> dict:
        from .atalho import criar_atalho
        return dict(caminho=criar_atalho())

    def alerta(self, d: dict):
        """Confirma a ocorrência e cancela o alerta ('dispensar') ou volta a exibir todos ('reexibir')."""
        with self.lock:
            if d.get("acao") == "reexibir":
                self.estado.reexibir_alertas()
            else:
                self.estado.dispensar_alerta(str(d["texto"]))

    def desmarcar(self, d: dict):
        with self.lock:
            self.estado.desmarcar(Periodo.parse(d["periodo"]))

    def escolher(self, tipo: str) -> dict:
        """Seletor de arquivo/pasta. Na janela própria usa o diálogo do pywebview; no navegador, um processo separado
        (tkinter dentro do servidor, ao lado da janela .NET, derrubava o programa)."""
        if self.janela is not None and self.modo == "janela":
            try:
                import webview  # type: ignore
                fd = getattr(webview, "FileDialog", None)
                if tipo == "arquivo":
                    r = self.janela.create_file_dialog(fd.OPEN if fd else webview.OPEN_DIALOG,
                                                       file_types=("Planilha Excel (*.xlsx;*.xlsm)", "Todos os arquivos (*.*)"))
                else:
                    r = self.janela.create_file_dialog(fd.FOLDER if fd else webview.FOLDER_DIALOG)
                return dict(caminho=(r[0] if r else "") or "")
            except Exception as e:  # noqa: BLE001
                registrar(self.cfg.dados_dir, f"diálogo pywebview falhou ({type(e).__name__}: {e}); usando processo externo")
        return escolher_externo(tipo, self.cfg.dados_dir)

    def abrir(self, caminho: str):
        p = Path(caminho)
        alvo = p if p.exists() else self.cfg.saida_dir
        if sys.platform.startswith("win"):
            os.startfile(str(alvo))  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(alvo)])
        else:
            subprocess.Popen(["xdg-open", str(alvo)])


def criar_handler(app: App):
    class H(BaseHTTPRequestHandler):
        server_version = "ARPE/2.0"

        def log_message(self, *a):  # silencioso
            pass

        def handle(self):
            try:
                super().handle()
            except (BrokenPipeError, ConnectionResetError):  # navegador cancelou a requisição (ex.: recarregou a página)
                pass

        def _json(self, obj, code=200):
            corpo = json.dumps(obj, ensure_ascii=False, default=_jsonable).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(corpo)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(corpo)

        def _arquivo(self, caminho: Path, download=False):
            if not caminho.is_file():
                return self._json({"erro": "Arquivo não encontrado"}, 404)
            tipo = mimetypes.guess_type(str(caminho))[0] or "application/octet-stream"
            dados = caminho.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", tipo)
            self.send_header("Content-Length", str(len(dados)))
            if download:
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{caminho.name}")
            self.end_headers()
            self.wfile.write(dados)

        def do_GET(self):
            u = urlparse(self.path)
            q = parse_qs(u.query)
            try:
                if u.path == "/api/ping":
                    app.ping()
                    return self._json({"ok": True, "app": "arpe"})
                if u.path == "/api/estado":
                    app.ping()
                    ano = int(q["ano"][0]) if "ano" in q else None
                    return self._json(app.snapshot(ano))
                if u.path == "/api/download":
                    nome = Path(unquote(q["nome"][0])).name
                    return self._arquivo(app.cfg.saida_dir / nome, download=True)
                rel = "index.html" if u.path in ("/", "") else u.path.lstrip("/")
                alvo = (WEB / rel).resolve()
                if WEB.resolve() not in alvo.parents:
                    return self._json({"erro": "negado"}, 403)
                return self._arquivo(alvo)
            except Exception as e:  # noqa: BLE001
                registrar(app.cfg.dados_dir, f"ERRO em {self.path}: {traceback.format_exc()}")
                return self._json({"erro": traduzir_erro(e)["mensagem"], "detalhe": f"{type(e).__name__}: {e}"}, 500)

        def do_POST(self):
            u = urlparse(self.path)
            n = int(self.headers.get("Content-Length") or 0)
            try:
                d = json.loads(self.rfile.read(n) or b"{}")
                rota = u.path
                if rota == "/api/gerar":
                    return self._json(app.gerar(d))
                if rota == "/api/recarregar":
                    app.recarregar(background=True)
                    return self._json({"ok": True})
                if rota == "/api/config":
                    app.config(d)
                    return self._json({"ok": True})
                if rota == "/api/baseline":
                    app.baseline(d)
                    return self._json({"ok": True})
                if rota == "/api/saindo":      # aba fechando (sendBeacon); um novo ping cancela
                    app.saindo_desde = time.time()
                    return self._json({"ok": True})
                if rota == "/api/encerrar":
                    app.encerrar.set()
                    return self._json({"ok": True})
                if rota == "/api/atalho":
                    return self._json(app.atalho())
                if rota == "/api/alerta":
                    app.alerta(d)
                    return self._json({"ok": True})
                if rota == "/api/desmarcar":
                    app.desmarcar(d)
                    return self._json({"ok": True})
                if rota == "/api/escolher":
                    return self._json(app.escolher(d.get("tipo", "arquivo")))
                if rota == "/api/abrir":
                    app.abrir(d.get("caminho", ""))
                    return self._json({"ok": True})
                return self._json({"erro": "rota inexistente"}, 404)
            except Exception as e:  # noqa: BLE001
                registrar(app.cfg.dados_dir, f"ERRO em {self.path}: {traceback.format_exc()}")
                t = traduzir_erro(e)
                return self._json({"erro": f"{t['titulo']}. {t['mensagem']} {t['dica']}" if t["codigo"] != "outro"
                                   else f"{t['titulo']}: {e}", "detalhe": t["detalhe"]}, 400)

    return H


def iniciar(cfg: Config, porta: int = 0, modo: str = "janela") -> tuple[ThreadingHTTPServer, str, App]:
    app = App(cfg, background=True)
    app.modo = modo
    srv = ThreadingHTTPServer(("127.0.0.1", porta), criar_handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    threading.Thread(target=app.vigiar, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/", app
