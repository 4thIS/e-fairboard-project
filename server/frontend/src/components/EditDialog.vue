<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import type { NodeInfo, Post } from '../api'
import { errorMessage } from '../api/client'
import { clip, wrap, utf8Bytes } from '../epaper/text'
import type { FieldDef } from '../epaper/types'
import { useDeployments } from '../stores/deployments'
import { usePosts } from '../stores/posts'
import EpaperPreview from './EpaperPreview.vue'

const props = defineProps<{ node: NodeInfo }>()
const emit = defineEmits<{ close: [] }>()

const posts = usePosts()
const deployments = useDeployments()
const dialog = ref<HTMLDialogElement | null>(null)
onMounted(() => dialog.value?.showModal())

const QR_MAX_BYTES = 198   // 백엔드 _MAX_TEXT_BYTES 와 동일 (schemas.py)

/** 편집 대상 = 이 노드의 현재 게시물(없으면 새로 등록). 노드마다 하나. */
const currentPost = props.node.current_post_id == null
  ? null : posts.byId.get(props.node.current_post_id) ?? null

const form = reactive({
  title: '',
  template_id: 0,
  fields: {} as Record<string, string>,
  qr_url: '',
})

/** 선택이 바뀌면 폼을 그 게시물(또는 빈 값)으로 채운다. */
function loadForm(p: Post | null) {
  form.title = p?.title ?? ''
  form.template_id = p?.template_id ?? posts.templates[0]?.id ?? 0
  form.fields = { ...(p?.fields ?? {}) }
  form.qr_url = p?.qr_url ?? ''
}
loadForm(currentPost)

const template = computed(() =>
  posts.templates.find(t => t.id === form.template_id) ?? null)

/** max_bytes(UTF-8) 초과 입력은 잘라서 거부 — 백엔드 422 이중 방어의 1차 (스펙 §7) */
function onFieldInput(f: FieldDef, e: Event) {
  const el = e.target as HTMLInputElement | HTMLTextAreaElement
  let v = el.value
  while (utf8Bytes(v) > f.max_bytes) v = v.slice(0, -1)
  if (v !== el.value) el.value = v
  form.fields[String(f.id)] = v
}
function onQrInput(e: Event) {
  const el = e.target as HTMLInputElement
  let v = el.value
  while (utf8Bytes(v) > QR_MAX_BYTES) v = v.slice(0, -1)
  if (v !== el.value) el.value = v
  form.qr_url = v
}

/** 픽셀 폭 초과 필드 id 집합 — 경고만, 저장 차단 없음 (스펙 §3.3) */
const clippedIds = computed(() => {
  const t = template.value
  if (!t) return new Set<number>()
  return new Set(t.fields
    .filter(f => {
      const v = form.fields[String(f.id)] ?? ''
      if (f.h) {
        const maxLines = Math.max(1, Math.floor(f.h / f.line_h))
        return wrap(v, f.avail_w, f.font_size, maxLines).clipped
      }
      return clip(v, f.avail_w, f.font_size).clipped
    })
    .map(f => f.id))
})

const refreshMode = ref<0 | 1>(0)
const busy = ref(false)
const error = ref('')

async function save() {
  const t = template.value
  if (!t) return
  busy.value = true
  error.value = ''
  try {
    // 템플릿의 모든 필드를 보낸다 — 빈 값도 전송해야 노드의 이전 텍스트가 지워진다
    const fields: Record<string, string> = {}
    for (const f of t.fields) fields[String(f.id)] = form.fields[String(f.id)] ?? ''
    const body = { title: form.title || t.name, template_id: t.id, fields, qr_url: form.qr_url }
    const saved = await posts.save(currentPost?.id ?? null, body)
    await deployments.deployToNode(saved, props.node.id, refreshMode.value)
    emit('close')
  } catch (e) {
    error.value = errorMessage(e, '인증이 만료되었습니다 — 다시 로그인하세요')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <dialog ref="dialog" class="dlg" @close="emit('close')">
    <div class="head">
      <strong>NODE 0x{{ node.id.toString(16).padStart(2, '0').toUpperCase() }} 내용 {{ currentPost ? '수정' : '등록' }}</strong>
      <button class="btn" @click="emit('close')">✕</button>
    </div>

    <div class="cols">
      <div class="form">
        <label for="title">게시물 이름</label>
        <input id="title" v-model="form.title" class="input" :placeholder="template?.name" />

        <label for="tpl">템플릿</label>
        <select id="tpl" v-model.number="form.template_id" class="input">
          <option v-for="t in posts.templates" :key="t.id" :value="t.id">{{ t.name }}</option>
        </select>

        <template v-for="f in template?.fields ?? []" :key="f.id">
          <label :for="`f${f.id}`">{{ f.name }}</label>
          <textarea
            v-if="f.h"
            :id="`f${f.id}`" class="input area" :class="{ invalid: clippedIds.has(f.id) }"
            :rows="Math.max(2, Math.floor(f.h / f.line_h))"
            :value="form.fields[String(f.id)] ?? ''" @input="onFieldInput(f, $event)"
          ></textarea>
          <input
            v-else
            :id="`f${f.id}`" class="input" :class="{ invalid: clippedIds.has(f.id) }"
            :value="form.fields[String(f.id)] ?? ''" @input="onFieldInput(f, $event)"
          />
          <p v-if="clippedIds.has(f.id)" class="warn" role="alert">⚠ 영역을 넘어 잘립니다 (폭·줄 수 초과)</p>
        </template>

        <label for="qr">QR URL</label>
        <input id="qr" :value="form.qr_url" class="input" @input="onQrInput" />
      </div>

      <div class="side">
        <label>라이브 미리보기 {{ template?.canvas ? `(${template.canvas.w}×${template.canvas.h})` : '' }}</label>
        <EpaperPreview :template="template" :fields="form.fields" :qr-url="form.qr_url" :box-w="400" :box-h="340" />
        <label>갱신 방식</label>
        <div class="radios">
          <label class="radio"><input v-model.number="refreshMode" type="radio" :value="0" /> 부분(빠름)</label>
          <label class="radio"><input v-model.number="refreshMode" type="radio" :value="1" /> 전체(잔상 제거)</label>
        </div>
      </div>
    </div>

    <p v-if="error" class="warn" role="alert">{{ error }}</p>
    <div class="foot">
      <button class="btn" :disabled="busy" @click="emit('close')">취소</button>
      <button class="btn btn-primary" :disabled="busy || !template" @click="save">
        {{ busy ? '요청 중…' : '저장하고 이 노드에 배포' }}
      </button>
    </div>
  </dialog>
</template>

<style scoped>
.dlg {
  background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  color: var(--text); padding: 16px; width: 760px; max-width: 90vw;
  /* base.css 의 * { margin: 0 } 이 native dialog 의 margin:auto 를 덮어써 좌상단에 붙는다 → 되살린다 */
  margin: auto;
}
.dlg::backdrop { background: rgba(14, 17, 22, .8); }
.head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
.cols { display: flex; gap: 16px; }
.form { flex: 1; min-width: 0; }
.side { width: 430px; flex-shrink: 0; }
.area { resize: vertical; min-height: 72px; font-family: inherit; line-height: 1.45; }
.warn { color: var(--err); font-size: 11px; margin-top: 2px; }
.radios { display: flex; gap: 12px; font-size: 12px; }
.radio { display: flex; align-items: center; gap: 4px; font-size: 12px; color: var(--text); margin: 0; }
.foot {
  display: flex; justify-content: flex-end; gap: 8px;
  border-top: 1px solid var(--border); margin-top: 14px; padding-top: 12px;
}
</style>
