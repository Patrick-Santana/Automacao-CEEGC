from __future__ import annotations

import csv
import unicodedata

import pandas as pd

from .config import Config
from .models import Dataset, Periodo


def normalizar(txt: str) -> str:
    """Chave para comparar nomes de cidade (sem acento, minúsculo, espaços únicos)."""
    s = unicodedata.normalize("NFKD", str(txt)).encode("ascii", "ignore").decode()
    return " ".join(s.casefold().split())


class MetaMunicipios:
    """Meta anual de fiscalizações por município (Tabela 01 do relatório).

    Ordem de busca: aba ``Meta_Municipios`` da planilha (colunas Cidade e Meta) →
    ``metas_municipios.csv`` na pasta do aplicativo → estimativa proporcional às fiscalizações do
    ano anterior (marcada como estimada).
    """

    def __init__(self, config: Config, ds: Dataset):
        self.cfg, self.ds = config, ds

    def para_ano(self, ano: int) -> tuple[dict[str, int], str]:
        """Devolve ({cidade: meta}, origem) com origem em 'planilha' | 'csv' | 'estimada'."""
        metas = self._da_planilha(ano)
        if metas:
            return metas, "planilha"
        metas = self._do_csv()
        if metas:
            return metas, "csv"
        return self._estimar(ano), "estimada"

    def _da_planilha(self, ano: int) -> dict[str, int]:
        try:
            xls = pd.ExcelFile(self.cfg.excel_path)
            aba = next((a for a in self.cfg.abas_metas if a in xls.sheet_names), None)
            if not aba:
                return {}
            df = xls.parse(aba)
        except Exception:  # noqa: BLE001
            return {}
        cols = {normalizar(c): c for c in df.columns}
        c_cid = cols.get("cidade") or cols.get("municipio")
        c_meta = cols.get("meta")
        if not c_cid or not c_meta:
            return {}
        c_ano = cols.get("ano")
        if c_ano:
            df = df[df[c_ano] == ano]
        return {str(r[c_cid]).strip(): int(r[c_meta]) for _, r in df.dropna(subset=[c_cid, c_meta]).iterrows()}

    def _do_csv(self) -> dict[str, int]:
        arq = self.cfg.base_dir / "metas_municipios.csv"
        if not arq.exists():
            return {}
        out = {}
        with arq.open(encoding="utf-8-sig", newline="") as fh:
            dialect = csv.Sniffer().sniff(fh.read(2048), delimiters=";,\t")
            fh.seek(0)
            for r in csv.DictReader(fh, dialect=dialect):
                k = {normalizar(a): b for a, b in r.items()}
                cid, meta = k.get("cidade") or k.get("municipio"), k.get("meta")
                if cid and meta and str(meta).strip().isdigit():
                    out[cid.strip()] = int(meta)
        return out

    def _estimar(self, ano: int) -> dict[str, int]:
        """Distribui a meta anual proporcionalmente ao nº de fiscalizações do ano anterior (maior resto)."""
        total = self.cfg.meta_do_ano(ano)
        base = [f for f in self.ds.fiscalizacoes if f.data.year == ano - 1] or \
               [f for f in self.ds.fiscalizacoes if f.data.year == ano]
        cont: dict[str, int] = {}
        for f in base:
            cont[f.cidade] = cont.get(f.cidade, 0) + 1
        for f in self.ds.fiscalizacoes:             # municípios já fiscalizados em qualquer ano entram com mínimo 1
            cont.setdefault(f.cidade, 0)
        if not cont:
            return {}
        soma = sum(cont.values()) or 1
        exato = {c: total * n / soma for c, n in cont.items()}
        meta = {c: max(1, int(v)) for c, v in exato.items()}
        dif = total - sum(meta.values())
        por_resto = sorted(exato, key=lambda c: exato[c] - int(exato[c]), reverse=True)
        i = 0
        while dif > 0:                                   # distribui o que faltou (maior resto primeiro)
            meta[por_resto[i % len(por_resto)]] += 1
            dif -= 1
            i += 1
        while dif < 0:                                   # tira o excesso gerado pelo mínimo de 1
            c = max(meta, key=lambda k: meta[k])
            if meta[c] <= 1:
                break
            meta[c] -= 1
            dif += 1
        return meta

    def tabela(self, p: Periodo) -> tuple[list[tuple[str, int | None, int]], str]:
        """Linhas (cidade, realizados acumulados no ano até p | None, meta) ordenadas por nome."""
        metas, origem = self.para_ano(p.ano)
        cont: dict[str, int] = {}
        for f in self.ds.do_ano_ate(p):
            cont[normalizar(f.cidade)] = cont.get(normalizar(f.cidade), 0) + 1
        nomes = {normalizar(c): c for c in metas}
        for f in self.ds.fiscalizacoes:
            if f.data.year == p.ano:
                nomes.setdefault(normalizar(f.cidade), f.cidade)
        linhas = []
        for chave, nome in nomes.items():
            meta = next((m for c, m in metas.items() if normalizar(c) == chave), 0)
            linhas.append((nome.upper(), cont.get(chave) or None, meta))
        linhas.sort(key=lambda x: normalizar(x[0]))
        return linhas, origem
