/**
 * API Client — centralised fetch wrapper for the Incremental HUIM backend.
 *
 * All endpoints are proxied through Vite so we use relative URLs.
 */

const BASE = '';

async function request(url, options = {}) {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

// ── Results ──────────────────────────────────────────────────────

export function fetchStats() {
  return request('/api/results/stats');
}

export function fetchTopK(k = 10) {
  return request(`/api/results/top-k?k=${k}`);
}

export function fetchPatternHistory(limit = 100, offset = 0) {
  return request(`/api/results/history?limit=${limit}&offset=${offset}`);
}

// ── Transactions ─────────────────────────────────────────────────

export function fetchBatches() {
  return request('/api/transactions/batches');
}

export function fetchTransactions(batchId) {
  return request(`/api/transactions/?batch_id=${batchId}`);
}

export function ingestBatch(transactions) {
  return request('/api/transactions/', {
    method: 'POST',
    body: JSON.stringify({ transactions }),
  });
}

// ── Pipeline ─────────────────────────────────────────────────────

export function runPipeline() {
  return request('/api/pipeline/run', { method: 'POST' });
}

export function runDataset(transactions, batch_size, top_k) {
  return request('/api/pipeline/run-dataset', {
    method: 'POST',
    body: JSON.stringify({ transactions, batch_size, top_k }),
  });
}

export function fetchPipelineStatus() {
  return request('/api/pipeline/status');
}

export function fetchPipelineHistory(limit = 20) {
  return request(`/api/pipeline/history?limit=${limit}`);
}

// ── Configuration ────────────────────────────────────────────────

export function fetchConfig() {
  return request('/api/config/');
}

export function updateConfig(updates) {
  return request('/api/config/', {
    method: 'PUT',
    body: JSON.stringify(updates),
  });
}
