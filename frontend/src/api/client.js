const API_BASE = import.meta.env.VITE_API_URL || '';

export async function submitThought(thought) {
  const res = await fetch(`${API_BASE}/api/thoughts/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ thought }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export async function fetchMap(domain = null) {
  const url = domain
    ? `${API_BASE}/api/thoughts/map?domain=${domain}`
    : `${API_BASE}/api/thoughts/map`;
  const res = await fetch(url);
  return res.json();
}

export async function fetchStats() {
  const res = await fetch(`${API_BASE}/api/thoughts/stats`);
  return res.json();
}

export async function fetchClusters() {
  const res = await fetch(`${API_BASE}/api/clusters`);
  return res.json();
}

export async function fetchTrends() {
  const res = await fetch(`${API_BASE}/api/trends/predictive`);
  return res.json();
}
