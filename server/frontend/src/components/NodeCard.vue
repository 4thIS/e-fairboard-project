<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, type NodeInfo } from '../api'
import { useDeployments } from '../stores/deployments'
import { useNodes } from '../stores/nodes'
import { usePosts } from '../stores/posts'
import DeployOverlay from './DeployOverlay.vue'
import EpaperPreview from './EpaperPreview.vue'

const props = defineProps<{ node: NodeInfo }>()
defineEmits<{ edit: [node: NodeInfo] }>()

const posts = usePosts()
const nodes = useNodes()
const deployments = useDeployments()
const deploy = computed(() => deployments.byNode.get(props.node.id))
const deploying = computed(() => deploy.value?.deployment.status === 'running')
const deployFailed = computed(() => deploy.value?.deployment.status === 'failed')

const currentPost = computed(() =>
  props.node.current_post_id == null ? null : posts.byId.get(props.node.current_post_id) ?? null)
// 미리보기 소스: 실물(serial) 모드엔 시뮬레이터가 없어 display_state 가 null → 카드가 빈 화면이 된다.
// 그럴 땐 마지막으로 배포된 게시물(current_post)로 미리보기를 채운다(=노드에 있을 화면).
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
const offline = computed(() => props.node.status !== 'online')
// 실물(serial) 모드에선 노드가 아직 응답 안 해도(offline) 배포를 눌러 전송할 수 있어야 한다.
// 가상 데모에선 기존대로 offline 이면 막는다. (virtualMode===false = serial)
const canEdit = computed(() =>
  !deploying.value && (nodes.virtualMode === false || !offline.value))

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
      <!-- ponytail: 고정 박스(340×250). 카드 폭이 반응형이라 완벽 정합은 아니나 2노드 데모엔 충분.
           반응형이 필요해지면 ResizeObserver 로 실제 폭 측정. -->
      <EpaperPreview
        :template="template"
        :fields="previewSrc?.fields ?? {}"
        :qr-url="previewSrc?.qr_url ?? ''"
        :box-w="340" :box-h="250"
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
      <button class="btn btn-primary grow" :disabled="!canEdit" @click="$emit('edit', node)">
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
.screen { position: relative; display: flex; justify-content: center; align-items: flex-start; }
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
