from __future__ import annotations

import json
from datetime import datetime

from .config import Config
from .models import Dataset, Periodo


class ReportStateStore:
    """Controla quais relatórios já foram gerados.

    Duas fontes: a coluna 'Relatório Gerado' da planilha (Concluido/Gerar), quando existir,
    e um JSON local atualizado a cada geração (a planilha pode estar aberta no Excel).
    """

    def __init__(self, config: Config):
        self.path = config.estado_path
        self._dados: dict = {}
        if self.path.exists():
            self._dados = json.loads(self.path.read_text(encoding="utf-8"))

    def _salvar(self):
        self.path.write_text(json.dumps(self._dados, ensure_ascii=False, indent=2), encoding="utf-8")

    def marcar(self, p: Periodo, arquivo: str = ""):
        self._dados[p.label] = {"gerado_em": datetime.now().isoformat(timespec="seconds"), "arquivo": arquivo}
        self._salvar()

    def desmarcar(self, p: Periodo):
        self._dados.pop(p.label, None)
        self._salvar()

    def info(self, p: Periodo) -> dict | None:
        return self._dados.get(p.label)

    def concluido(self, p: Periodo, ds: Dataset) -> bool:
        if p.label in self._dados:
            return True
        vals = [f.rel_gerado.casefold() for f in ds.do_periodo(p) if f.rel_gerado]
        return bool(vals) and all(v.startswith("conclu") for v in vals)

    def proximo_pendente(self, ds: Dataset) -> Periodo | None:
        for p in ds.periodos():
            if not self.concluido(p, ds):
                return p
        return None
