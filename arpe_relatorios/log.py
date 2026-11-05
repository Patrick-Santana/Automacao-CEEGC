"""Registro em arquivo (arpe_log.txt, pasta de dados do usuário). Nunca levanta exceção."""
from __future__ import annotations

import time
from pathlib import Path


def registrar(pasta, texto: str):
    try:
        arq = Path(pasta) / "arpe_log.txt"
        if arq.exists() and arq.stat().st_size > 300_000:
            arq.write_text("", encoding="utf-8")
        with arq.open("a", encoding="utf-8") as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {texto}\n")
    except Exception:  # noqa: BLE001
        pass
