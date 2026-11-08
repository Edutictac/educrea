export interface Wallet {
  enabled: boolean; livemode: false; currency: 'eur'; balance_microeur: number
  entries: { id: string; amount_microeur: number; created_at: string }[]
  topups: { id: string; state: string }[]
}

export async function loadWallet(): Promise<Wallet> {
  const response = await fetch('/api/billing/wallet', { credentials: 'same-origin', cache: 'no-store' })
  if (!response.ok) throw new Error('billing')
  return response.json() as Promise<Wallet>
}

export async function openCheckout(requestId: string, csrf: string): Promise<string> {
  const response = await fetch('/api/billing/checkout', { method: 'POST', credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf }, body: JSON.stringify({ request_id: requestId }) })
  if (!response.ok) throw new Error('billing')
  const result = await response.json() as { url: string }
  const url = new URL(result.url)
  if (url.protocol !== 'https:' || url.host !== 'checkout.stripe.com') throw new Error('billing')
  return url.href
}
