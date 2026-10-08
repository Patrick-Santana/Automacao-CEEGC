from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from .analytics import DashboardAnalytics
from .charts import ChartFactory
from .config import Config
from .models import Dataset, Periodo
from .photos import SyntheticPhotoGenerator
from .repository import ExcelRepository
from .report import ReportBuilder
from .state import ReportStateStore

COR_FUNDO, COR_CARD, COR_TXT, COR_SUB = "#F3F5F9", "#FFFFFF", "#1F2A44", "#6B778C"


class KpiCard(tk.Frame):
    def __init__(self, master, titulo: str, cor: str):
        super().__init__(master, bg=COR_CARD, highlightbackground="#DDE3EE", highlightthickness=1)
        tk.Frame(self, bg=cor, width=5).pack(side="left", fill="y")
        box = tk.Frame(self, bg=COR_CARD)
        box.pack(side="left", padx=12, pady=8)
        tk.Label(box, text=titulo, bg=COR_CARD, fg=COR_SUB, font=("Segoe UI", 9)).pack(anchor="w")
        self.valor = tk.Label(box, text="–", bg=COR_CARD, fg=COR_TXT, font=("Segoe UI", 20, "bold"))
        self.valor.pack(anchor="w")

    def set(self, v):
        self.valor.config(text=str(v))


class ChartPanel(tk.Frame):
    """Painel que hospeda uma figura matplotlib."""

    def __init__(self, master):
        super().__init__(master, bg=COR_CARD, highlightbackground="#DDE3EE", highlightthickness=1)
        self.pack_propagate(False)
        self.canvas = None

    def mostrar(self, fig):
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
        self.canvas = FigureCanvasTkAgg(fig, master=self)
        w = self.canvas.get_tk_widget()
        w.config(width=10, height=10)          # não impõe o tamanho da figura: ela se adapta ao painel
        w.pack(fill="both", expand=True, padx=4, pady=4)
        self.canvas.draw()


class DashboardApp(tk.Tk):
    def __init__(self, config: Config | None = None):
        super().__init__()
        self.cfg = config or Config()
        self.title("ARPE • Automação de Relatórios de Fiscalização")
        self.geometry("1280x820")
        self.configure(bg=COR_FUNDO)
        self.ds: Dataset | None = None
        self.an: DashboardAnalytics | None = None
        self.estado = ReportStateStore(self.cfg)
        self.var_excel = tk.StringVar(value=str(self.cfg.excel_path))
        self.var_ano = tk.StringVar()
        self.var_fotos_sint = tk.BooleanVar(value=True)
        self.var_tabela = tk.StringVar()
        self._montar()
        if self.cfg.excel_path.exists():
            self.after(100, self.carregar)

    # ---------- layout ----------
    def _montar(self):
        st = ttk.Style(self)
        st.theme_use("clam")
        st.configure("Treeview", rowheight=24, font=("Segoe UI", 9))
        st.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))
        st.configure("TNotebook", background=COR_FUNDO)

        topo = tk.Frame(self, bg=COR_FUNDO)
        topo.pack(fill="x", padx=14, pady=(12, 6))
        tk.Label(topo, text="Dashboard de Fiscalizações", bg=COR_FUNDO, fg=COR_TXT, font=("Segoe UI", 16, "bold")).pack(side="left")
        ttk.Button(topo, text="Recarregar", command=self.carregar).pack(side="right")
        ttk.Button(topo, text="Pasta de assets…", command=self._escolher_assets).pack(side="right", padx=6)
        ttk.Button(topo, text="Abrir planilha…", command=self._escolher_excel).pack(side="right")
        self.cb_ano = ttk.Combobox(topo, textvariable=self.var_ano, width=6, state="readonly")
        self.cb_ano.pack(side="right", padx=12)
        self.cb_ano.bind("<<ComboboxSelected>>", lambda e: self.atualizar())
        tk.Label(topo, text="Ano:", bg=COR_FUNDO, fg=COR_SUB).pack(side="right")

        self.lbl_arquivo = tk.Label(self, textvariable=self.var_excel, bg=COR_FUNDO, fg=COR_SUB, anchor="w", font=("Segoe UI", 8))
        self.lbl_arquivo.pack(fill="x", padx=16)

        cards = tk.Frame(self, bg=COR_FUNDO)
        cards.pack(fill="x", padx=14, pady=8)
        self.k = {n: KpiCard(cards, t, c) for n, t, c in (
            ("meta", "Meta anual", "#2F5FB3"), ("realizado", "Realizado", "#2E9E5B"), ("pct", "% da meta", "#F28C28"),
            ("mun", "Municípios fiscalizados", "#7A5AF8"), ("nc", "NCs detectadas", "#D64545"), ("pend", "NCs pendentes", "#B42318"))}
        for i, c in enumerate(self.k.values()):
            c.grid(row=0, column=i, sticky="ew", padx=5)
            cards.columnconfigure(i, weight=1)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=14, pady=(2, 12))
        self.abas = {}
        for nome, n in (("Visão geral", 2), ("Segmentos e municípios", 2), ("Não conformidades", 2)):
            f = tk.Frame(self.nb, bg=COR_FUNDO)
            self.nb.add(f, text=nome)
            paineis = [ChartPanel(f) for _ in range(n)]
            for i, p in enumerate(paineis):
                p.grid(row=0, column=i, sticky="nsew", padx=5, pady=6)
                f.columnconfigure(i, weight=1)
            f.rowconfigure(0, weight=1)
            self.abas[nome] = paineis
        self._aba_tabelas()
        self._aba_relatorios()

    def _aba_tabelas(self):
        f = tk.Frame(self.nb, bg=COR_FUNDO)
        self.nb.add(f, text="Tabelas")
        barra = tk.Frame(f, bg=COR_FUNDO)
        barra.pack(fill="x", padx=6, pady=6)
        self.cb_tab = ttk.Combobox(barra, textvariable=self.var_tabela, state="readonly", width=60)
        self.cb_tab.pack(side="left")
        self.cb_tab.bind("<<ComboboxSelected>>", lambda e: self._mostrar_tabela())
        self.tv = ttk.Treeview(f, show="headings")
        sx = ttk.Scrollbar(f, orient="horizontal", command=self.tv.xview)
        sy = ttk.Scrollbar(f, orient="vertical", command=self.tv.yview)
        self.tv.configure(xscrollcommand=sx.set, yscrollcommand=sy.set)
        sx.pack(side="bottom", fill="x"); sy.pack(side="right", fill="y")
        self.tv.pack(fill="both", expand=True, padx=6)

    def _aba_relatorios(self):
        f = tk.Frame(self.nb, bg=COR_FUNDO)
        self.nb.add(f, text="Relatórios")
        barra = tk.Frame(f, bg=COR_FUNDO)
        barra.pack(fill="x", padx=6, pady=8)
        ttk.Button(barra, text="Gerar próximo pendente", command=self.gerar_proximo).pack(side="left")
        ttk.Button(barra, text="Gerar selecionado", command=self.gerar_selecionado).pack(side="left", padx=6)
        ttk.Button(barra, text="Marcar como gerado", command=lambda: self._marcar(True)).pack(side="left")
        ttk.Button(barra, text="Desmarcar", command=lambda: self._marcar(False)).pack(side="left", padx=6)
        ttk.Button(barra, text="Abrir pasta de saída", command=self._abrir_saida).pack(side="right")
        ttk.Checkbutton(barra, text="Gerar fotos ilustrativas se faltarem", variable=self.var_fotos_sint).pack(side="right", padx=10)
        cols = ("periodo", "fiscs", "ncs", "status", "arquivo")
        self.tv_rel = ttk.Treeview(f, columns=cols, show="headings", selectmode="browse")
        for c, t, w in (("periodo", "Período", 90), ("fiscs", "Fiscalizações", 110), ("ncs", "Não conformidades", 140),
                        ("status", "Relatório", 120), ("arquivo", "Arquivo / gerado em", 520)):
            self.tv_rel.heading(c, text=t)
            self.tv_rel.column(c, width=w, anchor="w" if c == "arquivo" else "center")
        self.tv_rel.pack(fill="both", expand=True, padx=6)
        self.tv_rel.tag_configure("pendente", foreground="#B54708")
        self.tv_rel.tag_configure("ok", foreground="#067647")
        self.lbl_status = tk.Label(f, text="", bg=COR_FUNDO, fg=COR_SUB, anchor="w")
        self.lbl_status.pack(fill="x", padx=8, pady=4)

    # ---------- dados ----------
    def _escolher_excel(self):
        p = filedialog.askopenfilename(filetypes=[("Excel", "*.xlsx *.xlsm")])
        if p:
            self.cfg.excel_path = Path(p)
            self.var_excel.set(p)
            self.carregar()

    def _escolher_assets(self):
        p = filedialog.askdirectory()
        if p:
            self.cfg.assets_dir = Path(p)

    def carregar(self):
        try:
            self.ds = ExcelRepository(self.cfg).load()
        except Exception as e:  # noqa: BLE001
            messagebox.showerror("Erro ao ler a planilha", str(e))
            return
        anos = sorted({p.ano for p in self.ds.periodos()}, reverse=True)
        self.cb_ano["values"] = anos
        if not self.var_ano.get() or int(self.var_ano.get()) not in anos:
            self.var_ano.set(str(anos[0]))
        self.estado = ReportStateStore(self.cfg)
        self.atualizar()

    def atualizar(self):
        if not self.ds:
            return
        self.an = DashboardAnalytics(self.ds, int(self.var_ano.get()), self.cfg)
        k = self.an.kpis()
        self.k["meta"].set(k["meta"]); self.k["realizado"].set(k["realizado"])
        self.k["pct"].set(f"{k['pct_meta']:.1f}%".replace(".", ",")); self.k["mun"].set(k["municipios"])
        self.k["nc"].set(k["nc_detectadas"]); self.k["pend"].set(k["nc_pendentes"])
        cf = ChartFactory(self.an)
        v, s, n = self.abas["Visão geral"], self.abas["Segmentos e municípios"], self.abas["Não conformidades"]
        v[0].mostrar(cf.mensal(w=6, h=4)); v[1].mostrar(cf.acumulado(w=6, h=4))
        s[0].mostrar(cf.segmentos(w=6, h=4)); s[1].mostrar(cf.municipios(w=6, h=4))
        n[0].mostrar(cf.nc_evolucao(w=6, h=4)); n[1].mostrar(cf.nc_frequencia(w=6, h=4))
        tabs = self.an.tabelas()
        self._tabelas = tabs
        self.cb_tab["values"] = list(tabs)
        self.var_tabela.set(list(tabs)[0])
        self._mostrar_tabela()
        self._listar_relatorios()

    def _mostrar_tabela(self):
        df = self._tabelas[self.var_tabela.get()]
        self.tv.delete(*self.tv.get_children())
        cols = ["#"] + [str(c) for c in df.columns]
        self.tv["columns"] = cols
        for c in cols:
            self.tv.heading(c, text=c)
            self.tv.column(c, width=300 if c in ("#", "Não conformidade") else 70, anchor="w" if c == "#" else "center")
        for idx, row in df.iterrows():
            vals = ["" if (isinstance(v, float) and v != v) else (int(v) if isinstance(v, float) and v == int(v) and c != "%" else v)
                    for c, v in zip(df.columns, row)]
            self.tv.insert("", "end", values=[idx] + vals)

    def _listar_relatorios(self):
        self.tv_rel.delete(*self.tv_rel.get_children())
        ano = int(self.var_ano.get())
        for p in self.ds.periodos():
            if p.ano != ano:
                continue
            fiscs = self.ds.do_periodo(p)
            n_nc = sum(len(f.ncs) for f in fiscs)
            ok = self.estado.concluido(p, self.ds)
            info = self.estado.info(p)
            arq = f"{Path(info['arquivo']).name}  ({info['gerado_em']})" if info and info.get("arquivo") else ""
            self.tv_rel.insert("", "end", iid=p.label, values=(p.label, len(fiscs), n_nc, "Concluído" if ok else "Gerar", arq),
                               tags=("ok" if ok else "pendente",))
        prox = self.estado.proximo_pendente(self.ds)
        self.lbl_status.config(text=f"Próximo relatório a gerar: {prox.label}" if prox else "Todos os relatórios estão concluídos.")

    # ---------- ações ----------
    def _selecionado(self) -> Periodo | None:
        sel = self.tv_rel.selection()
        return Periodo.parse(sel[0]) if sel else None

    def gerar_proximo(self):
        p = self.estado.proximo_pendente(self.ds)
        if p:
            self._gerar(p)
        else:
            messagebox.showinfo("Relatórios", "Não há relatórios pendentes.")

    def gerar_selecionado(self):
        p = self._selecionado()
        if p:
            self._gerar(p)
        else:
            messagebox.showinfo("Relatórios", "Selecione um período na lista.")

    def _marcar(self, gerado: bool):
        p = self._selecionado()
        if not p:
            return
        (self.estado.marcar(p, "(marcado manualmente)") if gerado else self.estado.desmarcar(p))
        self._listar_relatorios()

    def _gerar(self, p: Periodo):
        self.lbl_status.config(text=f"Gerando relatório {p.label}…")

        def trabalho():
            try:
                if self.var_fotos_sint.get():
                    SyntheticPhotoGenerator(self.cfg).gerar_periodo(self.ds, p)
                destino = ReportBuilder(self.cfg, self.ds).build(p)
                self.estado.marcar(p, str(destino))
                self.after(0, lambda: self._fim(p, destino, None))
            except Exception as e:  # noqa: BLE001
                self.after(0, lambda: self._fim(p, None, e))
        threading.Thread(target=trabalho, daemon=True).start()

    def _fim(self, p, destino, erro):
        self._listar_relatorios()
        if erro:
            self.lbl_status.config(text=f"Falha ao gerar {p.label}")
            messagebox.showerror("Erro ao gerar relatório", str(erro))
        else:
            self.lbl_status.config(text=f"Relatório {p.label} gerado: {destino}")
            messagebox.showinfo("Relatório gerado", str(destino))

    def _abrir_saida(self):
        import os, subprocess, sys
        self.cfg.saida_dir.mkdir(parents=True, exist_ok=True)
        if sys.platform.startswith("win"):
            os.startfile(self.cfg.saida_dir)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(self.cfg.saida_dir)])


def executar(config: Config | None = None):
    DashboardApp(config).mainloop()
