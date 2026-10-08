# Automação de Relatórios de Fiscalização (ARPE / Copergás)

Dashboard + gerador de relatórios `.docx` a partir da planilha de fiscalizações e das fotos das não conformidades.

## Como usar
```bash
pip install -r requirements.txt
# coloque DadosFiscalização.xlsx na raiz do projeto (ou aponte com --excel)
python main.py                                   # abre o dashboard
python main.py relatorio                         # gera o próximo relatório pendente
python main.py relatorio --mes 05/2026 --fotos-sinteticas
python main.py fotos --mes 05/2026               # só gera as fotos ilustrativas
python main.py painel-png --ano 2026             # exporta os gráficos
python main.py marcar 01/2026 02/2026            # marca meses já entregues
```
Executável (Windows): `build_exe.bat` → `dist/ArpeRelatorios/ArpeRelatorios.exe`
(deixe `DadosFiscalização.xlsx` e a pasta `assets/` ao lado do .exe).

## Arquitetura (orientação a objetos)
| Classe | Módulo | Papel |
|---|---|---|
| `Config` | config.py | caminhos, metas anuais, nomes aceitos de abas/colunas |
| `Periodo`, `Fiscalizacao`, `NaoConformidade`, `Dataset` | models.py | modelo de domínio |
| `ExcelRepository` | repository.py | lê a planilha → `Dataset` |
| `ReportStateStore` | state.py | controla relatórios gerados (coluna "Relatório Gerado" e/ou JSON) |
| `DashboardAnalytics` | analytics.py | Tabelas 05–11 e KPIs do Apêndice 2 |
| `ChartFactory` | charts.py | gráficos (usados no dashboard e no .docx) |
| `PhotoLibrary`, `SyntheticPhotoGenerator` | photos.py | localiza fotos / gera fotos ilustrativas |
| `PhotoTableBuilder`, `ReportBuilder` | report.py | monta o .docx (fotos 3×2 por tabela + legenda) |
| `DashboardApp` | gui.py | interface Tkinter |

## Convenções de pastas de fotos
```
assets/fotos_nao_conformidades/ID <n> - <Cidade>/NC<Num_NC>_*.jpg
assets/fotos_condicoes_gerais/ID <n> - <Cidade>/*.jpg
```
`<n>` = ordem da cidade (pela primeira data de fiscalização) dentro do mês do relatório
(`photos.visita_ids`). Se a planilha tiver a coluna **Nome da Foto**, ela tem prioridade.

## Fotos sintéticas
As imagens geradas por `SyntheticPhotoGenerator` levam a tarja "IMAGEM ILUSTRATIVA (SINTÉTICA)".
Servem só para testar layout; **não use como evidência** em relatório oficial.
