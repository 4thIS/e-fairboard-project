# 노드 펌웨어 인수인계 — 설명 필드 멀티라인(줄바꿈) 렌더

> **한 줄:** 프로젝트 소개(템플릿 2·3)의 **설명**이 멀티라인 텍스트영역이 됐다.
> 서버·웹은 완료(줄바꿈+자동 wrap 동작 실증). **노드가 아직 한 줄만 그려서** 판넬에선
> 설명이 한 줄로 잘린다. 노드에 **멀티라인 draw** 를 넣고 재플래시하면 끝.
>
> - 대상 펌웨어: `node/src/main_hat1248.cpp` (최신 12.48" 3색) @ `main`
> - 담당: **hm**. `gen_templates.py`·`node_core` 는 공용이라 값/규칙만 서버와 맞춘다.
> - 폰트 재베이크 **불필요** — 설명은 이미 구운 40px.

---

## 0. 현황

**서버·웹 완료(main):**
- `templates.py` `FieldDef` 에 **`h`**(텍스트영역 높이, 0=한 줄) 추가. 설명: 가로2 `40px,w920,h560`,
  세로3 `40px,w888,h660`.
- 줄 높이 규칙 **`line_h(px) = px * 27 // 20`**(=1.35배). 설명 40px → **line_h 54**.
- 웹 미리보기·에디터(textarea)·서버 검증(max_bytes 198)까지 반영·실증됨.
- 한 필드 최대 **198바이트**(SET_FIELD 한도)는 그대로 — 멀티라인이라도 총 198B.

**노드가 아직 안 되는 것:**
- `templates.h` 의 `FieldDef` 에 `h` 가 **없다**(서버 쪽만 추가함 — 노드 빌드를 안 깨려고).
- `node_core` 는 `draw_utf8`(한 줄)만 있다. 설명을 한 줄로 그리고 `max_w` 에서 자른다.

---

## 1. 할 일 — 3곳

### ① 생성기에 `h` 추가 → `templates.h` 재생성
`tools/gen_templates.py`:
- `FieldDef` 구조체에 멤버 추가(맨 끝):
  ```cpp
  int16_t w;          // 명시 폭(0=QR/캔버스 자동)
  int16_t h;          // 멀티라인 텍스트영역 높이(0=한 줄)
  ```
- 데이터 방출에 `f.h` 추가 (필드 한 줄):
  ```python
  f'{COLOR[f.color]}, {mb}, {f.w}, {f.h}}},')
  ```
- 패딩 초기화도 원소 하나 늘린다: `{0, nullptr, 0, 0, 0, 0, 0, 0, 0}`
- `python tools/gen_templates.py` 실행해 `templates.h` 재생성·커밋.

### ② `node_core` 에 멀티라인 draw 추가
`node/lib/node_core/include/node/text.h` + `.../src/text.cpp` — `draw_utf8` 옆에:
```cpp
// (x,y) 왼쪽-위 기준, 폭 max_w·높이 max_h 영역에 멀티라인. 줄높이 line_h.
// 규칙(웹 text.ts wrap() 과 동일): 명시 '\n' 은 강제 줄바꿈, 그 외 공백 단위로 흘리고
// 한 단어가 max_w 를 넘으면 글자 단위로 쪼갠다. max_h/line_h 줄을 넘으면 버린다.
void draw_multiline(ICanvas& canvas, IGlyphSource& font, int16_t x, int16_t y,
                    const char* utf8, uint8_t px, int16_t max_w, int16_t max_h,
                    int16_t line_h, Ink ink = Ink::Black);
```
알고리즘(웹과 **글자 폭 기준이 같아야** 미리보기와 안 어긋남 — advance 는 BakedFont 가 이미
`font_advance.json` 값을 쓴다):
1. 현재 줄 폭 `pen` 누적. 다음 글자 advance 를 더해 `max_w` 초과면 줄바꿈(줄 수 +1, pen=0).
2. `'\n'` 만나면 강제 줄바꿈.
3. 각 줄을 `draw_utf8(canvas,font,x, y + line*line_h, <그 줄>, px, max_w, ink)` 로 그린다
   (줄 단위로 잘라 넘기면 재사용 가능).
4. `line * line_h >= max_h` 면 더 안 그림.

> 단어 단위 wrap 이 부담이면 **글자 단위 wrap + '\n'** 만이라도 먼저(웹도 긴 단어는 글자로 쪼갬).
> 단어 경계 우선은 웹과 미세하게 달라질 수 있으나 판넬 가독성엔 무해.

### ③ 렌더에서 멀티라인 필드 분기
`node/src/main_hat1248.cpp` `EpdDisplay::render()` 의 필드 루프:
```cpp
const node::FieldDef& f = tpl->fields[i];
...
if (f.h > 0) {
    const int16_t lh = f.font_size * 27 / 20;   // line_h — 서버 규칙과 동일
    node::draw_multiline(*this, g_font, f.x, f.y, s.fields[f.id],
                         f.font_size, f.w, f.h, lh, field_ink(f.color));
} else {
    const int16_t avail = node::field_avail_w(f, tpl->qr, tpl->canvas_w);
    node::draw_utf8(*this, g_font, f.x, f.y, s.fields[f.id], f.font_size, avail, field_ink(f.color));
}
```
> `line_h` 는 반드시 `px*27/20`(정수) — `templates.py::line_h`, 웹 `line_h` 와 같은 식.

---

## 2. 검증
- native 단위테스트(`node/test/test_text`)에 `draw_multiline` 케이스: `\n` 강제 줄바꿈,
  폭 초과 자동 줄바꿈, `max_h` 초과 줄 버림. `pio test -e native` 통과.
- 실측: 웹 에디터에서 프로젝트 소개(2·3) 설명에 여러 줄 입력 → 배포 → 판넬이 웹 미리보기와
  같은 줄바꿈으로 그려지는지 대조.

## 3. 손대지 말 것 / 참고
- 서버·웹 완료 — 노드만. 좌표·색·QR·밴드는 그대로(시안 A 확정).
- `line_h = px*27//20` 는 웹·서버·노드 **공용 규칙** — 어기면 미리보기와 줄 수가 달라진다.
- 참고 구현: 웹 `server/frontend/src/epaper/text.ts` 의 `wrap()` (같은 규칙, 그대로 옮기면 됨).
- 현재 미반영 판넬은 설명을 **한 줄로 잘라** 그린다(무해) — 재플래시 전까지의 임시 상태.
