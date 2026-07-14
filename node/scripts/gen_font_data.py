"""빌드 전 훅 — assets/efb_hangul16.bin 을 PROGMEM C++ 배열로 굽는다.

생성물(node/src/font_data.cpp)은 1.8MB 소스라 git 에 넣지 않는다(.gitignore).
바이너리(352KB)만 커밋하고 빌드 때마다 여기서 만든다 — 둘이 어긋날 일이 없다.

폰트 원본: Neo둥근모 (SIL OFL 1.1) — assets/OFL.txt. tools/gen_font.py 로 .bin 생성.
"""

from pathlib import Path

Import("env")  # noqa: F821  (PlatformIO 가 주입)

PROJECT = Path(env.subst("$PROJECT_DIR"))  # noqa: F821
BIN = PROJECT.parent / "assets" / "efb_hangul16.bin"
OUT = PROJECT / "src" / "font_data.cpp"


def main() -> None:
    if not BIN.exists():
        raise SystemExit(
            f"폰트 데이터가 없습니다: {BIN}\n"
            f"먼저 실행하세요:  ~/venv/bin/python tools/gen_font.py"
        )

    data = BIN.read_bytes()
    if OUT.exists() and OUT.stat().st_mtime > BIN.stat().st_mtime:
        return  # 최신

    lines = [
        "// 자동 생성 — node/scripts/gen_font_data.py. 수정하지 말 것.",
        "// 원본: assets/efb_hangul16.bin (Neo둥근모, SIL OFL 1.1 — assets/OFL.txt)",
        "//",
        "// 16px 1bpp, 글립당 32B 고정. ASCII 95자 + 완성형 한글 11,172자.",
        "// 서브셋이 아니라 어떤 한글도 두부가 되지 않는다 (이슈 #12).",
        "#include <Arduino.h>",
        "#include <pgmspace.h>",
        "",
        "// extern const — C++ 의 const 는 내부 링키지라 명시해야 main.cpp 에서 보인다.",
        "extern const uint8_t EFB_HANGUL16[] PROGMEM;",
        "extern const size_t EFB_HANGUL16_LEN;",
        "",
        "const uint8_t EFB_HANGUL16[] PROGMEM = {",
    ]
    for i in range(0, len(data), 16):
        lines.append("    " + ",".join(f"0x{b:02X}" for b in data[i : i + 16]) + ",")
    lines += [
        "};",
        f"extern const size_t EFB_HANGUL16_LEN = {len(data)};",
        "",
    ]

    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"[font] {OUT.name} 생성 — {len(data):,} B ({len(data) / 1024:.0f} KB)")


main()
