/**
 * Archive Files tab — Phase 2 Package E (req 8, 9, 10).
 *
 * Flat list of every agreement (previously required typing a raw project
 * or subcontractor UUID — GET /archive/agreements now lists everything),
 * grouped into 4 status buckets (computed client-side from current_status/
 * is_executed/gm_approval_date, no schema change), with filters across
 * Project Code / Agreement Ref / Project Name / Scope of Works /
 * Subcontractor Name / Status.
 */
import { useEffect, useMemo, useState } from "react";

import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { formatDateTime } from "../lib/formatDate";

type ArchiveRow = {
  id: string;
  reference_number: string;
  project_name?: string | null;
  project_code?: string | null;
  subcontractor_name?: string | null;
  scope_of_works?: string | null;
  current_status: string;
  status_label: string;
  pending_with: string;
  status_updated_on?: string | null;
  gm_approval_date?: string | null;
  execution_date?: string | null;
  is_executed: boolean;
  created_at?: string | null;
};

type BucketKey = "all" | "bucket1" | "bucket2" | "bucket3" | "bucket4";

const BUCKETS: { key: BucketKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "bucket1", label: "Signed by Both Parties" },
  { key: "bucket2", label: "Signed by BGCC — Subcontractor Pending" },
  { key: "bucket3", label: "Final Draft Approved by BGCC — Not Yet Issued" },
  { key: "bucket4", label: "Shared with Subcontractor — Comments Received" },
];

// req 9's four buckets, status-derived only — no schema change.
function isBucket1(row: ArchiveRow): boolean {
  return row.is_executed;
}
function isBucket2(row: ArchiveRow): boolean {
  return row.current_status === "under_gm_signature" || row.current_status === "under_subcontractor_signature";
}
// gm_approval_date is set exactly once, the moment all four main-chain
// reviewers have approved (see workflow_engine.approve_step) - it is never
// cleared afterward. A main-chain reviewer rejection can only happen
// *before* that milestone (return_step / resubmit_agreement never touch
// gm_approval_date), so under_bgcc_revision + gm_approval_date set can only
// mean "this was already forwarded once and the subcontractor sent
// comments back" - never an initial-pass rejection. That's what
// distinguishes bucket 3 (approved, not yet issued) from bucket 4
// (issued, comments received) without a dedicated tracking field.
function isBucket3(row: ArchiveRow): boolean {
  return row.current_status === "under_internal_review" && !!row.gm_approval_date;
}
function isBucket4(row: ArchiveRow): boolean {
  return (
    row.current_status === "draft_forwarded_to_subcontractor" ||
    row.current_status === "under_subcontractor_review" ||
    (row.current_status === "under_bgcc_revision" && !!row.gm_approval_date)
  );
}

const BUCKET_PREDICATES: Record<Exclude<BucketKey, "all">, (row: ArchiveRow) => boolean> = {
  bucket1: isBucket1,
  bucket2: isBucket2,
  bucket3: isBucket3,
  bucket4: isBucket4,
};

export default function ArchivePage() {
  const toast = useToast();

  const [status, setStatus] = useState("");
  const [reference, setReference] = useState("");
  const [projectCode, setProjectCode] = useState("");
  const [projectName, setProjectName] = useState("");
  const [subcontractorName, setSubcontractorName] = useState("");
  const [scopeOfWorks, setScopeOfWorks] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [bucket, setBucket] = useState<BucketKey>("all");
  const [rows, setRows] = useState<ArchiveRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const queryParams = useMemo(
    () => ({
      status: status || undefined,
      reference_number: reference || undefined,
      project_code: projectCode || undefined,
      project_name: projectName || undefined,
      subcontractor_name: subcontractorName || undefined,
      scope_of_works: scopeOfWorks || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    }),
    [status, reference, projectCode, projectName, subcontractorName, scopeOfWorks, dateFrom, dateTo]
  );

  const loadArchive = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/archive/agreements", { params: queryParams });
      setRows(data);
      setLoaded(true);
    } catch {
      toast.error("Failed to load archive.");
    } finally {
      setLoading(false);
    }
  };

  // Load everything once on mount so the tab is useful without requiring
  // the admin to apply a filter first.
  useEffect(() => {
    void loadArchive();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const exportExcel = async () => {
    try {
      const response = await api.get("/archive/export", { params: queryParams, responseType: "blob" });
      const blob = new Blob([response.data], {
        type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "archive_export.xlsx";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast.error("Failed to export archive.");
    }
  };

  const bucketCounts: Record<BucketKey, number> = {
    all: rows.length,
    bucket1: rows.filter(isBucket1).length,
    bucket2: rows.filter(isBucket2).length,
    bucket3: rows.filter(isBucket3).length,
    bucket4: rows.filter(isBucket4).length,
  };

  const displayed = bucket === "all" ? rows : rows.filter(BUCKET_PREDICATES[bucket]);

  return (
    <div className="space-y-4 p-4">
      <div>
        <h1 className="text-2xl font-bold text-sky-900">Archive Files</h1>
        <p className="text-sm text-gray-500">All agreements, past and present.</p>
      </div>

      {/* Bucket tabs (req 9) */}
      <div className="flex flex-wrap gap-2">
        {BUCKETS.map((b) => (
          <button
            key={b.key}
            className={`rounded-lg border px-3 py-1.5 text-sm font-medium transition ${
              bucket === b.key
                ? "border-sky-400 bg-sky-600 text-white"
                : "border-sky-200 bg-white text-sky-800 hover:bg-sky-50"
            }`}
            onClick={() => setBucket(b.key)}
          >
            {b.label} ({bucketCounts[b.key]})
          </button>
        ))}
      </div>

      {/* Filters (req 10) */}
      <div className="grid grid-cols-2 gap-2 rounded border p-3 sm:grid-cols-3 lg:grid-cols-7">
        <input
          className="rounded border p-2 text-sm"
          placeholder="Project Code"
          value={projectCode}
          onChange={(e) => setProjectCode(e.target.value)}
        />
        <input
          className="rounded border p-2 text-sm"
          placeholder="Agreement Reference"
          value={reference}
          onChange={(e) => setReference(e.target.value)}
        />
        <input
          className="rounded border p-2 text-sm"
          placeholder="Project Name"
          value={projectName}
          onChange={(e) => setProjectName(e.target.value)}
        />
        <input
          className="rounded border p-2 text-sm"
          placeholder="Scope of Works"
          value={scopeOfWorks}
          onChange={(e) => setScopeOfWorks(e.target.value)}
        />
        <input
          className="rounded border p-2 text-sm"
          placeholder="Subcontractor Name"
          value={subcontractorName}
          onChange={(e) => setSubcontractorName(e.target.value)}
        />
        <select className="rounded border p-2 text-sm" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="under_drafting">Under Drafting</option>
          <option value="under_internal_review">Under Internal Review</option>
          <option value="draft_forwarded_to_subcontractor">Draft Forwarded to Subcontractor</option>
          <option value="under_subcontractor_review">Under Subcontractor Review</option>
          <option value="under_subcontractor_signature">Under Subcontractor Signature</option>
          <option value="under_bgcc_revision">Under BGCC Revision</option>
          <option value="under_gm_signature">Under GM Signature</option>
          <option value="completed">Completed</option>
        </select>
        <div className="flex gap-1">
          <input className="w-1/2 rounded border p-2 text-sm" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} title="From" />
          <input className="w-1/2 rounded border p-2 text-sm" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} title="To" />
        </div>
        <div className="col-span-full flex gap-2">
          <button className="rounded bg-black px-4 py-2 text-sm text-white disabled:opacity-50" disabled={loading} onClick={loadArchive}>
            {loading ? "Loading…" : "Apply Filters"}
          </button>
          <button className="rounded bg-green-700 px-4 py-2 text-sm text-white" onClick={exportExcel}>
            Export to Excel
          </button>
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-sky-100 bg-white shadow-sm">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="bg-sky-50 text-left text-xs text-sky-900">
              <th className="border-b p-3 font-semibold">Project Code</th>
              <th className="border-b p-3 font-semibold">Agreement Ref</th>
              <th className="border-b p-3 font-semibold">Project Name</th>
              <th className="border-b p-3 font-semibold">Scope of Works</th>
              <th className="border-b p-3 font-semibold">Subcontractor Name</th>
              <th className="border-b p-3 font-semibold">Status</th>
              <th className="border-b p-3 font-semibold">Remarks — Pending With</th>
            </tr>
          </thead>
          <tbody>
            {!loaded && loading ? (
              <tr>
                <td colSpan={7} className="p-4 text-center text-sm text-gray-400">
                  Loading…
                </td>
              </tr>
            ) : displayed.length === 0 ? (
              <tr>
                <td colSpan={7} className="p-4 text-center text-sm text-gray-400">
                  No agreements match the current filters.
                </td>
              </tr>
            ) : (
              displayed.map((row) => {
                const signedByBoth = isBucket1(row);
                const readyToForward = isBucket3(row);
                return (
                  <tr key={row.id} className="border-b transition-colors last:border-0 hover:bg-gray-50">
                    <td className="p-3">{row.project_code ?? <span className="text-gray-400">—</span>}</td>
                    <td className="p-3 font-medium">{row.reference_number}</td>
                    <td className="p-3">{row.project_name ?? <span className="text-gray-400">—</span>}</td>
                    <td className="max-w-xs p-3">
                      <span className="line-clamp-2 whitespace-pre-wrap break-words">
                        {row.scope_of_works || <span className="text-gray-400">—</span>}
                      </span>
                    </td>
                    <td className="p-3">{row.subcontractor_name ?? <span className="text-gray-400">—</span>}</td>
                    {/* req 8: black = signed by both parties, red = pending from any party */}
                    <td className={`p-3 font-semibold ${signedByBoth ? "text-black" : "text-red-600"}`}>
                      {row.status_label}
                      {row.status_updated_on && (
                        <div className="text-[11px] font-normal text-gray-400">
                          {formatDateTime(row.status_updated_on)}
                        </div>
                      )}
                    </td>
                    {/* Remarks: names the responsible party. Green = nothing
                        blocking, ready to forward to the subcontractor; red =
                        still pending with someone; grey = fully executed. */}
                    <td
                      className={`p-3 ${
                        signedByBoth
                          ? "text-gray-500"
                          : readyToForward
                            ? "font-medium text-green-700"
                            : "font-medium text-red-700"
                      }`}
                    >
                      {row.pending_with}
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
