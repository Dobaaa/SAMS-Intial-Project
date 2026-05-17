/**
 * Compare view — Phase 4 v1 deliverable for Rev 01 items 3 + 17-extension.
 *
 * Side-by-side comparison of the blank 42-page master template ("Original /
 * Base Version") and this agreement's filled-in version ("Revised /
 * Admin-Amended"). A right-hand sidebar lists every field the admin has
 * populated, with original (master placeholder = empty) shown beside the
 * revised value, so reviewers can scan all amendments at a glance without
 * scrolling 42 pages of PDF.
 *
 * Not in scope here (Phase 4 v2): clause-prose track-changes with
 * inline <w:ins>/<w:del> revisions, accept/reject workflow, in-PDF
 * highlighting. v1 satisfies Rev 01 item 17-extension's "two parallel
 * columns / clause aligned page-by-page" core requirement.
 */
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { api } from "../lib/api";
import { formatNumber } from "../lib/formatNumber";

type MasterField = {
  id: string;
  field_id: string;
  field_label: string;
  clause_number?: string | null;
  input_type: string;
  sort_order: number;
};

type AgreementBundle = {
  id: string;
  reference_number: string;
  current_status: string;
  values: Record<string, string>;
};

const NUMERIC_FIELDS = new Set([
  "F08",
  "C03",
  "C11",
  "A07",
  "A09",
  "A10",
  "A20",
  "A21",
]);

function displayValue(fieldId: string, raw: string | undefined): string {
  if (!raw) return "";
  if (NUMERIC_FIELDS.has(fieldId)) return formatNumber(raw);
  return raw;
}

export default function AgreementCompare() {
  const { id: agreementId } = useParams<{ id: string }>();

  const [bundle, setBundle] = useState<AgreementBundle | null>(null);
  const [fields, setFields] = useState<MasterField[]>([]);
  const [originalUrl, setOriginalUrl] = useState<string>("");
  const [revisedUrl, setRevisedUrl] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const blobs: string[] = [];

    async function load() {
      if (!agreementId) return;
      setLoading(true);
      setError(null);
      try {
        // Pull bundle + masters first; PDFs are heavier so kick those in
        // parallel after we know the agreement exists.
        const [bundleResp, mastersResp] = await Promise.all([
          api.get<AgreementBundle>(`/agreements/${agreementId}`),
          api.get<{
            form?: Array<{ id: string }>;
            conditions?: Array<{ id: string }>;
            appendix?: Array<{ id: string }>;
          }>("/masters/"),
        ]);
        if (cancelled) return;
        setBundle(bundleResp.data);

        const active = [
          mastersResp.data.form?.[0],
          mastersResp.data.conditions?.[0],
          mastersResp.data.appendix?.[0],
        ].filter((t): t is { id: string } => Boolean(t));
        const allFields: MasterField[] = [];
        for (const tpl of active) {
          const fr = await api.get<MasterField[]>(
            `/masters/fields/${tpl.id}`
          );
          if (Array.isArray(fr.data)) allFields.push(...fr.data);
        }
        if (cancelled) return;
        setFields(allFields);

        // Now the two PDFs. Master is cached server-side keyed by docx mtime.
        const [masterBlob, revisedBlob] = await Promise.all([
          api.get("/pdf/master/preview", { responseType: "blob" }),
          api
            .get(`/pdf/${agreementId}/preview`, { responseType: "blob" })
            .catch(async () => {
              // If no PDF has been generated yet, force one then retry.
              await api.post(`/pdf/${agreementId}/generate`);
              return api.get(`/pdf/${agreementId}/preview`, {
                responseType: "blob",
              });
            }),
        ]);
        if (cancelled) return;
        const ou = URL.createObjectURL(masterBlob.data as Blob);
        const ru = URL.createObjectURL(revisedBlob.data as Blob);
        blobs.push(ou, ru);
        setOriginalUrl(ou);
        setRevisedUrl(ru);
      } catch (err) {
        console.error(err);
        if (!cancelled) setError("Failed to load comparison.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
      for (const b of blobs) URL.revokeObjectURL(b);
    };
  }, [agreementId]);

  /** All filled fields, grouped by F / C / A, in catalog order. */
  const diffRows = useMemo(() => {
    if (!bundle) return [] as Array<{
      field: MasterField;
      revised: string;
    }>;
    const values = bundle.values || {};
    return fields
      .filter((f) => (values[f.field_id] ?? "").trim() !== "")
      .sort((a, b) => {
        // Group by prefix (F < C < A), then sort_order
        const pa = a.field_id[0];
        const pb = b.field_id[0];
        if (pa !== pb) return pa < pb ? -1 : 1;
        return a.sort_order - b.sort_order;
      })
      .map((f) => ({ field: f, revised: values[f.field_id] }));
  }, [bundle, fields]);

  if (loading) {
    return <div className="p-6 text-sky-700">Loading comparison…</div>;
  }
  if (error || !bundle) {
    return (
      <div className="space-y-3 p-6">
        <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error ?? "Agreement not found."}
        </div>
        <Link className="text-sky-700 underline" to="/dashboard">
          ← Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-4.5rem)] flex-col">
      {/* Header strip */}
      <div className="flex items-center justify-between border-b border-sky-100 bg-sky-50/40 px-4 py-2">
        <div>
          <h1 className="text-base font-semibold text-sky-900">
            Compare — {bundle.reference_number}
          </h1>
          <p className="text-xs text-sky-700">
            Original base template (left) vs admin-amended version (right) ·
            <strong className="ml-1">{diffRows.length}</strong> field
            {diffRows.length === 1 ? "" : "s"} filled
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            className="rounded border border-sky-300 px-3 py-1 text-sm text-sky-700 hover:bg-sky-50"
            to={`/agreements/${agreementId}/document`}
          >
            Open Document editor
          </Link>
          <Link
            className="rounded border border-sky-300 px-3 py-1 text-sm text-sky-700 hover:bg-sky-50"
            to="/dashboard"
          >
            Done
          </Link>
        </div>
      </div>

      {/* Three-pane body: original | revised | diff sidebar */}
      <div className="grid flex-1 grid-cols-12 overflow-hidden">
        {/* Left: ORIGINAL / Base 42 pages */}
        <div className="col-span-5 flex flex-col border-r border-sky-100 bg-sky-50/30">
          <div className="border-b border-sky-100 bg-sky-100/70 px-3 py-1 text-xs font-semibold text-sky-900">
            ORIGINAL · Base Subcontract Agreement (template)
          </div>
          {originalUrl ? (
            <iframe
              src={originalUrl}
              title="Original master PDF"
              className="h-full w-full"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-sky-700">
              Rendering original…
            </div>
          )}
        </div>

        {/* Middle: REVISED / This agreement */}
        <div className="col-span-5 flex flex-col border-r border-sky-100 bg-white">
          <div className="border-b border-amber-100 bg-amber-100/60 px-3 py-1 text-xs font-semibold text-amber-900">
            REVISED · {bundle.reference_number}
          </div>
          {revisedUrl ? (
            <iframe
              src={revisedUrl}
              title="Revised agreement PDF"
              className="h-full w-full"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-sky-700">
              Rendering revised…
            </div>
          )}
        </div>

        {/* Right: changes sidebar */}
        <aside className="col-span-2 overflow-y-auto bg-sky-50/30 p-3">
          <h2 className="mb-2 text-sm font-semibold text-sky-900">Changes</h2>
          <p className="mb-3 text-xs text-sky-700">
            Field values admin has populated for this agreement. Empty cells
            in the master are shown as <em>—</em>.
          </p>
          {diffRows.length === 0 ? (
            <p className="text-xs text-gray-500">
              No fields filled yet — the revised PDF still matches the
              template.
            </p>
          ) : (
            <ul className="space-y-2">
              {diffRows.map(({ field, revised }) => (
                <li
                  key={field.field_id}
                  className="rounded border border-sky-100 bg-white p-2"
                >
                  <div className="text-[10px] font-semibold text-sky-700">
                    {field.field_id}
                    {field.clause_number && (
                      <span className="ml-1 text-gray-500">
                        · {field.clause_number}
                      </span>
                    )}
                  </div>
                  <div className="text-xs font-medium text-sky-900">
                    {field.field_label}
                  </div>
                  <div className="mt-1 grid grid-cols-1 gap-1 text-xs">
                    <div className="rounded bg-sky-50 px-1.5 py-1">
                      <span className="text-[10px] uppercase text-sky-700">
                        original
                      </span>
                      <div className="text-gray-400">—</div>
                    </div>
                    <div className="rounded bg-amber-50 px-1.5 py-1">
                      <span className="text-[10px] uppercase text-amber-700">
                        revised
                      </span>
                      <div
                        className="break-words text-amber-900"
                        style={{ wordBreak: "break-word" }}
                      >
                        {displayValue(field.field_id, revised)}
                      </div>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </aside>
      </div>
    </div>
  );
}
