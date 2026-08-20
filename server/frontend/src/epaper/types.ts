/** GET /api/templates 응답. avail_w·max_bytes 는 서버가 계산해 준다 (스펙 §6.2). */
export type Color = 'black' | 'red' | 'paper'
export type Fill = 'none' | 'black' | 'red'

export interface FieldDef {
  id: number
  name: string
  x: number
  y: number
  font_size: number   // 40/56/72
  color: Color
  w: number           // 명시 폭(0=자동)
  max_bytes: number
  avail_w: number     // 이 행이 쓸 수 있는 가로 폭 — 공식을 프론트에 재구현하지 말 것
}

/** 고정 텍스트 라벨 (비편집). */
export interface Label {
  x: number
  y: number
  font_size: number
  color: Color
  text: string
}

/** 장식 사각형 — 채움/테두리. 선은 얇은 fill 사각형. */
export interface Deco {
  x: number
  y: number
  w: number
  h: number
  fill: Fill
  stroke: Fill
  stroke_w: number
}

export interface QrDef { x: number; y: number; size: number }

export interface Canvas { w: number; h: number }

export interface TemplateDef {
  id: number
  name: string
  fields: FieldDef[]
  qr: QrDef
  decorations: Deco[]
  labels: Label[]
  canvas: Canvas      // 가로 1304×984 / 세로 984×1304 — 템플릿의 속성
}

/** 표시할 템플릿이 없을 때(미배포 노드) 그리는 빈 화면의 크기. */
export const DEFAULT_CANVAS: Canvas = { w: 1304, h: 984 }
