<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'

const auth = useAuth()
const router = useRouter()
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  busy.value = true
  error.value = ''
  try {
    await auth.login(password.value)
    router.push('/')
  } catch {
    error.value = '✕ 비밀번호가 올바르지 않습니다'
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <main class="wrap">
    <form class="panel" @submit.prevent="submit">
      <h1>E-FAIRBOARD</h1>
      <p class="sub">관리자 로그인</p>
      <label for="pw">비밀번호</label>
      <input id="pw" v-model="password" type="password" class="input" autofocus />
      <p v-if="error" class="err" role="alert">{{ error }}</p>
      <button class="btn btn-primary" type="submit" :disabled="busy || !password">
        {{ busy ? '확인 중…' : '로그인' }}
      </button>
    </form>
  </main>
</template>

<style scoped>
.wrap { min-height: 100vh; display: flex; align-items: center; justify-content: center; }
.panel {
  background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  padding: 32px; width: 320px; display: flex; flex-direction: column; gap: 4px;
}
h1 { font-size: 16px; letter-spacing: 3px; }
.sub { color: var(--muted); font-size: 12px; margin-bottom: 12px; }
.err { color: var(--err); font-size: 12px; margin-top: 6px; }
.btn { margin-top: 14px; }
</style>
