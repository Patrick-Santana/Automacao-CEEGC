"""Diagnóstico do ambiente: versões das bibliotecas e testes isolados (cada teste roda em um processo separado,
então uma falha nativa, como 'access violation', aparece como FALHOU em vez de fechar tudo).
Uso:  python diagnostico.py [caminho\\DadosFiscalização.xlsx]"""
from __future__ import annotations

import platform
import subprocess
import sys

TESTES = {
    "pandas: DataFrame com datas": "import pandas as pd, datetime as d; df=pd.DataFrame({'a':[d.datetime(2026,1,2)]*5}); print(df.dtypes.iloc[0])",
    "pandas: DataFrame de objetos": "import pandas as pd, datetime as d; df=pd.DataFrame([[1,d.date(2026,1,2)]]*5,dtype=object); print(len(df))",
    "pandas: pivot/groupby": "import pandas as pd; df=pd.DataFrame({'a':[1,2,1],'b':['x','y','x']}); print(df.pivot_table(index='b',columns='a',aggfunc='size',fill_value=0).shape)",
    "matplotlib: gerar PNG": "import io; from matplotlib.figure import Figure; f=Figure(); f.subplots().plot([1,2]); b=io.BytesIO(); f.savefig(b,format='png'); print(len(b.getvalue()))",
    "python-docx: criar documento": "import docx; d=docx.Document(); d.add_paragraph('ok'); print('ok')",
    "Pillow: criar imagem": "from PIL import Image; print(Image.new('RGB',(10,10)).size)",
    "pywebview (janela própria)": "import webview; print(getattr(webview,'__version__','?'))",
}


def rodar(codigo: str) -> tuple[bool, str]:
    r = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True, timeout=120)
    saida = (r.stdout.strip() or r.stderr.strip().splitlines()[-1:] and r.stderr.strip().splitlines()[-1] or "")
    if r.returncode != 0 and not saida:
        saida = f"processo terminou com código {r.returncode} (falha nativa)"
    return r.returncode == 0, saida


def main():
    linhas = [f"Python {sys.version.split()[0]} · {platform.platform()}", f"Executável: {sys.executable}", ""]
    for mod in ("numpy", "pandas", "openpyxl", "docx", "matplotlib", "PIL", "lxml", "webview"):
        ok, saida = rodar(f"import {mod}; print(getattr({mod},'__version__','?'), {mod}.__file__)")
        linhas.append(f"{mod:<11} {'OK' if ok else 'AUSENTE/FALHOU'}  {saida}")
    linhas.append("")
    for nome, codigo in TESTES.items():
        ok, saida = rodar(codigo)
        linhas.append(f"[{'OK' if ok else 'FALHOU'}] {nome}  {saida}")
    if len(sys.argv) > 1:
        r = subprocess.run([sys.executable, "-c", f"import sys; sys.path.insert(0, r'{__file__.rsplit('diagnostico.py', 1)[0]}'); "
                            "from arpe_relatorios.config import Config; from arpe_relatorios.repository import ExcelRepository; "
                            "ds=ExcelRepository(Config(excel_path=sys.argv[1])).load(); print(len(ds.fiscalizacoes),'fiscalizações,',len(ds.ncs),'NC')",
                            sys.argv[1]], capture_output=True, text=True, timeout=300)
        ok = r.returncode == 0
        linhas.append(f"[{'OK' if ok else 'FALHOU'}] ler a planilha {sys.argv[1]}  "
                      + (r.stdout.strip() or (r.stderr.strip().splitlines() or [f'código {r.returncode} (falha nativa)'])[-1]))
    texto = "\n".join(linhas)
    print(texto)
    try:
        from pathlib import Path
        Path(__file__).with_name("diagnostico.txt").write_text(texto, encoding="utf-8")
        print("\nRelatório salvo em diagnostico.txt")
    except OSError:
        pass


if __name__ == "__main__":
    main()
