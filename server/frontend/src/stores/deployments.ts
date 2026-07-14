import { defineStore } from 'pinia'
import { reactive } from 'vue'
import { api, type Deployment, type Post } from '../api'
import { useNodes } from './nodes'

export interface NodeDeploy {
  deployment: Deployment
  post: Post          // 진행 오버레이의 단계 목록 렌더용 — 방금 배포한 게시물
}

export const useDeployments = defineStore('deployments', () => {
  /** 노드별 진행/실패 상태. 성공하면 지워지고, 실패는 dismiss/retry 까지 남는다. */
  const byNode = reactive(new Map<number, NodeDeploy>())

  async function deployToNode(post: Post, nodeId: number, refreshMode: 0 | 1) {
    const dep = await api.deploy(post.id, [nodeId], refreshMode)
    byNode.set(nodeId, { deployment: dep, post })
    poll(dep.id, nodeId)
  }

  function poll(depId: number, nodeId: number) {
    const timer = window.setInterval(async () => {
      let dep: Deployment
      try {
        dep = await api.deployment(depId)
      } catch {
        return             // 일시 오류 — 다음 틱에 재시도
      }
      const cur = byNode.get(nodeId)
      if (cur) cur.deployment = dep
      if (dep.status !== 'running') {
        clearInterval(timer)
        await useNodes().fetch()            // 미리보기 즉시 교체 (스펙 §6.2)
        if (dep.status === 'success') byNode.delete(nodeId)
        // 단일 노드 배포라 partial 은 없다 — failed 만 카드에 남는다
      }
    }, 1000)
  }

  async function retry(nodeId: number) {
    const cur = byNode.get(nodeId)
    if (!cur) return
    await deployToNode(cur.post, nodeId, cur.deployment.refresh_mode as 0 | 1)
  }

  function dismiss(nodeId: number) { byNode.delete(nodeId) }

  return { byNode, deployToNode, retry, dismiss }
})
