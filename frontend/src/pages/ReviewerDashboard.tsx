import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../lib/api";
import { viewPdf } from "../lib/pdf";
import { useToast } from "../components/Toast";
import { useAuth } from "../stores/auth";

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

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  project_director: "Project Director",
  accounts: "Accounts",
  operation_manager: "Operation Manager",
  gm: "GM",
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
    <span
      className={`inline-block whitespace-nowrap rounded-md border px-2 py-1 text-[11px] font-semibold leading-tight ${colour}`}
    >
      {label}
    </span>
  );
}

function stepBadge(stepStatus: string) {
  if (stepStatus === "approved")
    return (
      <span className="inline-block whitespace-nowrap rounded-md bg-green-600 px-2 py-1 text-[11px] font-bold leading-tight text-white">
        ✓ Approved
      </span>
    );
  if (stepStatus === "pending")
    return (
      <span className="inline-block whitespace-nowrap rounded-md bg-amber-400 px-2 py-1 text-[11px] font-bold leading-tight text-white">
        Pending
      </span>
    );
  return (
    <span className="inline-block whitespace-nowrap rounded-md bg-gray-300 px-2 py-1 text-[11px] font-bold leading-tight text-gray-700">
      {stepStatus}
    </span>
  );
}

export default function ReviewerDashboard() {
  const toast = useToast();
  const role = useAuth((s) => s.user?.role);
  const [items, setItems] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [pendingWithById, setPendingWithById] = useState<Record<string, string>>({});

  // Filters — same logic as admin Dashboard: click name to set, chip to clear
  const [projectFilter, setProjectFilter] = useState("");
  const [subcontractorFilter, setSubcontractorFilter] = useState("");
  const [search, setSearch] = useState("");

  useEffect(() => {
    api
      .get("/workflow/my-agreements")
      .then(({ data }) => setItems(data))
      .catch(() => toast.error("Failed to load agreements."))
      .finally(() => setLoading(false));
    // Client feedback: every agreement already has a step for this role
    // (created at submission), so the list above already covers "pending
    // for me". What's missing is showing WHICH department it's actually
    // sitting with right now — reuse Archive's existing computation rather
    // than re-deriving chain order client-side.
    api
      .get("/archive/agreements")
      .then(({ data }) => {
        const map: Record<string, string> = {};
        for (const row of data as { id: string; pending_with: string }[]) {
          map[row.id] = row.pending_with;
        }
        setPendingWithById(map);
      })
      .catch(() => {
        /* non-critical — the actionable list above still loads fine without it */
      });
  }, []);

  const myRoleLabel = role ? ROLE_LABELS[role] : undefined;
  const isMyTurn = (agreementId: string) =>
    !!myRoleLabel && pendingWithById[agreementId] === `Pending with ${myRoleLabel}`;

  // Distinct sorted names for the dropdowns / click targets
  const projectNames = Array.from(
    new Set(items.map((i) => i.agreement.project_name).filter((n): n is string => !!n)),
  ).sort((a, b) => a.localeCompare(b));

  const subcontractorNames = Array.from(
    new Set(items.map((i) => i.agreement.subcontractor_name).filter((n): n is string => !!n)),
  ).sort((a, b) => a.localeCompare(b));

  const displayed = items.filter((i) => {
    if (projectFilter && (i.agreement.project_name ?? "") !== projectFilter) return false;
    if (subcontractorFilter && (i.agreement.subcontractor_name ?? "") !== subcontractorFilter)
      return false;
    if (search) {
      const q = search.toLowerCase();
      const hit =
        i.agreement.reference_number.toLowerCase().includes(q) ||
        (i.agreement.project_name ?? "").toLowerCase().includes(q) ||
        (i.agreement.subcontractor_name ?? "").toLowerCase().includes(q);
      if (!hit) return false;
    }
    return true;
  });

  const openPdf = async (agreementId: string, ref: string) => {
    try {
      await viewPdf(`/pdf/${agreementId}/preview`);
    } catch {
      toast.error(`No PDF available for ${ref} yet.`);
    }
  };

  const hasFilters = projectFilter || subcontractorFilter;

  return (
    <div className="space-y-4 p-5">
      {/* Header + search */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-bold text-sky-900">My Agreements</h1>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="rounded-lg border border-sky-200 bg-white px-2 py-1.5 text-sm"
            value={projectFilter}
            onChange={(e) => setProjectFilter(e.target.value)}
            title="Filter by project"
          >
            <option value="">All projects</option>
            {projectNames.map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
          <select
            className="rounded-lg border border-sky-200 bg-white px-2 py-1.5 text-sm"
            value={subcontractorFilter}
            onChange={(e) => setSubcontractorFilter(e.target.value)}
            title="Filter by subcontractor"
          >
            <option value="">All subcontractors</option>
            {subcontractorNames.map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
          <input
            className="rounded-lg border border-sky-200 px-3 py-1.5 text-sm"
            placeholder="Search reference…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      {/* Active filter chips */}
      {hasFilters && (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-sky-200 bg-sky-50 p-2 text-sm text-sky-800">
          <span>
            Showing {displayed.length} agreement{displayed.length === 1 ? "" : "s"} for:
          </span>
          {projectFilter && (
            <span className="inline-flex items-center gap-1 rounded-full bg-sky-200 px-2 py-0.5 text-xs font-semibold">
              Project: {projectFilter}
              <button
                className="hover:text-sky-900"
                onClick={() => setProjectFilter("")}
                title="Clear project filter"
              >
                ✕
              </button>
            </span>
          )}
          {subcontractorFilter && (
            <span className="inline-flex items-center gap-1 rounded-full bg-sky-200 px-2 py-0.5 text-xs font-semibold">
              Subcontractor: {subcontractorFilter}
              <button
                className="hover:text-sky-900"
                onClick={() => setSubcontractorFilter("")}
                title="Clear subcontractor filter"
              >
                ✕
              </button>
            </span>
          )}
          {projectFilter && subcontractorFilter && (
            <button
              className="rounded-full bg-sky-100 px-2 py-0.5 text-xs font-semibold underline-offset-2 hover:underline"
              onClick={() => { setProjectFilter(""); setSubcontractorFilter(""); }}
            >
              Clear all
            </button>
          )}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-gray-400">Loading…</p>
      ) : displayed.length === 0 ? (
        <p className="text-sm text-gray-400">No agreements match the current filters.</p>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-sky-100 bg-white shadow-sm">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-sky-50 text-left text-xs text-sky-900">
                <th className="border-b p-3 font-semibold">Reference</th>
                <th className="border-b p-3 font-semibold">Project</th>
                <th className="border-b p-3 font-semibold">Subcontractor</th>
                <th className="w-52 border-b p-3 font-semibold">Agreement Status</th>
                <th className="border-b p-3 font-semibold">Pending With</th>
                <th className="w-28 border-b p-3 font-semibold">My Step</th>
                <th className="border-b p-3 font-semibold">Actions</th>
              </tr>
            </thead>
            <tbody>
              {displayed.map((item) => (
                <tr
                  key={item.step.id}
                  className={`border-b transition-colors last:border-0 hover:bg-gray-50 ${
                    item.step.status === "approved" ? "bg-green-50/30" : ""
                  }`}
                >
                  <td className="p-3 font-medium">{item.agreement.reference_number}</td>

                  {/* Clickable project name — sets project filter */}
                  <td className="p-3">
                    {item.agreement.project_name ? (
                      <button
                        className="text-left text-sky-700 underline-offset-2 hover:underline"
                        onClick={() => setProjectFilter(item.agreement.project_name!)}
                        title="Filter to this project"
                      >
                        {item.agreement.project_name}
                      </button>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>

                  {/* Clickable subcontractor name — sets subcontractor filter */}
                  <td className="p-3">
                    {item.agreement.subcontractor_name ? (
                      <button
                        className="text-left text-sky-700 underline-offset-2 hover:underline"
                        onClick={() => setSubcontractorFilter(item.agreement.subcontractor_name!)}
                        title="Filter to this subcontractor"
                      >
                        {item.agreement.subcontractor_name}
                      </button>
                    ) : (
                      <span className="text-gray-400">—</span>
                    )}
                  </td>

                  <td className="p-3">{statusBadge(item.agreement.current_status)}</td>
                  <td className="p-3 text-xs text-gray-600">
                    {pendingWithById[item.agreement.id] ?? <span className="text-gray-400">—</span>}
                  </td>
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
                      {isMyTurn(item.agreement.id) && (
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
