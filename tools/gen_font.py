# -*- coding: utf-8 -*-
"""나눔고딕코딩 Bold 를 40/56/72px 로 각각 native 래스터해 assets/efb_common*.bin 을 만든다.

폰트 렌더 V2 (HANDOFF_FONT_RENDER_V2 §A): 16px 하나를 정수배 확대하던 방식은 큰 글씨가
계단이 됐다 — 서버가 쓰는 세 크기를 벡터에서 그 크기로 미리 구워 확대를 없앤다.
1비트 패널이라 계단을 완전히 없앨 수는 없어, **더 크고 굵게** 해서 덜 띄게 한다
(HANDOFF_NODE_FIRMWARE_FONT: 32/48/64 Regular → 40/56/72 Bold).

- 커버리지: ASCII 95자 + 자주쓰는 한글 2,000자. 밖의 드문 음절은 서버 입력검증
  (schemas.py, 우진)이 막는다.
- 한글 목록은 assets/common_hangul.txt 를 읽는다 — 굽기·서버 검증의 단일 기준
  (tools/gen_common_hangul.py 산출물). 여기서 다시 계산하면 기준이 둘이 된다.
- 고정폭: 한글 = 전각(advance = 크기), ASCII = 반각(advance = 크기/2) — 서버
  field_avail_w·웹 clip() 폭 모델과 동기 (비례폭 금지).
- 원본: 나눔고딕코딩 Bold(고정폭, SIL OFL 1.1 — assets/OFL.txt). 고정폭 폰트라 ASCII 가
  정확히 반각 셀에 들어간다 — 나눔고딕 일반은 비례폭이라 W/m 이 잘린다.

bin 포맷 (리틀엔디언 u16 헤더, node_core/text.cpp BakedFont 가 읽는다):
  u16 cell_px, u16 glyph_bytes(=cell²/8), u16 ascii_n(=95), u16 hangul_n
  u16 hangul_cps[hangul_n]  (오름차순 — 노드가 이진탐색)
  glyphs[(ascii_n+hangul_n) × glyph_bytes]  (ASCII 먼저, 행당 cell/8 바이트 MSB first)

사용: python tools/gen_font.py <NanumGothicCoding-Bold.ttf>
"""

import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SIZES = (40, 56, 72)
ASCII_START, ASCII_END = 0x20, 0x7E  # 95자


def common_hangul() -> list[int]:
    """assets/common_hangul.txt (tools/gen_common_hangul.py 산출물)의 자주쓰는 한글.

    글자수는 목록이 정한다 — 여기서 상수로 못박으면 우진이 개수를 조정할 때마다 어긋난다.
    (플래시가 넘치면 우진이 gen_common_hangul.py 의 N 을 낮춰 목록을 다시 뽑는다.)
    """
    src = ROOT / "assets" / "common_hangul.txt"
    if not src.exists():
        raise SystemExit(f"{src} 가 없습니다 — 먼저: python tools/gen_common_hangul.py")
    cps = sorted(ord(c) for c in src.read_text(encoding="utf-8").strip())
    if not cps:
        raise SystemExit(f"{src} 가 비어 있습니다 — 목록 재생성 필요")
    return cps


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
    cps = common_hangul()

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
