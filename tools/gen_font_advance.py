"""글자별 advance(전진 폭) 테이블 생성 — 비례폭 폰트(나눔스퀘어)용.

폰트 렌더 V3 (비례폭). 노드 BakedFont 와 웹 clip 이 **같은 폭**을 써야 미리보기가
노드와 어긋나지 않는다. 이 테이블이 그 단일 기준이다.

- 크기 40/56/72px 각각에서 글자별 advance = round(getlength(ch)) (round-half-up 정수).
  노드 gen_font.py 도 이 파일을 읽어 bin 에 같은 값을 넣는다 (재계산 금지 — 기준이 둘이 되면 안 됨).
- 대상: ASCII 95 + assets/common_hangul.txt (자주쓰는 2,000자).
- 원본: server/frontend/public/NanumSquareB.ttf (나눔스퀘어 Bold, SIL OFL).

출력(둘 다 같은 내용 — 노드용/웹용):
  assets/font_advance.json                       (노드 gen_font.py 가 읽음)
  server/frontend/src/epaper/font_advance.json   (웹이 import)

실행: python tools/gen_font_advance.py
"""

import json
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parent.parent
TTF = ROOT / "server" / "frontend" / "public" / "NanumSquareB.ttf"
COMMON = ROOT / "assets" / "common_hangul.txt"
OUTS = [
    ROOT / "assets" / "font_advance.json",
    ROOT / "server" / "frontend" / "src" / "epaper" / "font_advance.json",
]
SIZES = [40, 56, 72]


def main() -> None:
    chars = {chr(c) for c in range(0x20, 0x7F)}
    chars |= set(COMMON.read_text(encoding="utf-8").strip())
    fonts = {s: ImageFont.truetype(str(TTF), s) for s in SIZES}

    table = {str(ord(ch)): [int(fonts[s].getlength(ch) + 0.5) for s in SIZES]
             for ch in sorted(chars)}
    payload = {"sizes": SIZES, "adv": table}
    blob = json.dumps(payload, separators=(",", ":"), sort_keys=True)

    for out in OUTS:
        out.write_text(blob, encoding="utf-8")
    print(f"advance 테이블 {len(table)}자, 크기 {SIZES}, {len(blob):,} B")
    print(f"  → {OUTS[0].relative_to(ROOT)} · {OUTS[1].relative_to(ROOT)}")


if __name__ == "__main__":
    main()
