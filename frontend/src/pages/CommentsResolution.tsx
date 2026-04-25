import { useEffect, useState } from "react";

import { useToast } from "../components/Toast";
import { api } from "../lib/api";

type ResolutionRow = {
  id: string;
  agreement_id: string;
  subcontractor_comment: string;
  clause_reference?: string | null;
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
  const [progress, setProgress] = useState<{ om?: string; gm?: string }>({});
  const [internalComments, setInternalComments] = useState<WorkflowCommentLite[]>([]);
  const [steps, setSteps] = useState<WorkflowStepLite[]>([]);
  const [loading, setLoading] = useState(false);

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
        items: [{ subcontractor_comment: newComment, clause_reference: newClause || null }],
      });
      toast.success("Resolution item added.");
      setNewComment("");
      setNewClause("");
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
                      {step ? `${step.step_name} — ${step.role_required.replace(/_/g, " ")}` : "Workflow"}
                      {c.clause_reference ? ` · clause ${c.clause_reference}` : ""}
                      {c.created_at ? ` · ${new Date(c.created_at).toLocaleString()}` : ""}
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
        <div className="grid gap-2">
          <textarea
            className="rounded border p-2"
            placeholder="Subcontractor comment"
            rows={3}
            value={newComment}
            onChange={(e) => setNewComment(e.target.value)}
          />
          <input
            className="rounded border p-2"
            placeholder="Clause reference (optional)"
            value={newClause}
            onChange={(e) => setNewClause(e.target.value)}
          />
          <button
            className="w-fit rounded bg-blue-700 px-3 py-2 text-white disabled:opacity-50"
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

      <div className="overflow-x-auto rounded border border-sky-100 bg-white p-3 shadow-sm">
        <table className="w-full border-collapse border">
          <thead>
            <tr className="bg-gray-100">
              <th className="border p-2">Comment</th>
              <th className="border p-2">Clause Ref</th>
              <th className="border p-2">AI Suggestion</th>
              <th className="border p-2">PD Response</th>
              <th className="border p-2">OM Response</th>
              <th className="border p-2">Final Response</th>
              <th className="border p-2">Resolved</th>
              <th className="border p-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={8} className="p-3 text-center text-sm text-gray-500">
                  No subcontractor comments recorded for this agreement.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.id}>
                  <td className="border p-2">{row.subcontractor_comment}</td>
                  <td className="border p-2">{row.clause_reference || "-"}</td>
                  <td className="border p-2">
                    <textarea
                      className="w-full rounded border p-1"
                      rows={2}
                      value={row.ai_suggested_response || ""}
                      onChange={(e) =>
                        setRows((prev) =>
                          prev.map((r) => (r.id === row.id ? { ...r, ai_suggested_response: e.target.value } : r))
                        )
                      }
                    />
                  </td>
                  <td className="border p-2">
                    <textarea
                      className="w-full rounded border p-1"
                      rows={2}
                      value={row.pd_response || ""}
                      onChange={(e) =>
                        setRows((prev) => prev.map((r) => (r.id === row.id ? { ...r, pd_response: e.target.value } : r)))
                      }
                    />
                  </td>
                  <td className="border p-2">
                    <textarea
                      className="w-full rounded border p-1"
                      rows={2}
                      value={row.om_response || ""}
                      onChange={(e) =>
                        setRows((prev) => prev.map((r) => (r.id === row.id ? { ...r, om_response: e.target.value } : r)))
                      }
                    />
                  </td>
                  <td className="border p-2">
                    <textarea
                      className="w-full rounded border p-1"
                      rows={2}
                      value={row.final_response || ""}
                      onChange={(e) =>
                        setRows((prev) =>
                          prev.map((r) => (r.id === row.id ? { ...r, final_response: e.target.value } : r))
                        )
                      }
                    />
                  </td>
                  <td className="border p-2 text-center">
                    <input
                      type="checkbox"
                      checked={row.is_resolved}
                      onChange={(e) =>
                        setRows((prev) =>
                          prev.map((r) => (r.id === row.id ? { ...r, is_resolved: e.target.checked } : r))
                        )
                      }
                    />
                  </td>
                  <td className="border p-2">
                    <button className="rounded bg-gray-800 px-2 py-1 text-white" onClick={() => saveRow(row)}>
                      Save
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
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
