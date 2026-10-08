from __future__ import annotations

import io

from matplotlib.figure import Figure

from .analytics import DashboardAnalytics

AZUL, LARANJA, VERDE, VERMELHO, CINZA = "#2F5FB3", "#F28C28", "#2E9E5B", "#D64545", "#8A94A6"


class ChartFactory:
    """Cria figuras matplotlib (sem pyplot) para a interface e para o .docx."""

    def __init__(self, an: DashboardAnalytics):
        self.an = an

    @staticmethod
    def _fig(w=6.4, h=3.6):
        fig = Figure(figsize=(w, h), dpi=100, layout="constrained")
        return fig, fig.subplots()

    @staticmethod
    def _limpa(ax):
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.grid(axis="y", alpha=.25)
        ax.set_axisbelow(True)

    def mensal(self, **kw) -> Figure:
        ev = self.an.evolucao_mensal()
        fig, ax = self._fig(**kw)
        cores = [AZUL if i < self.an.ultimo_mes else "#D5DBE8" for i in range(12)]
        b = ax.bar(ev.mes, ev.realizado, color=cores)
        ax.plot(ev.mes, ev.meta, color=LARANJA, lw=2, label=f"Meta mensal ({self.an.meta_mensal:.0f})")
        for r, v in zip(b, ev.realizado):
            if v:
                ax.annotate(int(v), (r.get_x() + r.get_width() / 2, v), ha="center", va="bottom", fontsize=8)
        ax.set_title(f"Fiscalizações por mês – meta × realizado ({self.an.ano})", fontsize=10, fontweight="bold")
        ax.legend(frameon=False, fontsize=8)
        self._limpa(ax)
        return fig

    def acumulado(self, **kw) -> Figure:
        ev = self.an.evolucao_mensal()
        fig, ax = self._fig(**kw)
        ax.plot(ev.mes, ev.acum_meta, color=LARANJA, marker="o", ms=3, label="Meta acumulada")
        ax.plot(ev.mes, ev.acum_real, color=AZUL, marker="o", ms=4, label="Realizado acumulado")
        ax.set_title("Evolução acumulada – meta × realizado", fontsize=10, fontweight="bold")
        ax.legend(frameon=False, fontsize=8)
        self._limpa(ax)
        return fig

    def segmentos(self, **kw) -> Figure:
        pv = self.an.por_segmento_mes().drop(index="Total")["TOTAL"]
        pv = pv[pv > 0].sort_values()
        fig, ax = self._fig(**kw)
        b = ax.barh(pv.index, pv.values, color=AZUL)
        ax.bar_label(b, padding=3, fontsize=8)
        ax.set_title("Fiscalizações por segmento", fontsize=10, fontweight="bold")
        self._limpa(ax)
        ax.grid(axis="x", alpha=.25)
        ax.grid(axis="y", visible=False)
        return fig

    def municipios(self, top: int = 12, **kw) -> Figure:
        pv = self.an.por_cidade_mes().drop(index="Total")["TOTAL"].sort_values(ascending=False).head(top)[::-1]
        fig, ax = self._fig(**kw)
        b = ax.barh(pv.index, pv.values, color=AZUL)
        ax.bar_label(b, padding=3, fontsize=8)
        ax.set_title(f"Fiscalizações por município (top {top})", fontsize=10, fontweight="bold")
        self._limpa(ax)
        ax.grid(axis="x", alpha=.25)
        ax.grid(axis="y", visible=False)
        return fig

    def nc_evolucao(self, **kw) -> Figure:
        t = self.an.acompanhamento_nc().T
        t = t.iloc[: self.an.ultimo_mes]
        fig, ax = self._fig(**kw)
        x = range(len(t))
        w = .27
        ax.bar([i - w for i in x], t["NC detectadas"], w, color=LARANJA, label="Detectadas")
        ax.bar(list(x), t["NC sanadas"], w, color=VERDE, label="Sanadas")
        ax.bar([i + w for i in x], t["Saldo pendente"], w, color=VERMELHO, label="Pendentes (saldo)")
        ax.set_xticks(list(x), t.index)
        ax.set_title("Evolução mensal de não conformidades", fontsize=10, fontweight="bold")
        ax.legend(frameon=False, fontsize=8)
        self._limpa(ax)
        return fig

    def nc_frequencia(self, top: int = 8, **kw) -> Figure:
        fr = self.an.frequencia_nc(top)[::-1]
        fig, ax = self._fig(**kw)
        if fr.empty:
            ax.text(.5, .5, "Sem não conformidades", ha="center", transform=ax.transAxes)
            return fig
        rot = [t if len(t) < 42 else t[:40] + "…" for t in fr["Não conformidade"]]
        b = ax.barh(rot, fr["Frequência"], color=LARANJA)
        ax.bar_label(b, padding=3, fontsize=8)
        ax.tick_params(axis="y", labelsize=7)
        ax.set_title("Não conformidades mais frequentes", fontsize=10, fontweight="bold")
        self._limpa(ax)
        ax.grid(axis="x", alpha=.25)
        ax.grid(axis="y", visible=False)
        return fig

    @staticmethod
    def para_png(fig: Figure) -> io.BytesIO:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=160)
        buf.seek(0)
        return buf
