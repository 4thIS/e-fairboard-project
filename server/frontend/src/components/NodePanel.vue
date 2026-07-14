<script setup lang="ts">
import { computed } from 'vue'
import EpaperPreview from './EpaperPreview.vue'
import type { NodeInfo } from '../api'
import type { TemplateDef } from '../epaper/types'

const props = defineProps<{ node: NodeInfo; templates: TemplateDef[] }>()

const tpl = computed(() => {
  const id = props.node.display_state?.template_id
  return id == null ? null : props.templates.find(t => t.id === id) ?? null
})
const pct = computed(() => {
  const mv = props.node.batt_mv
  if (mv == null) return null
  return Math.max(0, Math.min(100, Math.round(((mv - 3000) / (4200 - 3000)) * 100)))
})
const low = computed(() => pct.value != null && pct.value < 30)
const offline = computed(() => props.node.status === 'offline')
</script>

<template>
  <div class="panel">
    <EpaperPreview
      :template="tpl"
      :fields="node.display_state?.fields ?? {}"
      :qr-url="node.display_state?.qr_url ?? ''"
      :scale="2"
    />
    <div class="meta">
      <!-- 상태는 색만으로 표현하지 않는다 — 형태 + 텍스트 동반 (스펙 §10) -->
      <span class="pix pix-16">노드 0x{{ node.id.toString(16).padStart(2, '0').toUpperCase() }}</span>
      <span :class="['badge', { bad: offline }]">
        {{ node.status === 'online' ? '●' : node.status === 'offline' ? '○' : '◌' }}
        {{ node.status === 'online' ? '온라인' : node.status === 'offline' ? '오프라인' : '확인 중' }}
      </span>
      <span :class="['pix', 'pix-16', { bad: low }]">배터리 {{ pct ?? '--' }}%</span>
      <span class="pix pix-16">RSSI {{ node.rssi ?? '--' }}</span>
    </div>
  </div>
</template>

<style scoped>
.panel { display: inline-block; }
.meta  { display: flex; gap: 16px; align-items: center; margin-top: 8px; }
.badge { font-size: 13px; }
.bad   { color: var(--epd-red); }
</style>
