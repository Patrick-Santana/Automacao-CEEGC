from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .config import Config
from .metas import normalizar
from .models import Dataset, Fiscalizacao, NaoConformidade, Periodo

EXT = {".jpg", ".jpeg", ".png", ".webp"}
_PASTA = re.compile(r"^\s*ID\s*(\d+)\s*[-–]\s*(.+?)\s*$", re.I)


def visita_ids(fiscs: list[Fiscalizacao]) -> dict[str, int]:
    """'ID n - Cidade': n = ordem da cidade (pela 1ª data) dentro do mês do relatório."""
    ordem: dict[str, int] = {}
    for f in sorted(fiscs, key=lambda x: (x.data, x.id)):
        ordem.setdefault(f.cidade, len(ordem) + 1)
    return ordem


@dataclass
class FotoItem:
    path: Path
    legenda: str


class PhotoLibrary:
    """Localiza fotos em assets/fotos_nao_conformidades e assets/fotos_condicoes_gerais.

    As pastas são 'ID <n> - <Cidade>'. A busca é tolerante: casa pelo nome da cidade (sem acento/caixa)
    e prefere o <n> esperado, mas aceita outro <n> da mesma cidade."""

    def __init__(self, config: Config):
        self.cfg = config

    @staticmethod
    def pasta_visita(base: Path, vid: int, cidade: str) -> Path:
        return base / f"ID {vid} - {cidade}"

    def _imgs(self, pasta: Path) -> list[Path]:
        if not pasta.exists():
            return []
        return sorted(p for p in pasta.rglob("*") if p.suffix.lower() in EXT)

    def _pastas_da_cidade(self, base: Path, cidade: str) -> list[tuple[int, Path]]:
        if not base.exists():
            return []
        achadas = []
        for d in base.iterdir():
            m = _PASTA.match(d.name) if d.is_dir() else None
            if m and normalizar(m.group(2)) == normalizar(cidade):
                achadas.append((int(m.group(1)), d))
        return sorted(achadas)

    def _imagens_cidade(self, base: Path, vid: int, cidade: str, todas: bool) -> list[Path]:
        pastas = self._pastas_da_cidade(base, cidade)
        exatas = [d for n, d in pastas if n == vid]
        escolhidas = exatas or ([d for _, d in pastas] if todas else
                                ([max(pastas, key=lambda x: x[1].stat().st_mtime)[1]] if pastas else []))
        return [i for d in escolhidas for i in self._imgs(d)]

    def fotos_nc(self, nc: NaoConformidade, f: Fiscalizacao, vid: int) -> list[Path]:
        todas = self._imagens_cidade(self.cfg.fotos_nc_dir, vid, f.cidade, todas=True) or \
            self._imgs(self.cfg.fotos_nc_dir)
        if nc.foto_nome:
            alvo = nc.foto_nome.casefold()
            achadas = [p for p in todas if p.name.casefold() == alvo or p.stem.casefold() == Path(alvo).stem]
            if achadas:
                return achadas
        padrao = re.compile(rf"^NC0*{nc.num}(\D|$)|fisc0*{f.seq}(\D|$)|fisc_?0*{f.id}(\D|$)", re.I)
        return [p for p in todas if padrao.search(p.stem)]

    def fotos_gerais(self, vid: int, cidade: str) -> list[Path]:
        return self._imagens_cidade(self.cfg.fotos_gerais_dir, vid, cidade, todas=False)


# ----------------------------------------------------------------------------------------------
class SyntheticPhotoGenerator:
    """Gera fotos ILUSTRATIVAS (sintéticas) a partir da descrição da não conformidade.

    Servem para testar o layout do relatório enquanto não há fotos reais. Todas trazem a tarja
    'IMAGEM ILUSTRATIVA' para nunca serem confundidas com evidência de campo."""

    W, H = 960, 1200

    def __init__(self, config: Config, seed: int = 7):
        self.cfg = config
        self.rng = np.random.default_rng(seed)
        self._fontes: dict = {}

    # ---------- infraestrutura ----------
    def _font(self, size: int, bold=True):
        key = (size, bold)
        if key not in self._fontes:
            try:
                from matplotlib import font_manager
                f = font_manager.findfont(font_manager.FontProperties(family="DejaVu Sans", weight="bold" if bold else "normal"))
                self._fontes[key] = ImageFont.truetype(f, size)
            except Exception:  # noqa: BLE001
                self._fontes[key] = ImageFont.load_default()
        return self._fontes[key]

    def _lowfreq(self, amp: float, cell=60):
        small = self.rng.random((self.H // cell + 2, self.W // cell + 2))
        im = Image.fromarray((small * 255).astype("uint8")).resize((self.W, self.H), Image.BICUBIC)
        return ((np.asarray(im, float) / 255) - .5)[..., None] * amp

    def _superficie(self, rgb, ruido=12, manchas=28):
        arr = np.ones((self.H, self.W, 3)) * np.array(rgb, float)
        arr += self.rng.normal(0, ruido, (self.H, self.W, 1)) + self._lowfreq(manchas)
        return Image.fromarray(arr.clip(0, 255).astype("uint8"))

    def _tubo(self, d, x0, y0, x1, y1, r, rgb):
        horiz = abs(x1 - x0) >= abs(y1 - y0)
        for i in range(-r, r + 1):
            k = .45 + .65 * math.cos(i / r * math.pi / 2.2)
            c = tuple(int(min(255, v * k)) for v in rgb)
            d.line([(x0, y0 + i), (x1, y0 + i)] if horiz else [(x0 + i, y0), (x0 + i, y1)], fill=c)

    def _texto(self, d, xy, txt, size, fill, bold=True, anchor="la"):
        d.text(xy, txt, font=self._font(size, bold), fill=fill, anchor=anchor)

    def _ferrugem(self, img, box, n=40, intens=1.0):
        d = ImageDraw.Draw(img, "RGBA")
        x0, y0, x1, y1 = box
        for _ in range(n):
            x, y = int(self.rng.integers(x0, x1)), int(self.rng.integers(y0, y1))
            r = int(self.rng.integers(6, 34))
            d.ellipse([x - r, y - r * .7, x + r, y + r * .7], fill=(int(150 + self.rng.integers(-30, 30)), 70, 25, int(70 * intens)))
            if self.rng.random() < .5:
                d.line([(x, y), (x + int(self.rng.integers(-6, 6)), y + int(self.rng.integers(40, 160)))],
                       fill=(120, 60, 25, int(55 * intens)), width=int(self.rng.integers(2, 6)))

    def _finalizar(self, img: Image.Image, luz=1.0) -> Image.Image:
        img = img.filter(ImageFilter.GaussianBlur(1.1))
        a = np.asarray(img, float)
        yy, xx = np.mgrid[0:self.H, 0:self.W]
        v = 1 - .42 * (((xx - self.W / 2) / (self.W / 1.15)) ** 2 + ((yy - self.H / 2) / (self.H / 1.15)) ** 2)
        a = a * v[..., None] * luz + self.rng.normal(0, 6, a.shape)
        img = Image.fromarray(a.clip(0, 255).astype("uint8"))
        d = ImageDraw.Draw(img, "RGBA")
        d.rectangle([0, self.H - 44, self.W, self.H], fill=(0, 0, 0, 150))
        self._texto(d, (self.W // 2, self.H - 22), "IMAGEM ILUSTRATIVA (SINTÉTICA) – NÃO É EVIDÊNCIA DE CAMPO", 19,
                    (255, 255, 255, 235), anchor="mm")
        return img

    # ---------- componentes ----------
    def _placa(self, img, box, estado="ok"):
        d = ImageDraw.Draw(img, "RGBA")
        x0, y0, x1, y1 = box
        d.rounded_rectangle(box, 10, fill=(238, 196, 30), outline=(40, 40, 40), width=5)
        cx = (x0 + x1) // 2
        d.polygon([(cx, y0 + 25), (cx - 65, y0 + 135), (cx + 65, y0 + 135)], fill=(20, 20, 20))
        self._texto(d, (cx, y0 + 105), "!", 70, (238, 196, 30), anchor="mm")
        self._texto(d, (cx, y0 + 175), "ATENÇÃO", 40, (20, 20, 20), anchor="mm")
        self._texto(d, (cx, y0 + 225), "GÁS INFLAMÁVEL", 30, (20, 20, 20), anchor="mm")
        self._texto(d, (cx, y0 + 268), "PROIBIDO FUMAR", 26, (180, 20, 20), anchor="mm")
        for px, py in ((x0 + 16, y0 + 16), (x1 - 16, y0 + 16), (x0 + 16, y1 - 16), (x1 - 16, y1 - 16)):
            d.ellipse([px - 6, py - 6, px + 6, py + 6], fill=(90, 90, 90))
        if estado == "ilegivel":
            d.rounded_rectangle(box, 10, fill=(225, 220, 200, 185))
            self._ferrugem(img, box, 18, .8)
            for _ in range(22):
                x, y = int(self.rng.integers(x0, x1)), int(self.rng.integers(y0, y1))
                d.line([(x, y), (x + int(self.rng.integers(-60, 60)), y + int(self.rng.integers(-30, 30)))], fill=(255, 255, 255, 140), width=3)

    def _medidor(self, img, estado):
        d = ImageDraw.Draw(img, "RGBA")
        self._tubo(d, 250, 40, 250, 470, 34, (165, 95, 60))
        self._tubo(d, 480, 40, 480, 470, 34, (170, 100, 65))
        self._tubo(d, 720, 40, 720, 470, 30, (235, 190, 40))
        d.rounded_rectangle([150, 470, 830, 900], 34, fill=(140, 142, 145))
        d.rounded_rectangle([200, 450, 800, 760], 26, fill=(214, 217, 219), outline=(120, 120, 125), width=4)
        d.rectangle([250, 480, 750, 545], fill=(238, 238, 236))
        for i, ch in enumerate("00184372"):
            d.rectangle([260 + i * 60, 488, 312 + i * 60, 538], fill=(25, 25, 25) if i < 5 else (170, 30, 30))
            self._texto(d, (286 + i * 60, 513), ch, 36, (245, 245, 245), anchor="mm")
        self._texto(d, (250, 575), "Qmáx: 6 m³/h   Qmín: 0,04 m³/h", 20, (60, 60, 65), bold=False)
        self._texto(d, (250, 606), "MEDIDOR TIPO DIAFRAGMA G4", 20, (60, 60, 65), bold=False)
        lb = [440, 640, 750, 735]
        if estado == "ausente":
            d.rectangle(lb, fill=(196, 199, 201))
            d.rectangle([lb[0] + 6, lb[1] + 8, lb[2] - 30, lb[3] - 12], fill=(178, 182, 186))
        else:
            d.rectangle(lb, fill=(28, 56, 150), outline=(230, 230, 230), width=2)
            txt = {"ok": ("MVAZ.05838-6", "CALIB: JUL/24"), "vencida": ("MVAZ.04890-9", "CALIB: MAR/15"),
                   "incompleta": ("MVAZ.04890-9", "CALIB: --/15"), "ilegivel": ("MVAZ.04890-9", "CALIB: MAR/15")}[estado]
            self._texto(d, ((lb[0] + lb[2]) // 2, lb[1] + 28), txt[0], 21, (240, 240, 255), anchor="mm")
            self._texto(d, ((lb[0] + lb[2]) // 2, lb[1] + 66), txt[1], 24, (255, 255, 255), anchor="mm")
            if estado == "ilegivel":
                d.rectangle(lb, fill=(180, 190, 210, 150))
                for _ in range(30):
                    x, y = int(self.rng.integers(lb[0], lb[2])), int(self.rng.integers(lb[1], lb[3]))
                    d.line([(x, y), (x + 40, y + int(self.rng.integers(-6, 6)))], fill=(230, 230, 230, 150), width=4)
        d.rounded_rectangle([170, 600, 250, 640], 8, fill=(240, 240, 240), outline=(150, 150, 150))

    def _psv(self, img, estado):
        d = ImageDraw.Draw(img, "RGBA")
        self._tubo(d, 100, 800, 860, 800, 40, (150, 155, 160))
        self._tubo(d, 480, 420, 480, 800, 46, (190, 30, 30))
        d.rounded_rectangle([395, 270, 565, 440], 22, fill=(196, 196, 200), outline=(90, 90, 95), width=3)
        d.rectangle([440, 150, 520, 280], fill=(170, 170, 175), outline=(90, 90, 95), width=3)
        for y in range(300, 420, 22):
            d.line([(395, y), (565, y)], fill=(120, 120, 125), width=3)
        d.line([(565, 350), (700, 470)], fill=(200, 200, 200), width=4)
        if estado != "ausente":
            tag = [640, 470, 860, 620]
            d.rectangle(tag, fill=(236, 232, 210), outline=(90, 90, 90), width=3)
            self._texto(d, (750, 505), "PSV-01", 24, (30, 30, 30), anchor="mm")
            self._texto(d, (750, 560), "CALIB: OUT/14" if estado == "vencida" else "CALIB: JUL/25", 24,
                        (150, 20, 20) if estado == "vencida" else (20, 90, 30), anchor="mm")
        else:
            d.line([(700, 470), (705, 560)], fill=(200, 200, 200), width=3)
        d.ellipse([465, 385, 495, 415], fill=(230, 60, 60))

    # ---------- cenários ----------
    def _cena(self, chave: str) -> Image.Image:
        W = self.W
        base = self._superficie((70, 72, 78), 14, 30)
        d = ImageDraw.Draw(base, "RGBA")
        if chave.startswith("medidor"):
            self._medidor(base, chave.split(":")[1])
        elif chave.startswith("psv"):
            self._psv(base, chave.split(":")[1])
        elif chave.startswith("placa"):
            est = chave.split(":")[1]
            img = self._superficie((176, 172, 162), 10, 34)
            dd = ImageDraw.Draw(img, "RGBA")
            self._tubo(dd, 0, 1020, W, 1020, 22, (150, 155, 160))
            dd.rectangle([120, 220, 840, 900], fill=(190, 192, 195), outline=(110, 110, 115), width=6)
            for x in range(120, 840, 60):
                dd.line([(x, 220), (x, 900)], fill=(150, 152, 155), width=3)
            if est == "ausente":
                dd.rectangle([300, 330, 660, 760], fill=(200, 202, 205))
                dd.rectangle([304, 334, 656, 756], outline=(150, 150, 150), width=3)
                for px, py in ((320, 350), (640, 350), (320, 740), (640, 740)):
                    dd.ellipse([px - 7, py - 7, px + 7, py + 7], fill=(60, 60, 60))
                    dd.line([(px, py), (px, py + 60)], fill=(140, 110, 90, 130), width=5)
            else:
                self._placa(img, (300, 330, 660, 760), est)
            return img
        elif chave == "lacre":
            self._tubo(d, 100, 600, 860, 600, 40, (150, 155, 160))
            d.rounded_rectangle([390, 430, 570, 700], 30, fill=(225, 180, 30), outline=(90, 70, 10), width=3)
            self._tubo(d, 480, 250, 480, 430, 36, (150, 155, 160))
            d.rounded_rectangle([250, 400, 700, 450], 14, fill=(215, 40, 40), outline=(90, 10, 10), width=3)
            d.line([(700, 425), (760, 520)], fill=(200, 200, 200), width=5)
            d.rounded_rectangle([730, 520, 800, 600], 10, fill=(240, 240, 240), outline=(120, 120, 120))
            d.line([(740, 540), (790, 585)], fill=(200, 30, 30), width=5)
        elif chave == "portao":
            img = self._superficie((120, 145, 105), 12, 40)
            dd = ImageDraw.Draw(img, "RGBA")
            dd.rectangle([60, 120, 130, 1050], fill=(90, 92, 96))
            dd.rectangle([830, 120, 900, 1050], fill=(90, 92, 96))
            dd.polygon([(190, 160), (620, 200), (640, 960), (200, 1000)], fill=(60, 62, 66, 60))
            for i in range(11):
                t = i / 10
                dd.line([(190 + 430 * t, 160 + 40 * t), (200 + 440 * t, 1000 - 40 * t)], fill=(75, 78, 84), width=9)
            for t in (0.05, .35, .65, .95):
                dd.line([(190 + 10 * t, 160 + 840 * t), (620 + 20 * t, 200 + 760 * t)], fill=(75, 78, 84), width=14)
            dd.polygon([(640, 210), (830, 150), (830, 1040), (650, 980)], fill=(25, 25, 25, 190))
            self._ferrugem(img, (180, 150, 640, 1000), 30, .7)
            return img
        elif chave == "cadeado":
            img = self._superficie((92, 118, 92), 12, 30)
            dd = ImageDraw.Draw(img, "RGBA")
            dd.rectangle([120, 160, 840, 1040], fill=(84, 110, 88), outline=(40, 55, 40), width=6)
            dd.rectangle([440, 470, 520, 640], fill=(70, 72, 75))
            dd.arc([420, 330, 560, 520], 180, 360, fill=(110, 90, 80), width=22)
            dd.rounded_rectangle([390, 520, 590, 720], 20, fill=(120, 78, 45), outline=(60, 35, 20), width=4)
            dd.ellipse([470, 590, 510, 630], fill=(30, 20, 15))
            self._ferrugem(img, (360, 300, 620, 760), 55, 1.4)
            self._ferrugem(img, (120, 160, 840, 1040), 24, .7)
            return img
        elif chave == "entulho":
            img = self._superficie((170, 168, 160), 12, 30)
            dd = ImageDraw.Draw(img, "RGBA")
            dd.rectangle([200, 120, 760, 800], fill=(96, 118, 100), outline=(50, 60, 50), width=5)
            dd.rectangle([230, 200, 730, 700], fill=(88, 108, 92))
            cores = [(150, 85, 60), (160, 160, 158), (120, 118, 115), (185, 130, 90), (200, 200, 195)]
            for _ in range(180):
                cx, cy = int(self.rng.integers(110, 850)), int(self.rng.integers(680, 1080))
                w, h = int(self.rng.integers(30, 120)), int(self.rng.integers(20, 70))
                dd.polygon([(cx, cy), (cx + w, cy + int(self.rng.integers(-15, 15))), (cx + w - 10, cy + h), (cx - 8, cy + h - 6)],
                           fill=cores[int(self.rng.integers(0, 5))] + (255,), outline=(60, 50, 45))
            return img
        elif chave.startswith("quadro"):
            img = self._superficie((60, 62, 66), 12, 30)
            dd = ImageDraw.Draw(img, "RGBA")
            dd.rectangle([140, 120, 820, 1050], fill=(150, 154, 158), outline=(70, 72, 75), width=8)
            dd.rectangle([180, 160, 780, 900], fill=(160, 164, 168), outline=(100, 100, 105), width=4)
            dd.rectangle([440, 500, 520, 560], fill=(60, 60, 62))
            self._ferrugem(img, (140, 800, 820, 1050) if "base" in chave else (180, 160, 780, 900), 95, 1.3)
            return img
        elif chave == "vazamento":
            self._tubo(d, 80, 620, 880, 620, 44, (235, 190, 40))
            self._tubo(d, 300, 250, 300, 620, 34, (160, 165, 170))
            d.rounded_rectangle([250, 570, 350, 670], 14, fill=(120, 124, 130), outline=(60, 60, 60), width=3)
            for _ in range(70):
                x, y, r = 300 + int(self.rng.normal(0, 60)), 560 + int(self.rng.normal(0, 55)), int(self.rng.integers(6, 20))
                d.ellipse([x - r, y - r, x + r, y + r], fill=(235, 240, 245, 150), outline=(255, 255, 255, 220), width=2)
            d.polygon([(690, 300), (620, 430), (760, 430)], fill=(238, 196, 30), outline=(20, 20, 20))
            self._texto(d, (690, 400), "!", 60, (20, 20, 20), anchor="mm")
        elif chave == "vedacao":
            img = self._superficie((165, 165, 160), 12, 30)
            dd = ImageDraw.Draw(img, "RGBA")
            dd.rectangle([260, 150, 700, 700], fill=(150, 154, 158), outline=(70, 72, 75), width=6)
            for k in range(6):
                x0, y0 = 120 + (k % 3) * 260, 620 + (k // 3) * 200
                dd.rectangle([x0, y0, x0 + 240, y0 + 190], fill=(176, 132, 84), outline=(90, 62, 36), width=4)
                dd.line([(x0 + 120, y0), (x0 + 120, y0 + 190)], fill=(200, 180, 130), width=10)
            return img
        elif chave == "estacao_ok":
            img = self._superficie((120, 160, 110), 12, 40)
            dd = ImageDraw.Draw(img, "RGBA")
            dd.rectangle([60, 120, 130, 1050], fill=(80, 84, 90))
            dd.rectangle([830, 120, 900, 1050], fill=(80, 84, 90))
            for x in range(150, 830, 34):
                dd.line([(x, 160), (x, 1000)], fill=(70, 74, 80), width=8)
            for y in (170, 580, 990):
                dd.line([(130, y), (830, y)], fill=(70, 74, 80), width=14)
            dd.rounded_rectangle([440, 560, 520, 660], 10, fill=(220, 200, 40), outline=(90, 80, 10), width=3)
            self._placa(img, (330, 200, 630, 490), "ok")
            return img
        elif chave == "lacre_ok":
            self._tubo(d, 100, 600, 860, 600, 40, (150, 155, 160))
            d.rounded_rectangle([390, 430, 570, 700], 30, fill=(225, 180, 30), outline=(90, 70, 10), width=3)
            self._tubo(d, 480, 250, 480, 430, 36, (150, 155, 160))
            d.rounded_rectangle([250, 400, 700, 450], 14, fill=(215, 40, 40), outline=(90, 10, 10), width=3)
            d.line([(700, 425), (700, 520), (600, 520), (560, 460)], fill=(200, 200, 200), width=4)
            d.rounded_rectangle([570, 500, 650, 560], 10, fill=(245, 245, 245), outline=(120, 120, 120))
            self._texto(d, (610, 530), "LACRE", 14, (30, 30, 30), anchor="mm")
        return base

    @staticmethod
    def classificar(detalhe: str) -> str:
        t = detalhe.casefold()
        if "vazamento" in t: return "vazamento"
        if "lacre" in t: return "lacre"
        if "portão" in t or "portao" in t: return "portao"
        if "cadeado" in t: return "cadeado"
        if "entulho" in t: return "entulho"
        if "vedação" in t or "vedacao" in t: return "vedacao"
        if "quadro" in t: return "quadro:base" if "base" in t else "quadro:porta"
        if "placa" in t: return "placa:ilegivel" if ("ilegí" in t or "ilegiv" in t) else "placa:ausente"
        equip = "psv" if "psv" in t else "medidor"
        if "sem etiqueta" in t or "ausência de etiqueta" in t or "ausencia de etiqueta" in t: est = "ausente"
        elif "incompleta" in t: est = "incompleta"
        elif "ilegí" in t or "ilegiv" in t: est = "ilegivel"
        else: est = "vencida"
        return f"{equip}:{est}"

    # ---------- API ----------
    def gerar_imagem(self, chave: str, destino: Path, luz: float = 1.0) -> Path:
        destino.parent.mkdir(parents=True, exist_ok=True)
        self._finalizar(self._cena(chave), luz).convert("RGB").save(destino, quality=88)
        return destino

    def gerar_periodo(self, ds: Dataset, p: Periodo, sobrescrever=False, condicoes_gerais=True) -> list[Path]:
        """Cria fotos que ainda não existem (nunca sobrescreve fotos reais, a menos que pedido)."""
        lib = PhotoLibrary(self.cfg)
        fiscs = ds.do_periodo(p)
        vids = visita_ids(fiscs)
        criadas: list[Path] = []
        if condicoes_gerais:
            for cidade, vid in vids.items():
                if lib.fotos_gerais(vid, cidade) and not sobrescrever:
                    continue
                pasta = PhotoLibrary.pasta_visita(self.cfg.fotos_gerais_dir, vid, cidade)
                for i, chave in enumerate(("estacao_ok", "medidor:ok", "lacre_ok"), start=1):
                    criadas.append(self.gerar_imagem(chave, pasta / f"geral_{i:02d}.jpg", luz=float(self.rng.uniform(.9, 1.1))))
        for f in fiscs:
            for nc in f.ncs:
                if lib.fotos_nc(nc, f, vids[f.cidade]) and not sobrescrever:
                    continue
                pasta = PhotoLibrary.pasta_visita(self.cfg.fotos_nc_dir, vids[f.cidade], f.cidade)
                criadas.append(self.gerar_imagem(self.classificar(nc.detalhe), pasta / f"NC{nc.num}_fisc{f.seq}.jpg",
                                                 luz=float(self.rng.uniform(.85, 1.1))))
        return criadas
