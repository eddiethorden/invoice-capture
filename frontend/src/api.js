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

export async function listInvoices() {
  const res = await fetch("/api/invoices");
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
