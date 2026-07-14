"""Neo둥근모(SIL OFL 1.1) TTF 를 16px 1bpp 비트맵으로 구워 펌웨어용 바이너리를 만든다.

완성형 전체(U+AC00~U+D7A3, 11,172자) + ASCII(0x20~0x7E)를 담는다. 서브셋이 아니므로
관리자가 어떤 한글을 쳐도 깨지지 않고, 서버 입력 검증(schemas.py)이 필요 없다.

글립 형식 — 전부 32바이트 고정:
    16행 x 2바이트, MSB first. ASCII 는 왼쪽 8비트만 쓰고 advance 만 8px.
    오프셋 = 색인 x 32.

색인:
    0        ~ 94     : ASCII 0x20 ~ 0x7E
    95       ~ 11266  : 한글 U+AC00 ~ U+D7A3

라이선스: 원본 폰트는 SIL OFL 1.1, Reserved Font Name "Neo둥근모"/"NeoDunggeunmo".
파생 비트맵이므로 예약 이름을 쓰지 않고(efb_hangul16), OFL 사본을 함께 배포한다.

실행: ~/venv/bin/python tools/gen_font.py
출력: assets/efb_hangul16.bin, assets/OFL.txt
"""

import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CACHE = ASSETS / ".cache"  # 원본 TTF — 커밋하지 않는다 (assets/.gitignore)

TTF_URL = "https://github.com/neodgm/neodgm/releases/download/v1.601/neodgm.ttf"
OFL_URL = "https://raw.githubusercontent.com/neodgm/neodgm/master/LICENSE.txt"

CELL = 16          # 글립 셀 높이·최대 너비
GLYPH_BYTES = 32   # 16행 x 2바이트

ASCII_START, ASCII_END = 0x20, 0x7E
HANGUL_START, HANGUL_END = 0xAC00, 0xD7A3

ASCII_COUNT = ASCII_END - ASCII_START + 1        # 95
HANGUL_COUNT = HANGUL_END - HANGUL_START + 1     # 11172


def fetch(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {url}")
    urllib.request.urlretrieve(url, dest)
    return dest


def rasterize(font: ImageFont.FreeTypeFont, ch: str) -> bytes:
    """16x16 셀에 1bpp 로 굽는다. Neo둥근모는 16px 에서 픽셀 퍼펙트라 안티에일리어싱이 없다."""
    img = Image.new("1", (CELL, CELL), 0)
    ImageDraw.Draw(img).text((0, 0), ch, font=font, fill=1)

    out = bytearray(GLYPH_BYTES)
    for y in range(CELL):
        for x in range(CELL):
            if img.getpixel((x, y)):
                out[y * 2 + (x >> 3)] |= 0x80 >> (x & 7)  # MSB first
    return bytes(out)


def main() -> None:
    ttf = fetch(TTF_URL, CACHE / "neodgm.ttf")
    font = ImageFont.truetype(str(ttf), CELL)

    ASSETS.mkdir(parents=True, exist_ok=True)
    fetch(OFL_URL, ASSETS / "OFL.txt")

    blob = bytearray()
    blank = 0

    for cp in range(ASCII_START, ASCII_END + 1):
        blob += rasterize(font, chr(cp))
    for cp in range(HANGUL_START, HANGUL_END + 1):
        g = rasterize(font, chr(cp))
        if not any(g):
            blank += 1
        blob += g

    expected = (ASCII_COUNT + HANGUL_COUNT) * GLYPH_BYTES
    if len(blob) != expected:
        sys.exit(f"크기 불일치: {len(blob)} != {expected}")

    out = ASSETS / "efb_hangul16.bin"
    out.write_bytes(blob)

    print(f"wrote {out.relative_to(ROOT)}")
    print(f"  ASCII  {ASCII_COUNT:>6}자")
    print(f"  한글   {HANGUL_COUNT:>6}자  (빈 글립 {blank})")
    print(f"  합계   {len(blob):>6,} B  = {len(blob) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
