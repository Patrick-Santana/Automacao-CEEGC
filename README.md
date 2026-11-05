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
- Fotos: `assets/fotos_nao_conformidades/ID <n> - <Cidade>/`; mapas **desativados por padrão (v2.2)**: para voltar a incluí-los, `"incluir_mapas": true` em `config.json` (ou `--com-mapas` na linha de comando) e salve `assets/mapas/figura01.png … figura04.png`.
- `metas_municipios.csv` (Cidade,Meta): meta por município da Tabela 01 (soma atual 372; a meta anual 2026 é 384).
- A aba `Gráficos AAAA` (dias programados, NC sanadas, clientes sanados, meta anual) é lida quando existir.
- Executável (Windows): `build_exe.bat` (`build_exe.bat debug` gera versão com console). Implantação em servidor: veja `LEIA-ME_implantacao.txt`.

## v2.2
- **Sem mapas no relatório:** Figuras 01 a 04, seus textos e avisos foram retirados pelo código; o Template não precisa ser editado
  (se você apagar os mapas do Template, o gerador continua funcionando). A tabela de situação por município do Apêndice 2 foi mantida,
  agora como "Tabela NN" numerada.
- **Tratamento de erros amigável:** sem planilha, planilha aberta no Excel, arquivo inválido ou aba/coluna faltando, a interface mostra
  uma tela explicando o que fazer ("Carregar planilha…" / "Tentar novamente"), com os detalhes técnicos recolhidos.

## v2.3 — executável em pasta de servidor
- Executando de `\\servidor\pasta` ou unidade mapeada (Y:), abre no navegador padrão e encerra ao fechar a aba (a janela própria usa .NET e falha ao carregar DLLs da rede).
- Qualquer erro de inicialização aparece numa janela do Windows e fica em `arpe_log.txt` (antes, em modo sem console, o programa simplesmente não abria).
- Não abre duas vezes: se já estiver aberto, reaproveita a instância.
- Atalho na Área de Trabalho: botão em Configurações, `criar_atalho.bat` ou `ARPE_Relatorios.exe --criar-atalho` (usa caminho UNC e "Iniciar em" correto).
- config.json/estado/log vão para `%LOCALAPPDATA%\ARPE_Relatorios` quando o programa está na rede ou sem permissão de escrita.

## v2.3.1 — correção: programa fechava ao carregar a planilha / janela não abria
- Leitura da planilha reescrita: abre o arquivo uma vez, em modo leitura, e lê só a região usada (antes, planilhas formatadas até a última
  linha do Excel consumiam muita memória e derrubavam o programa). Carga típica: ~0,5 s.
- A janela abre na hora e mostra "Carregando a planilha…"; a carga acontece em segundo plano.
- Proteção contra "ciclo de travamento": se uma planilha derrubar o programa, na próxima abertura ele volta sozinho à última planilha
  que funcionou e explica o que aconteceu (antes, o caminho ruim ficava salvo e o programa quebrava em toda abertura).
- "Abrir planilha…" / "Pasta de assets…": na janela própria usa o seletor do pywebview; fora dela, um processo separado
  (o tkinter dentro do servidor podia derrubar o programa).
- Janela própria usa perfil temporário do WebView2 a cada execução e, se não carregar em 25 s, abre no navegador.
- Diagnóstico: `arpe_log.txt` (passo a passo) e `arpe_crash.txt` (pilha em falha nativa ou travamento > 90 s).

## v2.3.1 (2) — causa do fechamento na carga
- `arpe_crash.txt` mostrou *access violation* dentro do pandas, ao converter datas (`_construct_from_dt64_naive`) – falha nativa
  típica de pacotes incompatíveis entre si (numpy/pandas de instalações diferentes, ex.: `%APPDATA%\Python\Python314` + Python 3.14 recente).
- O programa não depende mais dessa conversão: dados lidos como objetos e datas como `datetime.date`.
- `diagnostico.bat` / `python diagnostico.py [planilha.xlsx]` mostra as versões e testa cada biblioteca em processo separado.
- `build_exe.bat` agora cria o ambiente isolado `.venv_build` (Python 3.13/3.12 se disponível) antes de gerar o .exe.
- Se o diagnóstico acusar FALHOU no pandas: `python -m pip install --upgrade --force-reinstall numpy pandas` (ou use Python 3.12/3.13 num venv).
