<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, type NodeInfo } from '../api'
import { useDeployments } from '../stores/deployments'
import { useNodes } from '../stores/nodes'
import { usePosts } from '../stores/posts'
import DeployOverlay from './DeployOverlay.vue'
import EpaperPreview from './EpaperPreview.vue'

const props = defineProps<{ node: NodeInfo }>()
const emit = defineEmits<{ edit: [node: NodeInfo]; remove: [node: NodeInfo] }>()

const posts = usePosts()
const nodes = useNodes()
const deployments = useDeployments()

const deploy = computed(() => deployments.byNode.get(props.node.id))
const deploying = computed(() => deploy.value?.deployment.status === 'running')
const deployFailed = computed(() => deploy.value?.deployment.status === 'failed')
const offline = computed(() => props.node.status !== 'online')

const currentPost = computed(() =>
  props.node.current_post_id == null ? null : posts.byId.get(props.node.current_post_id) ?? null)
const previewSrc = computed(() => {
  const ds = props.node.display_state
  if (ds && ds.template_id != null)
    return { template_id: ds.template_id, fields: ds.fields, qr_url: ds.qr_url ?? '' }
  const p = currentPost.value
  return p ? { template_id: p.template_id, fields: p.fields, qr_url: p.qr_url } : null
})
const template = computed(() => {
  const tid = previewSrc.value?.template_id
  return tid == null ? null : posts.templates.find(t => t.id === tid) ?? null
})
const canEdit = computed(() =>
  !deploying.value && (nodes.virtualMode === false || !offline.value))

const statusPill = computed(() => {
  if (deploying.value) return { cls: 'info', label: '배포 중' }
  if (deployFailed.value) return { cls: 'err', label: '배포 실패' }
  if (!offline.value) return { cls: 'ok', label: '응답 성공' }
  return { cls: 'warn', label: '응답없음' }
})

const battPct = computed(() => {
  const mv = props.node.batt_mv
  return mv == null ? null : Math.min(100, Math.max(0, Math.round((mv - 3300) / 9)))
})
const battColor = computed(() =>
  battPct.value == null ? 'var(--muted)' : battPct.value < 20 ? 'var(--danger)' : battPct.value < 45 ? 'var(--warn)' : 'var(--ok)')

function timeAgo(iso: string | null): string {
  if (!iso) return '응답 기록 없음'
  const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (s < 60) return `${s}초 전`
  if (s < 3600) return `${Math.floor(s / 60)}분 전`
  return `${Math.floor(s / 3600)}시간 전`
}
const hex = computed(() => '0x' + props.node.id.toString(16).padStart(2, '0').toUpperCase())

const pinging = ref(false)
async function ping() {
  pinging.value = true
  try { await api.ping(props.node.id) } finally { pinging.value = false }
}
</script>

<template>
  <div class="detail">
    <div class="screen" :class="{ dim: offline && !deploy }">
      <EpaperPreview
        :template="template" :fields="previewSrc?.fields ?? {}"
        :qr-url="previewSrc?.qr_url ?? ''" :box-w="300" :box-h="300"
      />
      <DeployOverlay
        v-if="deploy" :nd="deploy"
        @retry="deployments.retry(node.id)" @dismiss="deployments.dismiss(node.id)"
      />
    </div>

    <div class="info">
      <div class="titlerow">
        <div>
          <span class="id mono">{{ hex }}</span>
          <span class="nm">{{ node.name }}</span>
        </div>
        <span class="pill" :class="statusPill.cls"><span class="dot"></span>{{ statusPill.label }}</span>
      </div>

      <div class="stats">
        <div class="stat">
          <span class="lab">배터리</span>
          <span class="batt"><span class="track"><span class="fill" :style="{ width: (battPct ?? 0) + '%', background: battColor }"></span></span>{{ battPct == null ? '—' : battPct + '%' }}</span>
        </div>
        <div class="stat">
          <span class="lab">RSSI</span>
          <span class="v mono">{{ node.rssi == null ? '—' : node.rssi + ' dBm' }}</span>
        </div>
        <div class="stat">
          <span class="lab">마지막 응답</span>
          <span class="v" :class="{ warn: offline }">{{ timeAgo(node.last_seen_at) }}</span>
        </div>
        <div class="stat wide">
          <span class="lab">현재 콘텐츠</span>
          <span class="v">{{ currentPost ? currentPost.title : '없음' }}</span>
        </div>
      </div>

      <div class="actions">
        <button class="btn primary" :disabled="!canEdit" @click="emit('edit', node)">
          {{ currentPost ? '내용 수정 · 배포' : '내용 등록 · 배포' }}
        </button>
        <button class="btn" :disabled="pinging" @click="ping">{{ pinging ? 'PING…' : 'PING' }}</button>
        <button class="btn" disabled title="다음 설계에서">이력</button>
        <button class="btn danger" @click="emit('remove', node)">노드 삭제</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.detail { display: grid; grid-template-columns: minmax(160px, 260px) 1fr; gap: 24px; padding: 22px; align-items: start; }
@media (max-width: 620px) { .detail { grid-template-columns: 1fr; } }
.screen { position: relative; display: flex; justify-content: center; }
.screen.dim :deep(.epd) { filter: brightness(.9) grayscale(.15); opacity: .8; }
.info { display: flex; flex-direction: column; gap: 18px; min-width: 0; }
.titlerow { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.id { font-weight: 600; font-size: 20px; }
.nm { color: var(--muted); margin-left: 10px; font-size: 14px; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.stat { background: var(--surface-2); border: 1px solid var(--line); border-radius: 9px; padding: 10px 12px; display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.stat.wide { grid-column: 1 / -1; }
.stat .v { font-weight: 600; font-size: 15px; }
.stat .v.warn { color: var(--warn); }
.stat .v.mono { font-size: 14px; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; }
.actions .danger { margin-left: auto; }
</style>
