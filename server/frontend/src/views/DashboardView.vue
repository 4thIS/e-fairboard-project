<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useNodes } from '../stores/nodes'
import { usePosts } from '../stores/posts'
import NodePanel from '../components/NodePanel.vue'

const nodes = useNodes()
const posts = usePosts()

onMounted(async () => { await posts.load(); nodes.startPolling() })
onUnmounted(nodes.stopPolling)
</script>

<template>
  <div>
    <div class="panels">
      <NodePanel v-for="n in nodes.list" :key="n.id" :node="n" :templates="posts.templates" />
    </div>

    <hr class="rule" />

    <div class="kpi">
      <div>
        <p class="cap">종이 절감</p>
        <p><span class="pix pix-48">{{ nodes.stats?.paper_saved ?? 0 }}</span> 장</p>
      </div>
      <div>
        <p class="cap">성공률</p>
        <p><span class="pix pix-48">
          {{ ((nodes.stats?.success_rate ?? 1) * 100).toFixed(1) }}
        </span> %</p>
      </div>
      <div>
        <p class="cap">온라인 노드</p>
        <p><span class="pix pix-48">
          {{ nodes.stats?.nodes_online ?? 0 }}/{{ nodes.stats?.nodes_total ?? 0 }}
        </span></p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.panels { display: flex; gap: 32px; flex-wrap: wrap; }
.rule   { border: 0; border-top: 1px solid var(--rule); margin: 32px 0; }
.kpi    { display: flex; gap: 64px; }
.cap    { font-size: 14px; color: var(--ink-60); margin: 0 0 8px; }
.kpi p:last-child { margin: 0; }
</style>
