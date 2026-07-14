<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import AppShell from '../components/AppShell.vue'
import NodeCard from '../components/NodeCard.vue'
import { useNodes } from '../stores/nodes'
import { usePosts } from '../stores/posts'
import type { NodeInfo } from '../api'

const nodes = useNodes()
const posts = usePosts()

onMounted(() => {
  nodes.startPolling(5000)      // 스펙 §5
  nodes.detectMode()
  posts.fetch()
  posts.fetchTemplates()
})
onUnmounted(() => nodes.stopPolling())

function openEdit(_node: NodeInfo) {
  // Task 6 에서 EditDialog 연결
}
</script>

<template>
  <AppShell>
    <div class="grid">
      <NodeCard v-for="n in nodes.list" :key="n.id" :node="n" @edit="openEdit" />
    </div>
  </AppShell>
</template>

<style scoped>
.grid { display: flex; gap: 16px; flex-wrap: wrap; }
</style>
