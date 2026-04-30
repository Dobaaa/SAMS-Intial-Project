import { useEffect, useState } from "react";

import { api } from "../lib/api";

type Props = {
  agreementId: string;
  /** Optional caption shown next to the title. */
  referenceNumber?: string;
};

/**
 * Embeds the latest generated agreement PDF inline. Same auth-aware
 * blob → object URL pattern as DeviationReport.
 *
 * If no PDF has been generated yet the backend returns 404 — surface a
 * friendly note instead of a stack trace, since reviewers can't trigger
 * generation themselves (admin-only endpoint).
 */
export default function AgreementPdf({ agreementId, referenceNumber }: Props) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    if (!agreementId) return;
    let cancelled = false;
    let objectUrl: string | null = null;

    async function load() {
      setLoading(true);
      setError(null);
      setMissing(false);
      try {
        const resp = await api.get(`/pdf/${agreementId}/preview`, { responseType: "blob" });
        if (cancelled) return;
        objectUrl = URL.createObjectURL(resp.data as Blob);
        setPdfUrl(objectUrl);
      } catch (err: unknown) {
        if (cancelled) return;
        const e = err as { response?: { status?: number } };
        if (e?.response?.status === 404) {
          setMissing(true);
        } else {
          console.error(err);
          setError("Failed to load agreement PDF.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      setPdfUrl((prev) => {
        if (prev && prev !== objectUrl) URL.revokeObjectURL(prev);
        return null;
      });
    };
  }, [agreementId]);

  return (
    <div className="rounded-xl border border-sky-100 bg-white p-3 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-sky-900">
          Agreement PDF{referenceNumber ? ` — ${referenceNumber}` : ""}
        </h3>
        {pdfUrl && (
          <a
            className="rounded border border-sky-200 px-2 py-1 text-xs text-sky-800 hover:bg-sky-50"
            href={pdfUrl}
            target="_blank"
            rel="noreferrer"
          >
            Open in new tab
          </a>
        )}
      </div>

      {loading && <div className="text-sm text-sky-700">Loading…</div>}
      {missing && (
        <div className="rounded border border-amber-200 bg-amber-50 p-2 text-sm text-amber-800">
          No PDF has been generated for this agreement yet. Ask the admin to generate one from the dashboard.
        </div>
      )}
      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {pdfUrl && !loading && (
        <iframe
          title="Agreement PDF"
          src={pdfUrl}
          className="h-[700px] w-full rounded border border-sky-100"
        />
      )}
    </div>
  );
}
