// Read-only access to the per-file version history; restoring still goes through HistoryPanel.

export interface VersionSummary {
  id: string
  path: string
  version: number
  source: string
  created_at: string
  size: number
}

export interface VersionContent extends VersionSummary { content: string }

async function checked(response: Response): Promise<Response> {
  if (!response.ok) {
    const data = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(data.detail ?? `Error ${response.status}`)
  }
  return response
}

export async function listVersions(projectId: string, path: string): Promise<VersionSummary[]> {
  const query = encodeURIComponent(path)
  return await (await checked(await fetch(`/api/projects/${projectId}/history?path=${query}`,
    { credentials: 'same-origin' }))).json() as VersionSummary[]
}

export async function versionContent(projectId: string, versionId: string): Promise<VersionContent> {
  return await (await checked(await fetch(`/api/projects/${projectId}/history/${versionId}`,
    { credentials: 'same-origin' }))).json() as VersionContent
}
