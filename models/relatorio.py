# models/relatorio.py
from dataclasses import dataclass, field
from typing import List, Dict
from models.fiscalizacao import Fiscalizacao
from NaoConformidade import NaoConformidade

@dataclass
class Relatorio:
    fiscalizacao: Fiscalizacao
    nao_conformidades: List[NaoConformidade] = field(default_factory=list)
    
    # Dados para Relatório de Qualidade
    indicadores: Dict = field(default_factory=dict)
    tabelas_extrapolacao: Dict = field(default_factory=dict)
    
    # Dados para Relatório de Acompanhamento
    linha_do_tempo: List[Dict] = field(default_factory=list)
    planos_acao: List[Dict] = field(default_factory=list)
    
    # Apêndices fotográficos
    tem_condicoes_gerais: bool = False
    fotos_condicoes_gerais: List[str] = field(default_factory=list)
    
    output_path: str = ""