<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { errorMessage } from '../api/client'
import { useNodes } from '../stores/nodes'

const emit = defineEmits<{ close: []; added: [id: number] }>()
const nodes = useNodes()

const dialog = ref<HTMLDialogElement | null>(null)
onMounted(() => dialog.value?.showModal())

const existing = new Set(nodes.list.map(n => n.id))
// 안 쓰는 가장 작은 id 를 기본값으로 제안
const suggest = (() => { let i = 1; while (existing.has(i)) i++; return i })()

const idNum = ref<number>(suggest)
const name = ref('')
const busy = ref(false)
const error = ref('')

const hex = computed(() =>
  Number.isFinite(idNum.value) ? '0x' + Math.trunc(idNum.value).toString(16).padStart(2, '0').toUpperCase() : '—')
const dupe = computed(() => existing.has(Math.trunc(idNum.value)))
const valid = computed(() => idNum.value >= 1 && idNum.value <= 254 && !dupe.value)

async function submit() {
  if (!valid.value) return
  busy.value = true; error.value = ''
  try {
    const id = Math.trunc(idNum.value)
    await nodes.addNode(id, name.value.trim())
    emit('added', id)
    emit('close')
  } catch (e) {
    error.value = errorMessage(e, '노드를 추가하지 못했습니다')
  } finally { busy.value = false }
}
</script>

<template>
  <dialog ref="dialog" class="dlg" @close="emit('close')">
    <div class="head"><strong>노드 추가</strong><button class="btn ghost" @click="emit('close')">✕</button></div>

    <label for="nid">노드 ID <span class="mono muted">(1–254 · {{ hex }})</span></label>
    <input id="nid" class="input" :class="{ invalid: !valid }" type="number" min="1" max="254"
           v-model.number="idNum" @keydown.enter="submit" />
    <p v-if="dupe" class="warn" role="alert">이미 있는 노드예요</p>

    <label for="nname">이름 <span class="muted">(선택)</span></label>
    <input id="nname" class="input" v-model="name" :placeholder="`노드 ${Math.trunc(idNum) || ''}`"
           @keydown.enter="submit" />

    <p v-if="error" class="warn" role="alert">{{ error }}</p>
    <div class="foot">
      <button class="btn" @click="emit('close')">취소</button>
      <button class="btn primary" :disabled="busy || !valid" @click="submit">{{ busy ? '추가 중…' : '추가' }}</button>
    </div>
  </dialog>
</template>

<style scoped>
.dlg { border: 1px solid var(--line-2); border-radius: 14px; background: var(--surface); color: var(--ink);
  padding: 20px; width: min(92vw, 360px); box-shadow: var(--shadow); }
.dlg::backdrop { background: rgba(10, 14, 20, .5); backdrop-filter: blur(2px); }
.head { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.head strong { font-size: 15px; }
.warn { color: var(--danger); font-size: 12px; margin-top: 5px; }
.muted { color: var(--muted); font-weight: 400; }
.foot { display: flex; justify-content: flex-end; gap: 8px; margin-top: 18px; }
</style>
