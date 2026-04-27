import { useEffect, useState } from "react";

import AIReviewPanel from "../components/AIReviewPanel";
import DeviationReport from "../components/DeviationReport";
import { useToast } from "../components/Toast";
import WorkflowTimeline from "../components/WorkflowTimeline";
import { api } from "../lib/api";
import { useAuth } from "../stores/auth";

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

type WorkflowAgreementDetails = {
  agreement: {
    id: string;
    reference_number: string;
    current_status: string;
    gm_approval_date?: string | null;
  };
  steps: Array<{
    id: string;
    step_name: string;
    step_order: number;
    role_required: string;
    status: string;
    acted_at?: string | null;
  }>;
  comments: Array<{
    id: string;
    workflow_step_id: string;
    comment_text: string;
    clause_reference?: string | null;
    status: string;
    created_at?: string | null;
  }>;
};

type AIAnalysis = {
  comparison: unknown;
  risks: unknown;
  cached: boolean;
};

type AISummary = {
  data: unknown;
  cached: boolean;
};

export default function WorkflowReview() {
  const toast = useToast();
  const role = useAuth((s) => s.user?.role ?? null);
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [selectedStepId, setSelectedStepId] = useState<string>("");
  const [details, setDetails] = useState<WorkflowAgreementDetails | null>(null);
  const [commentText, setCommentText] = useState("");
  const [clauseReference, setClauseReference] = useState("");
  const [busy, setBusy] = useState(false);
  const [analysis, setAnalysis] = useState<AIAnalysis | null>(null);
  const [summary, setSummary] = useState<AISummary | null>(null);
  const [aiBusy, setAiBusy] = useState<"" | "analyze" | "summary">("");

  const loadPending = async () => {
    const { data } = await api.get("/workflow/pending");
    setPending(data);
    if (data.length > 0 && !selectedStepId) {
      setSelectedStepId(data[0].step.id);
      const detailsResp = await api.get(`/workflow/agreements/${data[0].agreement.id}`);
      setDetails(detailsResp.data);
    }
  };

  useEffect(() => {
    void loadPending();
  }, []);

  const selectPending = async (item: PendingItem) => {
    setSelectedStepId(item.step.id);
    const detailsResp = await api.get(`/workflow/agreements/${item.agreement.id}`);
    setDetails(detailsResp.data);
    setAnalysis(null);
    setSummary(null);
  };

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
      console.error(err);
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
      console.error(err);
    } finally {
      setAiBusy("");
    }
  };

  const approve = async () => {
    if (!selectedStepId || busy) return;
    setBusy(true);
    try {
      const ref = details?.agreement.reference_number ?? "";
      await api.post(`/workflow/${selectedStepId}/approve`);
      toast.success(`Approved ${ref}.`);
      setSelectedStepId("");
      setDetails(null);
      await loadPending();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Failed to approve. See console for details.");
      console.error(err);
    } finally {
      setBusy(false);
    }
  };

  const returnForFix = async () => {
    if (!selectedStepId || busy) return;
    if (!commentText.trim()) {
      toast.error("A comment is required to return the agreement.");
      return;
    }
    setBusy(true);
    try {
      const ref = details?.agreement.reference_number ?? "";
      await api.post(`/workflow/${selectedStepId}/return`, {
        comment_text: commentText,
        clause_reference: clauseReference || undefined,
      });
      toast.success(`Returned ${ref} to admin with comment.`);
      setCommentText("");
      setClauseReference("");
      setSelectedStepId("");
      setDetails(null);
      await loadPending();
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Failed to return. See console for details.");
      console.error(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="grid grid-cols-12 gap-4 p-4">
      <aside className="col-span-4 rounded border p-3">
        <h2 className="mb-3 text-lg font-semibold">My Pending Agreements</h2>
        <div className="space-y-2">
          {pending.map((item) => (
            <button
              key={item.step.id}
              className={`w-full rounded border p-2 text-left ${selectedStepId === item.step.id ? "bg-gray-100" : ""}`}
              onClick={() => selectPending(item)}
            >
              <div className="font-medium">{item.agreement.reference_number}</div>
              <div className="text-xs text-gray-500">
                {item.step.step_name} - {item.step.role_required}
              </div>
            </button>
          ))}
        </div>
      </aside>

      <main className="col-span-8 space-y-4">
        {details ? (
          <>
            <div className="rounded border p-3">
              <h2 className="text-lg font-semibold">Agreement Summary</h2>
              <p>Reference: {details.agreement.reference_number}</p>
              <p>Status: {details.agreement.current_status}</p>
            </div>

            <DeviationReport agreementId={details.agreement.id} />

            <div className="rounded border p-3">
              <div className="mb-2 flex items-center justify-between">
                <h3 className="text-lg font-semibold">AI Review</h3>
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
              <p className="mb-3 text-xs text-gray-500">
                AI outputs are suggestions. A human reviewer must confirm before action.
              </p>
              <div className="space-y-3">
                {analysis ? (
                  <>
                    <AIReviewPanel
                      title="Clause Comparison"
                      data={analysis.comparison}
                      cached={analysis.cached}
                      onConfirm={() => toast.success("Comparison reviewed.")}
                    />
                    <AIReviewPanel
                      title="Risk Detection"
                      data={analysis.risks}
                      cached={analysis.cached}
                      onConfirm={() => toast.success("Risks reviewed.")}
                    />
                  </>
                ) : null}
                {summary ? (
                  <AIReviewPanel
                    title={`Role Summary (${role})`}
                    data={summary.data}
                    cached={summary.cached}
                    onConfirm={() => toast.success("Summary reviewed.")}
                  />
                ) : null}
                {!analysis && !summary ? (
                  <p className="text-sm text-gray-500">Run an analysis to see AI suggestions here.</p>
                ) : null}
              </div>
            </div>

            <WorkflowTimeline steps={details.steps} />

            <div className="rounded border p-3">
              <h3 className="mb-2 text-lg font-semibold">All Comments</h3>
              <div className="space-y-2">
                {details.comments.map((comment) => (
                  <div key={comment.id} className="rounded border p-2">
                    <div className="text-sm">{comment.comment_text}</div>
                    <div className="text-xs text-gray-500">
                      Clause: {comment.clause_reference || "N/A"} | Status: {comment.status}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded border p-3">
              <h3 className="mb-2 text-lg font-semibold">Review Action</h3>
              <div className="grid gap-2">
                <textarea
                  className="rounded border p-2"
                  rows={3}
                  placeholder="Comment (required for return)"
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
                    className="rounded bg-green-700 px-3 py-2 text-white disabled:opacity-50"
                    disabled={busy}
                    onClick={approve}
                  >
                    {busy ? "Working…" : "Approve"}
                  </button>
                  <button
                    className="rounded bg-amber-700 px-3 py-2 text-white disabled:opacity-50"
                    disabled={busy}
                    onClick={returnForFix}
                  >
                    {busy ? "Working…" : "Return with Comment"}
                  </button>
                </div>
              </div>
            </div>
          </>
        ) : (
          <div className="rounded border p-3 text-sm text-gray-600">No pending agreements for your role.</div>
        )}
      </main>
    </div>
  );
}
