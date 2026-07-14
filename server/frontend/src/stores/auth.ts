import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api } from '../api'

export const useAuth = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))

  async function login(password: string) {
    const { token: t } = await api.login(password)
    token.value = t
    localStorage.setItem('token', t)
  }
  function logout() {
    token.value = null
    localStorage.removeItem('token')
  }
  return { token, login, logout }
})
