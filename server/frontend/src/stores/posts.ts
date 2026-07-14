import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, type Post } from '../api'
import type { TemplateDef } from '../epaper/types'

export const usePosts = defineStore('posts', () => {
  const list = ref<Post[]>([])
  const templates = ref<TemplateDef[]>([])

  async function load() {
    if (!templates.value.length) templates.value = await api.templates()
    list.value = await api.posts()
  }
  async function save(body: Omit<Post, 'id' | 'created_at' | 'updated_at'>, id?: number) {
    if (id === undefined) await api.createPost(body)
    else await api.updatePost(id, body)
    await load()
  }
  async function remove(id: number) {
    await api.deletePost(id)
    await load()
  }
  const templateById = (id: number) => templates.value.find(t => t.id === id) ?? null

  return { list, templates, load, save, remove, templateById }
})
