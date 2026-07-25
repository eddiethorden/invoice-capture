export async function uploadInvoice(file) {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch("/api/invoices", { method: "POST", body: form });
  if (!res.ok) {
    const detail = await res.json().catch(() => ({}));
    throw new Error(detail.detail || `Upload failed (${res.status})`);
  }
  return res.json();
}

export async function verifyInvoice(id, fields, lineItems) {
  const res = await fetch(`/api/invoices/${id}/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields, line_items: lineItems }),
  });
  if (!res.ok) throw new Error(`Verify failed (${res.status})`);
  return res.json();
}

export async function getProjects() {
  const res = await fetch("/api/projects");
  if (!res.ok) throw new Error(`Projects failed (${res.status})`);
  return res.json();
}

export async function getConfig() {
  const res = await fetch("/api/config");
  if (!res.ok) throw new Error(`Config failed (${res.status})`);
  return res.json();
}

export async function listInvoices({ q = "", status = "all", page = 1, pageSize = 15 } = {}) {
  const params = new URLSearchParams({ q, status, page, page_size: pageSize });
  const res = await fetch(`/api/invoices?${params}`);
  if (!res.ok) throw new Error(`List failed (${res.status})`);
  return res.json();
}

export async function getInvoice(id) {
  const res = await fetch(`/api/invoices/${id}`);
  if (!res.ok) throw new Error(`Load failed (${res.status})`);
  return res.json();
}

export async function getAudit(id) {
  const res = await fetch(`/api/invoices/${id}/audit`);
  if (!res.ok) throw new Error(`Audit failed (${res.status})`);
  return res.json();
}

export async function getHandover(id) {
  const res = await fetch(`/api/invoices/${id}/handover`);
  if (!res.ok) throw new Error(`Handover failed (${res.status})`);
  return res.json();
}

// Accounts Receivable module (separate service, proxied at /ar).
export async function listReceivables() {
  const res = await fetch("/ar/receivables");
  if (!res.ok) throw new Error(`Receivables failed (${res.status})`);
  return res.json();
}

// ---- BAS + moms kontering ----

export async function getKonton() {
  const res = await fetch("/api/bas/konton");
  if (!res.ok) throw new Error(`Konton failed (${res.status})`);
  return res.json();
}

export async function getMomskoder() {
  const res = await fetch("/api/moms/koder");
  if (!res.ok) throw new Error(`Momskoder failed (${res.status})`);
  return res.json();
}

export async function konteringForslag(rader, angivetTotal) {
  const res = await fetch("/api/kontering/forslag", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rader, angivet_total: angivetTotal || null }),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Kontering failed (${res.status})`);
  return data;
}
