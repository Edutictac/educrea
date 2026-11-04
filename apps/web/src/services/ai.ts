import type { Grounding } from './sources'
export interface PaidModel { model: string; input_rate_microusd: number; output_rate_microusd: number }
export interface GeminiStatus { configured: boolean; verified_free_models: string[];
  confirmed_free_models: string[]; paid_models: PaidModel[] }
export type ProviderName = 'gemini' | 'openrouter' | 'groq' | 'ollama' | 'openai' | 'anthropic'
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
  usage: Record<string, number>; created_at: string; applied_at: string | null; grounding?: Grounding | null }

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(data.detail ?? `Error ${response.status}`)
  }
  return response
}

export async function geminiStatus(): Promise<GeminiStatus> {
  return await (await checked(await fetch('/api/ai/providers/gemini'))).json() as GeminiStatus
}

export async function providersStatus(): Promise<ProviderStatuses> {
  return await (await checked(await fetch('/api/ai/providers'))).json() as ProviderStatuses
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
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify({ instruction, provider, model, context_paths: automatic ? [] : contextPaths, automatic, source_ids: sourceIds, mode: 'paid' }),
  }))).json() as PaidEstimate
}

export async function saveProviderKey(provider: ProviderName, key: string, csrf: string): Promise<void> {
  await checked(await fetch(`/api/ai/providers/${provider}/key`, { method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ api_key: key }) }))
}

export async function revokeProviderKey(provider: ProviderName, csrf: string): Promise<void> {
  await checked(await fetch(`/api/ai/providers/${provider}/key`, { method: 'DELETE',
    headers: { 'X-CSRF-Token': csrf } }))
}

export async function confirmProviderModel(provider: ProviderName, model: string, csrf: string): Promise<void> {
  await checked(await fetch(`/api/ai/providers/${provider}/free-models/${encodeURIComponent(model)}/confirm`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify({ acknowledged: true }),
  }))
}

export async function saveGeminiKey(key: string, csrf: string): Promise<void> {
  await checked(await fetch('/api/ai/providers/gemini/key', { method: 'PUT',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ api_key: key }) }))
}

export async function revokeGeminiKey(csrf: string): Promise<void> {
  await checked(await fetch('/api/ai/providers/gemini/key', { method: 'DELETE', headers: { 'X-CSRF-Token': csrf } }))
}

export async function confirmFreeModel(model: string, csrf: string): Promise<void> {
  await checked(await fetch(`/api/ai/providers/gemini/free-models/${encodeURIComponent(model)}/confirm`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify({ acknowledged: true }),
  }))
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

export type AiStreamEvent = { event: 'status'; data: { stage: string; provider?: ProviderName; model?: string } }
  | { event: 'token'; data: { text: string } }
  | { event: 'proposal'; data: Proposal }
  | { event: 'error'; data: { status_code: number; message: string } }

export function parseSseBlock(block: string): AiStreamEvent | null {
  const event = block.split('\n').find(line => line.startsWith('event: '))?.slice(7)
  const data = block.split('\n').find(line => line.startsWith('data: '))?.slice(6)
  if (!event || !data || !['status', 'token', 'proposal', 'error'].includes(event)) return null
  return { event, data: JSON.parse(data) } as AiStreamEvent
}

export async function streamProposal(projectId: string, instruction: string, provider: ProviderName, model: string,
  contextPaths: string[], allowFallback: boolean, csrf: string,
  signal: AbortSignal, onEvent: (event: AiStreamEvent) => void,
  mode: 'free' | 'paid' = 'free', approvedMaxCost?: number, approvedFingerprint?: string,
  automatic = false, autoApply = false, sourceIds: string[] = []): Promise<void> {
  const response = await checked(await fetch(`/api/projects/${projectId}/ai/proposals/stream`, {
    method: 'POST', signal,
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify({ instruction, provider, model, context_paths: automatic ? [] : contextPaths, automatic, auto_apply: autoApply, source_ids: sourceIds, allow_fallback: allowFallback,
      mode, paid_authorized: mode === 'paid', approved_max_cost_microusd: approvedMaxCost,
      approved_estimate_fingerprint: approvedFingerprint }),
  }))
  if (!response.body) throw new Error('Streaming no disponible')
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
          if (event.event === 'error') throw new Error(event.data.message)
        }
        boundary = buffer.indexOf('\n\n')
      }
    }
  } finally { reader.releaseLock() }
  if (!completed) throw new Error('Respuesta incompleta')
}

