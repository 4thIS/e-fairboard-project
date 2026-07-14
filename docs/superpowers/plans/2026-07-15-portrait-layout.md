# 세로 레이아웃 + 팀 소개 팜플렛 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 스펙 [docs/web/2026-07-15-portrait-layout-design.md](../../web/2026-07-15-portrait-layout-design.md) — 캔버스를 템플릿의 속성으로 내리고, 세로(128×296) "팀 소개" 템플릿(id=4)을 추가한다.

**Architecture:** `templates.py` 의 `TemplateDef` 가 `canvas_w`/`canvas_h` 를 갖고, `field_avail_w()` 가 전역 상수 대신 그 값을 쓴다. 생성기가 이를 C++ 헤더로 내보내고 `node/templates.h` 를 재생성한다(드리프트 훅이 강제). 프론트는 `GET /api/templates` 의 `canvas` 를 받아 그린다.

**Tech Stack:** Python 3.10 / FastAPI / pytest — Vue 3 + TS + vitest. 새 의존성 없음.

## Global Constraints

- 브랜치 `wj`. main 직접 push 금지 (CLAUDE.md).
- **`node/` 에서 손으로 고치는 파일은 없다.** `node/lib/node_core/include/node/templates.h` 는 `tools/gen_templates.py` 의 **생성물**이므로 재생성만 한다 (팀장 승인 2026-07-15). `layout.cpp`·`main.cpp`·`node/test/` 는 준표 영역 — 건드리지 않는다.
- `app/protocol/` 의 다른 파일(packet·crc16·cobs·framing·link)과 `app/simulator/` 는 건드리지 않는다.
- 세로 템플릿의 글자 크기는 **전부 16px**. 32px 금지 (한글 3자만 들어감).
- `PROTOCOL.md` 는 준표 주관 — **수정하지 않는다.** §8 템플릿 표에 id=4 를 추가하는 건 PR 에서 협의 요청한다.
- 백엔드 테스트: `cd server/backend; .venv\Scripts\python.exe -m pytest -q` / 프론트: `cd server/frontend; npm test`
- 드리프트 검사: `python tools/gen_templates.py --check` (표준 라이브러리만 쓰므로 venv 불필요)
- 커밋 메시지는 한국어 + `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>` 트레일러.

---

### Task 1: 캔버스를 템플릿의 속성으로 (백엔드)

**Files:**
- Modify: `server/backend/app/protocol/templates.py`
- Modify: `server/backend/tests/test_templates.py`

**Interfaces:**
- Produces:
  - `TemplateDef(id, name, fields, qr, canvas_w=296, canvas_h=128)`
  - `field_avail_w(f: FieldDef, qr: QrDef, canvas_w: int) -> int` — **3번째 인자 필수** (기본값 없음. 기본값을 두면 세로 템플릿에서 296이 조용히 새어 들어와 미리보기가 거짓말을 한다)
  - `as_dict()` 각 템플릿에 `canvas: {"w": int, "h": int}` 포함

- [ ] **Step 1: 실패하는 테스트 3개 추가**

`server/backend/tests/test_templates.py` 끝에 추가:

```python
def test_template_carries_its_own_canvas():
    # 기존 가로 템플릿은 296×128 기본값 그대로
    assert (TEMPLATES[0].canvas_w, TEMPLATES[0].canvas_h) == (296, 128)


def test_field_avail_w_uses_the_given_canvas_not_a_global():
    """세로 캔버스(128)에서 296 이 새어 들어오면 미리보기가 거짓말을 한다."""
    tpl = TEMPLATES[0]
    f = tpl.fields[0]  # 제목 x=8, y=8 — QR(224,32,64)과 안 겹침
    assert field_avail_w(f, tpl.qr, 296) == 288
    assert field_avail_w(f, tpl.qr, 128) == 120   # 캔버스가 좁으면 가용 폭도 좁다


def test_as_dict_carries_canvas():
    data = as_dict()
    assert data[0]["canvas"] == {"w": 296, "h": 128}
```

- [ ] **Step 2: 실패 확인**

Run: `cd server/backend; .venv\Scripts\python.exe -m pytest tests/test_templates.py -q`
Expected: 3 FAILED — `AttributeError: 'TemplateDef' object has no attribute 'canvas_w'` / `TypeError: field_avail_w() takes 2 positional arguments but 3 were given` / `KeyError: 'canvas'`

- [ ] **Step 3: templates.py 구현**

`server/backend/app/protocol/templates.py` 의 `TemplateDef` 를 교체:

```python
@dataclass(frozen=True)
class TemplateDef:
    id: int
    name: str
    fields: tuple[FieldDef, ...]
    qr: QrDef
    # 캔버스는 템플릿의 속성이다 — 세로 템플릿은 패널을 세워 128×296 을 쓴다.
    # 기본값이 있어 기존 가로 템플릿 정의는 한 글자도 안 바뀐다.
    canvas_w: int = 296
    canvas_h: int = 128
```

같은 파일의 `field_avail_w` 와 `as_dict` 를 교체:

```python
def field_avail_w(f: FieldDef, qr: QrDef, canvas_w: int) -> int:
    """필드 한 행이 실제로 쓸 수 있는 가로 폭(px).

    QR 박스와 **세로로 겹치는 행만** QR 앞까지로 줄어든다. 안 겹치는 행은 캔버스 끝까지 쓴다.

    canvas_w 는 **템플릿의 것**을 넘긴다 — 전역 상수를 쓰면 세로 템플릿(128)에서 296 이
    새어 들어와, 노드는 자르는데 미리보기는 안 자르는 거짓말이 된다.

    node_core/layout.cpp 의 field_avail_w() 와 **같은 식**이다 — 한쪽만 고치면 다른 쪽이 터진다.
    프론트는 이 값을 API 로 받아쓴다. 세 번째 구현을 만들지 말 것.
    """
    overlaps = f.y < qr.y + qr.size and qr.y < f.y + f.font_size
    right = qr.x if overlaps else canvas_w
    return max(0, right - f.x)


def as_dict() -> list[dict]:
    out = []
    for tpl in TEMPLATES.values():
        d = asdict(tpl)
        d["canvas"] = {"w": d.pop("canvas_w"), "h": d.pop("canvas_h")}
        for fd, f in zip(d["fields"], tpl.fields):
            fd["avail_w"] = field_avail_w(f, tpl.qr, tpl.canvas_w)  # 스펙 §6.2
        out.append(d)
    return out
```

파일 상단의 전역 상수는 **남겨둔다** — 기본값의 근거이자 문서 역할이다. 주석만 바꾼다:

```python
# 가로 템플릿의 기본 캔버스. 세로 템플릿은 TemplateDef 에서 128×296 으로 덮어쓴다.
CANVAS_W = 296
CANVAS_H = 128
```

- [ ] **Step 4: 기존 테스트의 `field_avail_w` 호출부 5곳 갱신**

`server/backend/tests/test_templates.py` 에서 인자 2개로 부르는 곳을 전부 3개로 바꾼다.

`test_max_bytes_fits_screen_width` 안:

```python
            avail = field_avail_w(f, tpl.qr, tpl.canvas_w)
```

`test_field_avail_w_shrinks_only_for_rows_overlapping_qr` 안:

```python
    assert field_avail_w(title, tpl.qr, tpl.canvas_w) == 296 - 8
    assert field_avail_w(when, tpl.qr, tpl.canvas_w) == 224 - 8
```

`test_template3_qr_is_higher_so_different_rows_overlap` 안:

```python
    assert field_avail_w(date, tpl.qr, tpl.canvas_w) == 240 - 8   # y 8~24  겹침
    assert field_avail_w(s1, tpl.qr, tpl.canvas_w) == 240 - 8     # y 44~60 겹침
    assert field_avail_w(s2, tpl.qr, tpl.canvas_w) == 296 - 8     # y 72~88 안 겹침
```

- [ ] **Step 5: 캔버스를 하드코딩한 기하 테스트를 템플릿 기준으로 교체**

`test_geometry_inside_296x128` 를 통째로 아래로 교체한다(이름 포함) — 296×128 을 박아두면 세로 템플릿이 통과할 수 없다:

```python
def test_geometry_inside_each_templates_canvas():
    for tpl in TEMPLATES.values():
        w, h = tpl.canvas_w, tpl.canvas_h
        for f in tpl.fields:
            assert 0 <= f.x < w and 0 <= f.y < h, f"{tpl.name}/{f.name}"
        assert tpl.qr.x + tpl.qr.size <= w and tpl.qr.y + tpl.qr.size <= h, tpl.name
```

- [ ] **Step 6: 전체 백엔드 테스트 통과 확인**

Run: `cd server/backend; .venv\Scripts\python.exe -m pytest -q`
Expected: 전부 PASS (템플릿은 아직 4개 — 새 템플릿은 Task 2)

- [ ] **Step 7: 커밋**

```bash
git add server/backend/app/protocol/templates.py server/backend/tests/test_templates.py
git commit -m "refactor(templates): 캔버스를 템플릿의 속성으로 — field_avail_w 가 전역을 안 본다

세로 템플릿(128x296)을 받으려면 가용 폭이 템플릿 캔버스에서 나와야 한다.
기본값(296x128)이 있어 기존 가로 템플릿 정의는 그대로다.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: 세로 템플릿 id=4 "팀 소개" 추가 (백엔드)

**Files:**
- Modify: `server/backend/app/protocol/templates.py`
- Modify: `server/backend/tests/test_templates.py`

**Interfaces:**
- Consumes: Task 1 의 `TemplateDef(..., canvas_w, canvas_h)`, `field_avail_w(f, qr, canvas_w)`
- Produces: `TEMPLATES[4]` — 캔버스 128×296, 필드 4개(팀명·주제1·주제2·주제3) 전부 16px, QR(16, 140, 96)

- [ ] **Step 1: 실패하는 테스트 추가**

`server/backend/tests/test_templates.py` 끝에 추가:

```python
def test_portrait_template_is_128x296():
    tpl = TEMPLATES[4]
    assert (tpl.canvas_w, tpl.canvas_h) == (128, 296)
    assert tpl.name == "팀 소개"


def test_portrait_fields_are_all_16px():
    # 32px 한글은 폭 120px 안에 3자만 들어간다 — 한글 팀명이 잘린다 (스펙 §2)
    assert all(f.font_size == 16 for f in TEMPLATES[4].fields)


def test_portrait_avail_w_is_the_narrow_canvas():
    tpl = TEMPLATES[4]
    # QR(y 140~235)과 세로로 겹치는 필드가 없다 → 모든 행이 캔버스 끝(128)까지
    for f in tpl.fields:
        assert field_avail_w(f, tpl.qr, tpl.canvas_w) == 120, f.name
```

기존 세 테스트도 5개 템플릿으로 갱신한다. `test_four_templates_defined` 는 **이름째로** 교체한다
(개수가 이름에 박혀 있으면 다음 템플릿에서 또 거짓말이 된다):

```python
def test_templates_defined():
    assert set(TEMPLATES.keys()) == {0, 1, 2, 3, 4}
```

```python
def test_field_ids_match_protocol_spec():
    # PROTOCOL.md §8: 행사 안내(0)=4, 부스 지도(1)=2, 모집 공고(2)=3, 일정표(3)=4
    # + 팀 소개(4)=4 (세로, PROTOCOL.md 반영은 준표와 협의 — 스펙 §Global Constraints)
    assert [len(TEMPLATES[i].fields) for i in range(5)] == [4, 2, 3, 4, 4]
    for tpl in TEMPLATES.values():
        assert [f.id for f in tpl.fields] == list(range(len(tpl.fields)))
```

```python
def test_as_dict_is_json_shape():
    data = as_dict()
    assert len(data) == 5
    assert data[0]["fields"][0]["name"]
    assert {"x", "y", "size"} <= set(data[0]["qr"].keys())
```

- [ ] **Step 2: 실패 확인**

Run: `cd server/backend; .venv\Scripts\python.exe -m pytest tests/test_templates.py -q`
Expected: FAILED — `KeyError: 4` 외

- [ ] **Step 3: 템플릿 추가**

`server/backend/app/protocol/templates.py` 의 `TEMPLATES` 딕셔너리 끝(`3: ...` 다음)에 추가:

```python
    # 세로 팜플렛 — 패널을 세워 128×296 으로 쓴다 (스펙 2026-07-15-portrait-layout-design.md).
    # 폭 120px = 한글 7자. 문단은 안 들어간다 → 상세 소개는 QR 너머 웹페이지가 맡는다.
    # 노드 렌더러는 텍스트와 QR만 그린다(선·도형 없음) → 구분선 같은 장식 필드는 두지 않는다.
    # QR(y 140~235)은 어떤 필드 행과도 겹치지 않는다 → 모든 행의 가용 폭이 120px.
    4: TemplateDef(4, "팀 소개", (
        FieldDef(0, "팀명", 8, 8, 16, 21),    # 21B = 한글 7자 = 112px ≤ 120px
        FieldDef(1, "주제1", 8, 40, 16, 21),
        FieldDef(2, "주제2", 8, 62, 16, 21),
        FieldDef(3, "주제3", 8, 84, 16, 21),
    ), QrDef(16, 140, 96), canvas_w=128, canvas_h=296),   # QR x=16 → (128-96)/2 가운데
```

- [ ] **Step 4: 전체 백엔드 테스트 통과 확인**

Run: `cd server/backend; .venv\Scripts\python.exe -m pytest -q`
Expected: 전부 PASS. 특히 `test_max_bytes_fits_screen_width` 가 새 템플릿도 자동 검증한다 — `(21 // 3) * 16 = 112 ≤ 120`.

- [ ] **Step 5: API 응답 확인 (수동)**

Run: `cd server/backend; .venv\Scripts\python.exe -m uvicorn app.main:create_app --factory --port 8000` (별도 터미널)

```bash
PW=$(grep ADMIN_PASSWORD server/backend/.env | cut -d= -f2 | tr -d '\r')
T=$(curl -s -X POST http://localhost:8000/api/auth/login -H "Content-Type: application/json" -d "{\"password\":\"$PW\"}" | python -c "import sys,json;print(json.load(sys.stdin)['token'])")
curl -s http://localhost:8000/api/templates -H "Authorization: Bearer $T" | python -c "
import sys,json
t=[x for x in json.load(sys.stdin) if x['id']==4][0]
print(t['name'], t['canvas'])
for f in t['fields']: print(' ', f['name'], 'y=',f['y'], 'avail_w=',f['avail_w'])"
```

Expected:
```
팀 소개 {'w': 128, 'h': 296}
  팀명 y= 8 avail_w= 120
  주제1 y= 40 avail_w= 120
  주제2 y= 62 avail_w= 120
  주제3 y= 84 avail_w= 120
```

- [ ] **Step 6: 커밋**

```bash
git add server/backend/app/protocol/templates.py server/backend/tests/test_templates.py
git commit -m "feat(templates): 세로 팜플렛 템플릿 '팀 소개'(id=4) — 128x296

팀명·주제 3줄 + 큰 QR(96px). 폭 120px 은 한글 7자라 문단이 안 들어간다 —
상세 소개는 QR 너머 웹페이지가 맡는다 (스펙 §4).

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: 생성기가 캔버스를 내보내고 node/templates.h 재생성

**Files:**
- Modify: `tools/gen_templates.py`
- Regenerate (손으로 편집 금지): `node/lib/node_core/include/node/templates.h`

**Interfaces:**
- Consumes: Task 1·2 의 `TemplateDef.canvas_w/canvas_h`
- Produces: C++ `TemplateDef` 에 `int16_t canvas_w; int16_t canvas_h;` — 준표의 `layout.cpp` 가 이 값을 쓰게 된다(§6.2, 별도 작업)

**왜 이 태스크가 필수인가:** `tools/check_drift.py` 가 `node/platformio.ini` 의 빌드 전 훅이다. 재생성 없이 `templates.py` 만 바꾸면 **준표의 `pio run`/`pio test` 가 드리프트 에러로 즉시 멈춘다.**

- [ ] **Step 1: 재생성 없이 드리프트가 잡히는지 먼저 확인 (가드가 살아 있는가)**

Run: `python tools/gen_templates.py --check`
Expected: FAIL — `node/lib/node_core/include/node/templates.h 가 templates.py 와 어긋납니다.`

(여기서 통과가 뜨면 가드가 죽은 것이다 — 원인을 찾고 멈춘다.)

- [ ] **Step 2: 생성기가 캔버스를 내보내도록 수정**

`tools/gen_templates.py` 의 `render()` 안에서 **전역 상수 주석**을 교체:

```python
        "// e-Paper 2.9\" 기본(가로) 캔버스. 세로 템플릿은 TemplateDef.canvas_w/h 로 덮어쓴다.",
        "// layout.cpp 는 아직 이 전역을 쓴다 — 세로 지원 시 템플릿 값으로 옮겨야 한다(준표).",
        "constexpr int16_t CANVAS_W = 296;",
        "constexpr int16_t CANVAS_H = 128;",
```

같은 함수의 C++ `TemplateDef` 구조체 선언에 캔버스 두 줄을 추가:

```python
        "struct TemplateDef {",
        "    uint8_t id;",
        "    const char* name;",
        "    uint8_t field_count;",
        "    FieldDef fields[TEMPLATE_MAX_FIELDS];",
        "    QrDef qr;",
        "    int16_t canvas_w;   // 가로 296 / 세로 128",
        "    int16_t canvas_h;   // 가로 128 / 세로 296",
        "};",
```

그리고 템플릿 값을 찍는 마지막 줄(집합 초기화 순서가 구조체 선언 순서와 같아야 한다)을 교체:

```python
        lines.append(
            f"    }}, {{{tpl.qr.x}, {tpl.qr.y}, {tpl.qr.size}}}, "
            f"{tpl.canvas_w}, {tpl.canvas_h}}},"
        )
```

- [ ] **Step 3: 헤더 재생성**

Run: `python tools/gen_templates.py`
Expected: `wrote node/lib/node_core/include/node/templates.h  (5 templates)`

- [ ] **Step 4: 드리프트 가드 통과 확인**

Run: `python tools/gen_templates.py --check`
Expected: `OK   node/lib/node_core/include/node/templates.h — templates.py 와 일치`

- [ ] **Step 5: 생성물 눈으로 확인 (구조체 순서·세로 값)**

Read: `node/lib/node_core/include/node/templates.h`

확인할 것 — `TEMPLATE_COUNT = 5`, `TEMPLATE_MAX_FIELDS = 4`(그대로), 마지막 항목이
`{4, "팀 소개", 4, {...}, {16, 140, 96}, 128, 296},` 이고 앞 4개는 `..., 296, 128},` 로 끝난다.

- [ ] **Step 6: 커밋**

```bash
git add tools/gen_templates.py node/lib/node_core/include/node/templates.h
git commit -m "feat(tools): 생성기가 템플릿별 캔버스를 내보낸다 — node/templates.h 재생성

check_drift 가 pio 빌드 전 훅이라 재생성하지 않으면 펌웨어 빌드가 멈춘다.
templates.h 는 생성물이므로 손으로 고치지 않고 생성기로 다시 찍는다.

layout.cpp 의 field_avail_w 는 아직 전역 CANVAS_W 를 쓴다 — 세로 템플릿의
가용 폭을 296 으로 잘못 계산한다. 이건 준표 영역이라 PR 에서 협의한다.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: 프론트 — 템플릿 캔버스로 그린다

**Files:**
- Modify: `server/frontend/src/epaper/types.ts`
- Modify: `server/frontend/src/components/EpaperPreview.vue`
- Modify: `server/frontend/src/components/NodeCard.vue`
- Modify: `server/frontend/src/epaper/text.spec.ts`

**Interfaces:**
- Consumes: `GET /api/templates` 의 `canvas: {w, h}` (Task 1·2)
- Produces: `TemplateDef.canvas: {w: number; h: number}`, `DEFAULT_CANVAS`

- [ ] **Step 1: 세로 폭 잘라내기 테스트 추가 (실패)**

`server/frontend/src/epaper/text.spec.ts` 끝에 추가:

```ts
describe('세로 캔버스(폭 120px)', () => {
  it('한글 7자는 들어가고 8자째는 통째로 버린다', () => {
    // 노드와 같은 규칙: 한글 16px, 넘치는 글자는 반쪽으로 그리지 않고 버린다
    expect(clip('일이삼사오육칠', 120, 1)).toEqual({ text: '일이삼사오육칠', clipped: false })
    expect(clip('일이삼사오육칠팔', 120, 1)).toEqual({ text: '일이삼사오육칠', clipped: true })
  })

  it('ASCII 는 반각이라 15자까지 들어간다', () => {
    expect(measure('ABCDEFGHIJKLMNO', 1)).toBe(120)
    expect(clip('ABCDEFGHIJKLMNOP', 120, 1).clipped).toBe(true)
  })
})
```

`text.spec.ts` 상단 import 에 `measure` 가 없으면 추가한다:

```ts
import { advanceOf, clip, isRenderable, measure, scaleFor, utf8Bytes } from './text'
```

- [ ] **Step 2: 실패하지 않는지 확인 — 이건 기존 규칙이라 통과해야 정상**

Run: `cd server/frontend; npm test`
Expected: PASS. (이 테스트는 새 기능이 아니라 **세로 폭에서도 기존 규칙이 그대로임을 못 박는 회귀 방지**다. 실패하면 `text.ts` 가 폭을 잘못 다루는 것이므로 멈추고 원인을 찾는다.)

- [ ] **Step 3: types.ts — 캔버스를 템플릿에 싣는다**

`server/frontend/src/epaper/types.ts` 를 통째로 교체:

```ts
/** GET /api/templates 응답. avail_w 는 서버가 계산해 준다 (스펙 §6.2). */
export interface FieldDef {
  id: number
  name: string
  x: number
  y: number
  font_size: number   // 16 또는 32만
  max_bytes: number
  avail_w: number     // 이 행이 쓸 수 있는 가로 폭 — 공식을 프론트에 재구현하지 말 것
}

export interface QrDef { x: number; y: number; size: number }

export interface Canvas { w: number; h: number }

export interface TemplateDef {
  id: number
  name: string
  fields: FieldDef[]
  qr: QrDef
  canvas: Canvas      // 가로 296×128 / 세로 128×296 — 템플릿의 속성이다
}

/** 표시할 템플릿이 없을 때(미배포 노드) 그리는 빈 화면의 크기. */
export const DEFAULT_CANVAS: Canvas = { w: 296, h: 128 }

/** 세로 미리보기가 카드를 밀어내지 않는 한도. 정수 배율만 쓰므로 ×2/×1 만 나온다. */
export const MAX_PREVIEW_H = 320
```

- [ ] **Step 4: EpaperPreview — 캔버스를 템플릿에서 읽고 배율을 캡한다**

`server/frontend/src/components/EpaperPreview.vue` 의 `<script setup>` 에서 import 와 `previewScale` 을 교체:

```ts
import { clip, advanceOf, scaleFor, GLYPH_CELL } from '../epaper/text'
import { DEFAULT_CANVAS, MAX_PREVIEW_H, type TemplateDef } from '../epaper/types'
```

```ts
/** 캔버스는 템플릿의 속성. 템플릿이 없으면 가로 빈 화면. */
const canvas = computed(() => props.template?.canvas ?? DEFAULT_CANVAS)

/** 전체 배율. 소수/0 배율은 픽셀 정합을 깨므로 정수로 내린다.
 *  세로(296px)는 ×2 면 592px 라 카드를 밀어낸다 → 캔버스 높이로 상한을 건다.
 *  여기서 캡을 걸면 카드·다이얼로그 등 **모든 호출자가 한 번에 안전**해진다. */
const previewScale = computed(() => {
  const want = Math.max(1, Math.floor(props.scale))
  const fit = canvas.value.h * 2 <= MAX_PREVIEW_H ? 2 : 1
  return Math.min(want, fit)
})
```

같은 파일의 `<template>` 에서 `CANVAS_W`/`CANVAS_H` 를 쓰는 두 곳을 교체:

```html
    :style="{ width: canvas.w * previewScale + 'px', height: canvas.h * previewScale + 'px' }"
```

```html
      :style="{ width: canvas.w + 'px', height: canvas.h + 'px',
                transform: `scale(${previewScale})` }"
```

- [ ] **Step 5: NodeCard — 가로·세로 카드가 섞여도 안 무너지게**

`server/frontend/src/components/NodeCard.vue` 의 `<style scoped>` 에서 `.screen` 규칙을 교체:

```css
.screen { position: relative; display: flex; justify-content: center; align-items: flex-start; }
```

그리고 카드가 서로 다른 높이로 늘어나도 나란히 서도록 `.grid` 를 쓰는 `DashboardView.vue` 는
이미 `flex-wrap`+`gap` 이라 변경 없음 — 확인만 한다.

배율 로직은 손대지 않는다. `NodeCard` 는 지금처럼 뷰포트 기준 `previewScale`(1280px 미만 → ×1)을
`:scale` 로 넘기고, **높이 상한은 `EpaperPreview` 가 캡한다**(Step 4). 두 규칙이 곱해져
가로=×2, 세로=×1 이 된다.

- [ ] **Step 6: 타입체크·테스트**

Run: `cd server/frontend; npx vue-tsc -b; npm test`
Expected: 타입 에러 없음, 전부 PASS

- [ ] **Step 7: 수동 검증 — 세로 미리보기가 실제로 그려지는가**

백엔드(8000) + `npm run dev`(5173) 실행. 브라우저에서:

1. 노드 카드의 [내용 수정] → 템플릿 셀렉트에 **"팀 소개"** 가 보인다
2. 선택하면 폼이 팀명·주제1·주제2·주제3 으로 바뀌고, **우측 미리보기가 세로(128×296)** 로 바뀐다
3. 팀명에 한글 8자(`일이삼사오육칠팔`)를 넣으면 **"⚠ 화면에서 잘립니다"** 가 뜨고 미리보기에서 8자째가 사라진다
4. QR URL 을 넣으면 미리보기 하단에 큰 QR(96px)이 뜬다
5. 저장 → 배포 → 카드 미리보기가 **세로로** 바뀐다 (가로 노드 카드와 나란히 서도 레이아웃이 안 무너진다)

Expected: 위 5가지 + 콘솔 에러 없음

- [ ] **Step 8: 커밋**

```bash
git add server/frontend
git commit -m "feat(frontend): 미리보기가 템플릿 캔버스를 따른다 — 세로(128x296) 지원

전역 296x128 상수를 걷어내고 템플릿의 canvas 를 쓴다. 세로는 x2 면 592px 라
카드를 밀어내므로 EpaperPreview 가 높이 상한(320px)으로 배율을 캡한다 —
한 곳에서 캡하면 카드·다이얼로그 모든 호출자가 안전하다.

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: 전체 회귀 + 드리프트 확인

**Files:** 없음 (검증 태스크)

- [ ] **Step 1: 백엔드 전체**

Run: `cd server/backend; .venv\Scripts\python.exe -m pytest -q`
Expected: 전부 PASS

- [ ] **Step 2: 프론트 전체 + 프로덕션 빌드**

Run: `cd server/frontend; npm test; npm run build`
Expected: 전부 PASS, `dist/` 생성

- [ ] **Step 3: 생성물 드리프트 — 두 생성기 모두**

Run: `python tools/gen_templates.py --check && python tools/gen_test_vectors.py --check`
Expected: 둘 다 `OK` (test_vectors 는 프로토콜 계층을 안 건드렸으므로 원래 통과해야 한다. 여기서 실패하면 건드리면 안 될 걸 건드린 것이다.)

- [ ] **Step 4: 작업 트리 정리 확인**

Run: `git status --short`
Expected: 추적되는 변경 없음
