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

export async function verifyInvoice(id, fields) {
  const res = await fetch(`/api/invoices/${id}/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields }),
  });
  if (!res.ok) throw new Error(`Verify failed (${res.status})`);
  return res.json();
}
