/** 노드 렌더러(node_core/text.cpp draw_utf8)와 **같은 규칙**.
 *
 * 미리보기가 노드와 다르게 그리면 시연의 주인공이 거짓말을 한다.
 * 이 파일을 고칠 때는 node_core/text.cpp 를 먼저 읽을 것.
 *
 * 폰트는 efb_hangul16 — 16x16 비트맵. ASCII 는 왼쪽 8비트만 쓰고 전진도 8px(반각),
 * 한글은 16px(전각). 폰트에 없는 글자는 그리지도, 자리를 주지도 않는다.
 */

export const GLYPH_CELL = 16

/** 노드 scale_for 과 동일 — 정수 내림, 최소 x1 (node_core/layout.cpp).
 *  16 미만이면 0 이 되어 글자가 통째로 사라지므로 최소 x1 로 막는다. */
export function scaleFor(fontPx: number): number {
  return Math.max(1, Math.floor(fontPx / GLYPH_CELL))
}

/** 폰트에 있는 글자인가. ASCII(0x20~0x7E) + 완성형 한글(U+AC00~U+D7A3). */
export function isRenderable(ch: string): boolean {
  const cp = ch.codePointAt(0)
  if (cp === undefined) return false
  return (cp >= 0x20 && cp <= 0x7e) || (cp >= 0xac00 && cp <= 0xd7a3)
}

/** 글자 하나의 전진 폭(px, scale 1 기준). ASCII 반각 8, 한글 전각 16. */
export function advanceOf(ch: string): number {
  const cp = ch.codePointAt(0)
  return cp !== undefined && cp >= 0x20 && cp <= 0x7e ? 8 : GLYPH_CELL
}

/** 문자열이 실제로 차지하는 폭(px). 없는 글자는 폭 0. */
export function measure(text: string, scale: number): number {
  let w = 0
  for (const ch of text) {
    if (!isRenderable(ch)) continue
    w += advanceOf(ch) * scale
  }
  return w
}

/** maxW 를 넘는 글자는 **통째로** 버린다 — 반쪽 글자를 만들지 않는다.
 *  노드 draw_utf8 의 `if (pen + w > max_w) break;` 와 같다. */
export function clip(text: string, maxW: number, scale: number): { text: string; clipped: boolean } {
  let pen = 0
  let out = ''
  for (const ch of text) {
    if (!isRenderable(ch)) continue
    const w = advanceOf(ch) * scale
    if (pen + w > maxW) return { text: out, clipped: true }
    out += ch
    pen += w
  }
  return { text: out, clipped: false }
}

/** 서버 max_bytes 검증과 같은 기준(UTF-8 바이트). */
export function utf8Bytes(text: string): number {
  return new TextEncoder().encode(text).length
}
