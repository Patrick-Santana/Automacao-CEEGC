from __future__ import annotations

import io

import numpy as np
from matplotlib.figure import Figure

from .analytics import DashboardAnalytics
from .config import MESES_ABREV

AZUL, LARANJA, VERDE, VERMELHO, CINZA = "#4472C4", "#ED7D31", "#2E9E5B", "#E03C31", "#7F8794"


class ChartFactory:
    """Gráficos do relatório (.docx) no estilo do modelo da ARPE – matplotlib sem pyplot."""

    def __init__(self, an: DashboardAnalytics):
        self.an = an

    @staticmethod
    def _fig(w=7.0, h=3.2):
        fig = Figure(figsize=(w, h), dpi=100, layout="constrained")
        return fig, fig.subplots()

    @staticmethod
    def _limpa(ax):
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.grid(axis="y", alpha=.25)
        ax.set_axisbelow(True)
        ax.tick_params(labelsize=8)

    def mensal(self, **kw) -> Figure:
        ev = self.an.evolucao_mensal()
        n = self.an.ultimo_mes
        fig, ax = self._fig(**kw)
        b = ax.bar(ev.mes[:n], ev.realizado[:n], color=AZUL, width=.45, label="Realizado")
        ax.plot(ev.mes, ev.meta, color=LARANJA, lw=2, label=f"Meta mensal ({self.an.meta_mensal:.0f})")
        ax.set_xlim(-.6, 11.6)
        for r, v in zip(b, ev.realizado[:n]):
            ax.annotate(int(v), (r.get_x() + r.get_width() / 2, v), ha="center", va="bottom", fontsize=8, fontweight="bold")
        ax.legend(frameon=False, fontsize=8, ncols=2, loc="upper right")
        self._limpa(ax)
        return fig

    def acumulado(self, **kw) -> Figure:
        ev = self.an.evolucao_mensal()
        fig, ax = self._fig(**kw)
        ax.plot(ev.mes, ev.acum_meta, color=LARANJA, marker="o", ms=3, lw=2, label="Meta acumulada")
        ax.plot(ev.mes, ev.acum_real, color=AZUL, marker="o", ms=4, lw=2, label="Realizado acumulado")
        for x, v in zip(ev.mes, ev.acum_real):
            if v == v:
                ax.annotate(int(v), (x, v), textcoords="offset points", xytext=(0, 6), ha="center", fontsize=7, color=AZUL)
        ax.legend(frameon=False, fontsize=8, loc="upper left")
        self._limpa(ax)
        return fig

    def nc_evolucao(self, **kw) -> Figure:
        """Barras divergentes como no modelo: detectadas e pendentes abaixo de zero, sanadas acima."""
        ac = self.an.acompanhamento_nc()
        n = self.an.ultimo_mes
        det = ac.loc["NC detectadas no mês", MESES_ABREV].values[:n].astype(float)
        san = ac.loc["NC sanadas", MESES_ABREV].values[:n].astype(float)
        pen = ac.loc["Saldo NC pendentes", MESES_ABREV].values[:n].astype(float)
        fig, ax = self._fig(**kw)
        x = np.arange(n)
        w = .25
        for xs, vals, cor, nome in ((x - w, -det, LARANJA, "NC detectadas"), (x, san, VERDE, "NC sanadas"),
                                    (x + w, -pen, VERMELHO, "NC pendentes")):
            bars = ax.bar(xs, vals, w, color=cor, label=nome)
            for r, v in zip(bars, vals):
                if v != 0:
                    ax.annotate(int(v), (r.get_x() + r.get_width() / 2, v), ha="center",
                                va="bottom" if v > 0 else "top", fontsize=7)
        ax.axhline(0, color="#444", lw=.8)
        ax.set_xticks(x, MESES_ABREV[:n])
        ax.set_ylabel("Quantidade de NCs", fontsize=8)
        ax.legend(frameon=False, fontsize=8, ncols=3, loc="lower center", bbox_to_anchor=(.5, -.32))
        self._limpa(ax)
        return fig

    @staticmethod
    def para_png(fig: Figure, dpi=170) -> io.BytesIO:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi)
        buf.seek(0)
        return buf
