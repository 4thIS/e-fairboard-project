<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import AppShell from '../components/AppShell.vue'
import NodeCard from '../components/NodeCard.vue'
import EditDialog from '../components/EditDialog.vue'
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

const editing = ref<NodeInfo | null>(null)
function openEdit(node: NodeInfo) { editing.value = node }
</script>

<template>
  <AppShell>
    <div class="grid">
      <NodeCard v-for="n in nodes.list" :key="n.id" :node="n" @edit="openEdit" />
    </div>
    <EditDialog v-if="editing" :node="editing" @close="editing = null" />
  </AppShell>
</template>

<style scoped>
.grid { display: flex; gap: 16px; flex-wrap: wrap; }
</style>
