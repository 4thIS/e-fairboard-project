"""빌드 전 훅 — assets/efb_common{40,56,72}.bin 을 rodata C++ 배열로 굽는다.

생성물(node/src/font_data.cpp)은 ~15MB 소스라 git 에 넣지 않는다(.gitignore).
bin 3개(~2.5MB)만 커밋하고 빌드 때마다 여기서 만든다 — 둘이 어긋날 일이 없다.

폰트 렌더 V2: 서버가 쓰는 세 크기(40/56/72px)를 각각 native 로 구워 확대를 없앤다.
원본 나눔고딕코딩 Bold(SIL OFL 1.1 — assets/OFL.txt), tools/gen_font.py 로 생성.
자주쓰는 2,000자 — 밖의 드문 음절은 서버 입력검증(우진)이 막는다.
"""

import re
from pathlib import Path

Import("env")  # noqa: F821  (PlatformIO 가 주입)

PROJECT = Path(env.subst("$PROJECT_DIR"))  # noqa: F821
ASSETS = PROJECT.parent / "assets"
SIZES = (40, 56, 72)
OUT = PROJECT / "src" / "font_data.cpp"
TEXT_H = PROJECT / "lib" / "node_core" / "include" / "node" / "text.h"


def check_glyph_capacity() -> None:
    """text.h 의 MAX_GLYPH_BYTES 가 가장 큰 글립을 담는지 확인한다.

    작으면 BakedFont::add() 가 bin 을 거부해 **화면에 글자가 하나도 안 나온다** — 그런데
    빌드는 성공하고 부팅 로그 한 줄만 남아 놓치기 쉽다(2026-08-20 실측). 크기를 올릴 때
    상수를 같이 못 올리는 실수를 여기서 세운다.
    """
    need = max(n * n // 8 for n in SIZES)
    m = re.search(r"MAX_GLYPH_BYTES\s*=\s*(\d+)", TEXT_H.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"{TEXT_H} 에서 MAX_GLYPH_BYTES 를 못 찾았습니다")
    have = int(m.group(1))
    if have < need:
        raise SystemExit(
            f"MAX_GLYPH_BYTES={have} 가 {max(SIZES)}px 글립({need}B)보다 작습니다.\n"
            f"node/lib/node_core/include/node/text.h 의 값을 {need} 이상으로 올리세요."
        )


def main() -> None:
    bins = {n: ASSETS / f"efb_common{n}.bin" for n in SIZES}
    missing = [str(p) for p in bins.values() if not p.exists()]
    if missing:
        raise SystemExit(
            "폰트 bin 이 없습니다: " + ", ".join(missing) + "\n"
            "먼저 실행하세요:  python tools/gen_font.py <NanumGothicCoding-Bold.ttf>"
        )
    check_glyph_capacity()

    newest = max(p.stat().st_mtime for p in bins.values())
    if OUT.exists() and OUT.stat().st_mtime > newest:
        return  # 최신

    lines = [
        "// 자동 생성 — node/scripts/gen_font_data.py. 수정하지 말 것.",
        "// 원본: assets/efb_common{40,56,72}.bin (나눔고딕코딩 Bold, SIL OFL 1.1 — assets/OFL.txt)",
        "//",
        "// 크기별 native 베이크 — 확대 없음 (폰트 렌더 V2). 포맷은 node_core BakedFont 참조.",
        "#include <Arduino.h>",
        "",
        "// extern const — C++ 의 const 는 내부 링키지라 명시해야 main.cpp 에서 보인다.",
    ]
    total = 0
    for n in SIZES:
        lines.append(f"extern const uint8_t EFB_COMMON{n}[];")
        lines.append(f"extern const size_t EFB_COMMON{n}_LEN;")
    for n in SIZES:
        data = bins[n].read_bytes()
        total += len(data)
        lines.append("")
        lines.append(f"const uint8_t EFB_COMMON{n}[] = {{")
        for i in range(0, len(data), 16):
            lines.append("    " + ",".join(f"0x{b:02X}" for b in data[i : i + 16]) + ",")
        lines.append("};")
        lines.append(f"extern const size_t EFB_COMMON{n}_LEN = {len(data)};")
    lines.append("")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[font] {OUT.name} 생성 — bin 합계 {total:,} B ({total / 1024:.0f} KB)")


main()
