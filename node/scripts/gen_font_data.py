"""빌드 전 훅 — assets/efb_common{32,48,64}.bin 을 rodata C++ 배열로 굽는다.

생성물(node/src/font_data.cpp)은 ~14MB 소스라 git 에 넣지 않는다(.gitignore).
bin 3개(~2.3MB)만 커밋하고 빌드 때마다 여기서 만든다 — 둘이 어긋날 일이 없다.

폰트 렌더 V2 (HANDOFF_FONT_RENDER_V2 §A): 서버가 쓰는 세 크기(32/48/64px)를 각각
native 로 구워 확대를 없앤다. 원본 나눔고딕코딩(SIL OFL 1.1 — assets/OFL.txt),
tools/gen_font.py 로 생성. 상용 2,350자 — 밖의 희귀 음절은 서버 입력검증(우진)이 막는다.
"""

from pathlib import Path

Import("env")  # noqa: F821  (PlatformIO 가 주입)

PROJECT = Path(env.subst("$PROJECT_DIR"))  # noqa: F821
ASSETS = PROJECT.parent / "assets"
SIZES = (32, 48, 64)
OUT = PROJECT / "src" / "font_data.cpp"


def main() -> None:
    bins = {n: ASSETS / f"efb_common{n}.bin" for n in SIZES}
    missing = [str(p) for p in bins.values() if not p.exists()]
    if missing:
        raise SystemExit(
            "폰트 bin 이 없습니다: " + ", ".join(missing) + "\n"
            "먼저 실행하세요:  python tools/gen_font.py <NanumGothicCoding-Regular.ttf>"
        )

    newest = max(p.stat().st_mtime for p in bins.values())
    if OUT.exists() and OUT.stat().st_mtime > newest:
        return  # 최신

    lines = [
        "// 자동 생성 — node/scripts/gen_font_data.py. 수정하지 말 것.",
        "// 원본: assets/efb_common{32,48,64}.bin (나눔고딕코딩, SIL OFL 1.1 — assets/OFL.txt)",
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
