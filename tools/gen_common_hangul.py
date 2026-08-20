"""상용한글(KS X 1001, 2,350자) + ASCII 코드포인트 목록 생성.

폰트 렌더 V2 — 노드가 상용 2,350 을 32/48/64px 로 굽는다(HANDOFF_FONT_RENDER_V2.md).
이 목록이 굽기(pyftsubset/gen_font)·서버 입력검증의 **단일 기준**이다.

KS X 1001 완성형 한글 = EUC-KR 완성형 블록(리드 0xB0~0xC8, 트레일 0xA1~0xFE) = 2,350자.
(Python 'euc-kr' 코덱은 cp949 로 별칭돼 11,172 를 다 인코딩하므로, 바이트 범위로 거른다.)

출력:
  assets/common_hangul.txt  — 상용 한글 2,350자 (정렬, 한 줄). pyftsubset --text-file 입력.
  stdout                    — 개수 검증

실행: python tools/gen_common_hangul.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "common_hangul.txt"

HANGUL_START, HANGUL_END = 0xAC00, 0xD7A3
ASCII_START, ASCII_END = 0x20, 0x7E
EXPECTED = 2350


def common_hangul() -> list[int]:
    """cp949 인코딩이 EUC-KR 완성형 블록에 드는 한글 = KS X 1001 상용 2,350자."""
    out = []
    for cp in range(HANGUL_START, HANGUL_END + 1):
        try:
            b = chr(cp).encode("cp949")
        except UnicodeEncodeError:
            continue
        if len(b) == 2 and 0xB0 <= b[0] <= 0xC8 and 0xA1 <= b[1] <= 0xFE:
            out.append(cp)
    return out


def main() -> None:
    hangul = common_hangul()
    if len(hangul) != EXPECTED:
        sys.exit(
            f"상용 한글 {len(hangul)}자 (기대 {EXPECTED}). "
            f"euc-kr 코덱이 cp949 로 별칭됐을 수 있음 — 코덱 확인 필요."
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(chr(c) for c in hangul), encoding="utf-8")

    ascii_n = ASCII_END - ASCII_START + 1
    print(f"상용 한글 {len(hangul):,}자 + ASCII {ascii_n}자")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} B)")
    print("pyftsubset NanumGothic.ttf --text-file=assets/common_hangul.txt "
          f"--unicodes=U+{ASCII_START:04X}-{ASCII_END:04X} --output-file=nanum_common.ttf")


if __name__ == "__main__":
    main()
