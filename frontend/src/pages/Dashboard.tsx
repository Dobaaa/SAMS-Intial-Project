import axios from "axios";
import { useEffect, useState } from "react";

type Summary = {
  total_agreements: number;
  under_review: number;
  with_subcontractor: number;
  completed_this_month: number;
};

type AgreementRow = {
  id: string;
  reference_number: string;
  project_name?: string | null;
  subcontractor_name?: string | null;
  status: string;
  status_label: string;
  status_updated_on?: string | null;
};

type AuditItem = {
  id: string;
  user_name?: string | null;
  action: string;
  entity_type: string;
  entity_id?: string | null;
  created_at?: string | null;
};

type MasterVersion = {
  id: string;
  type: string;
  version_number: string;
  version_date: string;
};

const api = axios.create({ baseURL: "/api" });

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [agreements, setAgreements] = useState<AgreementRow[]>([]);
  const [audit, setAudit] = useState<AuditItem[]>([]);
  const [auditPage, setAuditPage] = useState(1);
  const [auditTotal, setAuditTotal] = useState(0);
  const [versions, setVersions] = useState<MasterVersion[]>([]);
  const [status, setStatus] = useState("");
  const [reference, setReference] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [auditAction, setAuditAction] = useState("");
  const [loadError, setLoadError] = useState<string>("");

  const loadAll = async () => {
    try {
      setLoadError("");
      const [sum, agr, aud, ver] = await Promise.all([
        api.get("/reports/dashboard/summary"),
        api.get("/reports/dashboard/agreements", {
          params: {
            status: status || undefined,
            reference_number: reference || undefined,
            date_from: dateFrom || undefined,
            date_to: dateTo || undefined,
          },
        }),
        api.get("/reports/audit-log", {
          params: { page: auditPage, page_size: 10, action: auditAction || undefined },
        }),
        api.get("/reports/masters/active-versions"),
      ]);
      setSummary(sum.data);
      setAgreements(Array.isArray(agr.data) ? agr.data : []);
      setAudit(Array.isArray(aud.data?.items) ? aud.data.items : []);
      setAuditTotal(typeof aud.data?.total === "number" ? aud.data.total : 0);
      setVersions(Array.isArray(ver.data) ? ver.data : []);
    } catch (error) {
      console.error("Failed to load dashboard data", error);
      setAgreements([]);
      setAudit([]);
      setVersions([]);
      setAuditTotal(0);
      setLoadError("Failed to load dashboard data. Please check backend API responses.");
    }
  };

  useEffect(() => {
    void loadAll();
  }, [auditPage]);

  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-semibold">Admin Dashboard</h1>
      {loadError && <div className="rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">{loadError}</div>}

      {summary && (
        <div className="grid grid-cols-4 gap-3">
          <div className="rounded border p-3">Total Agreements: <strong>{summary.total_agreements}</strong></div>
          <div className="rounded border p-3">Under Review: <strong>{summary.under_review}</strong></div>
          <div className="rounded border p-3">With Subcontractor: <strong>{summary.with_subcontractor}</strong></div>
          <div className="rounded border p-3">Completed This Month: <strong>{summary.completed_this_month}</strong></div>
        </div>
      )}

      <div className="rounded border p-3">
        <h2 className="mb-2 text-lg font-semibold">Agreements</h2>
        <div className="mb-3 grid grid-cols-5 gap-2">
          <select className="rounded border p-2" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="under_drafting">Under Drafting</option>
            <option value="under_internal_review">Under Internal Review</option>
            <option value="under_bgcc_revision">Under BGCC Revision</option>
            <option value="completed">Completed</option>
          </select>
          <input className="rounded border p-2" placeholder="Reference search" value={reference} onChange={(e) => setReference(e.target.value)} />
          <input className="rounded border p-2" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          <input className="rounded border p-2" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          <button className="rounded bg-black px-3 py-2 text-white" onClick={loadAll}>Apply</button>
        </div>
        <table className="w-full border-collapse border">
          <thead>
            <tr className="bg-gray-100">
              <th className="border p-2">Reference</th>
              <th className="border p-2">Project</th>
              <th className="border p-2">Subcontractor</th>
              <th className="border p-2">Status</th>
              <th className="border p-2">Updated On</th>
              <th className="border p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {agreements.map((a) => (
              <tr key={a.id}>
                <td className="border p-2">{a.reference_number}</td>
                <td className="border p-2">{a.project_name}</td>
                <td className="border p-2">{a.subcontractor_name}</td>
                <td className="border p-2">{a.status_label}</td>
                <td className="border p-2">{a.status_updated_on ? new Date(a.status_updated_on).toLocaleString() : "-"}</td>
                <td className="border p-2">
                  <div className="flex gap-2">
                    <a className="rounded border px-2 py-1" href={`/api/archive/agreements/${a.id}`} target="_blank" rel="noreferrer">View</a>
                    <button className="rounded border px-2 py-1" onClick={() => api.post(`/pdf/${a.id}/generate`)}>Generate PDF</button>
                    <a className="rounded border px-2 py-1" href={`/api/archive/agreements/${a.id}/download`} target="_blank" rel="noreferrer">Download</a>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded border p-3">
        <h2 className="mb-2 text-lg font-semibold">Audit Trail</h2>
        <div className="mb-2 flex gap-2">
          <input className="rounded border p-2" placeholder="Action filter" value={auditAction} onChange={(e) => setAuditAction(e.target.value)} />
          <button className="rounded bg-black px-3 py-2 text-white" onClick={() => { setAuditPage(1); void loadAll(); }}>Filter</button>
        </div>
        <table className="w-full border-collapse border">
          <thead>
            <tr className="bg-gray-100">
              <th className="border p-2">Who</th>
              <th className="border p-2">Action</th>
              <th className="border p-2">Entity</th>
              <th className="border p-2">When</th>
            </tr>
          </thead>
          <tbody>
            {audit.map((row) => (
              <tr key={row.id}>
                <td className="border p-2">{row.user_name || "-"}</td>
                <td className="border p-2">{row.action}</td>
                <td className="border p-2">{row.entity_type}</td>
                <td className="border p-2">{row.created_at ? new Date(row.created_at).toLocaleString() : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-2 flex items-center gap-2">
          <button className="rounded border px-2 py-1" disabled={auditPage <= 1} onClick={() => setAuditPage((p) => p - 1)}>Prev</button>
          <span className="text-sm">Page {auditPage} / {Math.max(1, Math.ceil(auditTotal / 10))}</span>
          <button className="rounded border px-2 py-1" disabled={auditPage >= Math.ceil(auditTotal / 10)} onClick={() => setAuditPage((p) => p + 1)}>Next</button>
        </div>
      </div>

      <div className="rounded border p-3">
        <h2 className="mb-2 text-lg font-semibold">Active Master Versions</h2>
        <div className="grid grid-cols-3 gap-2">
          {versions.map((v) => (
            <div key={v.id} className="rounded border p-2">
              <div className="font-medium capitalize">{v.type}</div>
              <div>{v.version_number}</div>
              <div className="text-xs text-gray-500">{v.version_date}</div>
            </div>
          ))}
        </div>
        <a className="mt-3 inline-block rounded bg-black px-3 py-2 text-white" href="/?view=masters">
          Manage Versions
        </a>
      </div>
    </div>
  );
}
