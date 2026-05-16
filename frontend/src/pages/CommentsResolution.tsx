import { useEffect, useState } from "react";

import AIReviewPanel from "../components/AIReviewPanel";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { formatDateTime } from "../lib/formatDate";
import { humanRole } from "../lib/roles";

type ResolutionRow = {
  id: string;
  agreement_id: string;
  subcontractor_comment: string;
  clause_reference?: string | null;
  original_clause_text?: string | null;
  ai_suggested_response?: string | null;
  pd_response?: string | null;
  om_response?: string | null;
  final_response?: string | null;
  is_resolved: boolean;
};

type AgreementOption = {
  id: string;
  reference_number: string;
  status: string;
  status_label: string;
};

type WorkflowStepLite = {
  id: string;
  step_name: string;
  role_required: string;
  status: string;
  acted_at?: string | null;
};

type WorkflowCommentLite = {
  id: string;
  workflow_step_id: string;
  comment_text: string;
  clause_reference?: string | null;
  status: string;
  created_at?: string | null;
};

export default function CommentsResolution() {
  const toast = useToast();
  const [agreementId, setAgreementId] = useState("");
  const [agreements, setAgreements] = useState<AgreementOption[]>([]);
  const [rows, setRows] = useState<ResolutionRow[]>([]);
  const [newComment, setNewComment] = useState("");
  const [newClause, setNewClause] = useState("");
  const [newOriginalClause, setNewOriginalClause] = useState("");
  const [progress, setProgress] = useState<{ om?: string; gm?: string }>({});
  const [internalComments, setInternalComments] = useState<WorkflowCommentLite[]>([]);
  const [steps, setSteps] = useState<WorkflowStepLite[]>([]);
  const [loading, setLoading] = useState(false);
  const [aiBusy, setAiBusy] = useState<"" | "suggest" | "validate">("");
  const [aiSuggestions, setAiSuggestions] = useState<{ data: unknown; cached: boolean } | null>(null);
  const [aiValidation, setAiValidation] = useState<{ data: unknown; cached: boolean } | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const { data } = await api.get<AgreementOption[]>("/reports/dashboard/agreements");
        if (!cancelled) setAgreements(Array.isArray(data) ? data : []);
      } catch (err) {
        console.error("Failed to load agreement list", err);
        if (!cancelled) toast.error("Failed to load agreement list.");
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadRows = async () => {
    if (!agreementId) {
      toast.error("Pick an agreement first.");
      return;
    }
    setLoading(true);
    try {
      // Resolution rows can legitimately be empty (no comments yet).
      const resolutionRes = await api.get(`/resolution/${agreementId}`).catch((err) => {
        if (err?.response?.status === 404) return { data: [] as ResolutionRow[] };
        throw err;
      });
      setRows(Array.isArray(resolutionRes.data) ? resolutionRes.data : []);

      const workflowData = await api.get(`/workflow/agreements/${agreementId}`);
      const stepsList = (workflowData.data?.steps ?? []) as WorkflowStepLite[];
      const commentsList = (workflowData.data?.comments ?? []) as WorkflowCommentLite[];
      setSteps(stepsList);
      setInternalComments(commentsList);
      const om = stepsList.find((s) => s.role_required === "operation_manager");
      const gm = stepsList.find((s) => s.role_required === "gm");
      setProgress({ om: om?.status, gm: gm?.status });
    } catch (err: unknown) {
      console.error(err);
      const e = err as { response?: { status?: number; data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Failed to load agreement details.");
    } finally {
      setLoading(false);
    }
  };

  const createSheet = async () => {
    if (!agreementId) {
      toast.error("Pick an agreement first.");
      return;
    }
    if (!newComment.trim()) {
      toast.error("Comment text is required.");
      return;
    }
    try {
      await api.post(`/agreements/${agreementId}/resolution-sheet`, {
        items: [
          {
            subcontractor_comment: newComment,
            clause_reference: newClause || null,
            original_clause_text: newOriginalClause || null,
          },
        ],
      });
      toast.success("Resolution item added.");
      setNewComment("");
      setNewClause("");
      setNewOriginalClause("");
      await loadRows();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Failed to add resolution item.");
      console.error(err);
    }
  };

  const saveRow = async (row: ResolutionRow) => {
    try {
      await api.put(`/resolution/${agreementId}/items/${row.id}`, {
        original_clause_text: row.original_clause_text ?? null,
        ai_suggested_response: row.ai_suggested_response ?? null,
        pd_response: row.pd_response ?? null,
        om_response: row.om_response ?? null,
        final_response: row.final_response ?? null,
        is_resolved: row.is_resolved,
      });
      toast.success("Row saved.");
      await loadRows();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Failed to save row.");
      console.error(err);
    }
  };

  const refreshAISuggestions = async () => {
    if (!agreementId || aiBusy) return;
    setAiBusy("suggest");
    try {
      const { data } = await api.post(`/ai/resolution/${agreementId}/suggest`);
      setAiSuggestions({ data: data?.data ?? null, cached: !!data?.cached });
      const mapped = new Map<string, string>();
      if (Array.isArray(data?.data)) {
        for (const item of data.data as Array<{ comment_id?: string; suggested_response?: string }>) {
          if (item?.comment_id) mapped.set(String(item.comment_id), item.suggested_response ?? "");
        }
      }
      setRows((prev) =>
        prev.map((r) =>
          mapped.has(r.id) ? { ...r, ai_suggested_response: mapped.get(r.id) ?? r.ai_suggested_response } : r
        )
      );
      toast.success("AI suggestions refreshed. Review and Save each row to persist.");
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "AI suggestion failed.");
      console.error(err);
    } finally {
      setAiBusy("");
    }
  };

  const validateRevisions = async () => {
    if (!agreementId || aiBusy) return;
    setAiBusy("validate");
    try {
      const { data } = await api.post(`/ai/${agreementId}/validate-revision`);
      setAiValidation({ data: data?.data ?? null, cached: !!data?.cached });
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "AI validation failed.");
      console.error(err);
    } finally {
      setAiBusy("");
    }
  };

  const submitForApproval = async () => {
    if (!agreementId) {
      toast.error("Pick an agreement first.");
      return;
    }
    try {
      await api.post(`/resolution/${agreementId}/submit-for-approval`);
      toast.success("Submitted for OM/GM approval.");
      await loadRows();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Failed to submit for approval.");
      console.error(err);
    }
  };

  const stepLookup = new Map(steps.map((s) => [s.id, s]));

  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-semibold">Comments &amp; Resolution</h1>

      <div className="rounded border border-sky-100 bg-white p-3 shadow-sm">
        <div className="flex flex-wrap items-end gap-2">
          <div className="grow">
            <label className="mb-1 block text-sm font-medium">Agreement</label>
            <select
              className="w-full rounded border border-sky-200 p-2"
              value={agreementId}
              onChange={(e) => setAgreementId(e.target.value)}
            >
              <option value="">Select an agreement…</option>
              {agreements.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.reference_number} — {a.status_label}
                </option>
              ))}
            </select>
          </div>
          <button
            className="rounded bg-sky-700 px-4 py-2 text-white hover:bg-sky-800 disabled:opacity-50"
            onClick={loadRows}
            disabled={loading || !agreementId}
          >
            {loading ? "Loading…" : "Load"}
          </button>
        </div>
      </div>

      {agreementId && (
        <div className="rounded border border-amber-200 bg-amber-50 p-3">
          <h2 className="mb-2 text-lg font-semibold text-amber-900">
            Internal Review Comments ({internalComments.length})
          </h2>
          {internalComments.length === 0 ? (
            <p className="text-sm text-amber-800">No comments returned during internal review.</p>
          ) : (
            <ul className="space-y-2">
              {internalComments.map((c) => {
                const step = stepLookup.get(c.workflow_step_id);
                return (
                  <li key={c.id} className="rounded border border-amber-100 bg-white p-2">
                    <div className="text-xs text-amber-700">
                      {step ? `${step.step_name} — ${humanRole(step.role_required)}` : "Workflow"}
                      {c.clause_reference ? ` · clause ${c.clause_reference}` : ""}
                      {c.created_at ? ` · ${formatDateTime(c.created_at)}` : ""}
                      {" · "}status: {c.status}
                    </div>
                    <div className="mt-1 whitespace-pre-wrap text-sm">{c.comment_text}</div>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}

      <div className="rounded border border-sky-100 bg-white p-3 shadow-sm">
        <h2 className="mb-2 text-lg font-semibold">Add Subcontractor Comment</h2>
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <label className="mb-1 block text-sm font-medium text-sky-900">
              Original SCA Clause (paste verbatim text from the agreement)
            </label>
            <textarea
              className="w-full rounded border p-2"
              placeholder="e.g. Clause 3.4.6: Interim Payment shall be made by the Main Contractor within 60 days of the Interim Payment Certificate..."
              rows={4}
              value={newOriginalClause}
              onChange={(e) => setNewOriginalClause(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-sm font-medium text-sky-900">
              Subcontractor's Comment
            </label>
            <textarea
              className="w-full rounded border p-2"
              placeholder="The subcontractor's proposed change or remark..."
              rows={4}
              value={newComment}
              onChange={(e) => setNewComment(e.target.value)}
            />
          </div>
        </div>
        <div className="mt-2 grid items-end gap-2 md:grid-cols-[1fr_auto]">
          <input
            className="rounded border p-2"
            placeholder="Clause reference (e.g. 3.4.6)"
            value={newClause}
            onChange={(e) => setNewClause(e.target.value)}
          />
          <button
            className="rounded bg-blue-700 px-3 py-2 text-white disabled:opacity-50"
            onClick={createSheet}
            disabled={!agreementId}
          >
            Create Resolution Item
          </button>
        </div>
      </div>

      <div className="rounded border border-sky-100 bg-white p-3 shadow-sm">
        <h2 className="mb-2 text-lg font-semibold">Approval Progress</h2>
        <p className="text-sm">
          OM: <strong>{progress.om || "pending"}</strong> · GM: <strong>{progress.gm || "pending"}</strong>
        </p>
      </div>

      <div className="space-y-3">
        {rows.length === 0 ? (
          <div className="rounded border border-sky-100 bg-white p-4 text-center text-sm text-gray-500 shadow-sm">
            No subcontractor comments recorded for this agreement.
          </div>
        ) : (
          rows.map((row) => (
            <div
              key={row.id}
              className="space-y-3 rounded border border-sky-100 bg-white p-3 shadow-sm"
            >
              <div className="flex items-center justify-between">
                <div className="text-sm text-sky-900">
                  <span className="font-semibold">Resolution Item</span>
                  {row.clause_reference && (
                    <span className="ml-2 rounded bg-sky-100 px-2 py-0.5 text-xs font-mono text-sky-800">
                      Clause {row.clause_reference}
                    </span>
                  )}
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={row.is_resolved}
                    onChange={(e) =>
                      setRows((prev) =>
                        prev.map((r) =>
                          r.id === row.id ? { ...r, is_resolved: e.target.checked } : r
                        )
                      )
                    }
                  />
                  Resolved
                </label>
              </div>

              <div className="grid gap-3 md:grid-cols-2">
                <div className="rounded border border-amber-200 bg-amber-50 p-2">
                  <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-amber-900">
                    Original SCA Clause
                  </div>
                  <textarea
                    className="w-full rounded border border-amber-200 bg-white p-2 text-sm"
                    rows={4}
                    placeholder="Paste the verbatim clause text from the SCA..."
                    value={row.original_clause_text || ""}
                    onChange={(e) =>
                      setRows((prev) =>
                        prev.map((r) =>
                          r.id === row.id ? { ...r, original_clause_text: e.target.value } : r
                        )
                      )
                    }
                  />
                </div>
                <div className="rounded border border-sky-200 bg-sky-50 p-2">
                  <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-sky-900">
                    Second Party (Subcontractor) Comment
                  </div>
                  <div className="whitespace-pre-wrap rounded border border-sky-200 bg-white p-2 text-sm">
                    {row.subcontractor_comment || (
                      <span className="text-gray-400">(no comment text)</span>
                    )}
                  </div>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <div>
                  <div className="mb-1 text-xs font-semibold text-indigo-900">
                    AI Suggestion
                  </div>
                  <textarea
                    className="w-full rounded border p-1 text-sm"
                    rows={3}
                    value={row.ai_suggested_response || ""}
                    onChange={(e) =>
                      setRows((prev) =>
                        prev.map((r) =>
                          r.id === row.id ? { ...r, ai_suggested_response: e.target.value } : r
                        )
                      )
                    }
                  />
                </div>
                <div>
                  <div className="mb-1 text-xs font-semibold text-sky-900">
                    PD Response
                  </div>
                  <textarea
                    className="w-full rounded border p-1 text-sm"
                    rows={3}
                    value={row.pd_response || ""}
                    onChange={(e) =>
                      setRows((prev) =>
                        prev.map((r) => (r.id === row.id ? { ...r, pd_response: e.target.value } : r))
                      )
                    }
                  />
                </div>
                <div>
                  <div className="mb-1 text-xs font-semibold text-sky-900">
                    OM Response
                  </div>
                  <textarea
                    className="w-full rounded border p-1 text-sm"
                    rows={3}
                    value={row.om_response || ""}
                    onChange={(e) =>
                      setRows((prev) =>
                        prev.map((r) => (r.id === row.id ? { ...r, om_response: e.target.value } : r))
                      )
                    }
                  />
                </div>
                <div>
                  <div className="mb-1 text-xs font-semibold text-emerald-900">
                    Final Response
                  </div>
                  <textarea
                    className="w-full rounded border p-1 text-sm"
                    rows={3}
                    value={row.final_response || ""}
                    onChange={(e) =>
                      setRows((prev) =>
                        prev.map((r) =>
                          r.id === row.id ? { ...r, final_response: e.target.value } : r
                        )
                      )
                    }
                  />
                </div>
              </div>

              <div className="flex justify-end">
                <button
                  className="rounded bg-gray-800 px-3 py-1 text-sm text-white hover:bg-black"
                  onClick={() => saveRow(row)}
                >
                  Save Row
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <div className="rounded border border-sky-100 bg-white p-3 shadow-sm">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="text-lg font-semibold">AI Assistance</h2>
          <div className="flex gap-2">
            <button
              type="button"
              className="rounded bg-indigo-700 px-3 py-1 text-sm text-white disabled:opacity-50"
              disabled={!agreementId || rows.length === 0 || !!aiBusy}
              onClick={refreshAISuggestions}
            >
              {aiBusy === "suggest" ? "Refreshing…" : "Refresh AI Suggestions"}
            </button>
            <button
              type="button"
              className="rounded bg-indigo-700 px-3 py-1 text-sm text-white disabled:opacity-50"
              disabled={!agreementId || rows.length === 0 || !!aiBusy}
              onClick={validateRevisions}
            >
              {aiBusy === "validate" ? "Validating…" : "Validate My Revisions"}
            </button>
          </div>
        </div>
        <p className="mb-3 text-xs text-gray-500">
          AI outputs are suggestions. Review each row and click Save to persist.
        </p>
        <div className="space-y-3">
          {aiSuggestions ? (
            <AIReviewPanel
              title="Suggested Responses"
              kind="suggestions"
              data={aiSuggestions.data}
              cached={aiSuggestions.cached}
              onConfirm={() => toast.success("Suggestions reviewed.")}
            />
          ) : null}
          {aiValidation ? (
            <AIReviewPanel
              title="Revision Validation"
              kind="validation"
              data={aiValidation.data}
              cached={aiValidation.cached}
              onConfirm={() => toast.success("Validation reviewed.")}
            />
          ) : null}
          {!aiSuggestions && !aiValidation ? (
            <p className="text-sm text-gray-500">Run an AI action above to see suggestions here.</p>
          ) : null}
        </div>
      </div>

      <button
        className="rounded bg-green-700 px-3 py-2 text-white disabled:opacity-50"
        onClick={submitForApproval}
        disabled={!agreementId}
      >
        Submit for OM/GM Approval
      </button>
    </div>
  );
}
