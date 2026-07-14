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

export interface TemplateDef {
  id: number
  name: string
  fields: FieldDef[]
  qr: QrDef
}

export const CANVAS_W = 296
export const CANVAS_H = 128
