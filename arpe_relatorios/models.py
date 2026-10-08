from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from functools import total_ordering

import pandas as pd

from .config import MESES_NOME

SEGMENTO_ALIAS = {"ERP": "ERP / CR", "CR": "ERP / CR", "CR COM": "Comercial"}
_TYPOS = [(r"\begurança", "segurança"), (r"\bilegivel\b", "ilegível")]


@total_ordering
@dataclass(frozen=True)
class Periodo:
    ano: int
    mes: int

    @classmethod
    def parse(cls, texto: str) -> "Periodo":
        m = re.match(r"^\s*(\d{1,2})/(\d{4})\s*$", str(texto))
        if not m:
            raise ValueError(f"Período inválido: {texto!r} (use MM/AAAA)")
        return cls(int(m.group(2)), int(m.group(1)))

    @property
    def label(self) -> str:
        return f"{self.mes:02d}/{self.ano}"

    @property
    def nome_mes(self) -> str:
        return MESES_NOME[self.mes - 1]

    def __lt__(self, other: "Periodo") -> bool:
        return (self.ano, self.mes) < (other.ano, other.mes)


def limpar_texto(valor) -> str:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or valor is pd.NaT:
        return ""
    return str(valor).strip()


def corrigir_typos(txt: str) -> str:
    for padrao, novo in _TYPOS:
        txt = re.sub(padrao, novo, txt, flags=re.I)
    return re.sub(r"\s+", " ", txt).strip()


@dataclass
class NaoConformidade:
    num: int
    fisc_id: int
    detalhe: str
    unidade: str = ""
    equipamento: str = ""
    tipo: str = ""
    status: str = ""
    rel_original: str = ""
    parecer: str = ""
    foto_nome: str = ""

    @property
    def resolvida(self) -> bool:
        return self.status.upper().startswith("RESOLV")

    @property
    def chave(self) -> str:
        return corrigir_typos(self.detalhe).casefold()


@dataclass
class Fiscalizacao:
    id: int
    data: date
    usuario: str
    logradouro: str = ""
    endereco: str = ""
    numero: str = ""
    bairro: str = ""
    cidade: str = ""
    segmento: str = ""
    func_arpe: str = ""
    func_copergas: str = ""
    rel_gerado: str = ""
    ncs: list[NaoConformidade] = field(default_factory=list)

    @property
    def seq(self) -> int:
        """Nº da fiscalização dentro do ano (2026327 -> 327)."""
        return self.id % 1000

    @property
    def periodo(self) -> Periodo:
        return Periodo(self.data.year, self.data.month)

    @property
    def segmento_norm(self) -> str:
        return SEGMENTO_ALIAS.get(self.segmento.upper(), self.segmento)

    @property
    def endereco_completo(self) -> str:
        partes = [f"{self.logradouro} {self.endereco}".strip(), self.numero, self.bairro, self.cidade]
        return ", ".join(p for p in partes if p)

    @property
    def conforme(self) -> bool:
        return not self.ncs


@dataclass
class Dataset:
    fiscalizacoes: list[Fiscalizacao]
    ncs: list[NaoConformidade]

    def periodos(self) -> list[Periodo]:
        return sorted({f.periodo for f in self.fiscalizacoes})

    def do_periodo(self, p: Periodo) -> list[Fiscalizacao]:
        return sorted((f for f in self.fiscalizacoes if f.periodo == p), key=lambda f: (f.data, f.id))

    def fisc_frame(self) -> pd.DataFrame:
        rows = [dict(id=f.id, seq=f.seq, data=pd.Timestamp(f.data), ano=f.data.year, mes=f.data.month,
                     cidade=f.cidade, segmento=f.segmento_norm, usuario=f.usuario, n_nc=len(f.ncs))
                for f in self.fiscalizacoes]
        return pd.DataFrame(rows, columns=["id", "seq", "data", "ano", "mes", "cidade", "segmento", "usuario", "n_nc"])

    def nc_frame(self) -> pd.DataFrame:
        rows = []
        for n in self.ncs:
            try:
                rel = Periodo.parse(n.rel_original)
            except ValueError:
                continue
            rows.append(dict(num=n.num, fisc_id=n.fisc_id, detalhe=corrigir_typos(n.detalhe), chave=n.chave,
                             resolvida=n.resolvida, parecer=n.parecer, rel_ano=rel.ano, rel_mes=rel.mes))
        return pd.DataFrame(rows, columns=["num", "fisc_id", "detalhe", "chave", "resolvida", "parecer",
                                           "rel_ano", "rel_mes"])
