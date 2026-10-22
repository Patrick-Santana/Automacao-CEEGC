"""Servidor local (somente 127.0.0.1) que alimenta a interface web do aplicativo."""
from __future__ import annotations

import json
import mimetypes
import os
import subprocess
import sys
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import numpy as np
import pandas as pd

from .analytics import DashboardAnalytics
from .config import MESES_ABREV, MESES_NOME, Config, resource_dir
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


class App:
    """Estado da aplicação (planilha carregada, configuração, controle de relatórios gerados)."""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.lock = threading.RLock()
        self.ds: Dataset | None = None
        self.erro: str | None = None
        self.estado = ReportStateStore(cfg)
        self.recarregar()

    def recarregar(self):
        with self.lock:
            self.estado = ReportStateStore(self.cfg)
            try:
                self.ds = ExcelRepository(self.cfg).load()
                self.erro = None
            except Exception as e:  # noqa: BLE001
                self.ds, self.erro = None, f"{type(e).__name__}: {e}"

    # ------------------------------------------------------------------ estado para a UI
    def snapshot(self, ano: int | None = None) -> dict:
        cfg = self.cfg
        base = dict(arquivo=str(cfg.excel_path), assets=str(cfg.assets_dir), saida=str(cfg.saida_dir),
                    template=str(cfg.template_efetivo()), erro=self.erro, meses=MESES_ABREV,
                    config=dict(pa=cfg.ultimo_pa, sei=cfg.ultimo_sei, fotos_sinteticas=cfg.gerar_fotos_sinteticas,
                                condicoes_gerais=cfg.incluir_condicoes_gerais, tema=cfg.tema))
        if not self.ds or not self.ds.fiscalizacoes:
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
                raise ValueError(self.erro or "Nenhuma planilha carregada.")
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
            self.recarregar()

    def baseline(self, d: dict):
        with self.lock:
            self.estado.definir_baseline(Periodo.parse(d["periodo"]) if d.get("periodo") else None)

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
            return dict(caminho=caminho or "")
        except Exception as e:  # noqa: BLE001
            return dict(caminho="", erro=f"Seletor de arquivos indisponível ({e}). Digite o caminho manualmente.")

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
                if u.path == "/api/estado":
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
                traceback.print_exc()
                return self._json({"erro": str(e)}, 500)

        def do_POST(self):
            u = urlparse(self.path)
            n = int(self.headers.get("Content-Length") or 0)
            try:
                d = json.loads(self.rfile.read(n) or b"{}")
                rota = u.path
                if rota == "/api/gerar":
                    return self._json(app.gerar(d))
                if rota == "/api/recarregar":
                    app.recarregar()
                    return self._json({"ok": True})
                if rota == "/api/config":
                    app.config(d)
                    return self._json({"ok": True})
                if rota == "/api/baseline":
                    app.baseline(d)
                    return self._json({"ok": True})
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
                traceback.print_exc()
                return self._json({"erro": f"{type(e).__name__}: {e}"}, 400)

    return H


def iniciar(cfg: Config, porta: int = 0) -> tuple[ThreadingHTTPServer, str, App]:
    app = App(cfg)
    srv = ThreadingHTTPServer(("127.0.0.1", porta), criar_handler(app))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/", app
