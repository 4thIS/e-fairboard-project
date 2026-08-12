<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'
import { useNodes } from '../stores/nodes'

const nodes = useNodes()
const auth = useAuth()
const router = useRouter()

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="shell">
    <header>
      <h1>E-FAIRBOARD</h1>
      <div class="status">
        <span v-if="nodes.connected" class="ok">● 서버 연결됨</span>
        <span v-else class="err">○ 서버 응답 없음</span>
        <span v-if="nodes.virtualMode" class="badge">가상 모드</span>
        <span class="muted">온라인 {{ nodes.onlineCount }}/{{ nodes.list.length }}</span>
        <router-link class="btn" to="/setup/radio">무선 설정</router-link>
        <button class="btn" @click="logout">로그아웃</button>
      </div>
    </header>
    <main><slot /></main>
  </div>
</template>

<style scoped>
.shell { max-width: 1280px; margin: 0 auto; padding: 20px 24px; }
header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
h1 { font-size: 16px; letter-spacing: 3px; }
.status { display: flex; align-items: center; gap: 12px; font-size: 12px; }
.ok { color: var(--ok); }
.err { color: var(--err); }
.muted { color: var(--muted); }
.badge {
  background: var(--panel); border: 1px solid var(--border); border-radius: 4px;
  color: var(--busy); padding: 1px 6px; font-size: 11px;
}
a.btn { text-decoration: none; }
</style>
