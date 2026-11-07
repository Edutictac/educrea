export interface BetaRequest { user_id: string; email: string; teaching_context: string; intended_use: string; requested_at: string }
export interface BetaGuest { user_id: string; email: string; access_status: 'invited' | 'revoked' }
export interface BetaInvitation { id: string; email: string; state: string; expires_at: string; sent_at: string | null }
export interface BetaDashboard { waitlist: BetaRequest[]; guests: BetaGuest[]; invitations: BetaInvitation[]; mail_ready: boolean;
  metrics: { active_users: number; credits_used: number; estimated_cost_microusd: number; monthly_budget_microusd: number } }

async function request<T>(path: string, method = 'GET', csrf?: string, body?: object): Promise<T> {
  const response = await fetch(`/api/admin/beta${path}`, { method, headers: {
    'Content-Type': 'application/json', ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
  }, ...(body ? { body: JSON.stringify(body) } : {}) })
  const data = await response.json()
  if (!response.ok) throw new Error(data.detail ?? `Error ${response.status}`)
  return data as T
}
export const betaDashboard = () => request<BetaDashboard>('')
export const changeBetaAccess = (userId: string, authorized: boolean, csrf: string) =>
  request(`/users/${encodeURIComponent(userId)}/access`, 'PUT', csrf, { authorized })
export const sendBetaInvitation = (email: string, csrf: string) => request<BetaInvitation>('/invitations', 'POST', csrf, { email })
export const revokeBetaInvitation = (id: string, csrf: string) => request(`/invitations/${encodeURIComponent(id)}/revoke`, 'POST', csrf)
