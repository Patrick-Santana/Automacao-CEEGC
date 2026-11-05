"""Criação do atalho (.lnk) na Área de Trabalho do usuário – Windows."""
from __future__ import annotations

import base64
import os
import subprocess
import sys
from pathlib import Path

from .config import caminho_unc


def comando_powershell() -> tuple[str, dict]:
    """Script PowerShell + variáveis de ambiente (os caminhos vão por variável: sem problemas de aspas/acentos)."""
    if getattr(sys, "frozen", False):
        alvo, args, pasta = sys.executable, "", Path(sys.executable).parent
    else:
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        alvo = str(pythonw if pythonw.exists() else sys.executable)
        args, pasta = f'"{Path(sys.argv[0]).resolve()}"', Path(sys.argv[0]).resolve().parent
    env = dict(ARPE_LNK_ALVO=caminho_unc(alvo), ARPE_LNK_ARGS=args, ARPE_LNK_PASTA=caminho_unc(pasta),
               ARPE_LNK_ICONE=caminho_unc(alvo))
    script = (
        "$ErrorActionPreference='Stop';"
        "$w=New-Object -ComObject WScript.Shell;"
        "$d=[Environment]::GetFolderPath('Desktop');"
        "$l=$w.CreateShortcut((Join-Path $d 'ARPE Relatórios.lnk'));"
        "$l.TargetPath=$env:ARPE_LNK_ALVO;$l.Arguments=$env:ARPE_LNK_ARGS;"
        "$l.WorkingDirectory=$env:ARPE_LNK_PASTA;$l.IconLocation=$env:ARPE_LNK_ICONE;"
        "$l.Description='ARPE - Relatórios de Fiscalização';$l.Save();Write-Output (Join-Path $d 'ARPE Relatórios.lnk')")
    return script, env


def criar_atalho() -> str:
    """Cria 'ARPE Relatórios.lnk' na Área de Trabalho apontando para o caminho de rede (UNC) do programa."""
    if not sys.platform.startswith("win"):
        raise OSError("O atalho só pode ser criado no Windows.")
    script, env = comando_powershell()
    cod = base64.b64encode(script.encode("utf-16-le")).decode()
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", cod],
                       capture_output=True, text=True, env={**os.environ, **env}, timeout=30,
                       creationflags=0x08000000)  # CREATE_NO_WINDOW
    if r.returncode != 0:
        raise OSError("Falha ao criar o atalho: " + (r.stderr or r.stdout or "erro desconhecido").strip())
    return r.stdout.strip()
