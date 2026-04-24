import { api } from "./api";

/**
 * Fetch a PDF endpoint with the auth'd axios client and open it in a new
 * tab via an object URL. We can't use a plain `<a href>` because the
 * anchor request wouldn't carry the Bearer token.
 *
 * The object URL is revoked after a delay so the new tab has time to
 * read it; if the user keeps the tab open beyond the timeout the PDF
 * is already loaded into memory by the browser, so revocation is safe.
 */
export async function viewPdf(url: string): Promise<void> {
  const resp = await api.get(url, { responseType: "blob" });
  const blob = new Blob([resp.data as Blob], { type: "application/pdf" });
  const objectUrl = URL.createObjectURL(blob);
  window.open(objectUrl, "_blank", "noopener,noreferrer");
  setTimeout(() => URL.revokeObjectURL(objectUrl), 60_000);
}

/**
 * Fetch a PDF endpoint with the auth'd axios client and trigger a
 * browser download with the supplied filename.
 */
export async function downloadPdf(url: string, filename: string): Promise<void> {
  const resp = await api.get(url, { responseType: "blob" });
  const blob = new Blob([resp.data as Blob], { type: "application/pdf" });
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objectUrl;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(objectUrl);
}
