# -*- coding: utf-8 -*-
"""나눔고딕코딩을 32/48/64px 로 각각 native 래스터해 assets/efb_common*.bin 을 만든다.

폰트 렌더 V2 (HANDOFF_FONT_RENDER_V2 §A): 16px 하나를 정수배 확대하던 방식은 큰 글씨가
계단이 됐다 — 서버가 쓰는 세 크기(32/48/64)를 벡터에서 그 크기로 미리 구워 확대를 없앤다.

- 커버리지: ASCII 95자 + KS X 1001 상용한글 2,350자 (완성형 full 은 64px 기준 5.7MB 라
  4MB 플래시에 불가). 상용 밖 희귀 음절은 서버 입력검증(schemas.py, 우진)이 막는다.
- 고정폭: 한글 = 전각(advance = 크기), ASCII = 반각(advance = 크기/2) — 서버
  field_avail_w·웹 clip() 폭 모델과 동기 (비례폭 금지).
- 원본: 나눔고딕코딩(고정폭, SIL OFL 1.1 — assets/OFL.txt). 고정폭 폰트라 ASCII 가
  정확히 반각 셀에 들어간다 — 나눔고딕 일반은 비례폭이라 W/m 이 잘린다.

bin 포맷 (리틀엔디언 u16 헤더, node_core/text.cpp BakedFont 가 읽는다):
  u16 cell_px, u16 glyph_bytes(=cell²/8), u16 ascii_n(=95), u16 hangul_n(=2350)
  u16 hangul_cps[hangul_n]  (오름차순 — 노드가 이진탐색)
  glyphs[(ascii_n+hangul_n) × glyph_bytes]  (ASCII 먼저, 행당 cell/8 바이트 MSB first)

사용: python tools/gen_font.py <NanumGothicCoding-Regular.ttf>
"""

import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SIZES = (32, 48, 64)
ASCII_START, ASCII_END = 0x20, 0x7E  # 95자


def ks1001_common() -> list[int]:
    """KS X 1001 상용한글 2,350자 = cp949 의 완성형 구역(리드 0xB0-0xC8, 트레일 0xA1-0xFE)."""
    out = []
    for cp in range(0xAC00, 0xD7A4):
        try:
            b = chr(cp).encode("cp949")
        except UnicodeEncodeError:
            continue
        if len(b) == 2 and 0xB0 <= b[0] <= 0xC8 and 0xA1 <= b[1] <= 0xFE:
            out.append(cp)
    assert len(out) == 2350, len(out)
    return out


def pick_font(ttf: Path, cell: int) -> tuple[ImageFont.FreeTypeFont, int]:
    """ascent+descent 가 cell 이하가 되는 최대 포인트를 찾는다. 반환: (폰트, y오프셋)."""
    for pt in range(cell + 8, 4, -1):
        font = ImageFont.truetype(str(ttf), pt)
        ascent, descent = font.getmetrics()
        if ascent + descent <= cell:
            return font, (cell - (ascent + descent)) // 2
    raise SystemExit(f"{cell}px 셀에 맞는 포인트를 못 찾음")


def raster(font: ImageFont.FreeTypeFont, cell: int, y_off: int, ch: str) -> bytes:
    """cell×cell 1bpp 글립 — 안티앨리어싱 후 커버리지 128 임계 (1비트 패널)."""
    img = Image.new("L", (cell, cell), 0)
    ImageDraw.Draw(img).text((0, y_off), ch, font=font, fill=255)
    row_bytes = cell // 8
    out = bytearray(cell * row_bytes)
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
    cps = ks1001_common()

    for cell in SIZES:
        font, y_off = pick_font(ttf, cell)
        glyphs = bytearray()
        for cp in range(ASCII_START, ASCII_END + 1):
            glyphs += raster(font, cell, y_off, chr(cp))
        for cp in cps:
            glyphs += raster(font, cell, y_off, chr(cp))

        out = ROOT / "assets" / f"efb_common{cell}.bin"
        gbytes = cell * cell // 8
        header = struct.pack("<4H", cell, gbytes, 95, len(cps))
        table = struct.pack(f"<{len(cps)}H", *cps)
        out.write_bytes(header + table + glyphs)
        print(f"{out.name}: {out.stat().st_size:,} B "
              f"({font.size}pt, y_off {y_off}, 글립 {95 + len(cps)}개 × {gbytes}B)")


if __name__ == "__main__":
    main()
