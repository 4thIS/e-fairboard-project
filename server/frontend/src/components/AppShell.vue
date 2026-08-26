<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'
import { useNodes } from '../stores/nodes'
import ResetAllDialog from './ResetAllDialog.vue'

const nodes = useNodes()
const auth = useAuth()
const router = useRouter()
const showReset = ref(false)

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="shell">
    <header>
      <div class="brand">
        <span class="mark">◨</span>
        <span class="wordmark">E-FairBoard</span>
      </div>
      <div class="status">
        <span class="conn" :class="nodes.connected ? 'ok' : 'err'">
          <span class="dot"></span>{{ nodes.connected ? '서버 연결됨' : '서버 응답 없음' }}
        </span>
        <span v-if="nodes.virtualMode" class="badge">가상 모드</span>
        <span class="count mono">응답 {{ nodes.onlineCount }} / {{ nodes.list.length }}</span>
        <span class="sep"></span>
        <button class="btn sm reset" @click="showReset = true" title="행사 종료 — 전 노드 초기화">전체 초기화</button>
        <router-link class="btn sm" to="/setup/radio">무선 설정</router-link>
        <button class="btn sm" @click="logout">로그아웃</button>
      </div>
    </header>
    <main><slot /></main>
    <ResetAllDialog v-if="showReset" @close="showReset = false" />
  </div>
</template>

<style scoped>
.shell { max-width: 1200px; margin: 0 auto; padding: 20px clamp(14px, 3vw, 28px) 60px; }
header {
  display: flex; justify-content: space-between; align-items: center;
  gap: 16px; flex-wrap: wrap; margin-bottom: 22px;
  padding-bottom: 16px; border-bottom: 1px solid var(--line-2);
}
.brand { display: flex; align-items: center; gap: 10px; }
.mark { color: var(--accent); font-size: 20px; line-height: 1; }
.wordmark { font-weight: 700; font-size: 17px; letter-spacing: -.01em; }
.status { display: flex; align-items: center; gap: 12px; font-size: 12.5px; flex-wrap: wrap; }
.conn { display: inline-flex; align-items: center; gap: 6px; font-weight: 600; }
.conn .dot { width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.conn.ok { color: var(--ok); }
.conn.err { color: var(--danger); }
.count { color: var(--muted); }
.badge {
  background: var(--tint-info); color: var(--info); border-radius: 5px;
  padding: 2px 8px; font-size: 11px; font-weight: 600;
}
a.btn { text-decoration: none; }
.sep { width: 1px; height: 16px; background: var(--line-2); margin: 0 2px; }
.reset { color: var(--danger); }
.reset:hover:not(:disabled) { border-color: var(--danger); color: var(--danger); background: var(--tint-danger); }
</style>
