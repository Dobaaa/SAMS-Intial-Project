import axios from "axios";
import { useState } from "react";

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

const api = axios.create({ baseURL: "/api" });

export default function CommentsResolution() {
  const [agreementId, setAgreementId] = useState("");
  const [rows, setRows] = useState<ResolutionRow[]>([]);
  const [newComment, setNewComment] = useState("");
  const [newClause, setNewClause] = useState("");
  const [progress, setProgress] = useState<{ om?: string; gm?: string }>({});

  const loadRows = async () => {
    if (!agreementId) return;
    const { data } = await api.get(`/resolution/${agreementId}`);
    setRows(data);
    const workflowData = await api.get(`/workflow/agreements/${agreementId}`);
    const om = workflowData.data.steps.find((s: any) => s.role_required === "operation_manager");
    const gm = workflowData.data.steps.find((s: any) => s.role_required === "gm");
    setProgress({ om: om?.status, gm: gm?.status });
  };

  const createSheet = async () => {
    if (!agreementId || !newComment.trim()) return;
    await api.post(`/agreements/${agreementId}/resolution-sheet`, {
      items: [{ subcontractor_comment: newComment, clause_reference: newClause || null }],
    });
    setNewComment("");
    setNewClause("");
    await loadRows();
  };

  const saveRow = async (row: ResolutionRow) => {
    await api.put(`/resolution/${agreementId}/items/${row.id}`, {
      ai_suggested_response: row.ai_suggested_response ?? null,
      pd_response: row.pd_response ?? null,
      om_response: row.om_response ?? null,
      final_response: row.final_response ?? null,
      is_resolved: row.is_resolved,
    });
    await loadRows();
  };

  const submitForApproval = async () => {
    await api.post(`/resolution/${agreementId}/submit-for-approval`);
    await loadRows();
  };

  return (
    <div className="space-y-4 p-4">
      <h1 className="text-2xl font-semibold">Comments Resolution</h1>

      <div className="rounded border p-3">
        <div className="flex gap-2">
          <input
            className="w-80 rounded border p-2"
            placeholder="Agreement ID"
            value={agreementId}
            onChange={(e) => setAgreementId(e.target.value)}
          />
          <button className="rounded bg-black px-3 py-2 text-white" onClick={loadRows}>
            Load
          </button>
        </div>
      </div>

      <div className="rounded border p-3">
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
          <button className="w-fit rounded bg-blue-700 px-3 py-2 text-white" onClick={createSheet}>
            Create Resolution Item
          </button>
        </div>
      </div>

      <div className="rounded border p-3">
        <h2 className="mb-2 text-lg font-semibold">Approval Progress</h2>
        <p>OM: {progress.om || "pending"} | GM: {progress.gm || "pending"}</p>
      </div>

      <div className="overflow-x-auto rounded border p-3">
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
            {rows.map((row) => (
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
                      setRows((prev) => prev.map((r) => (r.id === row.id ? { ...r, is_resolved: e.target.checked } : r)))
                    }
                  />
                </td>
                <td className="border p-2">
                  <button className="rounded bg-gray-800 px-2 py-1 text-white" onClick={() => saveRow(row)}>
                    Save
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <button className="rounded bg-green-700 px-3 py-2 text-white" onClick={submitForApproval} disabled={!agreementId}>
        Submit for OM/GM Approval
      </button>
    </div>
  );
}
