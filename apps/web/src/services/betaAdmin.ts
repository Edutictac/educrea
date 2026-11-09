import { apiError } from '../i18n/apiErrors'
export interface BetaRequest { user_id: string; email: string; teaching_context: string; intended_use: string; requested_at: string }
export interface BetaGuest { user_id: string; email: string; access_status: 'invited' | 'revoked' }
export interface BetaInvitation { id: string; email: string; state: string; expires_at: string; sent_at: string | null }
export interface ImageLimits { weekly_limit: number; global_daily_limit: number; weekly_custom: number | null;
  global_daily_custom: number | null; enabled: boolean }
export interface VideoLimits { daily_limit: number; global_daily_limit: number; daily_custom: number | null;
  global_daily_custom: number | null; enabled: boolean }
export interface BetaDashboard { waitlist: BetaRequest[]; guests: BetaGuest[]; invitations: BetaInvitation[]; mail_ready: boolean;
  metrics: { active_users: number; credits_used: number; estimated_cost_microusd: number; monthly_budget_microusd: number };
  image_limits: ImageLimits; video_limits: VideoLimits }

async function request<T>(path: string, method = 'GET', csrf?: string, body?: object): Promise<T> {
  const response = await fetch(`/api/admin/beta${path}`, { method, headers: {
    'Content-Type': 'application/json', ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
  }, ...(body ? { body: JSON.stringify(body) } : {}) })
  const data = await response.json()
  if (!response.ok) throw apiError(data.detail ?? `Error ${response.status}`)
  return data as T
}
export const betaDashboard = () => request<BetaDashboard>('')
export const changeBetaAccess = (userId: string, authorized: boolean, csrf: string) =>
  request(`/users/${encodeURIComponent(userId)}/access`, 'PUT', csrf, { authorized })
export const sendBetaInvitation = (email: string, csrf: string) => request<BetaInvitation>('/invitations', 'POST', csrf, { email })
export const revokeBetaInvitation = (id: string, csrf: string) => request(`/invitations/${encodeURIComponent(id)}/revoke`, 'POST', csrf)
export const updateImageLimits = (weeklyLimit: number, globalDailyLimit: number, csrf: string) =>
  request<ImageLimits>('/image-limits', 'PUT', csrf, { weekly_limit: weeklyLimit, global_daily_limit: globalDailyLimit })
export const updateVideoLimits = (dailyLimit: number, globalDailyLimit: number, csrf: string) =>
  request<VideoLimits>('/video-limits', 'PUT', csrf, { daily_limit: dailyLimit, global_daily_limit: globalDailyLimit })
