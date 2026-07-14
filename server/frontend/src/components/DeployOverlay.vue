<script setup lang="ts">
import { computed } from 'vue'
import type { NodeDeploy } from '../stores/deployments'

const props = defineProps<{ nd: NodeDeploy }>()
defineEmits<{ retry: [], dismiss: [] }>()

const target = computed(() => props.nd.deployment.targets[0])
const failed = computed(() => props.nd.deployment.status === 'failed')

/** 단계 목록 — build_packet_plan 과 같은 순서 (deploy_service.py §4) */
const steps = computed(() => {
  const p = props.nd.post
  const n = Object.keys(p.fields).length
  const s = ['SET_TEMPLATE']
  for (let i = 1; i <= n; i++) s.push(`SET_FIELD ${i}/${n}`)
  if (p.qr_url) s.push('SET_QR')
  s.push('COMMIT')
  return s
})
const cur = computed(() => target.value.step_index)   // 1-base, 0=시작 전
const pct = computed(() =>
  target.value.step_total ? Math.round((cur.value / target.value.step_total) * 100) : 0)
</script>

<template>
  <div class="overlay" role="status">
    <template v-if="!failed">
      <p v-for="(s, i) in steps" :key="s"
         :class="i + 1 < cur ? 'done' : i + 1 === cur ? 'now' : 'todo'">
        {{ i + 1 < cur ? '✓' : i + 1 === cur ? '▶' : '·' }} {{ s }}
      </p>
    </template>
    <template v-else>
      <p class="fail">✕ 실패 — {{ target.step_name }} {{ target.step_index }}/{{ target.step_total }}에서 중단</p>
      <p class="reason">{{ target.error }}</p>
      <div class="acts">
        <button class="btn" @click="$emit('dismiss')">닫기</button>
        <button class="btn btn-primary" @click="$emit('retry')">재시도</button>
      </div>
    </template>
  </div>
  <div v-if="!failed" class="bar"><div class="fill" :style="{ width: pct + '%' }" /></div>
</template>

<style scoped>
.overlay {
  position: absolute; inset: 0; background: rgba(14, 17, 22, .85);
  display: flex; flex-direction: column; justify-content: center;
  padding: 12px; font-size: 12px; gap: 2px;
}
.done { color: var(--ok); }
.now { color: var(--busy); }
.todo { color: var(--muted); }
.fail { color: var(--err); font-weight: 600; }
.reason { color: var(--muted); font-size: 11px; word-break: break-all; }
.acts { display: flex; gap: 8px; margin-top: 8px; }
.bar { background: var(--border); border-radius: 3px; height: 6px; margin-top: 8px; overflow: hidden; }
.fill { background: var(--busy); height: 100%; transition: width .3s; }
</style>
