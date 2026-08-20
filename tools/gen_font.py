"""나눔고딕코딩(SIL OFL 1.1) TTF 를 32px 1bpp 비트맵으로 구워 펌웨어용 바이너리를 만든다.

완성형 전체(U+AC00~U+D7A3, 11,172자) + ASCII(0x20~0x7E)를 담는다. 서브셋이 아니므로
관리자가 어떤 한글을 쳐도 깨지지 않고, 서버 입력 검증(schemas.py)이 필요 없다.

16px Neo둥근모에서 32px 벡터 래스터로 교체(HANDOFF_FONT_HIRES) — 큰 글씨의 확대
배율이 반으로 줄어(128px: 8배→4배) 뭉갬이 사라진다. 나눔고딕코딩은 고정폭이라
ASCII 폭이 정확히 한글의 절반 = 고정 advance(16/32px) 구조와 일치한다.

글립 형식 — 전부 128바이트 고정:
    32행 x 4바이트, MSB first. ASCII 는 왼쪽 16비트만 쓰고 advance 만 16px.
    오프셋 = 색인 x 128.

색인:
    0        ~ 94     : ASCII 0x20 ~ 0x7E
    95       ~ 11266  : 한글 U+AC00 ~ U+D7A3

라이선스: SIL OFL 1.1, Reserved Font Name "Nanum". 파생 비트맵이므로 예약 이름을
쓰지 않고(efb_hangul32), OFL 사본을 함께 배포한다.

실행: python tools/gen_font.py
출력: assets/efb_hangul32.bin, assets/OFL.txt
"""

import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CACHE = ASSETS / ".cache"  # 원본 TTF — 커밋하지 않는다 (assets/.gitignore)

TTF_URL = "https://github.com/google/fonts/raw/main/ofl/nanumgothiccoding/NanumGothicCoding-Regular.ttf"
OFL_URL = "https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothiccoding/OFL.txt"

CELL = 32           # 글립 셀 높이·최대 너비
ROW_BYTES = 4       # 32비트/행
GLYPH_BYTES = CELL * ROW_BYTES  # 128

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


def pick_font(ttf: Path) -> tuple[ImageFont.FreeTypeFont, int]:
    """ascent+descent 가 셀(32px)에 들어가는 최대 포인트를 고른다 — 벡터 폰트는
    명목 크기보다 줄 높이가 커서 32pt 그대로 구우면 위아래가 잘린다."""
    for size in range(CELL, CELL - 9, -1):
        font = ImageFont.truetype(str(ttf), size)
        ascent, descent = font.getmetrics()
        if ascent + descent <= CELL:
            return font, (CELL - (ascent + descent)) // 2
    sys.exit("셀에 맞는 크기를 못 찾음")


def rasterize(font: ImageFont.FreeTypeFont, ch: str, y_off: int) -> bytes:
    """32x32 셀에 1bpp 로 굽는다. 모드 '1' 렌더라 안티에일리어싱 없음(e-Paper용)."""
    img = Image.new("1", (CELL, CELL), 0)
    ImageDraw.Draw(img).text((0, y_off), ch, font=font, fill=1)

    out = bytearray(GLYPH_BYTES)
    for y in range(CELL):
        for x in range(CELL):
            if img.getpixel((x, y)):
                out[y * ROW_BYTES + (x >> 3)] |= 0x80 >> (x & 7)  # MSB first
    return bytes(out)


def main() -> None:
    ttf = fetch(TTF_URL, CACHE / "NanumGothicCoding-Regular.ttf")
    font, y_off = pick_font(ttf)

    ASSETS.mkdir(parents=True, exist_ok=True)
    fetch(OFL_URL, ASSETS / "OFL.txt")

    blob = bytearray()
    blank = 0

    for cp in range(ASCII_START, ASCII_END + 1):
        blob += rasterize(font, chr(cp), y_off)
    for cp in range(HANGUL_START, HANGUL_END + 1):
        g = rasterize(font, chr(cp), y_off)
        if not any(g):
            blank += 1
        blob += g

    expected = (ASCII_COUNT + HANGUL_COUNT) * GLYPH_BYTES
    if len(blob) != expected:
        sys.exit(f"크기 불일치: {len(blob)} != {expected}")

    out = ASSETS / "efb_hangul32.bin"
    out.write_bytes(blob)

    print(f"wrote {out.relative_to(ROOT)}  (셀 {CELL}px, 래스터 {font.size}pt, y_off {y_off})")
    print(f"  ASCII  {ASCII_COUNT:>6}자")
    print(f"  한글   {HANGUL_COUNT:>6}자  (빈 글립 {blank})")
    print(f"  합계   {len(blob):>9,} B  = {len(blob) / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()
