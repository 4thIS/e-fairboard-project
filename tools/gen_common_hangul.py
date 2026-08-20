"""자주 쓰는 한글 2,000자 + ASCII 코드포인트 목록 생성 (빈도 기반).

폰트 렌더 V2 — 노드가 이 글자들을 40/56/72px 로 굽는다(HANDOFF_FONT_RENDER_V2.md).
이 목록이 굽기(gen_font)·서버 입력검증의 **단일 기준**이다.

왜 2,000자인가:
  - 40/56/72px × 글자수 × (200+392+648)B. 2,000자 = 2.48MB → 4MB 앱 파티션에 여유(파티션 이동 불필요).
  - KS X 1001 상용 2,350 은 40/56/72 로 굽으면 2.91MB 라 앱에 빠듯 → 진짜 드문 359자를 뺀다.

어떻게 고르나 (눈대중 금지 — 봇/뱃 등은 실제로 쓰임):
  1. assets/hangul_freq.txt = 실제 코퍼스(OpenSubtitles 한국어 5만 단어, hermitdave/FrequencyWords)
     음절 빈도. 1,364자가 대화 텍스트의 100% 를 덮는다.
  2. 격식/이름 안전망으로 KS X 1001 상용 2,350 을 합집합.
  3. (코퍼스빈도 desc, KS 우선, 코드포인트) 순 정렬 후 상위 N=2,000.
  → 버려지는 ~359자는 전부 코퍼스 0회 등장(진짜 드묾). 상용 밖은 서버 입력검증(schemas.py)이 막는다.

출력:
  assets/common_hangul.txt  — 자주쓰는 한글 2,000자 (정렬, 한 줄)
실행: python tools/gen_common_hangul.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FREQ = ROOT / "assets" / "hangul_freq.txt"
OUT = ROOT / "assets" / "common_hangul.txt"

HANGUL_START, HANGUL_END = 0xAC00, 0xD7A3
ASCII_START, ASCII_END = 0x20, 0x7E
N = 2000


def ksx1001() -> set[str]:
    """KS X 1001 완성형 블록(cp949 리드 0xB0~0xC8) = 2,350자 — 격식/이름 안전망."""
    out = set()
    for cp in range(HANGUL_START, HANGUL_END + 1):
        b = chr(cp).encode("cp949")
        if len(b) == 2 and 0xB0 <= b[0] <= 0xC8 and 0xA1 <= b[1] <= 0xFE:
            out.add(chr(cp))
    return out


def corpus_freq() -> dict[str, int]:
    if not FREQ.exists():
        raise SystemExit(f"{FREQ} 없음 — 코퍼스 음절 빈도표 필요")
    freq = {}
    for line in FREQ.read_text(encoding="utf-8").splitlines():
        if "\t" not in line:
            continue
        ch, cnt = line.split("\t")
        freq[ch] = int(cnt)
    return freq


def main() -> None:
    freq = corpus_freq()
    ks = ksx1001()
    pool = set(freq) | ks
    ranked = sorted(pool, key=lambda ch: (-freq.get(ch, 0), 0 if ch in ks else 1, ord(ch)))
    sel = sorted(ranked[:N])

    OUT.write_text("".join(sel), encoding="utf-8")
    ascii_n = ASCII_END - ASCII_START + 1
    print(f"자주쓰는 한글 {len(sel):,}자 + ASCII {ascii_n}자")
    print(f"  후보 풀 {len(pool)}자 (코퍼스 {len(freq)} ∪ KS X 1001 {len(ks)})")
    print(f"  폰트 예상 {len(sel) * (200 + 392 + 648) / 1e6:.2f}MB (40/56/72px)")
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} B)")


if __name__ == "__main__":
    main()
