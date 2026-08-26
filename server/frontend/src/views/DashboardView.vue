<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import AppShell from '../components/AppShell.vue'
import NodeDetail from '../components/NodeDetail.vue'
import EditDialog from '../components/EditDialog.vue'
import AddNodeDialog from '../components/AddNodeDialog.vue'
import { useNodes } from '../stores/nodes'
import { usePosts } from '../stores/posts'
import { useDeployments } from '../stores/deployments'
import type { NodeInfo } from '../api'

const nodes = useNodes()
const posts = usePosts()
const deployments = useDeployments()

onMounted(() => {
  nodes.startPolling(5000)
  nodes.detectMode()
  posts.fetch()
  posts.fetchTemplates()
})
onUnmounted(() => nodes.stopPolling())

const selectedId = ref<number | null>(null)
const search = ref('')
const editing = ref<NodeInfo | null>(null)
const showAdd = ref(false)

const hexOf = (id: number) => '0x' + id.toString(16).padStart(2, '0').toUpperCase()

const filtered = computed(() => {
  const q = search.value.trim().toLowerCase()
  const rows = [...nodes.list].sort((a, b) => a.id - b.id)
  if (!q) return rows
  return rows.filter(n => hexOf(n.id).toLowerCase().includes(q) || n.name.toLowerCase().includes(q))
})
const selectedNode = computed(() => nodes.list.find(n => n.id === selectedId.value) ?? null)

// 목록이 로드/변경되면 선택이 유효하도록 — 없으면 첫 노드
watch(() => nodes.list.map(n => n.id).join(','), () => {
  if (selectedId.value == null || !nodes.list.some(n => n.id === selectedId.value))
    selectedId.value = filtered.value[0]?.id ?? null
}, { immediate: true })

function dotColor(n: NodeInfo): string {
  if (deployments.byNode.get(n.id)?.deployment.status === 'running') return 'var(--info)'
  return n.status === 'online' ? 'var(--ok)' : 'var(--warn)'
}
function timeAgo(iso: string | null): string {
  if (!iso) return '기록 없음'
  const s = Math.max(0, Math.floor((Date.now() - new Date(iso).getTime()) / 1000))
  if (s < 60) return `${s}초 전`
  if (s < 3600) return `${Math.floor(s / 60)}분 전`
  return `${Math.floor(s / 3600)}시간 전`
}

async function removeNode(n: NodeInfo) {
  if (!window.confirm(`노드 ${hexOf(n.id)} (${n.name}) 을 삭제할까요?`)) return
  await nodes.removeNode(n.id)
  if (selectedId.value === n.id) selectedId.value = filtered.value[0]?.id ?? null
}
</script>

<template>
  <AppShell>
    <div class="console">
      <aside class="list">
        <div class="search">
          <input class="input" v-model="search" placeholder="노드 검색…" aria-label="노드 검색" />
        </div>
        <div class="rows">
          <button
            v-for="n in filtered" :key="n.id"
            class="li" :class="{ sel: n.id === selectedId }" @click="selectedId = n.id"
          >
            <span class="dot" :style="{ background: dotColor(n) }"></span>
            <span class="id mono">{{ hexOf(n.id) }}</span>
            <span class="nm">{{ n.name }}</span>
            <span class="sub mono">{{ timeAgo(n.last_seen_at) }}</span>
          </button>
          <p v-if="!filtered.length" class="none">{{ search ? '검색 결과 없음' : '노드가 없어요' }}</p>
        </div>
        <button class="addrow" @click="showAdd = true"><span class="plus">+</span> 노드 추가</button>
      </aside>

      <section class="pane">
        <NodeDetail v-if="selectedNode" :key="selectedNode.id" :node="selectedNode"
                    @edit="editing = $event" @remove="removeNode" />
        <div v-else class="empty">
          <p>표시할 노드가 없어요.</p>
          <button class="btn primary" @click="showAdd = true">+ 노드 추가</button>
        </div>
      </section>
    </div>

    <EditDialog v-if="editing" :node="editing" @close="editing = null" />
    <AddNodeDialog v-if="showAdd" @close="showAdd = false" @added="selectedId = $event" />
  </AppShell>
</template>

<style scoped>
.console {
  display: grid; grid-template-columns: 264px 1fr; gap: 16px;
  align-items: start;
}
@media (max-width: 680px) { .console { grid-template-columns: 1fr; } }

.list {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  overflow: hidden; box-shadow: var(--shadow); display: flex; flex-direction: column;
}
.search { padding: 11px; border-bottom: 1px solid var(--line); }
.rows { display: flex; flex-direction: column; }
.li {
  display: flex; align-items: center; gap: 9px; padding: 11px 13px; font: inherit; font-size: 13px;
  background: transparent; border: 0; border-bottom: 1px solid var(--line); cursor: pointer;
  text-align: left; color: var(--ink); width: 100%;
}
.li:hover { background: var(--surface-2); }
.li.sel { background: var(--surface-2); box-shadow: inset 3px 0 0 var(--accent); }
.li .dot { width: 8px; height: 8px; border-radius: 50%; flex: none; }
.li .id { font-weight: 600; }
.li .nm { color: var(--ink-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.li .sub { color: var(--muted); font-size: 11px; margin-left: auto; flex: none; }
.none { padding: 18px 13px; color: var(--muted); font-size: 13px; text-align: center; }
.addrow {
  padding: 12px 13px; font: inherit; font-size: 13px; font-weight: 600; color: var(--accent);
  background: transparent; border: 0; border-top: 1px solid var(--line); cursor: pointer; text-align: left;
  display: flex; align-items: center; gap: 6px;
}
.addrow:hover { background: var(--surface-2); }
.addrow .plus { font-size: 16px; line-height: 1; }

.pane {
  background: var(--surface); border: 1px solid var(--line); border-radius: var(--radius);
  min-height: 340px; box-shadow: var(--shadow);
}
.empty { display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 14px; min-height: 340px; color: var(--muted); }
</style>
