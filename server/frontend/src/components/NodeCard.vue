<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { api, type NodeInfo } from '../api'
import { useDeployments } from '../stores/deployments'
import { usePosts } from '../stores/posts'
import DeployOverlay from './DeployOverlay.vue'
import EpaperPreview from './EpaperPreview.vue'

const props = defineProps<{ node: NodeInfo }>()
defineEmits<{ edit: [node: NodeInfo] }>()

const posts = usePosts()
const deployments = useDeployments()
const deploy = computed(() => deployments.byNode.get(props.node.id))
const deploying = computed(() => deploy.value?.deployment.status === 'running')
const deployFailed = computed(() => deploy.value?.deployment.status === 'failed')

/** 스펙 §5 — ×2 기본, 뷰포트 1280px 미만이면 ×1 (정수 배율만) */
const winW = ref(window.innerWidth)
const onResize = () => { winW.value = window.innerWidth }
onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))
const previewScale = computed(() => (winW.value < 1280 ? 1 : 2))

const template = computed(() => {
  const tid = props.node.display_state?.template_id
  return tid == null ? null : posts.templates.find(t => t.id === tid) ?? null
})
const currentPost = computed(() =>
  props.node.current_post_id == null ? null : posts.byId.get(props.node.current_post_id) ?? null)
const offline = computed(() => props.node.status !== 'online')

/* ponytail: 리튬 3.3~4.2V 선형 근사 — 실측 방전 곡선 나오면 보정 */
const battPct = computed(() => {
  const mv = props.node.batt_mv
  if (mv == null) return null
  return Math.min(100, Math.max(0, Math.round((mv - 3300) / 9)))
})
const battBar = computed(() =>
  battPct.value == null ? '' : '▮'.repeat(Math.round(battPct.value / 20)).padEnd(5, '▯'))

function timeAgo(iso: string | null): string {
  if (!iso) return '응답 기록 없음'
  const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (s < 60) return `${s}초 전`
  if (s < 3600) return `${Math.floor(s / 60)}분 전`
  return `${Math.floor(s / 3600)}시간 전`
}

const pinging = ref(false)
async function ping() {
  pinging.value = true
  try { await api.ping(props.node.id) } finally { pinging.value = false }
}
</script>

<template>
  <article class="card" :class="{ offline: offline && !deploying, busy: deploying }">
    <div class="screen" :class="{ dim: offline && !deploy }">
      <EpaperPreview
        :template="template"
        :fields="node.display_state?.fields ?? {}"
        :qr-url="node.display_state?.qr_url ?? ''"
        :scale="previewScale"
      />
      <span v-if="offline && !deploy" class="dim-label">마지막 커밋 화면</span>
      <DeployOverlay
        v-if="deploy" :nd="deploy"
        @retry="deployments.retry(node.id)"
        @dismiss="deployments.dismiss(node.id)"
      />
    </div>

    <div class="head">
      <span class="name">NODE 0x{{ node.id.toString(16).padStart(2, '0').toUpperCase() }} · {{ node.name }}</span>
      <span v-if="deploying" class="busy">◈ 배포 중</span>
      <span v-else-if="deployFailed" class="err">✕ 실패</span>
      <span v-else-if="!offline" class="ok">● ONLINE</span>
      <span v-else class="err">○ OFFLINE</span>
    </div>

    <p class="tele" :class="{ err: offline }">
      <template v-if="battPct != null">BATT {{ ((node.batt_mv ?? 0) / 1000).toFixed(1) }}V {{ battBar }} {{ battPct }}% · </template>
      <template v-if="node.rssi != null">RSSI {{ node.rssi }}dBm · </template>
      {{ offline ? '마지막 응답 ' : '' }}{{ timeAgo(node.last_seen_at) }}
    </p>
    <p class="post muted">
      게시물: {{ currentPost ? `${currentPost.title} #${currentPost.id}` : '없음' }}
    </p>

    <div class="actions">
      <button class="btn btn-primary grow" :disabled="offline || deploying" @click="$emit('edit', node)">
        {{ currentPost ? '내용 수정' : '내용 등록' }}
      </button>
      <button class="btn" :disabled="pinging" @click="ping">PING</button>
      <button class="btn" disabled title="다음 설계에서 구현">이력</button>
    </div>
  </article>
</template>

<style scoped>
.card {
  background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  padding: 14px; flex: 1; min-width: 0;
}
.card.offline { border-color: var(--err); }
.card.busy { border-color: var(--busy); }
.busy { color: var(--busy); }
.screen { position: relative; display: flex; justify-content: center; }
.screen :deep(.epd) { box-shadow: 0 0 16px rgba(255, 255, 255, .12); }
.screen.dim :deep(.epd) { filter: brightness(.45) grayscale(.3); }
.dim-label { position: absolute; top: 6px; right: 6px; font-size: 10px; color: var(--err); }
.head { display: flex; justify-content: space-between; margin-top: 10px; font-size: 13px; }
.ok { color: var(--ok); }
.err { color: var(--err); }
.muted { color: var(--muted); }
.tele { font-size: 12px; color: var(--muted); margin-top: 4px; }
.tele.err { color: var(--err); }
.post { font-size: 12px; margin-top: 2px; }
.actions { display: flex; gap: 8px; margin-top: 10px; }
.grow { flex: 1; }
</style>
