import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { downloadPdf, viewPdf } from "../lib/pdf";

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
  gm_approval_date?: string | null;
  open_returned_comments?: number;
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

export default function Dashboard() {
  const toast = useToast();
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
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

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

  const flash = (message: string) => {
    setActionMessage(message);
    setTimeout(() => setActionMessage(null), 4000);
  };

  const resubmitForReview = async (agreement: AgreementRow) => {
    setBusyId(agreement.id);
    try {
      await api.post(`/agreements/${agreement.id}/resubmit`);
      toast.success(`Resubmitted ${agreement.reference_number} for internal review.`);
      await loadAll();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? `Failed to resubmit ${agreement.reference_number}.`);
      console.error(err);
    } finally {
      setBusyId(null);
    }
  };

  const sendToSubcontractor = async (agreement: AgreementRow) => {
    setBusyId(agreement.id);
    try {
      await api.post(`/agreements/${agreement.id}/send-to-subcontractor`);
      toast.success(`Sent ${agreement.reference_number} to the subcontractor.`);
      await loadAll();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? `Failed to send ${agreement.reference_number} to the subcontractor.`);
      console.error(err);
    } finally {
      setBusyId(null);
    }
  };

  const recordSubcontractorResponse = async (
    agreement: AgreementRow,
    response_type: "signed" | "comments"
  ) => {
    setBusyId(agreement.id);
    try {
      await api.patch(`/agreements/${agreement.id}/subcontractor-response`, { response_type });
      const verb = response_type === "signed" ? "signed" : "returned with comments";
      toast.success(`Recorded ${agreement.reference_number} as ${verb}.`);
      await loadAll();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? `Failed to record response for ${agreement.reference_number}.`);
      console.error(err);
    } finally {
      setBusyId(null);
    }
  };

  const generatePdf = async (agreement: AgreementRow) => {
    setBusyId(agreement.id);
    try {
      await api.post(`/pdf/${agreement.id}/generate`);
      flash(`Generated PDF for ${agreement.reference_number}.`);
    } catch (err) {
      console.error(err);
      flash(`Failed to generate PDF for ${agreement.reference_number}.`);
    } finally {
      setBusyId(null);
    }
  };

  const previewPdf = async (agreement: AgreementRow) => {
    setBusyId(agreement.id);
    try {
      await viewPdf(`/pdf/${agreement.id}/preview`);
    } catch (err: unknown) {
      console.error(err);
      const status =
        typeof err === "object" && err && "response" in err
          ? (err as { response?: { status?: number } }).response?.status
          : undefined;
      flash(
        status === 404
          ? `No PDF found for ${agreement.reference_number}. Click Generate first.`
          : `Failed to open PDF for ${agreement.reference_number}.`
      );
    } finally {
      setBusyId(null);
    }
  };

  const downloadAgreementPdf = async (agreement: AgreementRow) => {
    setBusyId(agreement.id);
    try {
      await downloadPdf(`/pdf/${agreement.id}/preview`, `${agreement.reference_number}.pdf`);
    } catch (err: unknown) {
      console.error(err);
      const status =
        typeof err === "object" && err && "response" in err
          ? (err as { response?: { status?: number } }).response?.status
          : undefined;
      flash(
        status === 404
          ? `No PDF found for ${agreement.reference_number}. Click Generate first.`
          : `Failed to download PDF for ${agreement.reference_number}.`
      );
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-5 p-5">
      <h1 className="text-3xl font-bold text-sky-900">Admin Dashboard</h1>
      {loadError && <div className="rounded-xl border border-red-300 bg-red-50 p-3 text-sm text-red-700">{loadError}</div>}
      {actionMessage && (
        <div className="rounded-xl border border-sky-300 bg-sky-50 p-3 text-sm text-sky-800">
          {actionMessage}
        </div>
      )}

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
            <option value="draft_forwarded_to_subcontractor">Draft Forwarded to Subcontractor</option>
            <option value="under_subcontractor_review">Under Subcontractor Review</option>
            <option value="under_subcontractor_signature">Under Subcontractor Signature</option>
            <option value="under_bgcc_revision">Under BGCC Revision</option>
            <option value="under_gm_signature">Under GM Signature</option>
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
                <td className="border border-sky-100 p-2">
                  <div className="flex flex-wrap items-center gap-2">
                    <span>{a.reference_number}</span>
                    {(a.open_returned_comments ?? 0) > 0 && (
                      <Link
                        to="/resolution"
                        className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800 hover:bg-amber-200"
                        title="Returned with comments — open Resolution"
                      >
                        {a.open_returned_comments} comment{a.open_returned_comments === 1 ? "" : "s"}
                      </Link>
                    )}
                  </div>
                </td>
                <td className="border border-sky-100 p-2">{a.project_name}</td>
                <td className="border border-sky-100 p-2">{a.subcontractor_name}</td>
                <td className="border border-sky-100 p-2">{a.status_label}</td>
                <td className="border border-sky-100 p-2">{a.status_updated_on ? new Date(a.status_updated_on).toLocaleString() : "-"}</td>
                <td className="border border-sky-100 p-2">
                  <div className="flex flex-wrap gap-2">
                    {(a.status === "under_drafting" || a.status === "under_bgcc_revision") && (
                      <Link
                        to={`/agreements/${a.id}/edit`}
                        className="rounded-lg border border-sky-200 px-2 py-1 text-sky-700 hover:bg-sky-50"
                        title="Resume editing this draft"
                      >
                        Edit
                      </Link>
                    )}
                    {a.status === "under_bgcc_revision" && !a.gm_approval_date && (
                      <button
                        className="rounded-lg border border-sky-300 bg-sky-50 px-2 py-1 text-sky-800 hover:bg-sky-100 disabled:opacity-50"
                        disabled={busyId === a.id}
                        onClick={() => void resubmitForReview(a)}
                        title="Resubmit the revised draft for internal review (GM has not yet approved)"
                      >
                        Resubmit for Review
                      </button>
                    )}
                    {(a.status === "under_internal_review" || a.status === "under_bgcc_revision") && a.gm_approval_date && (
                      <button
                        className="rounded-lg border border-emerald-300 bg-emerald-50 px-2 py-1 text-emerald-800 hover:bg-emerald-100 disabled:opacity-50"
                        disabled={busyId === a.id}
                        onClick={() => void sendToSubcontractor(a)}
                        title="Send the agreement out to the subcontractor"
                      >
                        Send to Subcontractor
                      </button>
                    )}
                    {(a.status === "draft_forwarded_to_subcontractor" || a.status === "under_subcontractor_signature") && (
                      <button
                        className="rounded-lg border border-emerald-300 bg-emerald-50 px-2 py-1 text-emerald-800 hover:bg-emerald-100 disabled:opacity-50"
                        disabled={busyId === a.id}
                        onClick={() => void recordSubcontractorResponse(a, "signed")}
                        title="Record that the subcontractor signed without comments — locks the agreement"
                      >
                        Mark Signed
                      </button>
                    )}
                    {a.status === "draft_forwarded_to_subcontractor" && (
                      <button
                        className="rounded-lg border border-amber-300 bg-amber-50 px-2 py-1 text-amber-800 hover:bg-amber-100 disabled:opacity-50"
                        disabled={busyId === a.id}
                        onClick={() => void recordSubcontractorResponse(a, "comments")}
                        title="Record that the subcontractor returned comments — go to Resolution to enter them"
                      >
                        Comments Returned
                      </button>
                    )}
                    <button
                      className="rounded-lg border border-sky-200 px-2 py-1 text-sky-700 hover:bg-sky-50 disabled:opacity-50"
                      disabled={busyId === a.id}
                      onClick={() => void previewPdf(a)}
                      title="Open the latest generated PDF in a new tab"
                    >
                      View
                    </button>
                    <button
                      className="rounded-lg border border-sky-200 px-2 py-1 text-sky-700 hover:bg-sky-50 disabled:opacity-50"
                      disabled={busyId === a.id}
                      onClick={() => void generatePdf(a)}
                      title="Render Cover + Form + Conditions + Appendix into a fresh PDF"
                    >
                      {busyId === a.id ? "Working…" : "Generate PDF"}
                    </button>
                    <button
                      className="rounded-lg border border-sky-200 px-2 py-1 text-sky-700 hover:bg-sky-50 disabled:opacity-50"
                      disabled={busyId === a.id}
                      onClick={() => void downloadAgreementPdf(a)}
                      title="Download the latest generated PDF"
                    >
                      Download
                    </button>
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
