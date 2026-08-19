import os

# Lista de todas as pastas necessárias
pastas = [
    "app/pages",
    "app/components",
    "models",
    "services",
    "controllers",
    "config",
    "utils",
    "assets/templates",
    "assets/styles",
    "assets/images",
    "assets/fotos_nao_conformidades",
    "assets/fotos_condicoes_gerais",
    "data/input/planilhas",
    "data/input/uploads",
    "data/output/relatorios",
    "data/output/logs",
    "scripts"
]

# Lista de todos os arquivos necessários
arquivos = [
    "app/__init__.py", "app/main.py",
    "app/pages/home.py", "app/pages/upload.py", "app/pages/selection.py", "app/pages/report.py",
    "app/components/__init__.py", "app/components/file_uploader.py", "app/components/fiscalizacao_card.py", "app/components/image_preview.py",
    "models/__init__.py", "models/fiscalizacao.py", "models/nao_conformidade.py", "models/relatorio.py",
    "services/__init__.py", "services/excel_service.py", "services/image_service.py", "services/word_service.py", "services/report_service.py",
    "controllers/__init__.py", "controllers/file_controller.py", "controllers/report_controller.py",
    "config/__init__.py", "config/settings.py", "config/constants.py",
    "utils/__init__.py", "utils/file_utils.py", "utils/image_utils.py", "utils/validators.py",
    "assets/templates/RELATORIO_MODELO.docx", 
    "assets/styles/custom.css", 
    "assets/images/logo_pe.png",
    "scripts/setup.py", "scripts/gerar_teste.py",
    "requirements.txt", ".env.example", ".gitignore", "README.md"
]

print("Criando estrutura de pastas...")
for pasta in pastas:
    os.makedirs(pasta, exist_ok=True)

print("Criando arquivos vazios...")
for arquivo in arquivos:
    # Cria o arquivo vazio (se já existir, não apaga o conteúdo)
    with open(arquivo, 'a') as f:
        pass

print("Estrutura criada com sucesso!")