import { http } from './client'
import type { TemplateDef } from '../epaper/types'

export interface Post {
  id: number; title: string; template_id: number
  fields: Record<string, string>; qr_url: string
  created_at: string; updated_at: string
}
export interface NodeInfo {
  id: number; name: string
  status: 'online' | 'offline' | 'unknown'
  batt_mv: number | null; rssi: number | null
  last_seen_at: string | null; current_post_id: number | null
  display_state?: { template_id: number | null; fields: Record<string, string>; qr_url: string | null } | null
}
export interface DeployTarget {
  node_id: number; status: 'pending' | 'sending' | 'success' | 'failed'
  attempts: number; error: string; acked_at: string | null
  step_name: string; step_index: number; step_total: number
}
export interface Deployment {
  id: number; post_id: number
  status: 'running' | 'success' | 'partial' | 'failed'
  trigger: 'manual' | 'scheduled'; refresh_mode: number
  created_at: string; finished_at: string | null; targets: DeployTarget[]
}
export interface Schedule {
  id: number; post_id: number; node_ids: number[]
  run_at: string; status: 'pending' | 'done' | 'cancelled'; created_at: string
}
export interface StatsSummary {
  deployments_total: number; targets_total: number; targets_success: number
  success_rate: number; paper_saved: number
  nodes_online: number; nodes_total: number
}
export interface StatusSample { t: string; batt_mv: number; rssi: number }

export const api = {
  login: (password: string) =>
    http.post<{ token: string }>('/auth/login', { password }).then(r => r.data),

  templates: () => http.get<TemplateDef[]>('/templates').then(r => r.data),

  posts:      () => http.get<Post[]>('/posts').then(r => r.data),
  createPost: (b: Omit<Post, 'id' | 'created_at' | 'updated_at'>) =>
    http.post<Post>('/posts', b).then(r => r.data),
  updatePost: (id: number, b: Omit<Post, 'id' | 'created_at' | 'updated_at'>) =>
    http.put<Post>(`/posts/${id}`, b).then(r => r.data),
  deletePost: (id: number) => http.delete(`/posts/${id}`).then(() => undefined),

  nodes:   () => http.get<NodeInfo[]>('/nodes').then(r => r.data),
  node:    (id: number) => http.get<NodeInfo>(`/nodes/${id}`).then(r => r.data),
  history: (id: number) => http.get<StatusSample[]>(`/nodes/${id}/history`).then(r => r.data),
  ping:    (id: number) => http.post(`/nodes/${id}/ping`).then(r => r.data),

  deploy: (post_id: number, node_ids: number[] | 'all', refresh_mode: 0 | 1) =>
    http.post<Deployment>('/deployments', { post_id, node_ids, refresh_mode }).then(r => r.data),
  deployment:  (id: number) => http.get<Deployment>(`/deployments/${id}`).then(r => r.data),
  deployments: () => http.get<Deployment[]>('/deployments').then(r => r.data),

  schedules:      () => http.get<Schedule[]>('/schedules').then(r => r.data),
  createSchedule: (post_id: number, node_ids: number[] | 'all', run_at: string) =>
    http.post<Schedule>('/schedules', { post_id, node_ids, run_at }).then(r => r.data),
  cancelSchedule: (id: number) => http.delete(`/schedules/${id}`).then(() => undefined),

  stats: () => http.get<StatsSummary>('/stats/summary').then(r => r.data),

  simConfig:    () => http.get<{ loss_rate: number; airtime_s: number }>('/sim/config').then(r => r.data),
  setSimConfig: (b: { loss_rate?: number; airtime_s?: number }) =>
    http.put('/sim/config', b).then(r => r.data),
  setPower: (id: number, powered: boolean) =>
    http.post(`/sim/nodes/${id}/power`, { powered }).then(r => r.data),
}
