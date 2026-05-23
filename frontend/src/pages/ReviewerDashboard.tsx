import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { viewPdf } from "../lib/pdf";
import { useToast } from "../components/Toast";

type ReviewItem = {
  step: {
    id: string;
    status: string;
    role_required: string;
    step_name: string;
  };
  agreement: {
    id: string;
    reference_number: string;
    current_status: string;
    project_name?: string | null;
    subcontractor_name?: string | null;
  };
};

const STATUS_LABELS: Record<string, string> = {
  under_drafting: "Under Drafting",
  under_internal_review: "Under Internal Review",
  draft_forwarded_to_subcontractor: "Forwarded to Subcontractor",
  under_subcontractor_review: "Subcontractor Review",
  under_subcontractor_signature: "Subcontractor Signature",
  under_bgcc_revision: "Under BGCC Revision",
  under_gm_signature: "Under GM Signature",
  completed: "Completed",
};

function statusBadge(status: string) {
  const label = STATUS_LABELS[status] ?? status.replace(/_/g, " ");
  const colour =
    status === "completed"
      ? "bg-green-100 text-green-700 border-green-200"
      : status === "under_internal_review"
        ? "bg-sky-100 text-sky-700 border-sky-200"
        : status === "under_bgcc_revision"
          ? "bg-amber-100 text-amber-700 border-amber-200"
          : "bg-gray-100 text-gray-600 border-gray-200";
  return (
    <span className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${colour}`}>
      {label}
    </span>
  );
}

function stepBadge(stepStatus: string) {
  if (stepStatus === "approved")
    return (
      <span className="rounded-full bg-green-600 px-2 py-0.5 text-[10px] font-bold text-white">
        ✓ Approved
      </span>
    );
  if (stepStatus === "pending")
    return (
      <span className="rounded-full bg-amber-400 px-2 py-0.5 text-[10px] font-bold text-white">
        Pending
      </span>
    );
  return (
    <span className="rounded-full bg-gray-300 px-2 py-0.5 text-[10px] font-bold text-gray-700">
      {stepStatus}
    </span>
  );
}

export default function ReviewerDashboard() {
  const toast = useToast();
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api
      .get("/workflow/my-agreements")
      .then(({ data }) => setItems(data))
      .catch(() => toast.error("Failed to load agreements."))
      .finally(() => setLoading(false));
  }, []);

  const filtered = items.filter(
    (i) =>
      !search ||
      i.agreement.reference_number.toLowerCase().includes(search.toLowerCase()) ||
      (i.agreement.project_name ?? "").toLowerCase().includes(search.toLowerCase()) ||
      (i.agreement.subcontractor_name ?? "").toLowerCase().includes(search.toLowerCase()),
  );

  const openPdf = async (agreementId: string, ref: string) => {
    try {
      await viewPdf(`/pdf/${agreementId}/preview`);
    } catch {
      toast.error(`No PDF available for ${ref} yet.`);
    }
  };

  return (
    <div className="space-y-4 p-5">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-sky-900">My Agreements</h1>
        <input
          className="rounded-lg border border-sky-200 px-3 py-1.5 text-sm"
          placeholder="Search reference, project, subcontractor…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>

      {loading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : filtered.length === 0 ? (
        <p className="text-sm text-gray-400">No agreements found for your role.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-sky-100 bg-white shadow-sm">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-sky-50 text-left text-xs text-sky-900">
                <th className="border-b p-3 font-semibold">Reference</th>
                <th className="border-b p-3 font-semibold">Project</th>
                <th className="border-b p-3 font-semibold">Subcontractor</th>
                <th className="border-b p-3 font-semibold">Agreement Status</th>
                <th className="border-b p-3 font-semibold">My Step</th>
                <th className="border-b p-3 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item) => (
                <tr
                  key={item.step.id}
                  className={`border-b transition-colors last:border-0 hover:bg-gray-50 ${
                    item.step.status === "approved" ? "bg-green-50/30" : ""
                  }`}
                >
                  <td className="p-3 font-medium">{item.agreement.reference_number}</td>
                  <td className="p-3 text-gray-600">{item.agreement.project_name ?? "—"}</td>
                  <td className="p-3 text-gray-600">{item.agreement.subcontractor_name ?? "—"}</td>
                  <td className="p-3">{statusBadge(item.agreement.current_status)}</td>
                  <td className="p-3">{stepBadge(item.step.status)}</td>
                  <td className="p-3">
                    <div className="flex flex-wrap gap-1.5">
                      <button
                        className="rounded border border-sky-200 bg-white px-2 py-1 text-xs text-sky-700 hover:bg-sky-50"
                        onClick={() => openPdf(item.agreement.id, item.agreement.reference_number)}
                      >
                        View PDF
                      </button>
                      <Link
                        to={`/agreements/${item.agreement.id}/document`}
                        className="rounded border border-sky-200 bg-white px-2 py-1 text-xs text-sky-700 hover:bg-sky-50"
                      >
                        Document
                      </Link>
                      <Link
                        to={`/agreements/${item.agreement.id}/compare`}
                        className="rounded border border-sky-200 bg-white px-2 py-1 text-xs text-sky-700 hover:bg-sky-50"
                      >
                        Compare
                      </Link>
                      {item.step.status === "pending" && (
                        <Link
                          to="/workflow"
                          className="rounded border border-amber-200 bg-amber-50 px-2 py-1 text-xs font-medium text-amber-700 hover:bg-amber-100"
                        >
                          Review →
                        </Link>
                      )}
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
