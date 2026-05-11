import { useEffect, useState } from "react";

import { api } from "../lib/api";
import { formatNumber } from "../lib/formatNumber";

type AppendixRow = {
  field_id: string;
  row_label: string;
  clause_ref: string;
  current_value: string | null;
  is_modified_from_default: boolean;
  auto_source_field_id: string | null;
  show_in_appendix: boolean;
  admin_extra_note: string | null;
  sort_order: number;
};

type Props = {
  agreementId: string;
  referenceNumber?: string;
};

/**
 * Read-only Appendix view rendered alongside the agreement PDF in the
 * Workflow Review screen. Reviewers (PD/Accounts/OM/GM) need to see both
 * documents simultaneously without switching tabs — the PDF carries the
 * legal text on the left while this component lists the per-row values
 * on the right.
 *
 * Numbers go through formatNumber so financial figures match the PDF's
 * thousand-separator + dot-decimal rendering.
 */
export default function AppendixView({ agreementId, referenceNumber }: Props) {
  const [rows, setRows] = useState<AppendixRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!agreementId) return;
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const { data } = await api.get<AppendixRow[]>(
          `/agreements/${agreementId}/appendix`
        );
        if (!cancelled) {
          const visible = (Array.isArray(data) ? data : []).filter(
            (r) => r.show_in_appendix
          );
          visible.sort((a, b) => a.sort_order - b.sort_order);
          setRows(visible);
        }
      } catch (err) {
        if (!cancelled) {
          console.error(err);
          setError("Failed to load the appendix.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [agreementId]);

  return (
    <div className="rounded-xl border border-sky-100 bg-white p-3 shadow-sm">
      <h3 className="mb-2 text-lg font-semibold text-sky-900">
        Appendix{referenceNumber ? ` — ${referenceNumber}` : ""}
      </h3>
      {loading && <div className="text-sm text-sky-700">Loading…</div>}
      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {error}
        </div>
      )}
      {!loading && !error && rows.length === 0 && (
        <div className="rounded border border-sky-100 bg-sky-50/50 p-2 text-sm text-sky-700">
          No appendix rows configured for this agreement.
        </div>
      )}
      {rows.length > 0 && (
        <div className="overflow-y-auto" style={{ maxHeight: "700px" }}>
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 bg-sky-50">
              <tr>
                <th className="border border-sky-100 p-2 text-left">Item</th>
                <th className="border border-sky-100 p-2 text-left w-20">Clause</th>
                <th className="border border-sky-100 p-2 text-left">Information</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.field_id}>
                  <td className="border border-sky-100 p-2 align-top">
                    <div className="font-medium">{row.row_label}</div>
                    <div className="text-xs text-gray-500">
                      {row.field_id}
                      {row.auto_source_field_id && (
                        <span> · auto from {row.auto_source_field_id}</span>
                      )}
                    </div>
                  </td>
                  <td className="border border-sky-100 p-2 align-top font-mono text-xs">
                    {row.clause_ref}
                  </td>
                  <td className="border border-sky-100 p-2 align-top whitespace-pre-wrap">
                    {row.current_value ? (
                      formatNumber(row.current_value)
                    ) : (
                      <span className="text-gray-400">(empty)</span>
                    )}
                    {row.admin_extra_note && (
                      <div className="mt-1 border-t border-dashed border-sky-100 pt-1 text-xs italic text-gray-600">
                        {row.admin_extra_note}
                      </div>
                    )}
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
