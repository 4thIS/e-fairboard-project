import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, type Post } from '../api'
import type { TemplateDef } from '../epaper/types'

type PostBody = Omit<Post, 'id' | 'created_at' | 'updated_at'>

export const usePosts = defineStore('posts', () => {
  const list = ref<Post[]>([])
  const templates = ref<TemplateDef[]>([])

  async function fetch() { list.value = await api.posts() }
  async function fetchTemplates() { templates.value = await api.templates() }

  const byId = computed(() => new Map(list.value.map(p => [p.id, p])))

  /** id=null 이면 생성, 아니면 수정. 저장 후 목록 갱신, 저장된 Post 반환. */
  async function save(id: number | null, body: PostBody): Promise<Post> {
    const saved = id === null ? await api.createPost(body) : await api.updatePost(id, body)
    await fetch()
    return saved
  }

  return { list, templates, byId, fetch, fetchTemplates, save }
})
