<script setup lang="ts">
import { computed, reactive, watch } from 'vue'
import EpaperPreview from './EpaperPreview.vue'
import { clip, utf8Bytes } from '../epaper/text'
import type { TemplateDef } from '../epaper/types'
import type { Post } from '../api'

const props = defineProps<{ templates: TemplateDef[]; post: Post | null }>()
const emit = defineEmits<{ save: [Omit<Post, 'id' | 'created_at' | 'updated_at'>] }>()

const form = reactive({
  title: props.post?.title ?? '',
  template_id: props.post?.template_id ?? 0,
  fields: { ...(props.post?.fields ?? {}) } as Record<string, string>,
  qr_url: props.post?.qr_url ?? '',
})

const tpl = computed(() => props.templates.find(t => t.id === form.template_id) ?? null)

// 템플릿을 바꾸면 이전 템플릿의 필드는 서버가 422로 거절한다 — 미리 비운다.
watch(() => form.template_id, () => { form.fields = {} })

/** 필드마다 두 가지를 본다: 바이트 초과(서버가 막음) / 픽셀 초과(노드가 잘라냄). */
const issues = computed(() => {
  if (!tpl.value) return {} as Record<number, string>
  const out: Record<number, string> = {}
  for (const f of tpl.value.fields) {
    const text = form.fields[String(f.id)] ?? ''
    if (!text) continue
    if (utf8Bytes(text) > f.max_bytes) {
      out[f.id] = `${f.max_bytes}바이트를 넘습니다 — 저장할 수 없습니다`
    } else if (clip(text, f.avail_w, f.font_size / 16).clipped) {
      out[f.id] = '화면에서 잘립니다'   // 저장은 되지만 노드가 잘라 그린다
    }
  }
  return out
})

const blocked = computed(() =>
  Object.values(issues.value).some(m => m.includes('저장할 수 없습니다')))
</script>

<template>
  <div class="editor">
    <div class="form">
      <el-input v-model="form.title" placeholder="게시물 제목 (관리용)" />

      <el-select v-model="form.template_id" style="width: 100%; margin-top: 8px">
        <el-option v-for="t in templates" :key="t.id" :label="t.name" :value="t.id" />
      </el-select>

      <div v-for="f in tpl?.fields ?? []" :key="f.id" class="field">
        <label>{{ f.name }}</label>
        <el-input v-model="form.fields[String(f.id)]" />
        <p v-if="issues[f.id]" class="warn">⚠ {{ issues[f.id] }}</p>
        <p v-else class="hint">
          {{ utf8Bytes(form.fields[String(f.id)] ?? '') }} / {{ f.max_bytes }}바이트
        </p>
      </div>

      <el-input v-model="form.qr_url" placeholder="QR URL (선택)" style="margin-top: 8px" />

      <el-button type="primary" :disabled="blocked" style="margin-top: 16px"
                 @click="emit('save', { ...form })">
        저장
      </el-button>
    </div>

    <div class="preview">
      <p class="cap">e-Paper 미리보기 — 노드가 실제로 그리는 것과 같습니다</p>
      <EpaperPreview :template="tpl" :fields="form.fields" :qr-url="form.qr_url" :scale="2" />
    </div>
  </div>
</template>

<style scoped>
.editor { display: grid; grid-template-columns: 360px 1fr; gap: 32px; }
.field { margin-top: 16px; }
label { display: block; font-size: 13px; color: var(--ink-60); margin-bottom: 4px; }
.hint { font-size: 12px; color: var(--ink-60); margin: 4px 0 0; }
.warn { font-size: 12px; color: var(--epd-red); margin: 4px 0 0; }  /* ⚠ + 색 + 텍스트 */
.cap  { font-size: 13px; color: var(--ink-60); margin: 0 0 8px; }
</style>
