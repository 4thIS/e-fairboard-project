"""서버의 templates.py 에서 템플릿 좌표·폰트·색·장식을 뽑아 C++ 헤더로 생성한다.

PROTOCOL.md §8: "좌표·폰트는 펌웨어 상수 → 서버는 값만 전송".
단일 기준 소스는 server/backend/app/protocol/templates.py (웹 설계 §5.1).

실행: python tools/gen_templates.py
      python tools/gen_templates.py --check   # 드리프트 검사 (CI)
출력: node/lib/node_core/include/node/templates.h
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server" / "backend"))

from app.protocol.templates import TEMPLATES, field_max_bytes

OUT = ROOT / "node" / "lib" / "node_core" / "include" / "node" / "templates.h"

COLOR = {"black": 0, "red": 1, "paper": 2}   # 글자/라벨 색
FILL = {"none": 0, "black": 1, "red": 2}      # 장식 채움/테두리 색


def _c(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def render() -> str:
    max_fields = max(len(t.fields) for t in TEMPLATES.values())
    max_decos = max((len(t.decorations) for t in TEMPLATES.values()), default=0)
    max_labels = max((len(t.labels) for t in TEMPLATES.values()), default=0)

    L = [
        "// 자동 생성 — 수정하지 말 것. tools/gen_templates.py 로 재생성한다.",
        "// 원본: server/backend/app/protocol/templates.py (단일 기준 소스)",
        "#pragma once",
        "",
        "#include <stddef.h>",
        "#include <stdint.h>",
        "",
        "namespace node {",
        "",
        "constexpr int16_t CANVAS_W = 1304;  // 가로 기본. 템플릿별 canvas_w/h 가 우선.",
        "constexpr int16_t CANVAS_H = 984;",
        "",
        f"constexpr size_t TEMPLATE_COUNT = {len(TEMPLATES)};",
        f"constexpr size_t TEMPLATE_MAX_FIELDS = {max_fields};",
        f"constexpr size_t TEMPLATE_MAX_DECOS = {max(max_decos, 1)};",
        f"constexpr size_t TEMPLATE_MAX_LABELS = {max(max_labels, 1)};",
        "",
        "// 색: 0=검정 1=빨강 2=종이(빨강밴드 위 흰글자=두 플레인 knockout)",
        "// 장식 fill/stroke: 0=none 1=검정 2=빨강",
        "",
        "struct FieldDef {",
        "    uint8_t id;",
        "    const char* name;",
        "    int16_t x;",
        "    int16_t y;",
        "    uint8_t font_size;",
        "    uint8_t color;",
        "    uint8_t max_bytes;  // UTF-8 바이트 (파생)",
        "    int16_t w;          // 명시 폭(0=QR/캔버스 자동)",
        "    int16_t h;          // 멀티라인 텍스트영역 높이(0=한 줄)",
        "};",
        "",
        "struct Label {  // 고정 텍스트",
        "    int16_t x;",
        "    int16_t y;",
        "    uint8_t font_size;",
        "    uint8_t color;",
        "    const char* text;",
        "};",
        "",
        "struct Deco {  // 장식 사각형 (선=얇은 fill)",
        "    int16_t x;",
        "    int16_t y;",
        "    int16_t w;",
        "    int16_t h;",
        "    uint8_t fill;",
        "    uint8_t stroke;",
        "    uint8_t stroke_w;",
        "};",
        "",
        "struct QrDef {",
        "    int16_t x;",
        "    int16_t y;",
        "    int16_t size;",
        "};",
        "",
        "struct TemplateDef {",
        "    uint8_t id;",
        "    const char* name;",
        "    uint8_t field_count;",
        "    FieldDef fields[TEMPLATE_MAX_FIELDS];",
        "    QrDef qr;",
        "    uint8_t deco_count;",
        "    Deco decos[TEMPLATE_MAX_DECOS];",
        "    uint8_t label_count;",
        "    Label labels[TEMPLATE_MAX_LABELS];",
        "    int16_t canvas_w;",
        "    int16_t canvas_h;",
        "};",
        "",
        "constexpr TemplateDef TEMPLATES[TEMPLATE_COUNT] = {",
    ]

    for tid in sorted(TEMPLATES):
        t = TEMPLATES[tid]
        L.append(f"    // {t.name}")
        L.append(f'    {{{t.id}, "{_c(t.name)}", {len(t.fields)}, {{')
        for f in t.fields:
            # max_bytes 는 uint8_t 필드다. 분할 SET_FIELD 로 필드 상한이 198→512 가 됐지만
            # 노드는 이 값을 쓰지 않고(순수 메타) 실제 상한은 서버 field_max_bytes 다 →
            # 헤더는 255 로 클램프해 narrowing 빌드 오류만 피한다.
            mb = min(255, field_max_bytes(f, t.qr, t.canvas_w))
            L.append(f'        {{{f.id}, "{_c(f.name)}", {f.x}, {f.y}, {f.font_size}, '
                     f'{COLOR[f.color]}, {mb}, {f.w}, {f.h}}},')
        for _ in range(max_fields - len(t.fields)):
            L.append("        {0, nullptr, 0, 0, 0, 0, 0, 0, 0},")
        L.append(f"    }}, {{{t.qr.x}, {t.qr.y}, {t.qr.size}}},")

        L.append(f"    {len(t.decorations)}, {{")
        for d in t.decorations:
            L.append(f"        {{{d.x}, {d.y}, {d.w}, {d.h}, "
                     f"{FILL[d.fill]}, {FILL[d.stroke]}, {d.stroke_w}}},")
        for _ in range(max(max_decos, 1) - len(t.decorations)):
            L.append("        {0, 0, 0, 0, 0, 0, 0},")
        L.append("    },")

        L.append(f"    {len(t.labels)}, {{")
        for lb in t.labels:
            L.append(f'        {{{lb.x}, {lb.y}, {lb.font_size}, {COLOR[lb.color]}, "{_c(lb.text)}"}},')
        for _ in range(max(max_labels, 1) - len(t.labels)):
            L.append('        {0, 0, 0, 0, nullptr},')
        L.append("    },")

        L.append(f"    {t.canvas_w}, {t.canvas_h}}},")

    L += [
        "};",
        "",
        "// 없으면 nullptr.",
        "inline const TemplateDef* find_template(int16_t template_id) {",
        "    for (size_t i = 0; i < TEMPLATE_COUNT; ++i) {",
        "        if (TEMPLATES[i].id == template_id) return &TEMPLATES[i];",
        "    }",
        "    return nullptr;",
        "}",
        "",
        "}  // namespace node",
        "",
    ]
    return "\n".join(L)


def main() -> None:
    content = render()
    if "--check" in sys.argv:
        if not OUT.exists():
            sys.exit(f"FAIL {OUT.relative_to(ROOT)} 가 없습니다. gen_templates.py 를 실행하세요.")
        if OUT.read_text(encoding="utf-8") != content:
            sys.exit(
                f"FAIL {OUT.relative_to(ROOT)} 가 templates.py 와 어긋납니다.\n"
                f"     python tools/gen_templates.py 를 실행하고 커밋하세요."
            )
        print(f"OK   {OUT.relative_to(ROOT)} — templates.py 와 일치")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}  ({len(TEMPLATES)} templates)")


if __name__ == "__main__":
    main()
