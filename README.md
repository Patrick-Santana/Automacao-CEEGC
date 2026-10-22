# ARPE · Relatórios de Fiscalização — v2.0

## O que mudou
1. **Interface nova** (painel web local, janela própria com pywebview ou navegador): cartões de KPI, abas, gráficos
   com cantos arredondados, tema claro/escuro automático, diálogo de geração.
2. **Relatório gerado a partir do `modelos/Template.docx`** (o mesmo do ModeloGas.pdf): capa, sumário, seções 1–5,
   Apêndice 1 (fotos das NC, 6 por tabela, 3×2) e Apêndice 2 (tabelas e gráficos). Edite o Template e o próximo
   relatório já sai com a mudança; para outro modelo use *Configurações › Template*.
3. **Bug do primeiro relatório em 01/2024 corrigido**: na primeira execução o aplicativo pergunta
   *"qual foi o último relatório já entregue?"* (sugere o mês anterior ao mais recente). O próximo pendente passa a ser o
   mês seguinte; depois de gerar, o histórico avança sozinho. Antes de gerar, o diálogo mostra o mês escolhido.

## Uso
- Interface: `python main.py` (ou o `.exe`).
- Linha de comando: `python main.py status` · `python main.py gerar [--periodo 05/2026] [--pa 5] [--sei ...] [--baseline 04/2026]`
- Fotos: `assets/fotos_nao_conformidades/ID <n> - <Cidade>/`; mapas opcionais: `assets/mapas/figura01.png … figura04.png`.
- `metas_municipios.csv` (Cidade,Meta): meta por município da Tabela 01 (soma atual 372; a meta anual 2026 é 384).
- A aba `Gráficos AAAA` (dias programados, NC sanadas, clientes sanados, meta anual) é lida quando existir.
- Executável (Windows): `build_exe.bat`.
