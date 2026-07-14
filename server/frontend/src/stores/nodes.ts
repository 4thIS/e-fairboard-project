import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, type NodeInfo, type StatsSummary } from '../api'

export const useNodes = defineStore('nodes', () => {
  const list = ref<NodeInfo[]>([])
  const stats = ref<StatsSummary | null>(null)
  let timer: number | undefined

  async function refresh() {
    const ids = (await api.nodes()).map(n => n.id)
    // display_state 는 상세에만 있다 — 미리보기가 필요하므로 상세로 받는다 (노드 2개뿐)
    list.value = await Promise.all(ids.map(api.node))
    stats.value = await api.stats()
  }
  function startPolling() {
    void refresh()
    timer = window.setInterval(refresh, 5000)   // 스펙: 노드 5초
  }
  function stopPolling() {
    if (timer) window.clearInterval(timer)
    timer = undefined
  }
  return { list, stats, refresh, startPolling, stopPolling }
})
