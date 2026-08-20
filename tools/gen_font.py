# -*- coding: utf-8 -*-
"""나눔스퀘어 Bold 를 40/56/72px 로 각각 native 래스터해 assets/efb_common*.bin 을 만든다.

폰트 렌더 V3 (HANDOFF_NODE_FONT_PROPORTIONAL): 나눔스퀘어는 비례폭이라 고정폭
(한글=크기, ASCII=크기/2)으로 넣으면 글자 사이가 벌어지고 W 가 잘린다 — 글자별 실제
전진폭(advance)으로 그린다. 크기·글자수는 V2 그대로(40/56/72px, 자주쓰는 2,000자).

- **advance 를 여기서 계산하지 않는다.** assets/font_advance.json(우진 생성, 웹도 같은
  파일을 쓴다)을 읽어 bin 에 넣는다 — 기준이 둘이 되면 판넬과 미리보기 간격이 어긋난다.
- 한글 목록도 assets/common_hangul.txt 가 정본 (tools/gen_common_hangul.py 산출물).
- 글립은 여전히 cell×cell 좌측 정렬 비트맵이다. 좁은 글자는 셀 안 왼쪽만 차고, 다음
  글자가 advance 만큼만 전진해 빈칸 위에 얹힌다 — 저장 방식·용량은 V2 와 같다.
- 공백(0x20)은 빈 글립 + advance 만. 이 TTF 는 space 를 박스로 래스터하므로 그리면
  화면에 □ 가 뜬다 (인수인계서 §3-①).
- 폰트에 없는 글자도 같은 이유로 □ 가 된다(.notdef). 렌더 결과가 .notdef 와 같으면
  빈 글립으로 바꾸고 경고한다 — 판넬에 네모가 뜨는 것보다 안 보이는 편이 낫다.
  경고가 나오면 목록에서 빼도록 우진에게 알린다.
- 원본: 나눔스퀘어 Bold (SIL OFL 1.1 — assets/OFL.txt), assets/fonts/NanumSquareB.ttf.

bin 포맷 (리틀엔디언, node_core/text.cpp BakedFont 가 읽는다):
  u16 cell_px, u16 glyph_bytes(=cell²/8), u16 ascii_n(=95), u16 hangul_n
  u16 hangul_cps[hangul_n]              (오름차순 — 노드가 이진탐색)
  u8  advance[ascii_n + hangul_n]       (이 크기에서 글자별 전진폭, ASCII 먼저)
  glyphs[(ascii_n+hangul_n) × glyph_bytes]  (ASCII 먼저, 행당 cell/8 바이트 MSB first)

사용: python tools/gen_font.py assets/fonts/NanumSquareB.ttf
"""

import json
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SIZES = (40, 56, 72)
ASCII_START, ASCII_END = 0x20, 0x7E  # 95자
SPACE = 0x20


def common_hangul() -> list[int]:
    """assets/common_hangul.txt (tools/gen_common_hangul.py 산출물)의 자주쓰는 한글.

    글자수는 목록이 정한다 — 여기서 상수로 못박으면 우진이 개수를 조정할 때마다 어긋난다.
    """
    src = ROOT / "assets" / "common_hangul.txt"
    if not src.exists():
        raise SystemExit(f"{src} 가 없습니다 — 먼저: python tools/gen_common_hangul.py")
    cps = sorted(ord(c) for c in src.read_text(encoding="utf-8").strip())
    if not cps:
        raise SystemExit(f"{src} 가 비어 있습니다 — 목록 재생성 필요")
    return cps


def load_advance(cps: list[int]) -> dict[int, list[int]]:
    """assets/font_advance.json — 웹과 공유하는 단일 기준. 크기 순서는 SIZES 와 같아야 한다."""
    src = ROOT / "assets" / "font_advance.json"
    if not src.exists():
        raise SystemExit(f"{src} 가 없습니다 — 우진이 생성해 main 에 올린 파일입니다")
    data = json.loads(src.read_text(encoding="utf-8"))
    if tuple(data["sizes"]) != SIZES:
        raise SystemExit(f"font_advance.json 크기 {data['sizes']} != 굽기 크기 {list(SIZES)}")
    adv = {int(k): v for k, v in data["adv"].items()}

    need = list(range(ASCII_START, ASCII_END + 1)) + cps
    missing = [cp for cp in need if cp not in adv]
    if missing:
        raise SystemExit(
            f"advance 없는 글자 {len(missing)}개 (예: "
            + " ".join(chr(c) for c in missing[:10])
            + ") — font_advance.json 과 common_hangul.txt 가 어긋납니다"
        )
    over = [cp for cp in need if max(adv[cp]) > 255]
    if over:
        raise SystemExit(f"advance 가 255 를 넘는 글자 {len(over)}개 — u8 에 안 들어갑니다")
    return adv


def pick_font(ttf: Path, cell: int) -> tuple[ImageFont.FreeTypeFont, int]:
    """ascent+descent 가 cell 이하가 되는 최대 포인트를 찾는다. 반환: (폰트, y오프셋)."""
    for pt in range(cell + 8, 4, -1):
        font = ImageFont.truetype(str(ttf), pt)
        ascent, descent = font.getmetrics()
        if ascent + descent <= cell:
            return font, (cell - (ascent + descent)) // 2
    raise SystemExit(f"{cell}px 셀에 맞는 포인트를 못 찾음")


def raster(font: ImageFont.FreeTypeFont, cell: int, y_off: int, cp: int) -> bytes:
    """cell×cell 1bpp 글립 (좌측 정렬) — 안티앨리어싱 후 커버리지 128 임계 (1비트 패널)."""
    row_bytes = cell // 8
    out = bytearray(cell * row_bytes)
    if cp == SPACE:
        return bytes(out)  # 이 TTF 는 space 를 박스로 그린다 — 빈 글립으로 둔다

    img = Image.new("L", (cell, cell), 0)
    ImageDraw.Draw(img).text((0, y_off), chr(cp), font=font, fill=255)
    px = img.load()
    for y in range(cell):
        for x in range(cell):
            if px[x, y] >= 128:
                out[y * row_bytes + (x >> 3)] |= 0x80 >> (x & 7)
    return bytes(out)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    ttf = Path(sys.argv[1])
    cps = common_hangul()
    adv = load_advance(cps)
    order = list(range(ASCII_START, ASCII_END + 1)) + cps

    for i, cell in enumerate(SIZES):
        font, y_off = pick_font(ttf, cell)
        advances = bytes(adv[cp][i] for cp in order)

        # 폰트에 없는 글자 판별용 기준선 — 사용자 영역(U+E000)은 어떤 폰트에도 없다.
        notdef = raster(font, cell, y_off, 0xE000)
        blank = bytes(cell * (cell // 8))
        missing: list[str] = []
        parts = []
        for cp in order:
            g = raster(font, cell, y_off, cp)
            if g == notdef and g != blank:
                missing.append(chr(cp))
                g = blank
            parts.append(g)
        glyphs = b"".join(parts)

        out = ROOT / "assets" / f"efb_common{cell}.bin"
        gbytes = cell * cell // 8
        header = struct.pack("<4H", cell, gbytes, 95, len(cps))
        table = struct.pack(f"<{len(cps)}H", *cps)
        out.write_bytes(header + table + advances + glyphs)
        print(f"{out.name}: {out.stat().st_size:,} B "
              f"({font.size}pt, y_off {y_off}, 글립 {len(order)}개 × {gbytes}B, "
              f"advance {min(advances)}~{max(advances)}px)")
        if missing:
            print(f"  ⚠ 폰트에 없어 빈칸으로 대체한 글자 {len(missing)}개: {' '.join(missing)}")
            print("    → common_hangul.txt 에서 빼도록 우진에게 알릴 것")


if __name__ == "__main__":
    main()
