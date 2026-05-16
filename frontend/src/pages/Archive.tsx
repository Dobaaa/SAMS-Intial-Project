import { useMemo, useState } from "react";

import { api } from "../lib/api";
import { formatDateTime } from "../lib/formatDate";

type ArchiveRow = {
  id: string;
  reference_number: string;
  project_name?: string | null;
  project_code?: string | null;
  subcontractor_name?: string | null;
  current_status: string;
  status_label: string;
  status_updated_on?: string | null;
  gm_approval_date?: string | null;
  execution_date?: string | null;
  is_executed: boolean;
  created_at?: string | null;
};

const statusBadge: Record<string, string> = {
  completed: "bg-green-100 text-green-700",
  under_bgcc_revision: "bg-red-100 text-red-700",
  under_drafting: "bg-amber-100 text-amber-700",
  under_internal_review: "bg-amber-100 text-amber-700",
  draft_forwarded_to_subcontractor: "bg-amber-100 text-amber-700",
  under_subcontractor_review: "bg-amber-100 text-amber-700",
  under_subcontractor_signature: "bg-amber-100 text-amber-700",
  under_gm_signature: "bg-amber-100 text-amber-700",
};

export default function ArchivePage() {
  const [tab, setTab] = useState<"project" | "subcontractor">("project");
  const [projectId, setProjectId] = useState("");
  const [subcontractorId, setSubcontractorId] = useState("");
  const [status, setStatus] = useState("");
  const [reference, setReference] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [rows, setRows] = useState<ArchiveRow[]>([]);

  const queryParams = useMemo(
    () => ({
      status: status || undefined,
      reference_number: reference || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    }),
    [status, reference, dateFrom, dateTo]
  );

  const loadArchive = async () => {
    if (tab === "project" && projectId) {
      const { data } = await api.get(`/archive/projects/${projectId}`, { params: queryParams });
      setRows(data);
    }
    if (tab === "subcontractor" && subcontractorId) {
      const { data } = await api.get(`/archive/subcontractors/${subcontractorId}`, { params: queryParams });
      setRows(data);
    }
  };

  const exportExcel = async () => {
    const params = {
      ...(tab === "project" ? { project_id: projectId } : { subcontractor_id: subcontractorId }),
      ...queryParams,
    };
    const response = await api.get("/archive/export", {
      params,
      responseType: "blob",
    });
    const blob = new Blob([response.data], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "archive_export.xlsx";
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="grid grid-cols-12 gap-4 p-4">
      <aside className="col-span-3 rounded border p-3">
        <h2 className="mb-3 text-lg font-semibold">Filters</h2>
        <div className="mb-3 flex gap-2">
          <button className={`rounded px-3 py-1 ${tab === "project" ? "bg-black text-white" : "border"}`} onClick={() => setTab("project")}>
            Project View
          </button>
          <button className={`rounded px-3 py-1 ${tab === "subcontractor" ? "bg-black text-white" : "border"}`} onClick={() => setTab("subcontractor")}>
            Subcontractor View
          </button>
        </div>

        {tab === "project" ? (
          <input className="mb-2 w-full rounded border p-2" placeholder="Project ID" value={projectId} onChange={(e) => setProjectId(e.target.value)} />
        ) : (
          <input className="mb-2 w-full rounded border p-2" placeholder="Subcontractor ID" value={subcontractorId} onChange={(e) => setSubcontractorId(e.target.value)} />
        )}

        <input className="mb-2 w-full rounded border p-2" placeholder="Reference search" value={reference} onChange={(e) => setReference(e.target.value)} />
        <select className="mb-2 w-full rounded border p-2" value={status} onChange={(e) => setStatus(e.target.value)}>
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
        <input className="mb-2 w-full rounded border p-2" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        <input className="mb-3 w-full rounded border p-2" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />

        <button className="mb-2 w-full rounded bg-black px-3 py-2 text-white" onClick={loadArchive}>
          Apply Filters
        </button>
        <button className="w-full rounded bg-green-700 px-3 py-2 text-white" onClick={exportExcel}>
          Export to Excel
        </button>
      </aside>

      <main className="col-span-9 rounded border p-3">
        <h2 className="mb-3 text-lg font-semibold">Archive Records</h2>
        <div className="overflow-x-auto">
          <table className="w-full border-collapse border">
            <thead>
              <tr className="bg-gray-100">
                <th className="border p-2">Reference</th>
                <th className="border p-2">Project</th>
                <th className="border p-2">Subcontractor</th>
                <th className="border p-2">Status</th>
                <th className="border p-2">Status Updated On</th>
                <th className="border p-2">GM Approval</th>
                <th className="border p-2">Execution</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.id}>
                  <td className="border p-2">{row.reference_number}</td>
                  <td className="border p-2">
                    {row.project_name} {row.project_code ? `(${row.project_code})` : ""}
                  </td>
                  <td className="border p-2">{row.subcontractor_name}</td>
                  <td className="border p-2">
                    <span className={`rounded px-2 py-1 text-xs ${statusBadge[row.current_status] ?? "bg-gray-100 text-gray-700"}`}>
                      {row.status_label}
                    </span>
                  </td>
                  <td className="border p-2">{row.status_updated_on ? formatDateTime(row.status_updated_on) : "-"}</td>
                  <td className="border p-2">{row.gm_approval_date ?? "-"}</td>
                  <td className="border p-2">{row.execution_date ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
