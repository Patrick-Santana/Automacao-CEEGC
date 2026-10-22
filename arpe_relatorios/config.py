from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

MESES_ABREV = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"]
MESES_NOME = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
              "agosto", "setembro", "outubro", "novembro", "dezembro"]


def app_dir() -> Path:
    """Pasta do usuário: ao lado do .exe (PyInstaller) ou raiz do projeto."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def resource_dir() -> Path:
    """Arquivos embutidos (web/, modelos/) – dentro do bundle do PyInstaller quando congelado."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


# Assinantes padrão (retirados do rodapé do Template.docx). Edite em config.json.
ASSINANTES_PADRAO = [
    {"nome": "Adriano de Paula Santana", "cargo": "Analista de Regulação", "matricula": "3408787-04"},
    {"nome": "Argemiro Alvarez Rivas", "cargo": "Analista Suplementar de Regulação e Fiscalização", "matricula": "1219413-03"},
    {"nome": "Ernesto Oliveira de Melo", "cargo": "Analista de Desenvolvimento", "matricula": "2227916-04"},
    {"nome": "Marta Rejane de Lima", "cargo": "Analista Suplementar de Regulação e Fiscalização", "matricula": "1831011-03"},
]

# Campos que o usuário pode alterar pela interface e que ficam salvos em config.json
CAMPOS_PERSISTIDOS = ("excel_path", "assets_dir", "saida_dir", "template_path", "meta_anual", "meta_padrao",
                      "total_municipios", "fundamentacao_artigo", "fundamentacao_inciso", "assinantes",
                      "incluir_condicoes_gerais", "gerar_fotos_sinteticas", "tema", "ultimo_pa", "ultimo_sei")
_CAMPOS_CAMINHO = ("excel_path", "assets_dir", "saida_dir", "template_path")


@dataclass
class Config:
    base_dir: Path = field(default_factory=app_dir)
    excel_path: Path | None = None
    assets_dir: Path | None = None
    saida_dir: Path | None = None
    template_path: Path | None = None
    estado_path: Path | None = None
    config_path: Path | None = None

    meta_anual: dict[int, int] = field(default_factory=lambda: {2025: 372, 2026: 384})
    meta_padrao: int = 372
    total_municipios: int = 26            # municípios com instalações da Copergás (texto do relatório)

    fundamentacao_artigo: str = "Art. 38"
    fundamentacao_inciso: str = "Inciso V"
    assinantes: list = field(default_factory=lambda: [dict(a) for a in ASSINANTES_PADRAO])

    fotos_por_tabela: int = 6             # 3 linhas x 2 colunas
    fotos_colunas: int = 2
    incluir_condicoes_gerais: bool = False
    gerar_fotos_sinteticas: bool = False
    tema: str = "auto"
    ultimo_pa: str = ""
    ultimo_sei: str = ""

    abas_fisc: tuple = ("Fiscalizacoes", "Fiscalizações")
    abas_nc: tuple = ("Nao_Conformidades", "Nao-conformidades", "Nao_conformidades")
    abas_metas: tuple = ("Meta_Municipios", "Metas", "Meta Municipios")
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
        b = self.base_dir
        self.config_path = Path(self.config_path) if self.config_path else b / "config.json"
        self.excel_path = Path(self.excel_path) if self.excel_path else b / "DadosFiscalização.xlsx"
        self.assets_dir = Path(self.assets_dir) if self.assets_dir else b / "assets"
        self.saida_dir = Path(self.saida_dir) if self.saida_dir else b / "saida"
        self.template_path = Path(self.template_path) if self.template_path else b / "modelos" / "Template.docx"
        self.estado_path = Path(self.estado_path) if self.estado_path else b / "estado_relatorios.json"

    # ---------- persistência ----------
    @classmethod
    def carregar(cls, base_dir: Path | None = None, **overrides) -> "Config":
        """Lê config.json (se existir); argumentos explícitos (linha de comando) têm prioridade."""
        explicitos = {k: v for k, v in overrides.items() if v is not None}
        cfg = cls(base_dir=base_dir or app_dir(), **explicitos)
        if cfg.config_path.exists():
            try:
                dados = json.loads(cfg.config_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                dados = {}
            for k, v in dados.items():
                if k in CAMPOS_PERSISTIDOS and k not in explicitos:
                    cfg.definir(k, v)
        return cfg

    def definir(self, chave: str, valor):
        if chave in _CAMPOS_CAMINHO:
            valor = Path(valor)
        elif chave == "meta_anual":
            valor = {int(k): int(v) for k, v in dict(valor).items()}
        elif chave in ("meta_padrao", "total_municipios"):
            valor = int(valor)
        setattr(self, chave, valor)

    def salvar(self):
        dados = {}
        for k in CAMPOS_PERSISTIDOS:
            v = getattr(self, k)
            if k in _CAMPOS_CAMINHO:
                v = str(v)
            elif k == "meta_anual":
                v = {str(a): b for a, b in v.items()}
            dados[k] = v
        self.config_path.write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- derivados ----------
    @property
    def fotos_nc_dir(self) -> Path:
        return self.assets_dir / "fotos_nao_conformidades"

    @property
    def fotos_gerais_dir(self) -> Path:
        return self.assets_dir / "fotos_condicoes_gerais"

    @property
    def mapas_dir(self) -> Path:
        return self.assets_dir / "mapas"

    def meta_do_ano(self, ano: int) -> int:
        return self.meta_anual.get(ano, self.meta_padrao)

    def template_efetivo(self) -> Path:
        """Template escolhido pelo usuário; se não existir, usa a cópia embutida."""
        if self.template_path.exists():
            return self.template_path
        return resource_dir() / "modelos" / "Template.docx"
