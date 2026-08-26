/**
 * GM Portal Dashboard — Phase 2 Package B (req 6.1), revised per client
 * feedback (2026-08-26): the GM portal must not surface any other option
 * such as Workflow Review, so GM's approve/reject actions and the reviewer
 * comment trail now live directly on this page instead of a separate page.
 * Still exactly five identifying columns (Project Code / Agreement Ref /
 * Project Name / Scope of Works / Subcontractor Name) plus an actions area:
 * View PDF (red-highlighted admin-entered content, Package C), Compare
 * (the full Original-vs-Revised view, not the mostly-empty formal-clause-
 * revisions-only table most agreements never populate), and — expanded per
 * row — the reviewer comment trail plus Approve / Approve with Comments /
 * Reject with Comments, mirroring WorkflowReview.tsx's 3-button model.
 */
import { Fragment, useEffect, useState } from "react";
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
};

type WorkflowComment = {
  id: string;
  comment_text: string;
  clause_reference: string | null;
  author_name: string | null;
  author_role: string | null;
  created_at: string | null;
};

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  project_director: "Project Director",
  accounts: "Accounts",
  operation_manager: "Operation Manager",
  gm: "GM",
};

function humanRole(role: string | null): string {
  if (!role) return "Unknown";
  return ROLE_LABELS[role] ?? role;
}

// Resolution-chain GM steps carry this exact name (see resolution_service.py).
function stepKindLabel(stepName: string): string {
  return stepName.startsWith("Resolution") ? "Resolution Approval" : "Final Approval";
}

export default function GMDashboard() {
  const toast = useToast();
  const [rows, setRows] = useState<GMRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [comments, setComments] = useState<WorkflowComment[]>([]);
  const [commentsLoading, setCommentsLoading] = useState(false);
  const [commentText, setCommentText] = useState("");
  const [busyStepId, setBusyStepId] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    api
      .get("/workflow/gm-dashboard")
      .then(({ data }) => setRows(data))
      .catch(() => toast.error("Failed to load your pending agreements."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openHighlightedPdf = async (agreementId: string, ref: string) => {
    try {
      await viewPdf(`/pdf/${agreementId}/preview/gm-highlighted`);
    } catch {
      toast.error(`No PDF available for ${ref} yet.`);
    }
  };

  const toggleExpand = async (row: GMRow) => {
    if (expandedId === row.step_id) {
      setExpandedId(null);
      return;
    }
    setExpandedId(row.step_id);
    setCommentText("");
    setCommentsLoading(true);
    try {
      const { data } = await api.get(`/workflow/agreements/${row.agreement_id}`);
      setComments(data.comments ?? []);
    } catch {
      toast.error("Failed to load comments for this agreement.");
      setComments([]);
    } finally {
      setCommentsLoading(false);
    }
  };

  const approve = async (row: GMRow, withComment: boolean) => {
    if (withComment && !commentText.trim()) {
      toast.error("Please enter a comment.");
      return;
    }
    setBusyStepId(row.step_id);
    try {
      await api.post(
        `/workflow/${row.step_id}/approve`,
        withComment ? { comment_text: commentText } : undefined
      );
      toast.success(withComment ? `Approved ${row.reference_number} with comments.` : `Approved ${row.reference_number}.`);
      setCommentText("");
      setExpandedId(null);
      load();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Failed to approve.");
    } finally {
      setBusyStepId(null);
    }
  };

  const reject = async (row: GMRow) => {
    if (!commentText.trim()) {
      toast.error("Please enter a reason for rejection.");
      return;
    }
    setBusyStepId(row.step_id);
    try {
      await api.post(`/workflow/${row.step_id}/return`, { comment_text: commentText });
      toast.success(`Rejected ${row.reference_number}. Sent back to Admin for revision.`);
      setCommentText("");
      setExpandedId(null);
      load();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Failed to reject.");
    } finally {
      setBusyStepId(null);
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
              {rows.map((row) => {
                const expanded = expandedId === row.step_id;
                const busy = busyStepId === row.step_id;
                return (
                  <Fragment key={row.step_id}>
                    <tr className="border-b transition-colors last:border-0 hover:bg-gray-50">
                      <td className="p-3">{row.project_code ?? <span className="text-gray-400">—</span>}</td>
                      <td className="p-3 font-medium">
                        {row.reference_number}
                        <div className="text-[10px] font-normal text-gray-400">{stepKindLabel(row.step_name)}</div>
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
                            to={`/agreements/${row.agreement_id}/compare`}
                            className="rounded border border-sky-200 bg-white px-2 py-1 text-xs text-sky-700 hover:bg-sky-50"
                          >
                            Compare
                          </Link>
                          <button
                            className="rounded border border-sky-300 bg-sky-50 px-2 py-1 text-xs font-medium text-sky-800 hover:bg-sky-100"
                            onClick={() => toggleExpand(row)}
                          >
                            {expanded ? "Hide Review" : "Review & Decide"}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expanded && (
                      <tr>
                        <td colSpan={6} className="border-b bg-sky-50/40 p-4">
                          <div className="space-y-3">
                            <div>
                              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-sky-800">
                                Reviewer Comments
                              </h3>
                              {commentsLoading ? (
                                <p className="text-xs text-gray-400">Loading comments…</p>
                              ) : comments.length === 0 ? (
                                <p className="text-xs text-gray-400">No comments on this agreement.</p>
                              ) : (
                                <div className="max-h-48 space-y-2 overflow-y-auto rounded border bg-white p-2">
                                  {comments.map((c) => (
                                    <div key={c.id} className="rounded border-l-2 border-sky-300 bg-sky-50/60 p-2 text-xs">
                                      <div className="font-medium text-sky-900">
                                        {c.author_name ?? "Unknown"}{" "}
                                        <span className="font-normal text-gray-400">({humanRole(c.author_role)})</span>
                                        {c.clause_reference && (
                                          <span className="ml-1 text-gray-400">— {c.clause_reference}</span>
                                        )}
                                      </div>
                                      <div className="mt-0.5 whitespace-pre-wrap text-gray-700">{c.comment_text}</div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>

                            <div>
                              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-sky-800">
                                Your Decision
                              </h3>
                              <textarea
                                className="w-full rounded border p-2 text-xs"
                                rows={2}
                                placeholder="Comment (required for 'Approved with comments' or 'Rejected with comments')"
                                value={commentText}
                                onChange={(e) => setCommentText(e.target.value)}
                                disabled={busy}
                              />
                              <div className="mt-2 flex flex-wrap gap-2">
                                <button
                                  className="rounded bg-green-600 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
                                  disabled={busy}
                                  onClick={() => approve(row, false)}
                                >
                                  Approved
                                </button>
                                <button
                                  className="rounded bg-green-100 px-3 py-1.5 text-xs font-medium text-green-800 disabled:opacity-50"
                                  disabled={busy}
                                  onClick={() => approve(row, true)}
                                >
                                  Approved with comments
                                </button>
                                <button
                                  className="rounded bg-red-100 px-3 py-1.5 text-xs font-medium text-red-800 disabled:opacity-50"
                                  disabled={busy}
                                  onClick={() => reject(row)}
                                >
                                  Rejected with comments
                                </button>
                              </div>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
