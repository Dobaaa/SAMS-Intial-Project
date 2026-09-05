/**
 * GM Portal Dashboard — Phase 2 Package B (req 1). Restricted view: only
 * agreements pending GM's own approval step, with exactly five identifying
 * columns (Project Code / Agreement Ref / Project Name / Scope of Works /
 * Subcontractor Name) and exactly two actions — View PDF (red-highlighted
 * admin-entered content, Package C) and Compare (the Original vs Revised
 * table, Package D). GM's decision (Approved / Approved with comments /
 * Rejected with comments, req 7) lives at the bottom of the Compare page,
 * not here — GM's nav points here instead of the general ReviewerDashboard
 * or Workflow Review (req 1: no other options in the GM portal).
 */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { viewPdf } from "../lib/pdf";

type GMRow = {
  step_id: string;
  step_name: string;
  agreement_id: string;
  reference_number: string;
  project_code: string | null;
  project_name: string | null;
  scope_of_works: string;
  subcontractor_name: string | null;
  needs_reaffirm: boolean;
};

export default function GMDashboard() {
  const toast = useToast();
  const [rows, setRows] = useState<GMRow[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .get("/workflow/gm-dashboard")
      .then(({ data }) => setRows(data))
      .catch(() => toast.error("Failed to load your pending agreements."))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openHighlightedPdf = async (agreementId: string, ref: string) => {
    try {
      await viewPdf(`/pdf/${agreementId}/preview/gm-highlighted`);
    } catch {
      toast.error(`No PDF available for ${ref} yet.`);
    }
  };

  return (
    <div className="space-y-4 p-5">
      <div>
        <h1 className="text-2xl font-bold text-sky-900">GM Dashboard</h1>
        <p className="text-sm text-gray-500">
          Agreements pending your approval. Admin-entered content is highlighted red in
          View PDF.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-gray-400">No agreements pending your approval.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-sky-100 bg-white shadow-sm">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-sky-50 text-left text-xs text-sky-900">
                <th className="border-b p-3 font-semibold">Project Code</th>
                <th className="border-b p-3 font-semibold">Agreement Ref</th>
                <th className="border-b p-3 font-semibold">Project Name</th>
                <th className="border-b p-3 font-semibold">Scope of Works</th>
                <th className="border-b p-3 font-semibold">Subcontractor Name</th>
                <th className="border-b p-3 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.step_id} className="border-b transition-colors last:border-0 hover:bg-gray-50">
                  <td className="p-3">{row.project_code ?? <span className="text-gray-400">—</span>}</td>
                  <td className="p-3 font-medium">
                    {row.reference_number}
                    {row.needs_reaffirm && (
                      <span
                        className="ml-1.5 rounded-full bg-amber-500 px-1.5 py-0.5 text-[9px] font-bold text-white"
                        title="Approved, but Admin changed it since — open Compare to re-check"
                      >
                        ⚠
                      </span>
                    )}
                  </td>
                  <td className="p-3">{row.project_name ?? <span className="text-gray-400">—</span>}</td>
                  <td className="max-w-xs p-3">
                    <span className="line-clamp-2 whitespace-pre-wrap break-words">
                      {row.scope_of_works || <span className="text-gray-400">—</span>}
                    </span>
                  </td>
                  <td className="p-3">{row.subcontractor_name ?? <span className="text-gray-400">—</span>}</td>
                  <td className="p-3">
                    <div className="flex flex-wrap gap-1.5">
                      <button
                        className="rounded border border-sky-200 bg-white px-2 py-1 text-xs text-sky-700 hover:bg-sky-50"
                        onClick={() => openHighlightedPdf(row.agreement_id, row.reference_number)}
                      >
                        View PDF
                      </button>
                      <Link
                        to={`/agreements/${row.agreement_id}/compare-table`}
                        className="rounded border border-sky-200 bg-white px-2 py-1 text-xs text-sky-700 hover:bg-sky-50"
                      >
                        Compare
                      </Link>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
