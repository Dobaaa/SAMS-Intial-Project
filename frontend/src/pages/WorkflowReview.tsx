import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import AgreementPdf from "../components/AgreementPdf";
import AIReviewPanel from "../components/AIReviewPanel";
import AppendixView from "../components/AppendixView";
import { humanRole } from "../lib/roles";
import { useToast } from "../components/Toast";
import WorkflowTimeline from "../components/WorkflowTimeline";
import { api } from "../lib/api";
import { useAuth } from "../stores/auth";

// ─── Domain types ───────────────────────────────────────────────────────────

type PendingItem = {
  step: {
    id: string;
    agreement_id: string;
    step_name: string;
    step_order: number;
    role_required: string;
    status: string;
  };
  agreement: {
    id: string;
    reference_number: string;
    current_status: string;
  };
};

type WorkflowStep = {
  id: string;
  step_name: string;
  step_order: number;
  role_required: string;
  status: string;
  acted_at?: string | null;
};

type WorkflowComment = {
  id: string;
  workflow_step_id: string;
  comment_text: string;
  clause_reference?: string | null;
  status: string;
  created_at?: string | null;
  author_name?: string | null;
  author_role?: string | null;
};

type WorkflowAgreementDetails = {
  agreement: {
    id: string;
    reference_number: string;
    current_status: string;
    gm_approval_date?: string | null;
  };
  steps: WorkflowStep[];
  comments: WorkflowComment[];
};

type FieldRow = {
  field_id: string;
  field_label: string;
  clause_number: string;
  input_type: string;
  default_value: string;
  current_value: string;
};

type AIAnalysis = { comparison: unknown; risks: unknown; cached: boolean };
type AISummary = { data: unknown; cached: boolean };
type ActiveTab = "clauses" | "document" | "ai" | "action";

// ─── Constants ───────────────────────────────────────────────────────────────

const REVIEWER_ROLES = [
  { role: "project_director", short: "Project Director" },
  { role: "accounts", short: "Accounts" },
  { role: "operation_manager", short: "Op. Manager" },
  { role: "gm", short: "GM" },
] as const;

const TABS: { key: ActiveTab; label: string }[] = [
  { key: "clauses", label: "Clause Review" },
  { key: "document", label: "Document" },
  { key: "ai", label: "AI Review" },
  { key: "action", label: "Action" },
];

// ─── Helpers ─────────────────────────────────────────────────────────────────

function truncate(text: string, max = 120) {
  if (!text) return "—";
  return text.length > max ? text.slice(0, max) + "…" : text;
}

// ─── Clause Review Matrix ────────────────────────────────────────────────────

type RoleCommentCellProps = {
  fieldId: string;
  roleKey: string;
  comments: WorkflowComment[];
  isMyRole: boolean;
  myStepId: string | null;
  onAddComment: (fieldId: string, text: string, stepId: string) => Promise<void>;
};

function RoleCommentCell({
  fieldId,
  roleKey,
  comments,
  isMyRole,
  myStepId,
  onAddComment,
}: RoleCommentCellProps) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  const cellComments = comments.filter(
    (c) => c.author_role === roleKey && c.clause_reference === fieldId,
  );

  return (
    <td className="min-w-[160px] max-w-[220px] border-l p-2 align-top text-xs">
      <div className="space-y-1">
        {cellComments.map((c) => (
          <div
            key={c.id}
            className="rounded border border-amber-200 bg-amber-50 p-1.5 text-gray-700"
          >
            <p className="break-words leading-snug">{c.comment_text}</p>
            {c.created_at && (
              <p className="mt-0.5 text-gray-400">
                {new Date(c.created_at).toLocaleDateString()}
              </p>
            )}
          </div>
        ))}
      </div>

      {isMyRole && myStepId && (
        <div className="mt-1.5">
          <textarea
            rows={2}
            className="w-full rounded border px-1.5 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-sky-400"
            placeholder="Add comment…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
          />
          <button
            className="mt-0.5 rounded bg-sky-600 px-2 py-0.5 text-xs text-white hover:bg-sky-700 disabled:opacity-40"
            disabled={!draft.trim() || busy}
            onClick={async () => {
              setBusy(true);
              await onAddComment(fieldId, draft.trim(), myStepId);
              setDraft("");
              setBusy(false);
            }}
          >
            {busy ? "Saving…" : "Add"}
          </button>
        </div>
      )}

      {!cellComments.length && (!isMyRole || !myStepId) && (
        <span className="text-gray-300">—</span>
      )}
    </td>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function WorkflowReview() {
  const toast = useToast();
  const role = useAuth((s) => s.user?.role ?? null);

  const [pending, setPending] = useState<PendingItem[]>([]);
  const [selectedStepId, setSelectedStepId] = useState<string>("");
  const [details, setDetails] = useState<WorkflowAgreementDetails | null>(null);
  const [fieldMatrix, setFieldMatrix] = useState<FieldRow[]>([]);
  const [matrixLoading, setMatrixLoading] = useState(false);

  const [activeTab, setActiveTab] = useState<ActiveTab>("clauses");

  // General (non-clause) comment + approve state
  const [commentText, setCommentText] = useState("");
  const [clauseReference, setClauseReference] = useState("");
  const [busy, setBusy] = useState(false);

  // AI state
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [summary, setSummary] = useState<AISummary | null>(null);
  const [aiBusy, setAiBusy] = useState<"" | "analyze" | "summary">("");

  // ── Data loading ────────────────────────────────────────────────────────────

  const loadDetails = async (agreementId: string) => {
    const detailsResp = await api.get(`/workflow/agreements/${agreementId}`);
    setDetails(detailsResp.data);
    return detailsResp.data as WorkflowAgreementDetails;
  };

  const loadFieldMatrix = async (agreementId: string) => {
    setMatrixLoading(true);
    try {
      const { data } = await api.get(`/workflow/agreements/${agreementId}/fields`);
      setFieldMatrix((data.fields as FieldRow[]) || []);
    } catch {
      setFieldMatrix([]);
    } finally {
      setMatrixLoading(false);
    }
  };

  const loadPending = async () => {
    const { data } = await api.get("/workflow/pending");
    setPending(data);
    if (data.length > 0 && !selectedStepId) {
      const first = data[0] as PendingItem;
      setSelectedStepId(first.step.id);
      await loadDetails(first.agreement.id);
      await loadFieldMatrix(first.agreement.id);
    }
  };

  useEffect(() => {
    void loadPending();
  }, []);

  const selectPending = async (item: PendingItem) => {
    setSelectedStepId(item.step.id);
    setAnalysis(null);
    setSummary(null);
    setActiveTab("clauses");
    await loadDetails(item.agreement.id);
    await loadFieldMatrix(item.agreement.id);
  };

  // ── AI actions ──────────────────────────────────────────────────────────────

  const runAnalyze = async () => {
    if (!details || aiBusy) return;
    setAiBusy("analyze");
    try {
      const { data } = await api.post(`/ai/${details.agreement.id}/analyze`);
      setAnalysis({
        comparison: data?.data?.comparison ?? null,
        risks: data?.data?.risks ?? null,
        cached: !!data?.cached,
      });
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "AI analyze failed.");
    } finally {
      setAiBusy("");
    }
  };

  const runSummary = async () => {
    if (!details || aiBusy || !role) return;
    setAiBusy("summary");
    try {
      const { data } = await api.get(`/ai/${details.agreement.id}/summary`, {
        params: { role },
      });
      setSummary({ data: data?.data ?? null, cached: !!data?.cached });
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "AI summary failed.");
    } finally {
      setAiBusy("");
    }
  };

  // ── Workflow actions ────────────────────────────────────────────────────────

  const approve = async () => {
    if (!selectedStepId || busy) return;
    setBusy(true);
    try {
      const ref = details?.agreement.reference_number ?? "";
      await api.post(`/workflow/${selectedStepId}/approve`);
      toast.success(`Approved ${ref}.`);
      setSelectedStepId("");
      setDetails(null);
      setFieldMatrix([]);
      await loadPending();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Failed to approve.");
    } finally {
      setBusy(false);
    }
  };

  const addGeneralComment = async () => {
    if (!selectedStepId || busy) return;
    if (!commentText.trim()) {
      toast.error("Please enter a comment.");
      return;
    }
    setBusy(true);
    try {
      const ref = details?.agreement.reference_number ?? "";
      const agreementId = details?.agreement.id;
      await api.post(`/workflow/${selectedStepId}/comment`, {
        comment_text: commentText,
        clause_reference: clauseReference || undefined,
      });
      toast.success(`Comment added to ${ref}.`);
      setCommentText("");
      setClauseReference("");
      if (agreementId) await loadDetails(agreementId);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Failed to add comment.");
    } finally {
      setBusy(false);
    }
  };

  // Called from inline RoleCommentCell inputs in the matrix
  const addClauseComment = async (fieldId: string, text: string, stepId: string) => {
    try {
      await api.post(`/workflow/${stepId}/comment`, {
        comment_text: text,
        clause_reference: fieldId,
      });
      if (details?.agreement.id) await loadDetails(details.agreement.id);
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Failed to add comment.");
    }
  };

  // ── Derived values ──────────────────────────────────────────────────────────

  // Step that belongs to the current logged-in role (for posting comments)
  const myStep = details?.steps.find((s) => s.role_required === role) ?? null;

  // Group fields by prefix (F = Form, C = Conditions)
  const formFields = fieldMatrix.filter((f) => f.field_id.startsWith("F"));
  const conditionFields = fieldMatrix.filter((f) => f.field_id.startsWith("C"));

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="grid grid-cols-12 gap-4 p-4">
      {/* Sidebar: pending agreements */}
      <aside className="col-span-2 rounded border p-3">
        <h2 className="mb-3 text-lg font-semibold">My Pending</h2>
        <div className="space-y-2">
          {pending.map((item) => (
            <button
              key={item.step.id}
              className={`w-full rounded border p-2 text-left text-sm ${
                selectedStepId === item.step.id ? "bg-sky-50 border-sky-300" : ""
              }`}
              onClick={() => selectPending(item)}
            >
              <div className="font-medium">{item.agreement.reference_number}</div>
              <div className="text-xs text-gray-500">
                {item.step.step_name} · {humanRole(item.step.role_required)}
              </div>
            </button>
          ))}
        </div>
      </aside>

      {/* Main panel */}
      <main className="col-span-10 space-y-0">
        {details ? (
          <>
            {/* Agreement header */}
            <div className="rounded-t border border-b-0 p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <h2 className="text-lg font-semibold">
                    {details.agreement.reference_number}
                  </h2>
                  <p className="text-sm text-gray-500">
                    Status: {details.agreement.current_status.replace(/_/g, " ")}
                  </p>
                </div>
                <Link
                  to={`/agreements/${details.agreement.id}/compare`}
                  className="rounded-lg border border-sky-300 bg-sky-50 px-3 py-1 text-sm text-sky-800 hover:bg-sky-100"
                >
                  Open Compare view →
                </Link>
              </div>
            </div>

            {/* Tab bar */}
            <div className="flex border border-b-0 bg-gray-50">
              {TABS.map((t) => (
                <button
                  key={t.key}
                  className={`border-b-2 px-5 py-2.5 text-sm font-medium transition-colors ${
                    activeTab === t.key
                      ? "border-sky-600 bg-white text-sky-700"
                      : "border-transparent text-gray-500 hover:text-gray-700"
                  }`}
                  onClick={() => setActiveTab(t.key)}
                >
                  {t.label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="rounded-b border p-4">

              {/* ── Tab 1: Clause Review Matrix ── */}
              {activeTab === "clauses" && (
                <div>
                  <p className="mb-3 text-xs text-gray-500">
                    Each row shows the master-template original vs the value
                    filled in for this agreement. Your role's column has a comment
                    input; other roles' columns are read-only.
                  </p>

                  {matrixLoading ? (
                    <p className="text-sm text-gray-400">Loading fields…</p>
                  ) : fieldMatrix.length === 0 ? (
                    <p className="text-sm text-gray-400">No fields found for this agreement.</p>
                  ) : (
                    <div className="overflow-x-auto">
                      <table className="min-w-[1100px] w-full border-collapse text-sm">
                        <thead>
                          <tr className="bg-gray-100 text-left text-xs text-gray-600">
                            <th className="w-48 border p-2 font-semibold">Clause</th>
                            <th className="w-52 border p-2 font-semibold">Original (Master)</th>
                            <th className="w-52 border p-2 font-semibold">Amended (Agreement)</th>
                            {REVIEWER_ROLES.map((r) => (
                              <th
                                key={r.role}
                                className={`min-w-[160px] border p-2 font-semibold ${
                                  r.role === role ? "bg-sky-50 text-sky-700" : ""
                                }`}
                              >
                                {r.short}
                                {r.role === role && (
                                  <span className="ml-1 text-[10px] font-normal text-sky-500">
                                    (you)
                                  </span>
                                )}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {/* Form section */}
                          {formFields.length > 0 && (
                            <>
                              <tr className="bg-gray-50">
                                <td
                                  colSpan={3 + REVIEWER_ROLES.length}
                                  className="border px-2 py-1 text-xs font-bold uppercase tracking-wide text-gray-500"
                                >
                                  Form Fields (F)
                                </td>
                              </tr>
                              {formFields.map((field) => (
                                <FieldMatrixRow
                                  key={field.field_id}
                                  field={field}
                                  comments={details.comments}
                                  currentRole={role}
                                  myStepId={myStep?.id ?? null}
                                  onAddComment={addClauseComment}
                                />
                              ))}
                            </>
                          )}

                          {/* Conditions section */}
                          {conditionFields.length > 0 && (
                            <>
                              <tr className="bg-gray-50">
                                <td
                                  colSpan={3 + REVIEWER_ROLES.length}
                                  className="border px-2 py-1 text-xs font-bold uppercase tracking-wide text-gray-500"
                                >
                                  Conditions Clauses (C)
                                </td>
                              </tr>
                              {conditionFields.map((field) => (
                                <FieldMatrixRow
                                  key={field.field_id}
                                  field={field}
                                  comments={details.comments}
                                  currentRole={role}
                                  myStepId={myStep?.id ?? null}
                                  onAddComment={addClauseComment}
                                />
                              ))}
                            </>
                          )}

                          {/* Fields not in F or C (edge case) */}
                          {fieldMatrix
                            .filter((f) => !f.field_id.startsWith("F") && !f.field_id.startsWith("C"))
                            .map((field) => (
                              <FieldMatrixRow
                                key={field.field_id}
                                field={field}
                                comments={details.comments}
                                currentRole={role}
                                myStepId={myStep?.id ?? null}
                                onAddComment={addClauseComment}
                              />
                            ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* ── Tab 2: Document ── */}
              {activeTab === "document" && (
                <div className="grid gap-3 xl:grid-cols-2">
                  <AgreementPdf
                    agreementId={details.agreement.id}
                    referenceNumber={details.agreement.reference_number}
                  />
                  <AppendixView
                    agreementId={details.agreement.id}
                    referenceNumber={details.agreement.reference_number}
                  />
                </div>
              )}

              {/* ── Tab 3: AI Review ── */}
              {activeTab === "ai" && (
                <div>
                  <div className="mb-3 flex items-center justify-between">
                    <p className="text-xs text-gray-500">
                      AI outputs are suggestions — a human reviewer must confirm before action.
                    </p>
                    <div className="flex gap-2">
                      <button
                        type="button"
                        className="rounded bg-indigo-700 px-3 py-1 text-sm text-white disabled:opacity-50"
                        disabled={!!aiBusy}
                        onClick={runAnalyze}
                      >
                        {aiBusy === "analyze" ? "Analyzing…" : "Run Compare + Risks"}
                      </button>
                      <button
                        type="button"
                        className="rounded bg-indigo-700 px-3 py-1 text-sm text-white disabled:opacity-50"
                        disabled={!!aiBusy || !role}
                        onClick={runSummary}
                      >
                        {aiBusy === "summary" ? "Summarizing…" : `Summary (${role ?? "?"})`}
                      </button>
                    </div>
                  </div>
                  <div className="space-y-3">
                    {analysis && (
                      <>
                        <AIReviewPanel
                          title="Clause Comparison"
                          kind="comparison"
                          data={analysis.comparison}
                          cached={analysis.cached}
                          onConfirm={() => toast.success("Comparison reviewed.")}
                        />
                        <AIReviewPanel
                          title="Risk Detection"
                          kind="risks"
                          data={analysis.risks}
                          cached={analysis.cached}
                          onConfirm={() => toast.success("Risks reviewed.")}
                        />
                      </>
                    )}
                    {summary && (
                      <AIReviewPanel
                        title={`Role Summary (${role})`}
                        kind="summary"
                        data={summary.data}
                        cached={summary.cached}
                        onConfirm={() => toast.success("Summary reviewed.")}
                      />
                    )}
                    {!analysis && !summary && (
                      <p className="text-sm text-gray-500">
                        Run an analysis to see AI suggestions here.
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* ── Tab 4: Action ── */}
              {activeTab === "action" && (
                <div className="space-y-4">
                  <WorkflowTimeline steps={details.steps} />

                  {/* All comments summary */}
                  <div>
                    <h3 className="mb-2 font-semibold">All Comments</h3>
                    <p className="mb-2 text-xs text-gray-500">
                      Every role reviews in parallel and sees all comments. Use
                      the Clause Review tab to add clause-specific comments.
                    </p>
                    <div className="space-y-2">
                      {details.comments.length === 0 ? (
                        <p className="text-sm text-gray-400">No comments yet.</p>
                      ) : (
                        details.comments.map((comment) => (
                          <div key={comment.id} className="rounded border p-2 text-sm">
                            <div className="mb-0.5 text-xs font-semibold text-sky-800">
                              {comment.author_name ?? "Unknown"}
                              {comment.author_role
                                ? ` · ${humanRole(comment.author_role)}`
                                : ""}
                              {comment.clause_reference && (
                                <span className="ml-2 rounded bg-gray-100 px-1 py-0.5 text-[10px] text-gray-500">
                                  {comment.clause_reference}
                                </span>
                              )}
                            </div>
                            <div>{comment.comment_text}</div>
                            <div className="text-xs text-gray-400">
                              Status: {comment.status}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Action controls */}
                  <div className="rounded border p-3">
                    <h3 className="mb-2 font-semibold">Review Action</h3>
                    <p className="mb-2 text-xs text-gray-500">
                      Add a general comment (not tied to a specific clause) or
                      approve. The agreement can only be forwarded to the
                      subcontractor once every reviewer role has approved.
                    </p>
                    <div className="grid gap-2">
                      <textarea
                        className="rounded border p-2"
                        rows={3}
                        placeholder="General comment (optional)"
                        value={commentText}
                        onChange={(e) => setCommentText(e.target.value)}
                      />
                      <input
                        className="rounded border p-2"
                        placeholder="Clause reference (optional)"
                        value={clauseReference}
                        onChange={(e) => setClauseReference(e.target.value)}
                      />
                      <div className="flex gap-2">
                        <button
                          className="rounded bg-green-700 px-4 py-2 text-white disabled:opacity-50"
                          disabled={busy}
                          onClick={approve}
                        >
                          {busy ? "Working…" : "Approve"}
                        </button>
                        <button
                          className="rounded bg-amber-700 px-4 py-2 text-white disabled:opacity-50"
                          disabled={busy}
                          onClick={addGeneralComment}
                        >
                          {busy ? "Working…" : "Add Comment"}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

            </div>
          </>
        ) : (
          <div className="rounded border p-4 text-sm text-gray-500">
            No pending agreements for your role.
          </div>
        )}
      </main>
    </div>
  );
}

// ─── Field matrix row (extracted for readability) ────────────────────────────

type FieldMatrixRowProps = {
  field: FieldRow;
  comments: WorkflowComment[];
  currentRole: string | null;
  myStepId: string | null;
  onAddComment: (fieldId: string, text: string, stepId: string) => Promise<void>;
};

function FieldMatrixRow({
  field,
  comments,
  currentRole,
  myStepId,
  onAddComment,
}: FieldMatrixRowProps) {
  const isAmended =
    field.current_value && field.current_value !== field.default_value;

  return (
    <tr className={isAmended ? "bg-yellow-50" : undefined}>
      {/* Clause identity */}
      <td className="border p-2 align-top text-xs">
        <span className="font-mono font-semibold text-gray-700">{field.field_id}</span>
        {field.clause_number && (
          <span className="ml-1 text-gray-400">§{field.clause_number}</span>
        )}
        <div className="mt-0.5 text-gray-600">{field.field_label}</div>
      </td>

      {/* Original (master default) */}
      <td className="max-w-[200px] border p-2 align-top text-xs text-gray-500">
        {truncate(field.default_value, 150)}
      </td>

      {/* Amended (current agreement value) */}
      <td
        className={`max-w-[200px] border p-2 align-top text-xs ${
          isAmended ? "font-medium text-gray-900" : "text-gray-400"
        }`}
      >
        {truncate(field.current_value || field.default_value, 150)}
        {isAmended && (
          <span className="ml-1 rounded bg-yellow-200 px-1 text-[9px] font-semibold text-yellow-800">
            amended
          </span>
        )}
      </td>

      {/* One column per reviewer role */}
      {REVIEWER_ROLES.map((r) => (
        <RoleCommentCell
          key={r.role}
          fieldId={field.field_id}
          roleKey={r.role}
          comments={comments}
          isMyRole={r.role === currentRole}
          myStepId={myStepId}
          onAddComment={onAddComment}
        />
      ))}
    </tr>
  );
}
