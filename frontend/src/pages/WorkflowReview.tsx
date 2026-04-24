import { useEffect, useState } from "react";

import DeviationReport from "../components/DeviationReport";
import WorkflowTimeline from "../components/WorkflowTimeline";
import { api } from "../lib/api";

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

export default function WorkflowReview() {
  const [pending, setPending] = useState<PendingItem[]>([]);
  const [selectedStepId, setSelectedStepId] = useState<string>("");
  const [details, setDetails] = useState<WorkflowAgreementDetails | null>(null);
  const [commentText, setCommentText] = useState("");
  const [clauseReference, setClauseReference] = useState("");

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
  };

  const approve = async () => {
    if (!selectedStepId) return;
    await api.post(`/workflow/${selectedStepId}/approve`);
    await loadPending();
  };

  const returnForFix = async () => {
    if (!selectedStepId) return;
    await api.post(`/workflow/${selectedStepId}/return`, {
      comment_text: commentText,
      clause_reference: clauseReference || undefined,
    });
    setCommentText("");
    setClauseReference("");
    await loadPending();
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
              <h3 className="mb-2 text-lg font-semibold">AI Summary (Placeholder)</h3>
              <p className="text-sm text-gray-600">AI summary panel will be integrated in Task 10.</p>
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
                  <button className="rounded bg-green-700 px-3 py-2 text-white" onClick={approve}>
                    Approve
                  </button>
                  <button className="rounded bg-amber-700 px-3 py-2 text-white" onClick={returnForFix}>
                    Return with Comment
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
