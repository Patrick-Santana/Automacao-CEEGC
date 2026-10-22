"""Textos de análise do relatório (Apêndice 2 e trechos variáveis), gerados a partir dos dados."""
from __future__ import annotations

from .analytics import DashboardAnalytics
from .config import Config, MESES_ABREV, MESES_NOME
from .models import Dataset, Periodo

_UNID = ["zero", "um", "dois", "três", "quatro", "cinco", "seis", "sete", "oito", "nove", "dez", "onze", "doze",
         "treze", "quatorze", "quinze", "dezesseis", "dezessete", "dezoito", "dezenove"]
_DEZ = {20: "vinte", 30: "trinta", 40: "quarenta", 50: "cinquenta", 60: "sessenta", 70: "setenta", 80: "oitenta", 90: "noventa"}


def extenso(n: int) -> str:
    if n < 20:
        return _UNID[n]
    if n < 100:
        d, u = divmod(n, 10)
        return _DEZ[d * 10] + (f" e {_UNID[u]}" if u else "")
    return str(n)


def lista_pt(itens: list[str]) -> str:
    itens = [i for i in itens if i]
    if len(itens) <= 1:
        return itens[0] if itens else ""
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def pct(x: float, casas=2) -> str:
    return f"{x:.{casas}f}".replace(".", ",") + "%"


def num(x: float, casas=1) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def plural(n: int, singular: str, plural_: str) -> str:
    return singular if n == 1 else plural_


class Numeracao:
    """Numeração sequencial das tabelas (depende do nº de dias de fiscalização do mês)."""

    def __init__(self, n_dias: int):
        self.meta_anterior = 1
        self.dias = [2 + i for i in range(n_dias)]
        k = 2 + n_dias
        self.nc = k
        self.meta_atual = k + 1
        base = k + 2
        self.segmento, self.municipio, self.pct_meta, self.media_dia = base, base + 1, base + 2, base + 3
        self.clientes, self.nc_acomp, self.frequencia = base + 4, base + 5, base + 6

    @staticmethod
    def t(n: int) -> str:
        return f"{n:02d}"

    def refs(self, nums: list[int], singular="Tabela", plural_="Tabelas", artigo=False) -> str:
        ns = [self.t(n) for n in nums]
        txt = f"{singular if len(ns) == 1 else plural_} {lista_pt(ns)}"
        if artigo:
            txt = ("A " if len(ns) == 1 else "As ") + txt
        return txt


class Narrativa:
    def __init__(self, cfg: Config, ds: Dataset, p: Periodo, an: DashboardAnalytics, nm: Numeracao,
                 cidades_mes: list[str], n_nc_mes: int, n_clientes_nc_mes: int):
        self.cfg, self.ds, self.p, self.an, self.nm = cfg, ds, p, an, nm
        self.cidades_mes = cidades_mes
        self.n_nc_mes, self.n_cli_nc_mes = n_nc_mes, n_clientes_nc_mes

    # ---------- seção 4.2 ----------
    def intro_execucao_parte1(self) -> str:
        dias = self.nm.dias
        verbo = "apresenta" if len(dias) == 1 else "apresentam"
        return f"{self.nm.refs(dias)} {verbo}"

    # ---------- Apêndice 2 ----------
    def nicho_municipio(self) -> str:
        an, nm = self.an, self.nm
        seg = an.por_segmento_mes().drop(index="Total")["TOTAL"]
        cid = an.por_cidade_mes().drop(index="Total")["TOTAL"].sort_values(ascending=False)
        cid = cid[cid > 0]
        total = int(seg.sum()) or 1
        top_seg = seg.idxmax()
        txt = (f"{nm.refs([nm.segmento, nm.municipio], artigo=True)} apresentam a quantidade de fiscalizações realizadas ao longo do ano, "
               f"classificadas por nicho e município. Nota-se que o principal setor fiscalizado foi o {top_seg.lower()} "
               f"({pct(100 * seg.max() / total)} das fiscalizações)")
        if top_seg.lower() == "residencial":
            txt += ", que concentra a maior parte dos clientes da concessionária"
        txt += ". "
        top3 = list(cid.index[:3])
        if top3:
            share = 100 * cid.iloc[:3].sum() / total
            txt += (f"Ao analisar a distribuição das fiscalizações por cidade, observa-se maior concentração em "
                    f"{lista_pt(top3)} ({pct(share)} do total). ")
        fisc_n = int(cid.shape[0])
        todos = len({f.cidade for f in self.ds.fiscalizacoes})
        total_mun = max(self.cfg.total_municipios, todos)
        txt += (f"Vale ressaltar que já {plural(fisc_n, 'foi fiscalizado', 'foram fiscalizados')} {fisc_n} ({extenso(fisc_n)}) dos "
                f"{total_mun} ({extenso(total_mun)}) municípios ({pct(100 * fisc_n / total_mun)}) em que se tem instalações da Copergás.")
        return txt

    def evolucao(self) -> list[str]:
        an, nm, p = self.an, self.nm, self.p
        ev = an.evolucao_mensal().iloc[:an.ultimo_mes]
        meta_m = an.meta_mensal
        abaixo = [MESES_NOME[i] for i, v in enumerate(ev.realizado) if v < meta_m]
        acima = [MESES_NOME[i] for i, v in enumerate(ev.realizado) if v >= meta_m]
        refs_pm = nm.refs([nm.pct_meta, nm.media_dia], artigo=True)
        t1 = (f"Os Gráficos 01 e 02 e {refs_pm[0].lower() + refs_pm[1:]} apresentam o acompanhamento das fiscalizações "
              f"realizadas ao longo do ano de {p.ano}. ")
        if abaixo and acima:
            t1 += (f"Em {lista_pt(abaixo)}, a quantidade de fiscalizações ficou abaixo da meta mensal ({meta_m:.0f}); "
                   f"em {lista_pt(acima)}, a meta mensal foi atingida ou superada.")
        elif abaixo:
            t1 += f"Em todos os meses até {p.nome_mes} a quantidade de fiscalizações ficou abaixo da meta mensal ({meta_m:.0f})."
        else:
            t1 += f"Em todos os meses até {p.nome_mes} a meta mensal ({meta_m:.0f}) foi atingida ou superada."
        mes = ev.iloc[-1]
        dm = an.dias_e_media()
        dias = int(dm.loc["Dias usados", MESES_ABREV[p.mes - 1]])
        n = int(mes.realizado)
        media = n / dias if dias else 0
        acum = int(ev.realizado.sum())
        acum_meta = meta_m * p.mes
        rel = "acima" if acum >= acum_meta else "abaixo"
        t2 = (f"Durante o mês de {p.nome_mes}, foram realizadas {n} fiscalizações em {dias} {plural(dias, 'dia', 'dias')}, "
              f"com média de {num(media, 2)} fiscalizações por dia ({pct(100 * n / an.meta_anual, 1)} da meta anual). "
              f"No acumulado do ano, até {p.nome_mes}, foram realizadas {acum} fiscalizações "
              f"({pct(100 * acum / an.meta_anual, 1)} da meta anual de {an.meta_anual}), "
              f"{rel} da meta acumulada para o período ({acum_meta:.0f}).")
        return [t1, t2]

    def nao_conformidades(self) -> str:
        an, nm, p = self.an, self.nm, self.p
        refs = nm.refs([nm.clientes, nm.nc_acomp, nm.frequencia], artigo=True)
        t = f"{refs} e o Gráfico 03 mostram o levantamento das não conformidades. "
        det = len(an.nc)
        if det == 0:
            return t + f"Até {p.nome_mes} de {p.ano} não foram constatadas não conformidades."
        k = an.kpis()
        san = det - k["nc_pendentes"]
        if self.n_nc_mes:
            t += (f"Em {p.nome_mes} {plural(self.n_nc_mes, 'foi constatada', 'foram constatadas')} {self.n_nc_mes} "
                  f"{plural(self.n_nc_mes, 'não conformidade', 'não conformidades')} em {self.n_cli_nc_mes} "
                  f"{plural(self.n_cli_nc_mes, 'cliente', 'clientes')}. ")
        else:
            t += f"Em {p.nome_mes} não foram constatadas novas não conformidades. "
        t += (f"No acumulado de {p.ano} foram detectadas {det} não conformidades, das quais {san} já foram sanadas e "
              f"{k['nc_pendentes']} permanecem pendentes. ")
        fr = an.frequencia_nc()
        if len(fr):
            top = fr.iloc[0]
            t += (f"A principal não conformidade identificada até {p.nome_mes} foi “{top['Não conformidade'].lower()}”, com "
                  f"{int(top['Frequência'])} {plural(int(top['Frequência']), 'ocorrência', 'ocorrências')} ({pct(top['%'])} do total).")
        return t.strip()

    def mapas(self) -> str:
        pend = self.an.cidades_com_pendencia()
        t = ("As Figuras 02, 03 e 04 ilustram a situação dos municípios quanto à fiscalização, indicando se foram ou não "
             "inspecionados. Além disso, apresentam o status das não conformidades, revelando se ainda há pendências a serem "
             "resolvidas ou se todas as irregularidades já foram sanadas.")
        if pend:
            t += (f" Assim, percebe-se que {plural(len(pend), 'o município', 'os municípios')} de {lista_pt(pend)} "
                  f"{plural(len(pend), 'possui', 'possuem')} não conformidades pendentes.")
        else:
            t += " Não há não conformidades pendentes nos municípios fiscalizados."
        return t
