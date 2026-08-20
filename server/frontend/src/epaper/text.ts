/** 노드 렌더러(node_core BakedFont)와 **같은 규칙**.
 *
 * 미리보기가 노드와 다르게 그리면 시연의 주인공이 거짓말을 한다.
 *
 * 비례폭(나눔스퀘어) — 글자별 advance 는 `font_advance.json`(tools/gen_font_advance.py 산출).
 * 노드 gen_font.py 가 bin 에 넣는 값과 **같은 파일**을 여기서 import 한다 (단일 기준).
 * baked 크기(40/56/72)만 테이블에 있다. 테이블에 없는 글자는 노드에도 없으니 자리도 안 준다.
 */

import advanceData from './font_advance.json'

const SIZES: number[] = advanceData.sizes
const ADV = advanceData.adv as Record<string, number[]>

/** 노드 폰트에 있는 글자인가. ASCII + baked 한글(font_advance 테이블 = 자주쓰는 2,000자). */
export function isRenderable(ch: string): boolean {
  const cp = ch.codePointAt(0)
  if (cp === undefined) return false
  if (cp >= 0x20 && cp <= 0x7e) return true
  return String(cp) in ADV
}

/** 글자 하나의 전진 폭(px). 비례폭 — baked advance 테이블에서. fontPx 는 40/56/72.
 *  테이블에 없는 크기/글자는 전각(fontPx) 보수적 폴백. */
export function advancePx(ch: string, fontPx: number): number {
  const i = SIZES.indexOf(fontPx)
  const cp = ch.codePointAt(0)
  if (i < 0 || cp === undefined) return fontPx
  const a = ADV[String(cp)]
  return a ? a[i] : fontPx
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
