<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '../stores/auth'

const password = ref('')
const error = ref('')
const auth = useAuth()
const router = useRouter()

async function submit() {
  error.value = ''
  try {
    await auth.login(password.value)
    router.push('/')
  } catch {
    error.value = '비밀번호가 틀렸습니다'
  }
}
</script>

<template>
  <div class="wrap">
    <div class="box">
      <div class="pix pix-32">E-FairBoard</div>
      <p class="sub">LoRa e-Paper 게시판 관리</p>
      <el-input v-model="password" type="password" placeholder="관리자 비밀번호"
                @keyup.enter="submit" />
      <el-button type="primary" style="width: 100%; margin-top: 16px" @click="submit">
        로그인
      </el-button>
      <p v-if="error" class="err">✕ {{ error }}</p>
    </div>
  </div>
</template>

<style scoped>
.wrap { min-height: 100vh; display: grid; place-items: center; }
.box { width: 320px; padding: 32px; background: var(--paper); border: 1px solid var(--rule); }
.sub { color: var(--ink-60); margin: 8px 0 24px; }
.err { color: var(--epd-red); margin-top: 16px; }   /* 형태(✕)+색+텍스트 — 스펙 §10 */
</style>
