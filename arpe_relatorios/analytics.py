from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Config, MESES_ABREV
from .models import Dataset, Periodo

ORDEM_SEGMENTOS = ["Cogeração", "Comercial", "Encerrado", "ERP / CR", "ETC", "GNV", "Industrial", "Residencial"]


class DashboardAnalytics:
    """Indicadores do painel e do Apêndice 2 do relatório (Tabelas 05–11, Gráficos 01–03).

    ``ate_mes`` limita a análise ao mês do relatório (os meses seguintes ficam em branco)."""

    def __init__(self, ds: Dataset, ano: int, config: Config, ate_mes: int | None = None):
        self.ds, self.ano, self.cfg = ds, ano, config
        self.oficial = ds.oficial.get(ano) or {}          # blocos digitados em 'Gráficos AAAA' (podem não existir)
        self.meta_anual = int(self.oficial.get("meta_anual") or config.meta_do_ano(ano))
        self.meta_mensal = self.meta_anual / 12
        f = ds.fisc_frame()
        f = f[f.ano == ano]
        ult = int(f.mes.max()) if len(f) else 0
        self.ultimo_mes_dados = ult
        self.ultimo_mes = min(ate_mes, 12) if ate_mes else ult
        self.f = f[f.mes <= self.ultimo_mes].copy()
        nc = ds.nc_frame()
        nc = nc[(nc.rel_ano == ano) & (nc.rel_mes <= self.ultimo_mes)].copy()
        self.nc = nc
        self.nc["resolvido_mes"] = self.nc.apply(self._mes_resolucao, axis=1)

    # ---------- utilidades ----------
    def _mes_resolucao(self, r) -> float:
        """Mês em que a NC foi sanada: mês do parecer; sem parecer, mês seguinte ao do relatório."""
        if not r.resolvida:
            return np.nan
        try:
            p = Periodo.parse(r.parecer)
            if p.ano == self.ano:
                return p.mes
            if p.ano < self.ano:
                return r.rel_mes
        except ValueError:
            pass
        return min(r.rel_mes + 1, 12)

    def _oficial_mes(self, chave: str, mes: int, calculado: int) -> int:
        """Valor lançado à mão em 'Gráficos AAAA' para o mês; sem lançamento, o valor calculado."""
        serie = self.oficial.get(chave)
        if serie and serie[mes - 1] is not None:
            return int(serie[mes - 1])
        return calculado

    @property
    def usa_planilha_oficial(self) -> bool:
        return bool(self.oficial.get("nc_sanadas"))

    @property
    def meses_ativos(self) -> range:
        return range(1, self.ultimo_mes + 1)

    # ---------- indicadores ----------
    def kpis(self) -> dict:
        real = len(self.f)
        acomp = self.acompanhamento_nc()
        saldo = acomp.loc["Saldo NC pendentes"].dropna()
        return dict(meta=self.meta_anual, realizado=real,
                    pct_meta=100 * real / self.meta_anual if self.meta_anual else 0.0,
                    municipios=int(self.f.cidade.nunique()), nc_detectadas=len(self.nc),
                    nc_pendentes=int(saldo.iloc[-1]) if len(saldo) else 0,
                    pct_conformes=float(100 * (1 - (self.f.n_nc > 0).mean())) if real else 0.0,
                    ultimo_mes=self.ultimo_mes)

    def resumo_meta(self) -> dict:
        k = self.kpis()
        return dict(meta_anual=k["meta"], realizado=k["realizado"], pct=k["pct_meta"], meta_mensal=self.meta_mensal)

    # ---------- tabelas ----------
    def _pivot(self, col: str, ordem: list[str] | None = None) -> pd.DataFrame:
        pv = self.f.pivot_table(index=col, columns="mes", values="id", aggfunc="count", fill_value=0)
        pv = pv.reindex(columns=range(1, 13), fill_value=0)
        if ordem:
            pv = pv.reindex([o for o in ordem if o in pv.index] + [i for i in pv.index if i not in ordem])
        pv.columns = MESES_ABREV
        pv["TOTAL"] = pv.sum(axis=1)
        return pv.astype(int)

    def por_segmento_mes(self) -> pd.DataFrame:
        pv = self._pivot("segmento", ORDEM_SEGMENTOS)
        total = pv["TOTAL"].sum() or 1
        pv["%"] = (100 * pv["TOTAL"] / total).round(2)
        pv.loc["Total"] = list(pv[MESES_ABREV + ["TOTAL"]].sum()) + [100.0 if len(pv) else 0.0]
        return pv

    def por_cidade_mes(self) -> pd.DataFrame:
        pv = self._pivot("cidade").sort_values("TOTAL", ascending=False)
        pv.loc["Total"] = pv.sum()
        return pv

    def evolucao_mensal(self) -> pd.DataFrame:
        real = self.f.groupby("mes").size().reindex(range(1, 13), fill_value=0)
        df = pd.DataFrame({"mes": MESES_ABREV, "realizado": real.values})
        ativo = np.arange(1, 13) <= self.ultimo_mes
        df["meta"] = self.meta_mensal
        df["acum_real"] = df.realizado.cumsum().where(ativo)
        df["acum_meta"] = self.meta_mensal * np.arange(1, 13)
        df["pct_meta"] = (100 * df.realizado / self.meta_anual).round(1).where(ativo)
        return df

    def dias_e_media(self) -> pd.DataFrame:
        dias = self.f.groupby("mes")["data"].nunique().reindex(range(1, 13), fill_value=0)
        qtd = self.f.groupby("mes").size().reindex(range(1, 13), fill_value=0)
        med = (qtd / dias.replace(0, np.nan)).round(2)
        ativo = np.arange(1, 13) <= self.ultimo_mes
        colunas = {}
        prog = self.oficial.get("dias_programados")
        if prog:
            colunas["Dias programados"] = [(prog[i] if prog[i] is not None and ativo[i] else np.nan) for i in range(12)]
        colunas.update({"Dias usados": dias.where(ativo).values, "Fiscalizações": qtd.where(ativo).values,
                        "Fiscs / dia": med.where(ativo).values})
        df = pd.DataFrame(colunas, index=MESES_ABREV)
        tot = [float(np.nansum(df[c])) for c in colunas]
        tot[list(colunas).index("Fiscs / dia")] = round(qtd.sum() / dias.sum(), 2) if dias.sum() else np.nan
        t = pd.DataFrame([tot], index=["TOTAL"], columns=df.columns)
        return pd.concat([df, t]).T

    def acompanhamento_nc(self) -> pd.DataFrame:
        rows, saldo = [], 0
        tot_det = tot_san = 0
        for m in range(1, 13):
            if m > self.ultimo_mes:
                rows.append([np.nan] * 5)
                continue
            det = int((self.nc.rel_mes == m).sum())
            san = self._oficial_mes("nc_sanadas", m, int((self.nc.resolvido_mes == m).sum()))
            sub = saldo + det
            rows.append([det, saldo, sub, san, sub - san])
            saldo = sub - san
            tot_det += det
            tot_san += san
        df = pd.DataFrame(rows, index=MESES_ABREV,
                          columns=["NC detectadas no mês", "Saldo pendente do mês anterior", "Subtotal de pendências",
                                   "NC sanadas", "Saldo NC pendentes"]).T
        df["TOTAL"] = [tot_det, np.nan, np.nan, tot_san, np.nan]
        return df

    def acompanhamento_clientes(self) -> pd.DataFrame:
        """Clientes (fiscalizações) conformes × não conformes e saneamento mês a mês (Tabela 09)."""
        com_nc = self.nc.groupby("fisc_id").agg(rel=("rel_mes", "first"), todas=("resolvida", "all"),
                                                fim=("resolvido_mes", "max"))
        rows, saldo = [], 0
        t_fisc = t_nc = t_san = 0
        for m in range(1, 13):
            if m > self.ultimo_mes:
                rows.append([np.nan] * 6)
                continue
            fis = int((self.f.mes == m).sum())
            novos = int((com_nc.rel == m).sum())
            san = self._oficial_mes("clientes_sanados", m, int(((com_nc.todas) & (com_nc.fim == m)).sum()))
            sub = saldo + novos
            rows.append([fis, novos, saldo, sub, san, sub - san])
            saldo = sub - san
            t_fisc += fis; t_nc += novos; t_san += san
        df = pd.DataFrame(rows, index=MESES_ABREV,
                          columns=["Clientes fiscalizados", "Clientes não conformes", "Saldo clientes NC mês anterior",
                                   "Subtotal de clientes NC", "Clientes sanados", "Clientes pendentes"]).T
        df["TOTAL"] = [t_fisc, t_nc, np.nan, np.nan, t_san, np.nan]
        return df

    def frequencia_nc(self, top: int | None = None, outros: bool = False) -> pd.DataFrame:
        if self.nc.empty:
            return pd.DataFrame(columns=["Não conformidade", "Frequência", "%"])
        g = self.nc.groupby("chave").agg(freq=("num", "count"), nome=("detalhe", lambda s: s.value_counts().index[0]))
        g = g.sort_values(["freq", "nome"], ascending=[False, True])
        total = int(g.freq.sum())
        out = pd.DataFrame({"Não conformidade": g.nome.values, "Frequência": g.freq.values})
        out["%"] = (100 * out["Frequência"] / total).round(2)
        out["Não conformidade"] = out["Não conformidade"].map(lambda t: t[:1].upper() + t[1:])
        if top and len(out) > top:
            resto = out.iloc[top:]
            out = out.iloc[:top]
            if outros:
                out.loc[len(out)] = ["Outros", int(resto["Frequência"].sum()), round(float(resto["%"].sum()), 2)]
        return out.reset_index(drop=True)

    def avisos(self) -> list[str]:
        """Divergências entre a aba 'Gráficos AAAA' (lançada à mão) e a aba Nao_Conformidades."""
        out = []
        serie = self.oficial.get("nc_sanadas")
        if serie and self.ultimo_mes == self.ultimo_mes_dados:
            oficial = int(sum(v for v in serie[:self.ultimo_mes] if v is not None))
            marcadas = int(self.nc.resolvida.sum())
            if oficial != marcadas:
                out.append(f"'Gráficos {self.ano}' registra {oficial} NC sanadas até {MESES_ABREV[self.ultimo_mes - 1]}, mas "
                           f"a aba Nao_Conformidades marca {marcadas} como RESOLVIDA. O relatório usa o valor de "
                           f"'Gráficos {self.ano}'; confira qual está desatualizado.")
        return out

    def cidades_com_pendencia(self) -> list[str]:
        pend = self.nc[self.nc.resolvido_mes.isna() | (self.nc.resolvido_mes > self.ultimo_mes)]
        return sorted({c for c in pend.cidade if c})

    def tabelas(self) -> dict[str, pd.DataFrame]:
        ev = self.evolucao_mensal().set_index("mes")
        meta_pct = pd.DataFrame([ev["realizado"].where(np.arange(1, 13) <= self.ultimo_mes).values,
                                 ev["pct_meta"].values], index=["Realizado", "% da meta anual"], columns=ev.index)
        return {
            "Fiscalizações por segmento e mês": self.por_segmento_mes(),
            "Fiscalizações por município e mês": self.por_cidade_mes(),
            "Meta × realizado e média por dia": pd.concat([meta_pct, self.dias_e_media().drop(columns="TOTAL")]),
            "Acompanhamento dos clientes não conformes": self.acompanhamento_clientes(),
            "Acompanhamento das não conformidades": self.acompanhamento_nc(),
            "Não conformidades mais frequentes": self.frequencia_nc(),
        }

    # ---------- séries para o painel web ----------
    def series_web(self) -> dict:
        ev = self.evolucao_mensal()
        seg = self.por_segmento_mes().drop(index="Total")
        seg = seg[seg["TOTAL"] > 0].sort_values("TOTAL", ascending=False)
        cid = self.por_cidade_mes().drop(index="Total")["TOTAL"].sort_values(ascending=False)
        ac = self.acompanhamento_nc()
        n = self.ultimo_mes
        num = lambda s: [None if pd.isna(v) else float(v) for v in s]  # noqa: E731
        return dict(
            meses=MESES_ABREV, ultimo_mes=n,
            realizado=[int(v) for v in ev.realizado], meta_mensal=round(self.meta_mensal, 2),
            acum_real=num(ev.acum_real), acum_meta=[round(float(v), 1) for v in ev.acum_meta],
            segmentos=[dict(nome=i, total=int(r["TOTAL"]), pct=float(r["%"])) for i, r in seg.iterrows()],
            municipios=[dict(nome=i, total=int(v)) for i, v in cid.items() if v > 0],
            nc_detectadas=num(ac.loc["NC detectadas no mês", MESES_ABREV]),
            nc_sanadas=num(ac.loc["NC sanadas", MESES_ABREV]),
            nc_pendentes=num(ac.loc["Saldo NC pendentes", MESES_ABREV]),
            frequencia=self.frequencia_nc(8).to_dict("records"),
            media_dia=num(self.dias_e_media().loc["Fiscs / dia", MESES_ABREV]),
        )
