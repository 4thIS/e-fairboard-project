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
export const DEFAULT_CANVAS: Canvas = { w: 800, h: 480 }
