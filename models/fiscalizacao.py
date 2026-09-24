# models/fiscalizacao.py
from dataclasses import dataclass
from typing import Optional

@dataclass
class Fiscalizacao:
    id: int
    municipio: str
    tipo: str  # 'QUALIDADE_TRIMESTRAL', 'ACOMPANHAMENTO', etc.
    periodo: str = ""
    processo_adm: str = ""
    data: str = ""
    concessionaria: str = "COPERGAS"
    gerar_relatorio: bool = False
    unidade: Optional[str] = None
    dados_extras: Optional[dict] = None