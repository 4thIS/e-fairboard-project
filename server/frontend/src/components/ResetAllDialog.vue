<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { api } from '../api'
import { errorMessage } from '../api/client'
import { useNodes } from '../stores/nodes'
import { usePosts } from '../stores/posts'

const emit = defineEmits<{ close: [] }>()
const nodes = useNodes()
const posts = usePosts()

const dialog = ref<HTMLDialogElement | null>(null)
onMounted(() => dialog.value?.showModal())

const busy = ref(false)
const error = ref('')
const done = ref<{ nodes: number; broadcast: boolean } | null>(null)

async function reset() {
  busy.value = true; error.value = ''
  try {
    const r = await api.resetAll()
    await nodes.fetch()
    await posts.fetch()
    done.value = { nodes: r.nodes, broadcast: r.broadcast }
  } catch (e) {
    error.value = errorMessage(e, '초기화하지 못했습니다')
  } finally { busy.value = false }
}
</script>

<template>
  <dialog ref="dialog" class="dlg" @close="emit('close')">
    <div class="head"><strong>전체 초기화</strong><button class="btn ghost" @click="emit('close')">✕</button></div>

    <template v-if="!done">
      <p class="body">
        행사가 끝났나요? <b>모든 노드</b>를 브로드캐스트로 한 번에 기본(대기) 화면으로 되돌립니다.
      </p>
      <ul class="pts">
        <li>{{ nodes.list.length }}개 노드가 <b>동시에</b> 초기화돼요</li>
        <li>각 노드의 게시 콘텐츠 연결이 해제돼요</li>
        <li>되돌릴 수 없어요 — 다시 배포하려면 새로 작성</li>
      </ul>
      <p v-if="error" class="err" role="alert">{{ error }}</p>
      <div class="foot">
        <button class="btn" @click="emit('close')">취소</button>
        <button class="btn dz" :disabled="busy" @click="reset">{{ busy ? '초기화 중…' : '전체 초기화' }}</button>
      </div>
    </template>

    <template v-else>
      <p class="body ok">✓ {{ done.nodes }}개 노드를 초기화했어요{{ done.broadcast ? ' (브로드캐스트 전송됨)' : '' }}.</p>
      <p v-if="!done.broadcast" class="hint">전송 링크가 없어 서버 상태만 초기화됐어요 — 하드웨어 연결 시 판넬도 반영돼요.</p>
      <div class="foot"><button class="btn primary" @click="emit('close')">닫기</button></div>
    </template>
  </dialog>
</template>

<style scoped>
.dlg { border: 1px solid var(--line-2); border-radius: 14px; background: var(--surface); color: var(--ink);
  padding: 22px; width: min(92vw, 420px); box-shadow: var(--shadow); }
.dlg::backdrop { background: rgba(10, 14, 20, .5); backdrop-filter: blur(2px); }
.head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px; }
.head strong { font-size: 16px; }
.body { font-size: 14px; color: var(--ink-2); line-height: 1.6; }
.body.ok { color: var(--ok); font-weight: 600; }
.pts { margin: 12px 0 4px; padding-left: 18px; display: flex; flex-direction: column; gap: 6px;
  font-size: 13px; color: var(--ink-2); }
.pts b { color: var(--ink); }
.hint { font-size: 12.5px; color: var(--muted); margin-top: 6px; }
.err { color: var(--danger); font-size: 13px; margin-top: 8px; }
.foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px; }
.btn.dz { background: var(--danger); color: #fff; border-color: var(--danger); font-weight: 600; }
.btn.dz:hover:not(:disabled) { filter: brightness(.93); }
</style>
