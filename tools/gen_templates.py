"""서버의 templates.py 에서 템플릿 좌표·폰트·최대길이를 뽑아 C++ 헤더로 생성한다.

PROTOCOL.md §8: "좌표·폰트는 펌웨어 상수 → 서버는 값만 전송".
그 상수의 단일 기준 소스는 server/backend/app/protocol/templates.py 다 (웹 설계 §5.1).
손으로 옮겨 적으면 반드시 어긋나므로 생성한다.

실행: ~/venv/bin/python tools/gen_templates.py
      ~/venv/bin/python tools/gen_templates.py --check   # 드리프트 검사 (CI)
출력: node/lib/node_core/include/node/templates.h
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "server" / "backend"))

from app.protocol.templates import TEMPLATES

OUT = ROOT / "node" / "lib" / "node_core" / "include" / "node" / "templates.h"


def render() -> str:
    max_fields = max(len(t.fields) for t in TEMPLATES.values())

    lines = [
        "// 자동 생성 — 수정하지 말 것. tools/gen_templates.py 로 재생성한다.",
        "// 원본: server/backend/app/protocol/templates.py (좌표·폰트의 단일 기준 소스)",
        "#pragma once",
        "",
        "#include <stddef.h>",
        "#include <stdint.h>",
        "",
        "namespace node {",
        "",
        "// e-Paper 2.9\" 296x128 기준 좌표.",
        "constexpr int16_t CANVAS_W = 296;",
        "constexpr int16_t CANVAS_H = 128;",
        "",
        f"constexpr size_t TEMPLATE_COUNT = {len(TEMPLATES)};",
        f"constexpr size_t TEMPLATE_MAX_FIELDS = {max_fields};",
        "",
        "struct FieldDef {",
        "    uint8_t id;",
        "    const char* name;",
        "    int16_t x;",
        "    int16_t y;",
        "    uint8_t font_size;",
        "    uint8_t max_bytes;  // UTF-8 바이트 기준",
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
        "};",
        "",
        "constexpr TemplateDef TEMPLATES[TEMPLATE_COUNT] = {",
    ]

    for tid in sorted(TEMPLATES):
        tpl = TEMPLATES[tid]
        lines.append(f"    // {tpl.name}")
        lines.append(f"    {{{tpl.id}, \"{tpl.name}\", {len(tpl.fields)}, {{")
        for f in tpl.fields:
            lines.append(
                f"        {{{f.id}, \"{f.name}\", {f.x}, {f.y}, {f.font_size}, {f.max_bytes}}},"
            )
        # 남는 슬롯을 0으로 채워 집합 초기화 경고를 막는다
        for _ in range(max_fields - len(tpl.fields)):
            lines.append("        {0, nullptr, 0, 0, 0, 0},")
        lines.append(f"    }}, {{{tpl.qr.x}, {tpl.qr.y}, {tpl.qr.size}}}}},")

    lines += [
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

    return "\n".join(lines)


def main() -> None:
    content = render()

    # 드리프트 가드 — 생성물이 소스와 어긋나면 실패한다.
    # templates.py 만 고치고 templates.h 재생성을 잊으면 펌웨어가 옛 좌표·폰트로 그린다.
    # 아무 테스트도 안 깨지므로 여기서 잡지 않으면 화면이 잘린 뒤에야 안다 (이슈 #12).
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
