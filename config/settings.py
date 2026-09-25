# config/settings.py
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Assets
ASSETS_DIR = BASE_DIR / 'assets'
TEMPLATES_DIR = ASSETS_DIR / 'templates'
STYLES_DIR = ASSETS_DIR / 'styles'
IMAGES_DIR = ASSETS_DIR / 'images'
FOTOS_NC_DIR = ASSETS_DIR / 'fotos_nao_conformidades'
FOTOS_CG_DIR = ASSETS_DIR / 'fotos_condicoes_gerais'

# Data
DATA_DIR = BASE_DIR / 'data'
INPUT_DIR = DATA_DIR / 'input'
PLANILHAS_DIR = INPUT_DIR / 'planilhas'
UPLOADS_DIR = INPUT_DIR / 'uploads'
OUTPUT_DIR = DATA_DIR / 'output'
RELATORIOS_DIR = OUTPUT_DIR / 'relatorios'
LOGS_DIR = OUTPUT_DIR / 'logs'

# Criação das Pastas 
for d in [ASSETS_DIR, TEMPLATES_DIR, STYLES_DIR, IMAGES_DIR, FOTOS_NC_DIR, FOTOS_CG_DIR,
          DATA_DIR, INPUT_DIR, PLANILHAS_DIR, UPLOADS_DIR, OUTPUT_DIR, RELATORIOS_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# Templates
TEMPLATE_QUALIDADE = TEMPLATES_DIR / 'RELATORIO_QUALIDADE.docx'
TEMPLATE_ACOMPANHAMENTO = TEMPLATES_DIR / 'RELATORIO_ACOMPANHAMENTO.docx'
TEMPLATE_DIRETA = TEMPLATES_DIR / 'RELATORIO_DIRETA.docx'

# Estilização
CSS_CUSTOM = STYLES_DIR / 'custom.css'