from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config, MESES_ABREV
from .models import Dataset, Periodo

ORDEM_SEGMENTOS = ["Cogeração", "Comercial", "Encerrado", "ERP / CR", "ETC", "GNV", "Industrial", "Residencial"]


class DashboardAnalytics:
    """Reproduz as Tabelas 05–11 e Gráficos 01–03 do Apêndice 2 do relatório."""

    def __init__(self, ds: Dataset, ano: int, config: Config):
        self.ano = ano
        self.meta_anual = config.meta_do_ano(ano)
        self.meta_mensal = self.meta_anual / 12
        f = ds.fisc_frame()
        self.f = f[f.ano == ano].copy()
        nc = ds.nc_frame()
        self.nc = nc[nc.rel_ano == ano].copy()
        self.ultimo_mes = int(self.f.mes.max()) if len(self.f) else 0
        self.nc["resolvido_mes"] = self.nc.apply(self._mes_resolucao, axis=1)

    # ---------- KPIs ----------
    def kpis(self) -> dict:
        real = len(self.f)
        acomp = self.acompanhamento_nc()
        saldo = acomp.loc["Saldo pendente"].dropna()
        pend = int(saldo.iloc[-1]) if len(saldo) else 0
        return dict(meta=self.meta_anual, realizado=real, pct_meta=100 * real / self.meta_anual if self.meta_anual else 0,
                    municipios=self.f.cidade.nunique(), nc_detectadas=len(self.nc), nc_pendentes=pend,
                    clientes_conformes=100 * (1 - (self.f.n_nc > 0).mean()) if real else 0)

    # ---------- Tabelas ----------
    def _pivot(self, col: str, ordem: list[str] | None = None) -> pd.DataFrame:
        pv = self.f.pivot_table(index=col, columns="mes", values="id", aggfunc="count", fill_value=0)
        pv = pv.reindex(columns=range(1, 13), fill_value=0)
        if ordem:
            pv = pv.reindex([o for o in ordem if o in pv.index] + [i for i in pv.index if i not in ordem])
        pv.columns = MESES_ABREV
        pv["TOTAL"] = pv.sum(axis=1)
        return pv

    def por_segmento_mes(self) -> pd.DataFrame:
        pv = self._pivot("segmento", ORDEM_SEGMENTOS)
        pv["%"] = (100 * pv["TOTAL"] / pv["TOTAL"].sum()).round(2)
        pv.loc["Total"] = list(pv[MESES_ABREV + ["TOTAL"]].sum()) + [100.0]
        return pv

    def por_cidade_mes(self) -> pd.DataFrame:
        pv = self._pivot("cidade").sort_values("TOTAL", ascending=False)
        pv.loc["Total"] = pv.sum()
        return pv

    def evolucao_mensal(self) -> pd.DataFrame:
        real = self.f.groupby("mes").size().reindex(range(1, 13), fill_value=0)
        df = pd.DataFrame({"mes": MESES_ABREV, "realizado": real.values})
        df["meta"] = self.meta_mensal
        df["acum_real"] = df.realizado.cumsum().where(np.arange(1, 13) <= self.ultimo_mes)
        df["acum_meta"] = self.meta_mensal * np.arange(1, 13)
        df["pct_meta"] = (100 * df.realizado / self.meta_anual).round(1)
        return df

    def dias_e_media(self) -> pd.DataFrame:
        dias = self.f.groupby("mes")["data"].nunique().reindex(range(1, 13), fill_value=0)
        qtd = self.f.groupby("mes").size().reindex(range(1, 13), fill_value=0)
        df = pd.DataFrame({"Dias usados": dias.values, "Fiscalizações": qtd.values,
                           "Fiscs / dia": (qtd / dias.replace(0, np.nan)).round(2).values}, index=MESES_ABREV)
        return df.T

    def _mes_resolucao(self, r) -> float:
        if not r.resolvida:
            return np.nan
        try:
            p = Periodo.parse(r.parecer)
            if p.ano == self.ano:
                return p.mes
        except ValueError:
            pass
        return min(r.rel_mes + 1, 12)  # sem data de parecer: assume saneada no mês seguinte ao relatório

    def acompanhamento_nc(self) -> pd.DataFrame:
        rows, saldo = [], 0
        for m in range(1, 13):
            if m > self.ultimo_mes:
                rows.append([np.nan] * 5)
                continue
            det = int((self.nc.rel_mes == m).sum())
            san = int((self.nc.resolvido_mes == m).sum())
            sub = saldo + det
            saldo = sub - san
            rows.append([det, sub - det, sub, san, saldo])
        return pd.DataFrame(rows, index=MESES_ABREV,
                            columns=["NC detectadas", "Saldo mês anterior", "Subtotal", "NC sanadas", "Saldo pendente"]).T

    def frequencia_nc(self, top: int | None = None) -> pd.DataFrame:
        if self.nc.empty:
            return pd.DataFrame(columns=["Não conformidade", "Frequência", "%"])
        g = self.nc.groupby("chave").agg(freq=("num", "count"),
                                         nome=("detalhe", lambda s: s.value_counts().index[0]))
        g = g.sort_values("freq", ascending=False)
        g["%"] = (100 * g.freq / g.freq.sum()).round(2)
        out = g.rename(columns={"nome": "Não conformidade", "freq": "Frequência"})[["Não conformidade", "Frequência", "%"]]
        out["Não conformidade"] = out["Não conformidade"].str.capitalize().where(
            out["Não conformidade"].str[:1].str.islower(), out["Não conformidade"])
        return out.head(top) if top else out.reset_index(drop=True)

    def tabelas(self) -> dict[str, pd.DataFrame]:
        return {
            "Tabela 05 – Fiscalizações por segmento e mês": self.por_segmento_mes(),
            "Tabela 06 – Fiscalizações por município e mês": self.por_cidade_mes(),
            "Tabela 07/08 – Meta e média por dia": pd.concat(
                [self.evolucao_mensal().set_index("mes")[["realizado", "pct_meta"]].T
                 .rename(index={"realizado": "Realizado", "pct_meta": "% da meta anual"}),
                 self.dias_e_media()]),
            "Tabela 10 – Acompanhamento das NCs": self.acompanhamento_nc(),
            "Tabela 11 – NCs mais frequentes": self.frequencia_nc(),
        }
