/** 노드 렌더러(node_core BakedFont)와 **같은 규칙**.
 *
 * 미리보기가 노드와 다르게 그리면 시연의 주인공이 거짓말을 한다.
 * 이 파일을 고칠 때는 노드 폰트 규칙(gen_font.py / BakedFont)을 먼저 읽을 것.
 *
 * baked 폰트는 **고정폭**: 한글 = 전각(advance = font_px), ASCII = 반각(advance = font_px/2).
 * 폰트에 없는 글자는 그리지도, 자리를 주지도 않는다. font_px 는 실제 px(40/56/72).
 */

/** 폰트에 있는 글자인가. ASCII(0x20~0x7E) + 완성형 한글(U+AC00~U+D7A3).
 *  (노드가 굽는 자주쓰는 2,000자 밖은 서버 입력검증이 막는다 — 그 플립 전까진 완성형 범위로 둔다.) */
export function isRenderable(ch: string): boolean {
  const cp = ch.codePointAt(0)
  if (cp === undefined) return false
  return (cp >= 0x20 && cp <= 0x7e) || (cp >= 0xac00 && cp <= 0xd7a3)
}

/** 글자 하나의 전진 폭(px). ASCII 반각(font_px/2), 한글 전각(font_px). */
export function advancePx(ch: string, fontPx: number): number {
  const cp = ch.codePointAt(0)
  const ascii = cp !== undefined && cp >= 0x20 && cp <= 0x7e
  return ascii ? Math.floor(fontPx / 2) : fontPx
}

/** 문자열이 실제로 차지하는 폭(px). 없는 글자는 폭 0. */
export function measure(text: string, fontPx: number): number {
  let w = 0
  for (const ch of text) {
    if (!isRenderable(ch)) continue
    w += advancePx(ch, fontPx)
  }
  return w
}

/** maxW 를 넘는 글자는 **통째로** 버린다 — 반쪽 글자를 만들지 않는다.
 *  노드 draw_utf8 의 `if (pen + w > max_w) break;` 와 같다. */
export function clip(text: string, maxW: number, fontPx: number): { text: string; clipped: boolean } {
  let pen = 0
  let out = ''
  for (const ch of text) {
    if (!isRenderable(ch)) continue
    const w = advancePx(ch, fontPx)
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
