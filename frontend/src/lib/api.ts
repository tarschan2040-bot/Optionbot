/**
 * API client for the OptionBot FastAPI backend.
 * All requests include the Supabase JWT for authentication.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Fetch wrapper that injects the auth token from Supabase session.
 */
async function apiFetch(
  path: string,
  token: string,
  options: RequestInit = {}
): Promise<Response> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...options.headers,
    },
  });
  return res;
}

// ── Config endpoints ──────────────────────────────────────────────────

export async function getConfig(token: string) {
  const res = await apiFetch("/config", token);
  if (!res.ok) throw new Error(`Failed to load config: ${res.status}`);
  return res.json();
}

export async function updateConfig(token: string, updates: Record<string, unknown>) {
  const res = await apiFetch("/config", token, {
    method: "PUT",
    body: JSON.stringify(updates),
  });
  if (!res.ok) throw new Error(`Failed to update config: ${res.status}`);
  return res.json();
}

// ── Scan endpoints ────────────────────────────────────────────────────

export async function getScanResults(token: string) {
  const res = await apiFetch("/scan/results", token);
  if (!res.ok) throw new Error(`Failed to load results: ${res.status}`);
  return res.json();
}

export async function triggerScan(
  token: string,
  options?: { tickers?: string[]; strategy?: string }
) {
  const res = await apiFetch("/scan/trigger", token, {
    method: "POST",
    body: JSON.stringify(options || {}),
  });
  if (!res.ok) throw new Error(`Failed to trigger scan: ${res.status}`);
  return res.json();
}

export async function getScanHistory(token: string, limit = 10) {
  const res = await apiFetch(`/scan/history?limit=${limit}`, token);
  if (!res.ok) throw new Error(`Failed to load history: ${res.status}`);
  return res.json();
}

export async function getScanStatus(token: string) {
  const res = await apiFetch("/scan/status", token);
  if (!res.ok) throw new Error(`Failed to get status: ${res.status}`);
  return res.json();
}

export async function getScanResultDetail(token: string, index: number) {
  const res = await apiFetch(`/scan/results/${index}`, token);
  if (!res.ok) throw new Error(`Failed to load detail: ${res.status}`);
  return res.json();
}

// ── Candidate + Portfolio endpoints ────────────────────────────────────

export async function getCandidates(token: string) {
  const res = await apiFetch("/candidates", token);
  if (!res.ok) throw new Error(`Failed to load candidates: ${res.status}`);
  return res.json();
}

export async function starCandidate(token: string, data: Record<string, unknown>) {
  const res = await apiFetch("/candidates/star", token, {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to star: ${res.status}`);
  return res.json();
}

export async function confirmCandidate(token: string, id: string) {
  const res = await apiFetch(`/candidates/${id}/confirm`, token, { method: "POST" });
  if (!res.ok) throw new Error(`Failed to confirm: ${res.status}`);
  return res.json();
}

export async function removeCandidate(token: string, id: string) {
  const res = await apiFetch(`/candidates/${id}`, token, { method: "DELETE" });
  if (!res.ok) throw new Error(`Failed to remove: ${res.status}`);
  return res.json();
}

export async function getPortfolio(token: string) {
  const res = await apiFetch("/candidates/portfolio", token);
  if (!res.ok) throw new Error(`Failed to load portfolio: ${res.status}`);
  return res.json();
}

export async function getPortfolioSummary(token: string) {
  const res = await apiFetch("/candidates/portfolio/summary", token);
  if (!res.ok) throw new Error(`Failed to load summary: ${res.status}`);
  return res.json();
}

export async function closeTrade(token: string, id: string, exitPrice?: number) {
  const res = await apiFetch(`/candidates/${id}/close`, token, {
    method: "POST",
    body: JSON.stringify({ exit_price: exitPrice ?? 0 }),
  });
  if (!res.ok) throw new Error(`Failed to close: ${res.status}`);
  return res.json();
}

// ── Health ─────────────────────────────────────────────────────────────

export async function getHealth() {
  const res = await fetch(`${API_URL}/health`);
  return res.json();
}
