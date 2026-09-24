# models/nao_conformidade.py
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class NaoConformidade:
    id_fiscalizacao: int
    inciso: str
    indicador: str
    descricao: str
    fundamentacao: str
    quantidade: int
    nome_fotos: List[str]
    fotos_paths: Optional[List[str]] = None
    justificativa: Optional[str] = None
    status: Optional[str] = "Pendente"
    plano_acao: Optional[str] = None