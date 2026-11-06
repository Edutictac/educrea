export interface Capability { name: string; description: string; input_schema: Record<string, unknown>; mutates: boolean; source: string }
export interface AuditRow { capability: string; status: 'ok' | 'error' | 'denied'; detail: string; input_bytes: number;
  output_bytes: number; duration_ms: number; created_at: string }

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(data.detail ?? `Error ${response.status}`)
  }
  return response
}

export async function listCapabilities(): Promise<Capability[]> {
  return await (await checked(await fetch('/api/capabilities'))).json() as Capability[]
}

export async function invokeCapability(projectId: string, name: string, args: Record<string, unknown>, approved: boolean,
  csrf: string): Promise<unknown> {
  return await (await checked(await fetch(`/api/projects/${projectId}/capabilities/${encodeURIComponent(name)}/invoke`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
    body: JSON.stringify({ arguments: args, approved }),
  }))).json()
}

export async function capabilityAudit(projectId: string): Promise<AuditRow[]> {
  return await (await checked(await fetch(`/api/projects/${projectId}/capabilities/audit`))).json() as AuditRow[]
}

// Parses the JSON arguments typed by the teacher. Only plain objects are valid arguments.
export function parseArguments(text: string): Record<string, unknown> | null {
  try {
    const value: unknown = JSON.parse(text.trim() || '{}')
    return value !== null && typeof value === 'object' && !Array.isArray(value) ? value as Record<string, unknown> : null
  } catch { return null }
}
