import { apiMessage } from '../i18n/apiErrors'
import { apiError } from '../i18n/apiErrors'
import { t } from '../i18n'
import { temporaryKeyHeaders, usesTemporaryKeys, rememberTemporaryKey, forgetTemporaryKey, confirmTemporaryModel, unconfirmTemporaryModel } from './temporaryKeys'
import type { Grounding } from './sources'
export interface PaidModel { model: string; input_rate_microusd: number; output_rate_microusd: number }
export interface GeminiStatus { configured: boolean; verified_free_models: string[];
  confirmed_free_models: string[]; paid_models: PaidModel[] }
export type ProviderName = 'gemini' | 'mistral' | 'openrouter' | 'groq' | 'ollama' | 'openai' | 'anthropic' | 'deepseek'
export type ProviderStatuses = Record<ProviderName, GeminiStatus>
export interface BudgetStatus { monthly_limit_microusd: number; spent_or_reserved_microusd: number;
  maximum_allowed_microusd: number }
export interface PaidEstimate { provider: ProviderName; model: string; max_input_tokens: number;
  max_output_tokens: number; maximum_cost_microusd: number; input_rate_microusd: number;
  output_rate_microusd: number; fingerprint: string }
export interface QuotaStatus { requests_used: number; requests_limit: number; tokens_used_or_reserved: number;
  shared: { requests_used: number; requests_limit: number; tokens_used_or_reserved: number; tokens_limit: number } }
export interface ProposalChange { path: string; before_content: string | null; after_content: string; base_version: number }
export interface Proposal { id: string; project_id: string; provider: string; model: string; summary: string;
  changes: ProposalChange[]; status: 'pending' | 'applied' | 'rejected' | 'restored';
  usage: Record<string, number>; created_at: string; applied_at: string | null; grounding?: Grounding | null;
  agent_trace?: AgentStep[] | null }
export interface AgentStep { name: string; arguments: string; status: 'ok' | 'error' | 'needs_approval'; detail?: string; truncated?: boolean }

export class AiError extends Error {
  code?: string
  provider?: string
  constructor(message: string, code?: string, provider?: string) {
    super(apiMessage(message))
    this.name = 'AiError'
    this.code = code
    this.provider = provider
  }
}

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string }
    throw apiError(data.detail ?? `Error ${response.status}`)
  }
  return response
}

export async function geminiStatus(): Promise<GeminiStatus> {
  return await (await checked(await fetch('/api/ai/providers/gemini', { headers: temporaryKeyHeaders() }))).json() as GeminiStatus
}

export async function providersStatus(): Promise<ProviderStatuses> {
  return await (await checked(await fetch('/api/ai/providers', { headers: temporaryKeyHeaders() }))).json() as ProviderStatuses
}

export async function quotaStatus(): Promise<QuotaStatus> {
  return await (await checked(await fetch('/api/ai/quota'))).json() as QuotaStatus
}

export async function budgetStatus(): Promise<BudgetStatus> {
  return await (await checked(await fetch('/api/ai/budget'))).json() as BudgetStatus
}

export async function updateBudget(limit: number, csrf: string): Promise<BudgetStatus> {
  return await (await checked(await fetch('/api/ai/budget', { method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify({ monthly_limit_microusd: limit }),
  }))).json() as BudgetStatus
}

export async function estimatePaid(projectId: string, instruction: string, provider: ProviderName,
  model: string, contextPaths: string[], csrf: string, automatic = false,
  sourceIds: string[] = []): Promise<PaidEstimate> {
  return await (await checked(await fetch(`/api/projects/${projectId}/ai/estimate`, { method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...temporaryKeyHeaders() },
    body: JSON.stringify({ instruction, provider, model, context_paths: automatic ? [] : contextPaths, automatic, source_ids: sourceIds, mode: 'paid' }),
  }))).json() as PaidEstimate
}

export async function saveProviderKey(provider: ProviderName, key: string, csrf: string): Promise<void> {
  if (usesTemporaryKeys()) { rememberTemporaryKey(provider, key); return }
  await checked(await fetch(`/api/ai/providers/${provider}/key`, { method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...temporaryKeyHeaders() }, body: JSON.stringify({ api_key: key }) }))
}

export async function revokeProviderKey(provider: ProviderName, csrf: string): Promise<void> {
  if (usesTemporaryKeys()) { forgetTemporaryKey(provider); return }
  await checked(await fetch(`/api/ai/providers/${provider}/key`, { method: 'DELETE',
    headers: { 'X-CSRF-Token': csrf } }))
}

export async function confirmProviderModel(provider: ProviderName, model: string, csrf: string): Promise<void> {
  if (usesTemporaryKeys()) { confirmTemporaryModel(provider, model); return }
  await checked(await fetch(`/api/ai/providers/${provider}/free-models/${encodeURIComponent(model)}/confirm`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...temporaryKeyHeaders() },
    body: JSON.stringify({ acknowledged: true }),
  }))
}

// Stops using a confirmed free model (for example, because the key now has billing).
export async function disableProviderModel(provider: ProviderName, model: string, csrf: string): Promise<void> {
  if (usesTemporaryKeys()) { unconfirmTemporaryModel(provider, model); return }
  await checked(await fetch(`/api/ai/providers/${provider}/free-models/${encodeURIComponent(model)}/confirm`, {
    method: 'DELETE', headers: { 'X-CSRF-Token': csrf },
  }))
}

export async function saveGeminiKey(key: string, csrf: string): Promise<void> { return saveProviderKey('gemini', key, csrf) }
export async function revokeGeminiKey(csrf: string): Promise<void> { return revokeProviderKey('gemini', csrf) }
export async function confirmFreeModel(model: string, csrf: string): Promise<void> { return confirmProviderModel('gemini', model, csrf) }

export async function adaptDua(projectId: string, path: string, needs: string, autoApply: boolean,
  csrf: string, choice: { provider?: string; model?: string } = {}): Promise<Proposal> {
  return await (await checked(await fetch(`/api/projects/${projectId}/ai/dua`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...temporaryKeyHeaders() },
    body: JSON.stringify({ path, needs, auto_apply: autoApply, ...choice }),
  }))).json() as Proposal
}

export async function generateFromBrief(projectId: string, csrf: string, choice: { provider?: string; model?: string } = {}): Promise<Proposal> {
  return await (await checked(await fetch(`/api/projects/${projectId}/ai/from-brief`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...temporaryKeyHeaders() }, body: JSON.stringify(choice) }))).json() as Proposal
}

export async function listProposals(projectId: string): Promise<Proposal[]> {
  return await (await checked(await fetch(`/api/projects/${projectId}/ai/proposals`))).json() as Proposal[]
}

export async function listContextFiles(projectId: string): Promise<string[]> {
  const files = await (await checked(await fetch(`/api/projects/${projectId}/files`))).json() as { path: string }[]
  return files.map(file => file.path)
}

export async function changeProposal(projectId: string, proposalId: string,
  action: 'apply' | 'reject' | 'restore', csrf: string): Promise<Proposal> {
  return await (await checked(await fetch(`/api/projects/${projectId}/ai/proposals/${proposalId}/${action}`, {
    method: 'POST', headers: { 'X-CSRF-Token': csrf },
  }))).json() as Proposal
}

export type AiStreamEvent = { event: 'status'; data: { stage: string; provider?: ProviderName | 'educrea'; model?: string; passages?: number; retry?: boolean; section?: string; index?: number; total?: number } }
  | { event: 'section'; data: { index: number; total: number; section: string; chars: number } }
  | { event: 'token'; data: { text: string } }
  | { event: 'consulted'; data: { capabilities: AgentStep[] } }
  | { event: 'proposal'; data: Proposal }
  | { event: 'error'; data: { status_code: number; message: string; code?: string; provider?: string } }

export function parseSseBlock(block: string): AiStreamEvent | null {
  const event = block.split('\n').find(line => line.startsWith('event: '))?.slice(7)
  const data = block.split('\n').find(line => line.startsWith('data: '))?.slice(6)
  if (!event || !data || !['status', 'token', 'proposal', 'error', 'consulted', 'section'].includes(event)) return null
  return { event, data: JSON.parse(data) } as AiStreamEvent
}

export async function streamProposal(projectId: string, instruction: string, provider: ProviderName | 'educrea', model: string,
  contextPaths: string[], allowFallback: boolean, csrf: string,
  signal: AbortSignal, onEvent: (event: AiStreamEvent) => void,
  mode: 'free' | 'paid' | 'included' = 'free', approvedMaxCost?: number, approvedFingerprint?: string,
  automatic = false, autoApply = false, sourceIds: string[] = [], taskType = 'unknown'): Promise<void> {
  const response = await checked(await fetch(`/api/projects/${projectId}/ai/proposals/stream`, {
    method: 'POST', signal,
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...temporaryKeyHeaders() },
    body: JSON.stringify({ instruction, provider, model, task_type: taskType, context_paths: automatic ? [] : contextPaths, automatic, auto_apply: autoApply, source_ids: sourceIds, allow_fallback: allowFallback,
      mode, paid_authorized: mode === 'paid', approved_max_cost_microusd: approvedMaxCost,
      approved_estimate_fingerprint: approvedFingerprint }),
  }))
  return await readEvents(response, onEvent)
}

// Reads the server-sent events of a generation and returns the final proposal.
async function readEvents(response: Response, onEvent: (event: AiStreamEvent) => void): Promise<void> {
  if (!response.body) throw new Error(t('streamUnavailable'))
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let completed = false
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true }).replaceAll('\r\n', '\n')
      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        const event = parseSseBlock(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
        if (event) {
          onEvent(event)
          if (event.event === 'proposal') completed = true
          if (event.event === 'error') throw new AiError(event.data.message, event.data.code, event.data.provider)
        }
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally { reader.releaseLock(); if (typeof window !== 'undefined') window.dispatchEvent(new Event('educrea-ai-usage')) }
  if (!completed) throw new Error(t('incompleteResponse'))
}

// Teacher shortcuts with real progress: first version from the brief and DUA adaptation.
export async function streamTeacherAction(projectId: string, action: 'from-brief' | 'dua' | 'sections', body: object, csrf: string,
  signal: AbortSignal, onEvent: (event: AiStreamEvent) => void): Promise<Proposal> {
  const response = await checked(await fetch(`/api/projects/${projectId}/ai/${action}/stream`, {
    method: 'POST', signal, headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf, ...temporaryKeyHeaders() }, body: JSON.stringify(body) }))
  let proposal: Proposal | null = null
  await readEvents(response, event => { if (event.event === 'proposal') proposal = event.data; onEvent(event) })
  if (!proposal) throw new Error(t('incompleteResponse'))
  return proposal
}


export interface IncludedStatus { authorized: boolean; access_status: 'invited' | 'not_invited' | 'revoked'; enabled: boolean; available: boolean; period_key: string;
  monthly_credits_limit: number; monthly_credits_used: number; remaining_credits: number; renews_at: string }
export async function includedStatus(): Promise<IncludedStatus> {
  return await (await checked(await fetch('/api/ai/included'))).json() as IncludedStatus
}

export interface BetaWaitlistStatus {
  status: 'none' | 'pending' | 'accepted' | 'closed'; teaching_context?: string; intended_use?: string; requested_at?: string
}
export async function betaWaitlistStatus(): Promise<BetaWaitlistStatus> {
  return await (await checked(await fetch('/api/ai/included/waitlist'))).json() as BetaWaitlistStatus
}
export async function joinBetaWaitlist(teachingContext: string, intendedUse: string, csrf: string): Promise<BetaWaitlistStatus> {
  return await (await checked(await fetch('/api/ai/included/waitlist', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify({ teaching_context: teachingContext, intended_use: intendedUse }),
  }))).json() as BetaWaitlistStatus
}
