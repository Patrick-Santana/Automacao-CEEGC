from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd

from .config import Config
from .models import Dataset, Fiscalizacao, NaoConformidade, limpar_texto
from .oficial import PlanilhaOficial


MAX_COLUNAS = 60        # as abas de dados têm ~40 colunas
MAX_VAZIAS = 200        # fim dos dados = 200 linhas vazias seguidas (planilhas com formatação até a linha 1.048.576)


def _para_data(v) -> date:
    """Converte a célula de data em datetime.date sem criar arrays datetime64 do pandas."""
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    txt = str(v).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(txt, fmt).date()
        except ValueError:
            continue
    return pd.Timestamp(v).date()


class _Livro:
    """Livro aberto UMA vez em modo leitura (rápido e com pouca memória), compartilhado por dados e aba oficial."""

    def __init__(self, caminho):
        import openpyxl
        self.wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
        self.sheet_names = list(self.wb.sheetnames)

    def aba(self, nome: str) -> pd.DataFrame:
        """DataFrame da aba lendo só a região realmente usada. A leitura 'ingênua' (pandas/iter_rows sem limite) de
        planilhas cuja dimensão declarada vai até a linha 1.048.576 consome gigabytes e derruba o programa."""
        cab, linhas, vazias = None, [], 0
        for row in self.wb[nome].iter_rows(max_col=MAX_COLUNAS, values_only=True):
            if all(v is None or (isinstance(v, str) and not v.strip()) for v in row):
                vazias += 1
                if vazias >= MAX_VAZIAS:
                    break
                continue
            vazias = 0
            if cab is None:
                cab = [str(v) if v is not None else f"Unnamed: {i}" for i, v in enumerate(row)]
                continue
            linhas.append(list(row) + [None] * (len(cab) - len(row)))
        if cab is None:
            return pd.DataFrame()
        # dtype=object: sem inferência automática de datas do pandas (em alguns ambientes essa etapa nativa derruba o Python)
        return pd.DataFrame([l[:len(cab)] for l in linhas], columns=cab, dtype=object)

    def fechar(self):
        self.wb.close()


class ExcelRepository:
    """Lê a planilha e devolve objetos de domínio (Dataset)."""

    def __init__(self, config: Config):
        self.cfg = config

    def _col(self, df: pd.DataFrame, chave: str) -> str | None:
        for nome in self.cfg.colunas[chave]:
            if nome in df.columns:
                return nome
        return None

    @staticmethod
    def _sheet(xls: pd.ExcelFile, candidatos: tuple, obrigatoria=True) -> str | None:
        for c in candidatos:
            if c in xls.sheet_names:
                return c
        if obrigatoria:
            raise ValueError(f"Aba não encontrada. Esperado uma de {candidatos}; existentes: {xls.sheet_names}")
        return None

    @staticmethod
    def _get(row, col):
        return limpar_texto(row[col]) if col else ""

    def abas(self) -> list[str]:
        livro = _Livro(self.cfg.excel_path)
        try:
            return livro.sheet_names
        finally:
            livro.fechar()

    def load(self) -> Dataset:
        if not Path(self.cfg.excel_path).exists():
            raise FileNotFoundError(f"Planilha não encontrada: {self.cfg.excel_path}")
        xls = _Livro(self.cfg.excel_path)
        try:
            f_df = xls.aba(self._sheet(xls, self.cfg.abas_fisc))
            n_df = xls.aba(self._sheet(xls, self.cfg.abas_nc))
            ds = self._montar(f_df, n_df)
            ds.oficial = self._oficial({f.data.year for f in ds.fiscalizacoes}, xls)
        finally:
            xls.fechar()
        return ds

    def _montar(self, f_df: pd.DataFrame, n_df: pd.DataFrame) -> Dataset:

        c = {k: self._col(f_df, k) for k in ("fisc_id", "data", "usuario", "logradouro", "endereco", "numero",
                                             "bairro", "cidade", "segmento", "func_arpe", "func_copergas", "rel_gerado")}
        if not c["fisc_id"] or not c["data"]:
            raise ValueError("A aba de fiscalizações precisa das colunas ID_FISC e Data.")
        f_df = f_df.dropna(subset=[c["fisc_id"], c["data"]])

        fiscs: dict[int, Fiscalizacao] = {}
        for _, r in f_df.iterrows():
            fid = int(r[c["fisc_id"]])
            fiscs[fid] = Fiscalizacao(
                id=fid, data=_para_data(r[c["data"]]), usuario=self._get(r, c["usuario"]),
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

    def _oficial(self, anos, livro=None) -> dict:
        """Blocos digitados à mão em 'Gráficos AAAA' (opcionais: se faltarem, o app calcula por conta própria)."""
        out = {}
        leitor = PlanilhaOficial(self.cfg.excel_path)
        for ano in sorted(anos):
            try:
                dados = leitor.ler(ano, livro.wb if livro else None)
            except Exception:  # noqa: BLE001 - aba ausente/danificada não deve impedir o uso
                dados = {}
            if dados:
                out[ano] = dados
        return out
