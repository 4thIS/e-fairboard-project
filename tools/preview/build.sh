#!/usr/bin/env bash
# e-Paper 미리보기 — 펌웨어의 렌더러(node_core)를 호스트에서 그대로 돌려 296x128 을 PBM 으로 뽑는다.
# 하드웨어가 없으니 이게 "실제 화면"을 보는 유일한 방법이다.
#
# 사용: tools/preview/build.sh [outdir]
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT="${1:-$ROOT/.preview}"
mkdir -p "$OUT"

if [[ ! -f "$ROOT/assets/efb_hangul16.bin" ]]; then
    echo "폰트 데이터가 없습니다. 먼저: ~/venv/bin/python tools/gen_font.py" >&2
    exit 1
fi

g++ -std=c++17 -Wall -Wextra -O2 \
    -I "$ROOT/node/lib/node_core/include" \
    "$ROOT/tools/preview/main.cpp" \
    "$ROOT/node/lib/node_core/src/text.cpp" \
    "$ROOT/node/lib/node_core/src/layout.cpp" \
    -o "$OUT/preview"

# --force16: templates.py 가 16px 단일로 정리된 뒤의 모습 (이슈 #12)
"$OUT/preview" "$ROOT/assets/efb_hangul16.bin" "$OUT" "${2:---force16}"
echo "-> $OUT/template*.pbm"
