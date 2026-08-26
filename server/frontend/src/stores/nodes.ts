import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, type NodeInfo } from '../api'

export const useNodes = defineStore('nodes', () => {
  const list = ref<NodeInfo[]>([])
  const connected = ref(true)              // 마지막 fetch 성공 여부 — 상단 바 표시
  const virtualMode = ref<boolean | null>(null)   // null = 아직 모름
  let timer: number | undefined

  async function fetch() {
    try {
      list.value = await api.nodes()
      connected.value = true
    } catch {
      connected.value = false               // 401은 인터셉터가 로그인으로 보낸다
    }
  }

  /** GET /api/sim/config 200 → 가상 모드, 409 → 시리얼 모드 (routers/sim.py) */
  async function detectMode() {
    try {
      await api.simConfig()
      virtualMode.value = true
    } catch {
      virtualMode.value = false
    }
  }

  function startPolling(ms = 5000) {
    stopPolling()
    fetch()
    timer = window.setInterval(fetch, ms)
  }
  function stopPolling() {
    if (timer !== undefined) { clearInterval(timer); timer = undefined }
  }

  const onlineCount = computed(() => list.value.filter(n => n.status === 'online').length)

  async function addNode(id: number, name: string) {
    const node = await api.createNode(id, name)
    await fetch()
    return node
  }
  async function removeNode(id: number) {
    await api.deleteNode(id)
    await fetch()
  }

  return { list, connected, virtualMode, onlineCount, fetch, detectMode,
           startPolling, stopPolling, addNode, removeNode }
})
