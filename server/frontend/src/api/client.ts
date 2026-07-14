import axios, { AxiosError } from 'axios'

export const http = axios.create({ baseURL: '/api' })

/** 실패 원인을 사람 말로. 서버가 꺼진 것과 입력이 틀린 것은 다른 문제다 —
 *  구분하지 않으면 "비밀번호가 틀렸다"며 멀쩡한 비밀번호를 다시 치게 만든다. */
export function errorMessage(err: unknown, on401: string): string {
  const status = err instanceof AxiosError ? err.response?.status : undefined
  if (status === 401) return `✕ ${on401}`
  if (status === 422) return '✕ 입력값이 서버 검증에 걸렸습니다'
  if (status === undefined) return '✕ 서버에 연결할 수 없습니다 — 백엔드가 떠 있는지 확인하세요'
  return `✕ 서버 오류 (${status})`
}

http.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

http.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      if (location.pathname !== '/login') location.href = '/login'
    }
    return Promise.reject(err)
  },
)
