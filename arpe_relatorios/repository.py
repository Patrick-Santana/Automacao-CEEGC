from __future__ import annotations

import pandas as pd

from .config import Config
from .models import Dataset, Fiscalizacao, NaoConformidade, limpar_texto


class ExcelRepository:
    """Lê a planilha e devolve objetos de domínio (Dataset)."""

    def __init__(self, config: Config):
        self.cfg = config

    def _col(self, df: pd.DataFrame, chave: str) -> str | None:
        for nome in self.cfg.colunas[chave]:
            if nome in df.columns:
                return nome
        return None

    def _sheet(self, xls: pd.ExcelFile, candidatos: tuple) -> str:
        for c in candidatos:
            if c in xls.sheet_names:
                return c
        raise ValueError(f"Aba não encontrada. Esperado uma de {candidatos}; existentes: {xls.sheet_names}")

    def _get(self, row, col):
        return limpar_texto(row[col]) if col else ""

    def load(self) -> Dataset:
        xls = pd.ExcelFile(self.cfg.excel_path)
        f_df = xls.parse(self._sheet(xls, self.cfg.abas_fisc))
        n_df = xls.parse(self._sheet(xls, self.cfg.abas_nc))

        c = {k: self._col(f_df, k) for k in ("fisc_id", "data", "usuario", "logradouro", "endereco", "numero",
                                             "bairro", "cidade", "segmento", "func_arpe", "func_copergas", "rel_gerado")}
        if not c["fisc_id"] or not c["data"]:
            raise ValueError("A aba de fiscalizações precisa das colunas ID_FISC e Data.")
        f_df = f_df.dropna(subset=[c["fisc_id"], c["data"]])

        fiscs: dict[int, Fiscalizacao] = {}
        for _, r in f_df.iterrows():
            fid = int(r[c["fisc_id"]])
            fiscs[fid] = Fiscalizacao(
                id=fid, data=pd.Timestamp(r[c["data"]]).date(), usuario=self._get(r, c["usuario"]),
                logradouro=self._get(r, c["logradouro"]), endereco=self._get(r, c["endereco"]),
                numero=self._get(r, c["numero"]).replace(".0", ""), bairro=self._get(r, c["bairro"]),
                cidade=self._get(r, c["cidade"]), segmento=self._get(r, c["segmento"]),
                func_arpe=self._get(r, c["func_arpe"]), func_copergas=self._get(r, c["func_copergas"]),
                rel_gerado=self._get(r, c["rel_gerado"]))

        k = {x: self._col(n_df, x) for x in ("nc_num", "nc_fisc", "nc_detalhe", "nc_unidade", "nc_equip",
                                             "nc_tipo", "nc_status", "nc_parecer", "nc_rel", "nc_foto")}
        if not k["nc_fisc"] or not k["nc_detalhe"]:
            raise ValueError("A aba de não conformidades precisa de ID da Fiscalização e Não Conformidade.")
        n_df = n_df.dropna(subset=[k["nc_fisc"], k["nc_detalhe"]])

        ncs: list[NaoConformidade] = []
        for i, (_, r) in enumerate(n_df.iterrows(), start=1):
            fid = int(r[k["nc_fisc"]])
            fisc = fiscs.get(fid)
            rel = self._get(r, k["nc_rel"]) or (fisc.periodo.label if fisc else "")
            nc = NaoConformidade(
                num=int(r[k["nc_num"]]) if k["nc_num"] and pd.notna(r[k["nc_num"]]) else i,
                fisc_id=fid, detalhe=self._get(r, k["nc_detalhe"]),
                unidade=self._get(r, k["nc_unidade"]) or (fisc.usuario if fisc else ""),
                equipamento=self._get(r, k["nc_equip"]), tipo=self._get(r, k["nc_tipo"]),
                status=self._get(r, k["nc_status"]), rel_original=rel,
                parecer=self._get(r, k["nc_parecer"]), foto_nome=self._get(r, k["nc_foto"]))
            ncs.append(nc)
            if fisc:
                fisc.ncs.append(nc)
        return Dataset(list(fiscs.values()), ncs)
