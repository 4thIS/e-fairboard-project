<script setup lang="ts">
import { computed, ref, watchEffect } from 'vue'
import QRCode from 'qrcode'
import { clip } from '../epaper/text'
import { DEFAULT_CANVAS, type TemplateDef, type Color, type Fill } from '../epaper/types'

const props = withDefaults(defineProps<{
  template: TemplateDef | null
  fields: Record<string, string>
  qrUrl?: string
  boxW?: number
  boxH?: number
}>(), { qrUrl: '', boxW: 296, boxH: 128 })

/** 캔버스는 템플릿의 속성. 템플릿이 없으면 가로 빈 화면. */
const canvas = computed(() => props.template?.canvas ?? DEFAULT_CANVAS)

/** 박스(boxW×boxH) 안에 폭·높이 둘 다 넘지 않게 축소. 분수 배율 허용.
 *  가로(800×480)는 폭이, 세로(480×800)는 높이가 제약이 되어 한 공식으로 둘 다 처리(스펙 §6). */
const previewScale = computed(() =>
  Math.max(0.01, Math.min(props.boxW / canvas.value.w, props.boxH / canvas.value.h)))

/** 필드별로 노드와 같은 규칙으로 잘라낸다.
 *  clip() 은 현재 노드(고정폭) 기준으로 폭을 맞춘다 — 노드가 stb 비례폭으로 플립하고
 *  폰트 메트릭(woff2)을 번들하면 정확 일치로 후속. 지금은 근사(한글은 전각이라 정확). */
const rows = computed(() => {
  if (!props.template) return []
  return props.template.fields.map((f) => {
    const raw = props.fields[String(f.id)] ?? ''
    const { text } = clip(raw, f.avail_w, f.font_size)
    return { f, text }   // clip() 이 이미 렌더 불가 글자를 거른다
  })
})

/** 색 이름 → CSS 변수. 노드 3색과 같은 매핑 (paper=밴드 위 흰 글자). */
function inkVar(c: Color): string {
  return c === 'red' ? 'var(--red)' : c === 'paper' ? 'var(--paper)' : 'var(--ink)'
}
function fillVar(c: Fill): string {
  return c === 'red' ? 'var(--red)' : c === 'black' ? 'var(--ink)' : 'transparent'
}

/** QR — 노드와 같은 버전 선택(ECC L, 길이별). 담을 수 없으면 그리지 않는다. */
const qrCanvas = ref<HTMLCanvasElement | null>(null)
watchEffect(async () => {
  const c = qrCanvas.value
  if (!c) return
  // 안 그리는 모든 경로에서 이전 QR을 지운다 — 캔버스는 렌더 사이에 그대로 남는다.
  const clear = () => c.getContext('2d')?.clearRect(0, 0, c.width, c.height)

  if (!props.template || !props.qrUrl) { clear(); return }
  const len = new TextEncoder().encode(props.qrUrl).length
  if (len > 192) { clear(); return }            // 노드도 이 경우 안 그린다

  const version = len > 106 ? 8 : len > 53 ? 5 : 3
  const box = props.template.qr

  // 노드 draw_qr 과 같은 정수 스케일 — box.size / 모듈수 (내림). 모듈수는 버전에서
  // 역산하지 않고 라이브러리 계산값을 그대로 쓴다(버전별 모듈수를 하드코딩하지 않는다).
  const moduleCount = QRCode.create(props.qrUrl, { errorCorrectionLevel: 'L', version }).modules.size
  const scale = Math.floor(box.size / moduleCount)
  if (scale < 1) { clear(); return }            // 이 박스에 담을 수 없다 — 노드도 안 그린다

  const drawn = scale * moduleCount
  const offset = Math.floor((box.size - drawn) / 2)   // 박스 안에서 중앙 정렬 (노드와 동일)

  const style = getComputedStyle(document.documentElement)
  await QRCode.toCanvas(c, props.qrUrl, {
    errorCorrectionLevel: 'L', version, margin: 0,
    scale,
    color: {
      dark: style.getPropertyValue('--ink').trim(),
      light: style.getPropertyValue('--paper').trim(),
    },
  })
  // toCanvas 가 캔버스 크기(drawn px)는 이미 맞춰준다 — 여기선 중앙 정렬 위치만 잡는다.
  c.style.left = box.x + offset + 'px'
  c.style.top = box.y + offset + 'px'
})
</script>

<template>
  <div
    class="epd"
    :style="{ width: canvas.w * previewScale + 'px', height: canvas.h * previewScale + 'px' }"
    role="img"
    :aria-label="template
      ? `${template.name}: ` + rows.map(r => `${r.f.name} ${r.text}`).join(', ')
      : '표시 내용 없음'"
  >
    <div
      class="inner"
      :style="{ width: canvas.w + 'px', height: canvas.h + 'px',
                transform: `scale(${previewScale})` }"
    >
      <!-- 장식(밴드·박스·룰선·격자) — 텍스트 뒤에 먼저 그린다. 선=얇은 fill 사각형. -->
      <div
        v-for="(d, i) in template?.decorations ?? []" :key="'d' + i"
        class="deco"
        :style="{ left: d.x + 'px', top: d.y + 'px', width: d.w + 'px', height: d.h + 'px',
                  background: fillVar(d.fill),
                  border: d.stroke !== 'none' ? d.stroke_w + 'px solid ' + fillVar(d.stroke) : undefined }"
      ></div>

      <!-- 고정 라벨 (일시·시간·SCAN 등) -->
      <div
        v-for="(l, i) in template?.labels ?? []" :key="'l' + i"
        class="row pix"
        :style="{ left: l.x + 'px', top: l.y + 'px',
                  fontSize: l.font_size + 'px', lineHeight: l.font_size + 'px', color: inkVar(l.color) }"
      >{{ l.text }}</div>

      <!-- 편집 필드 — 나눔스퀘어 비례폭, 색은 필드별. -->
      <div
        v-for="r in rows" :key="r.f.id"
        class="row pix"
        :style="{ left: r.f.x + 'px', top: r.f.y + 'px',
                  fontSize: r.f.font_size + 'px', lineHeight: r.f.font_size + 'px', color: inkVar(r.f.color) }"
      >{{ r.text }}</div>

      <canvas
        v-if="template && qrUrl"
        ref="qrCanvas"
        class="qr"
      />
    </div>
  </div>
</template>

<style scoped>
.epd {
  background: var(--paper);
  border: 1px solid var(--ink);   /* e-Paper 패널의 테두리 */
  overflow: hidden;
}
.inner { position: relative; transform-origin: top left; }
.deco { position: absolute; box-sizing: border-box; }
.row { position: absolute; white-space: nowrap; color: var(--ink); }
.qr { position: absolute; image-rendering: pixelated; }
</style>
