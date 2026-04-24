import { useEffect, useState } from "react";

import { api } from "../lib/api";

type Props = {
  agreementId: string;
};

/**
 * Renders the deviation-report PDF inline via an auth'd fetch → object URL.
 *
 * We can't just use <iframe src="/api/..."/> because the iframe request
 * would not carry the Authorization header from our axios interceptor.
 * Instead, pull the PDF as a blob via the shared api client, create an
 * object URL, and embed that. The URL is revoked when the component
 * unmounts (or the agreementId changes) so we don't leak blobs.
 */
export default function DeviationReport({ agreementId }: Props) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!agreementId) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const resp = await api.get(`/agreements/${agreementId}/deviation-report`, {
          responseType: "blob",
        });
        if (cancelled) return;
        objectUrl = URL.createObjectURL(resp.data as Blob);
        setPdfUrl(objectUrl);
      } catch (err) {
        if (!cancelled) {
          console.error(err);
          setError("Failed to load deviation report.");
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

  const regenerate = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.post(`/agreements/${agreementId}/deviation-report/regenerate`);
      // Fetch the fresh copy.
      const resp = await api.get(`/agreements/${agreementId}/deviation-report`, {
        responseType: "blob",
      });
      const newUrl = URL.createObjectURL(resp.data as Blob);
      setPdfUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return newUrl;
      });
    } catch (err) {
      console.error(err);
      setError("Failed to regenerate deviation report.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="rounded-xl border border-sky-100 bg-white p-3 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-sky-900">Deviation Report</h3>
        <div className="flex items-center gap-2">
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
          <button
            type="button"
            onClick={regenerate}
            disabled={loading}
            className="rounded border border-sky-200 px-2 py-1 text-xs text-sky-800 hover:bg-sky-50 disabled:opacity-50"
          >
            Regenerate
          </button>
        </div>
      </div>

      {loading && <div className="text-sm text-sky-700">Loading…</div>}
      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {pdfUrl && !loading && (
        <iframe
          title="Deviation Report"
          src={pdfUrl}
          className="h-[600px] w-full rounded border border-sky-100"
        />
      )}
    </div>
  );
}
