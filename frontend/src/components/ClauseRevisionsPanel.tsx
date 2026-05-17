/**
 * Per-agreement clause revisions panel (Phase 4 v2).
 *
 * Drops into the Document view. Three sections:
 *   1. Existing revisions on this agreement (status badges + edit / delete).
 *   2. A clause picker — every revisable paragraph in the master docx,
 *      grouped by section. Click to open an edit modal.
 *   3. Inline edit modal with the original text on top + a textarea for
 *      the modified text + change-reason input.
 *
 * v2.0 deliberately does NOT show accept/reject buttons. That's v2.1.
 */
import { useEffect, useMemo, useState } from "react";

import { useToast } from "./Toast";
import { api } from "../lib/api";
import { formatDateTime } from "../lib/formatDate";
import { useAuth, type Role } from "../stores/auth";

const REVIEWER_ROLES: Role[] = [
  "admin",
  "project_director",
  "accounts",
  "operation_manager",
  "gm",
];

type Clause = {
  clause_hash: string;
  clause_label: string;
  text: string;
  section: string;
  position: number;
  has_pending: boolean;
  has_accepted: boolean;
};

type Revision = {
  id: string;
  clause_hash: string;
  clause_label: string;
  original_text: string;
  modified_text: string;
  change_reason: string | null;
  status: "pending" | "accepted" | "rejected";
  created_by: string | null;
  created_at: string | null;
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
};

type Props = {
  agreementId: string;
  /** Called whenever a revision is created / updated / deleted so the
   *  parent can trigger a PDF regenerate. */
  onChange?: () => void;
};

const STATUS_BADGE: Record<Revision["status"], string> = {
  pending: "bg-amber-100 text-amber-900",
  accepted: "bg-emerald-100 text-emerald-900",
  rejected: "bg-rose-100 text-rose-900",
};

export default function ClauseRevisionsPanel({ agreementId, onChange }: Props) {
  const toast = useToast();
  const currentUser = useAuth((s) => s.user);
  const canReview = currentUser ? REVIEWER_ROLES.includes(currentUser.role) : false;

  const [clauses, setClauses] = useState<Clause[]>([]);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState<
    | { mode: "create"; clause: Clause }
    | { mode: "update"; revision: Revision }
    | null
  >(null);
  const [draftText, setDraftText] = useState("");
  const [draftReason, setDraftReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [sectionFilter, setSectionFilter] = useState<string>("all");
  const [search, setSearch] = useState("");

  // Accept/reject confirmation modal state. Decision note is optional but
  // strongly encouraged so the audit log has something to read in the
  // archive view.
  const [decision, setDecision] = useState<
    | { rev: Revision; action: "accept" | "reject" }
    | null
  >(null);
  const [decisionNote, setDecisionNote] = useState("");

  // ---------------------------- data load ----------------------------
  const reload = async () => {
    setLoading(true);
    try {
      const [clausesResp, revsResp] = await Promise.all([
        api.get<{ clauses: Clause[] }>(`/agreements/${agreementId}/clauses`),
        api.get<{ revisions: Revision[] }>(`/agreements/${agreementId}/revisions`),
      ]);
      setClauses(clausesResp.data.clauses ?? []);
      setRevisions(revsResp.data.revisions ?? []);
    } catch (err) {
      console.error(err);
      toast.error("Failed to load clause revisions.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!agreementId) return;
    void reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [agreementId]);

  // ----------------------- derived filtered list ---------------------
  const sections = useMemo(() => {
    const s = new Set<string>();
    for (const c of clauses) s.add(c.section);
    return ["all", ...Array.from(s)];
  }, [clauses]);

  const filteredClauses = useMemo(() => {
    const q = search.trim().toLowerCase();
    return clauses.filter((c) => {
      if (sectionFilter !== "all" && c.section !== sectionFilter) return false;
      if (q && !c.text.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [clauses, sectionFilter, search]);

  // ----------------------------- actions -----------------------------
  const openCreate = (clause: Clause) => {
    setEditing({ mode: "create", clause });
    setDraftText(clause.text);
    setDraftReason("");
  };

  const openUpdate = (rev: Revision) => {
    setEditing({ mode: "update", revision: rev });
    setDraftText(rev.modified_text);
    setDraftReason(rev.change_reason ?? "");
  };

  const cancelEdit = () => {
    setEditing(null);
    setDraftText("");
    setDraftReason("");
  };

  const submit = async () => {
    if (!editing) return;
    setSubmitting(true);
    try {
      if (editing.mode === "create") {
        await api.post(`/agreements/${agreementId}/revisions`, {
          clause_hash: editing.clause.clause_hash,
          modified_text: draftText,
          change_reason: draftReason || null,
        });
        toast.success("Revision created — pending review.");
      } else {
        await api.patch(
          `/agreements/${agreementId}/revisions/${editing.revision.id}`,
          {
            modified_text: draftText,
            change_reason: draftReason || null,
          }
        );
        toast.success("Revision updated.");
      }
      cancelEdit();
      await reload();
      onChange?.();
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } } };
      const detail = apiErr.response?.data?.detail ?? "Failed to save revision.";
      toast.error(detail);
    } finally {
      setSubmitting(false);
    }
  };

  const withdraw = async (rev: Revision) => {
    if (rev.status !== "pending") return;
    if (!window.confirm(`Withdraw revision on "${rev.clause_label}"?`)) return;
    try {
      await api.delete(`/agreements/${agreementId}/revisions/${rev.id}`);
      toast.success("Revision withdrawn.");
      await reload();
      onChange?.();
    } catch {
      toast.error("Failed to withdraw revision.");
    }
  };

  const openDecision = (rev: Revision, action: "accept" | "reject") => {
    setDecision({ rev, action });
    setDecisionNote("");
  };

  const cancelDecision = () => {
    setDecision(null);
    setDecisionNote("");
  };

  const submitDecision = async () => {
    if (!decision) return;
    setSubmitting(true);
    try {
      const endpoint = decision.action === "accept" ? "accept" : "reject";
      await api.post(
        `/agreements/${agreementId}/revisions/${decision.rev.id}/${endpoint}`,
        { decision_note: decisionNote.trim() || null }
      );
      toast.success(
        decision.action === "accept" ? "Revision accepted." : "Revision rejected."
      );
      cancelDecision();
      await reload();
      onChange?.();
    } catch (err: unknown) {
      const apiErr = err as { response?: { data?: { detail?: string } } };
      const detail = apiErr.response?.data?.detail ?? "Failed to record decision.";
      toast.error(detail);
    } finally {
      setSubmitting(false);
    }
  };

  /** Reviewer can decide IF role is in REVIEWER_ROLES AND they didn't
   *  author the revision themselves (segregation of duties — mirrored
   *  in the backend's _ensure_can_decide). */
  const canDecide = (rev: Revision): boolean => {
    if (!currentUser || !canReview) return false;
    if (rev.status !== "pending") return false;
    return rev.created_by !== currentUser.id;
  };

  // ------------------------------ render -----------------------------
  if (loading) {
    return <div className="text-sm text-sky-700">Loading clauses…</div>;
  }

  return (
    <div className="space-y-4">
      {/* Existing revisions */}
      <div>
        <h3 className="mb-1 text-sm font-semibold text-sky-900">
          Revisions on this agreement
          {revisions.length > 0 && (
            <span className="ml-2 text-xs font-normal text-sky-700">
              ({revisions.length})
            </span>
          )}
        </h3>
        {revisions.length === 0 ? (
          <p className="text-xs text-gray-500">
            No revisions yet. Pick a clause below to propose an edit.
          </p>
        ) : (
          <ul className="space-y-2">
            {revisions.map((rev) => (
              <li
                key={rev.id}
                className="rounded border border-sky-100 bg-white p-2"
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <div className="text-[10px] uppercase text-sky-700">
                      {rev.clause_label}
                    </div>
                    <div className="mt-1 text-xs">
                      <div className="rounded bg-sky-50 p-1 text-sky-900">
                        <span className="text-[10px] uppercase text-sky-600">
                          original
                        </span>
                        <div className="whitespace-pre-wrap">
                          {rev.original_text}
                        </div>
                      </div>
                      <div className="mt-1 rounded bg-amber-50 p-1 text-amber-900">
                        <span className="text-[10px] uppercase text-amber-700">
                          modified
                        </span>
                        <div className="whitespace-pre-wrap">
                          {rev.modified_text}
                        </div>
                      </div>
                      {rev.change_reason && (
                        <div className="mt-1 text-[11px] italic text-gray-600">
                          Reason: {rev.change_reason}
                        </div>
                      )}
                    </div>
                    <div className="mt-1 flex items-center gap-2 text-[10px] text-gray-500">
                      <span
                        className={`rounded px-1.5 py-0.5 font-semibold ${STATUS_BADGE[rev.status]}`}
                      >
                        {rev.status}
                      </span>
                      {rev.created_at && (
                        <span>created {formatDateTime(rev.created_at)}</span>
                      )}
                      {rev.decided_at && (
                        <span>
                          {rev.status} {formatDateTime(rev.decided_at)}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
                {rev.status === "pending" && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {currentUser?.id === rev.created_by && (
                      <>
                        <button
                          type="button"
                          className="rounded border border-sky-300 px-2 py-0.5 text-[11px] text-sky-700 hover:bg-sky-50"
                          onClick={() => openUpdate(rev)}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="rounded border border-rose-300 px-2 py-0.5 text-[11px] text-rose-700 hover:bg-rose-50"
                          onClick={() => void withdraw(rev)}
                        >
                          Withdraw
                        </button>
                      </>
                    )}
                    {canDecide(rev) && (
                      <>
                        <button
                          type="button"
                          className="rounded border border-emerald-300 bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-800 hover:bg-emerald-100"
                          onClick={() => openDecision(rev, "accept")}
                        >
                          Accept
                        </button>
                        <button
                          type="button"
                          className="rounded border border-rose-300 bg-rose-50 px-2 py-0.5 text-[11px] font-semibold text-rose-800 hover:bg-rose-100"
                          onClick={() => openDecision(rev, "reject")}
                        >
                          Reject
                        </button>
                      </>
                    )}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Clause picker */}
      <div className="rounded border border-sky-100 bg-sky-50/30 p-2">
        <h3 className="text-sm font-semibold text-sky-900">Revise a clause</h3>
        <p className="mb-2 text-xs text-sky-700">
          Pick any clause from the master template to propose an edit. Pending
          revisions show up above and are applied to the rendered PDF once
          accepted by a reviewer (Phase 4 v2.1).
        </p>
        <div className="mb-2 flex gap-2">
          <select
            className="rounded border border-sky-200 px-2 py-1 text-xs"
            value={sectionFilter}
            onChange={(e) => setSectionFilter(e.target.value)}
          >
            {sections.map((s) => (
              <option key={s} value={s}>
                {s === "all" ? "All sections" : s}
              </option>
            ))}
          </select>
          <input
            type="search"
            className="flex-1 rounded border border-sky-200 px-2 py-1 text-xs"
            placeholder="Search clause text…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className="max-h-72 overflow-y-auto rounded border border-sky-100 bg-white">
          <ul className="divide-y divide-sky-100">
            {filteredClauses.length === 0 ? (
              <li className="p-3 text-xs text-gray-500">
                No clauses match your filter.
              </li>
            ) : (
              filteredClauses.slice(0, 200).map((clause) => (
                <li
                  key={clause.clause_hash}
                  className="cursor-pointer p-2 hover:bg-sky-50"
                  onClick={() => openCreate(clause)}
                >
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] uppercase text-sky-700">
                      {clause.section}
                    </span>
                    {clause.has_pending && (
                      <span className="rounded bg-amber-100 px-1 text-[10px] text-amber-800">
                        pending
                      </span>
                    )}
                    {clause.has_accepted && (
                      <span className="rounded bg-emerald-100 px-1 text-[10px] text-emerald-800">
                        accepted
                      </span>
                    )}
                  </div>
                  <div className="line-clamp-2 text-xs text-gray-800">
                    {clause.text}
                  </div>
                </li>
              ))
            )}
            {filteredClauses.length > 200 && (
              <li className="p-2 text-[11px] text-gray-500">
                Showing first 200 — refine the filter to see more.
              </li>
            )}
          </ul>
        </div>
      </div>

      {/* Accept / reject confirmation modal */}
      {decision && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-xl bg-white p-4 shadow-xl">
            <h3 className="mb-2 text-base font-semibold text-sky-900">
              {decision.action === "accept" ? "Accept revision" : "Reject revision"}
            </h3>
            <div className="mb-3 rounded bg-sky-50 p-2 text-xs text-sky-900">
              <div className="text-[10px] uppercase text-sky-700">
                {decision.rev.clause_label}
              </div>
              <div className="mt-1 grid grid-cols-1 gap-1">
                <div className="rounded bg-white p-1">
                  <span className="text-[10px] uppercase text-sky-600">original</span>
                  <div className="whitespace-pre-wrap">{decision.rev.original_text}</div>
                </div>
                <div className="rounded bg-amber-50 p-1">
                  <span className="text-[10px] uppercase text-amber-700">modified</span>
                  <div className="whitespace-pre-wrap text-amber-900">
                    {decision.rev.modified_text}
                  </div>
                </div>
              </div>
            </div>
            <label className="mb-1 block text-xs font-medium text-sky-900">
              Decision note (optional — visible in the audit log)
            </label>
            <textarea
              className="mb-3 w-full rounded border border-sky-200 p-2 text-sm"
              rows={3}
              placeholder={
                decision.action === "accept"
                  ? "e.g. Approved by PD on legal review."
                  : "e.g. Out of scope for this round; revisit in v2."
              }
              value={decisionNote}
              onChange={(e) => setDecisionNote(e.target.value)}
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="rounded border border-sky-300 px-3 py-1 text-sm text-sky-700 hover:bg-sky-50"
                onClick={cancelDecision}
              >
                Cancel
              </button>
              <button
                type="button"
                className={`rounded px-3 py-1 text-sm font-semibold text-white disabled:opacity-50 ${
                  decision.action === "accept"
                    ? "bg-emerald-600 hover:bg-emerald-700"
                    : "bg-rose-600 hover:bg-rose-700"
                }`}
                disabled={submitting}
                onClick={() => void submitDecision()}
              >
                {submitting
                  ? "Saving…"
                  : decision.action === "accept"
                    ? "Confirm accept"
                    : "Confirm reject"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit modal */}
      {editing && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-xl bg-white p-4 shadow-xl">
            <h3 className="mb-2 text-base font-semibold text-sky-900">
              {editing.mode === "create"
                ? "Propose a revision"
                : "Edit revision"}
            </h3>
            <div className="mb-3 rounded bg-sky-50 p-2 text-xs">
              <div className="text-[10px] uppercase text-sky-700">Original</div>
              <div className="whitespace-pre-wrap text-sky-900">
                {editing.mode === "create"
                  ? editing.clause.text
                  : editing.revision.original_text}
              </div>
            </div>
            <label className="mb-1 block text-xs font-medium text-amber-900">
              Modified text
            </label>
            <textarea
              className="mb-3 w-full rounded border border-amber-300 p-2 text-sm"
              rows={6}
              value={draftText}
              onChange={(e) => setDraftText(e.target.value)}
            />
            <label className="mb-1 block text-xs font-medium text-sky-900">
              Reason (optional — visible to reviewers)
            </label>
            <textarea
              className="mb-3 w-full rounded border border-sky-200 p-2 text-sm"
              rows={2}
              placeholder="e.g. Per legal review 17 May 2026 — extend retention to 24 months"
              value={draftReason}
              onChange={(e) => setDraftReason(e.target.value)}
            />
            <div className="flex justify-end gap-2">
              <button
                type="button"
                className="rounded border border-sky-300 px-3 py-1 text-sm text-sky-700 hover:bg-sky-50"
                onClick={cancelEdit}
              >
                Cancel
              </button>
              <button
                type="button"
                className="rounded bg-sky-600 px-3 py-1 text-sm text-white hover:bg-sky-700 disabled:opacity-50"
                disabled={submitting || !draftText.trim()}
                onClick={() => void submit()}
              >
                {submitting
                  ? "Saving…"
                  : editing.mode === "create"
                    ? "Submit revision"
                    : "Save changes"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
