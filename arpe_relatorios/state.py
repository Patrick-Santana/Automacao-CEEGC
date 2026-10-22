from __future__ import annotations

import json
from datetime import datetime

from .config import Config
from .models import Dataset, Periodo


class ReportStateStore:
    """Controla quais relatórios já foram gerados/entregues.

    Fontes (qualquer uma marca o mês como concluído):
      1. ``baseline``: "último mês já entregue" – tudo até ele é histórico (corrige o bug da v1, em que,
         sem nenhuma marca, o 'próximo pendente' era o primeiro mês da planilha, 01/2024);
      2. marcas individuais, gravadas a cada geração (JSON local – a planilha pode estar aberta no Excel);
      3. coluna 'Relatório Gerado' da planilha, se existir (valor 'Concluido').
    """

    def __init__(self, config: Config):
        self.path = config.estado_path
        self._dados: dict = {"baseline": None, "gerados": {}, "alertas_dispensados": []}
        if self.path.exists():
            try:
                lido = json.loads(self.path.read_text(encoding="utf-8"))
                # compatível com o formato da v1 (dicionário plano "MM/AAAA" -> info)
                if "gerados" in lido or "baseline" in lido:
                    self._dados.update(lido)
                else:
                    self._dados["gerados"] = lido
            except (OSError, ValueError):
                pass

    def _salvar(self):
        self.path.write_text(json.dumps(self._dados, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---------- escrita ----------
    def definir_baseline(self, p: Periodo | None):
        self._dados["baseline"] = p.label if p else None
        self._salvar()

    def marcar(self, p: Periodo, arquivo: str = ""):
        self._dados["gerados"][p.label] = {"gerado_em": datetime.now().isoformat(timespec="seconds"), "arquivo": arquivo}
        self._salvar()

    # ---------- alertas confirmados (dispensados) ----------
    @property
    def alertas_dispensados(self) -> list[str]:
        return list(self._dados.get("alertas_dispensados", []))

    def dispensar_alerta(self, texto: str):
        lista = self._dados.setdefault("alertas_dispensados", [])
        if texto not in lista:
            lista.append(texto)
            self._salvar()

    def reexibir_alertas(self):
        self._dados["alertas_dispensados"] = []
        self._salvar()

    def desmarcar(self, p: Periodo):
        self._dados["gerados"].pop(p.label, None)
        self._salvar()

    # ---------- leitura ----------
    @property
    def baseline(self) -> Periodo | None:
        b = self._dados.get("baseline")
        return Periodo.parse(b) if b else None

    def info(self, p: Periodo) -> dict | None:
        return self._dados["gerados"].get(p.label)

    def _marcado_na_planilha(self, p: Periodo, ds: Dataset) -> bool:
        vals = [f.rel_gerado.casefold() for f in ds.do_periodo(p) if f.rel_gerado]
        return bool(vals) and all(v.startswith("conclu") for v in vals)

    def status(self, p: Periodo, ds: Dataset) -> str:
        """'gerado' | 'historico' | 'planilha' | 'pendente'"""
        if p.label in self._dados["gerados"]:
            return "gerado"
        if self._marcado_na_planilha(p, ds):
            return "planilha"
        b = self._ancora(ds)
        if b and p <= b:
            return "historico"
        return "pendente"

    def _ancora(self, ds: Dataset) -> Periodo | None:
        """Último mês considerado entregue: o maior entre o baseline, os gerados e os concluídos na planilha.
        Tudo o que vem antes é histórico (evita que, após gerar 09/2026, o 'próximo' volte a ser 01/2024)."""
        cands = [p for p in (Periodo.parse(k) for k in self._dados["gerados"]) if p]
        if self.baseline:
            cands.append(self.baseline)
        cands += [p for p in ds.periodos() if self._marcado_na_planilha(p, ds)]
        return max(cands) if cands else None

    def concluido(self, p: Periodo, ds: Dataset) -> bool:
        return self.status(p, ds) != "pendente"

    def sem_historico(self, ds: Dataset) -> bool:
        """Nada indica o que já foi entregue: o aplicativo deve perguntar o último mês entregue."""
        if self.baseline or self._dados["gerados"]:
            return False
        return not any(self._marcado_na_planilha(p, ds) for p in ds.periodos())

    def sugerir_baseline(self, ds: Dataset) -> Periodo | None:
        """Sugestão: o mês anterior ao mais recente com dados (o mais recente é o relatório da vez)."""
        ps = ds.periodos()
        return ps[-1].anterior if ps else None

    def pendentes(self, ds: Dataset) -> list[Periodo]:
        return [p for p in ds.periodos() if not self.concluido(p, ds)]

    def proximo_pendente(self, ds: Dataset) -> Periodo | None:
        """Mais antigo ainda pendente. Sem histórico algum, devolve o mês mais recente (nunca 01/2024)."""
        ps = ds.periodos()
        if not ps:
            return None
        if self.sem_historico(ds):
            return ps[-1]
        pend = self.pendentes(ds)
        return pend[0] if pend else None
