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
    <div className="space-y-5 p-5">
      <h1 className="text-3xl font-bold text-sky-900">Admin Dashboard</h1>
      {loadError && <div className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-700">{loadError}</div>}

      {summary && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          <div className="rounded-xl border border-sky-100 bg-white p-4 shadow-sm">Total Agreements: <strong className="text-sky-800">{summary.total_agreements}</strong></div>
          <div className="rounded-xl border border-sky-100 bg-white p-4 shadow-sm">Under Review: <strong className="text-sky-800">{summary.under_review}</strong></div>
          <div className="rounded-xl border border-sky-100 bg-white p-4 shadow-sm">With Subcontractor: <strong className="text-sky-800">{summary.with_subcontractor}</strong></div>
          <div className="rounded-xl border border-sky-100 bg-white p-4 shadow-sm">Completed This Month: <strong className="text-sky-800">{summary.completed_this_month}</strong></div>
        </div>
      )}

      <div className="rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-xl font-semibold text-sky-900">Agreements</h2>
        <div className="mb-3 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-5">
          <select className="rounded-lg border border-sky-200 bg-white p-2" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="under_drafting">Under Drafting</option>
            <option value="under_internal_review">Under Internal Review</option>
            <option value="under_bgcc_revision">Under BGCC Revision</option>
            <option value="completed">Completed</option>
          </select>
          <input className="rounded-lg border border-sky-200 p-2" placeholder="Reference search" value={reference} onChange={(e) => setReference(e.target.value)} />
          <input className="rounded-lg border border-sky-200 p-2" type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          <input className="rounded-lg border border-sky-200 p-2" type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
          <button className="rounded-lg bg-sky-600 px-3 py-2 text-white transition hover:bg-sky-700" onClick={loadAll}>Apply</button>
        </div>
        <table className="w-full border-collapse overflow-hidden rounded-lg border border-sky-100">
          <thead>
            <tr className="bg-sky-50 text-sky-900">
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
                <td className="border border-sky-100 p-2">{a.reference_number}</td>
                <td className="border border-sky-100 p-2">{a.project_name}</td>
                <td className="border border-sky-100 p-2">{a.subcontractor_name}</td>
                <td className="border border-sky-100 p-2">{a.status_label}</td>
                <td className="border border-sky-100 p-2">{a.status_updated_on ? new Date(a.status_updated_on).toLocaleString() : "-"}</td>
                <td className="border border-sky-100 p-2">
                  <div className="flex gap-2">
                    <a className="rounded-lg border border-sky-200 px-2 py-1 text-sky-700 hover:bg-sky-50" href={`/api/archive/agreements/${a.id}`} target="_blank" rel="noreferrer">View</a>
                    <button className="rounded-lg border border-sky-200 px-2 py-1 text-sky-700 hover:bg-sky-50" onClick={() => api.post(`/pdf/${a.id}/generate`)}>Generate PDF</button>
                    <a className="rounded-lg border border-sky-200 px-2 py-1 text-sky-700 hover:bg-sky-50" href={`/api/archive/agreements/${a.id}/download`} target="_blank" rel="noreferrer">Download</a>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
        <h2 className="mb-2 text-xl font-semibold text-sky-900">Audit Trail</h2>
        <div className="mb-2 flex gap-2">
          <input className="rounded-lg border border-sky-200 p-2" placeholder="Action filter" value={auditAction} onChange={(e) => setAuditAction(e.target.value)} />
          <button className="rounded-lg bg-sky-600 px-3 py-2 text-white hover:bg-sky-700" onClick={() => { setAuditPage(1); void loadAll(); }}>Filter</button>
        </div>
        <table className="w-full border-collapse overflow-hidden rounded-lg border border-sky-100">
          <thead>
            <tr className="bg-sky-50 text-sky-900">
              <th className="border p-2">Who</th>
              <th className="border p-2">Action</th>
              <th className="border p-2">Entity</th>
              <th className="border p-2">When</th>
            </tr>
          </thead>
          <tbody>
            {audit.map((row) => (
              <tr key={row.id}>
                <td className="border border-sky-100 p-2">{row.user_name || "-"}</td>
                <td className="border border-sky-100 p-2">{row.action}</td>
                <td className="border border-sky-100 p-2">{row.entity_type}</td>
                <td className="border border-sky-100 p-2">{row.created_at ? new Date(row.created_at).toLocaleString() : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        <div className="mt-2 flex items-center gap-2">
          <button className="rounded-lg border border-sky-200 px-2 py-1 text-sky-700 disabled:opacity-40" disabled={auditPage <= 1} onClick={() => setAuditPage((p) => p - 1)}>Prev</button>
          <span className="text-sm">Page {auditPage} / {Math.max(1, Math.ceil(auditTotal / 10))}</span>
          <button className="rounded-lg border border-sky-200 px-2 py-1 text-sky-700 disabled:opacity-40" disabled={auditPage >= Math.ceil(auditTotal / 10)} onClick={() => setAuditPage((p) => p + 1)}>Next</button>
        </div>
      </div>

      <div className="rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
        <h2 className="mb-2 text-xl font-semibold text-sky-900">Active Master Versions</h2>
        <div className="grid grid-cols-3 gap-2">
          {versions.map((v) => (
            <div key={v.id} className="rounded-lg border border-sky-100 bg-sky-50/40 p-2">
              <div className="font-medium capitalize text-sky-800">{v.type}</div>
              <div>{v.version_number}</div>
              <div className="text-xs text-gray-500">{v.version_date}</div>
            </div>
          ))}
        </div>
        <a className="mt-3 inline-block rounded-lg bg-sky-600 px-3 py-2 text-white hover:bg-sky-700" href="/?view=masters">
          Manage Versions
        </a>
      </div>
    </div>
  );
}
