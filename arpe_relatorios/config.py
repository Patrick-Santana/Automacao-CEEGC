from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

MESES_ABREV = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
MESES_NOME = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
              "agosto", "setembro", "outubro", "novembro", "dezembro"]


def app_dir() -> Path:
    """Pasta base: ao lado do .exe (PyInstaller) ou raiz do projeto."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


@dataclass
class Config:
    base_dir: Path = field(default_factory=app_dir)
    excel_path: Path | None = None
    assets_dir: Path | None = None
    saida_dir: Path | None = None
    estado_path: Path | None = None

    # metas anuais de fiscalização (ano -> meta). Ajuste conforme a Agenda Regulatória.
    meta_anual: dict[int, int] = field(default_factory=lambda: {2025: 372, 2026: 384})
    meta_padrao: int = 372

    fundamentacao_padrao: str = "Art. 38 Inciso V"
    fotos_por_tabela: int = 6          # 3 linhas x 2 colunas
    fotos_colunas: int = 2

    # Nomes aceitos para abas e colunas (o primeiro encontrado vence).
    abas_fisc: tuple = ("Fiscalizacoes", "Fiscalizações")
    abas_nc: tuple = ("Nao_Conformidades", "Nao-conformidades", "Nao_conformidades")
    colunas: dict = field(default_factory=lambda: {
        "fisc_id": ["ID_FISC", "ID da Fiscalização"],
        "data": ["Data"],
        "usuario": ["Usuário", "Usuario", "Cliente"],
        "logradouro": ["Logradouro"],
        "endereco": ["Endereco", "Endereço"],
        "numero": ["Numero", "Número"],
        "bairro": ["Bairro"],
        "cidade": ["Cidade"],
        "segmento": ["Segmento", "Nicho"],
        "func_arpe": ["Func_ARPE"],
        "func_copergas": ["Func_Copergas"],
        "rel_gerado": ["Relatório Gerado", "Relatorio Gerado"],
        "nc_num": ["Num_NC"],
        "nc_fisc": ["ID_FISC_original", "ID da Fiscalização", "ID_FISC"],
        "nc_detalhe": ["Detalhes_NC", "Não Conformidade", "Nao Conformidade"],
        "nc_unidade": ["Cliente_NC", "Unidade"],
        "nc_equip": ["Equipamento"],
        "nc_tipo": ["Nao_conformidade"],
        "nc_status": ["Status_da_NC"],
        "nc_parecer": ["PARECER"],
        "nc_rel": ["Rel_original"],
        "nc_foto": ["Nome da Foto", "Nome_da_Foto"],
    })

    def __post_init__(self):
        self.base_dir = Path(self.base_dir)
        self.excel_path = Path(self.excel_path) if self.excel_path else self.base_dir / "DadosFiscalização.xlsx"
        self.assets_dir = Path(self.assets_dir) if self.assets_dir else self.base_dir / "assets"
        self.saida_dir = Path(self.saida_dir) if self.saida_dir else self.base_dir / "saida"
        self.estado_path = Path(self.estado_path) if self.estado_path else self.base_dir / "estado_relatorios.json"

    @property
    def fotos_nc_dir(self) -> Path:
        return self.assets_dir / "fotos_nao_conformidades"

    @property
    def fotos_gerais_dir(self) -> Path:
        return self.assets_dir / "fotos_condicoes_gerais"

    def meta_do_ano(self, ano: int) -> int:
        return self.meta_anual.get(ano, self.meta_padrao)
