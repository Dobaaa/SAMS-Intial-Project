import { useMemo, useState } from "react";

import { api } from "../lib/api";
import { formatDateTime } from "../lib/formatDate";

type EditHistory = {
  id: string;
  edited_by_name?: string | null;
  previous_text: string;
  new_text: string;
  edited_at?: string | null;
};

type CommentItem = {
  id: string;
  original_author_name?: string | null;
  created_at?: string | null;
  comment_text: string;
  clause_reference?: string | null;
  status: "open" | "in_discussion" | "resolved";
  last_edited_by_name?: string | null;
  last_edited_at?: string | null;
  edit_history: EditHistory[];
};

type Props = {
  comments: CommentItem[];
  onUpdated?: (comment: CommentItem) => void;
};

const badgeClasses: Record<string, string> = {
  open: "bg-yellow-100 text-yellow-700",
  in_discussion: "bg-blue-100 text-blue-700",
  resolved: "bg-green-100 text-green-700",
};

export default function CommentThread({ comments, onUpdated }: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftText, setDraftText] = useState("");
  const [expandedHistory, setExpandedHistory] = useState<Record<string, boolean>>({});

  const sortedComments = useMemo(
    () =>
      [...comments].sort((a, b) => {
        const aTime = a.created_at ? new Date(a.created_at).getTime() : 0;
        const bTime = b.created_at ? new Date(b.created_at).getTime() : 0;
        return aTime - bTime;
      }),
    [comments]
  );

  const startEdit = (comment: CommentItem) => {
    setEditingId(comment.id);
    setDraftText(comment.comment_text);
  };

  const saveEdit = async (commentId: string) => {
    const { data } = await api.put(`/comments/${commentId}`, { comment_text: draftText });
    setEditingId(null);
    setDraftText("");
    onUpdated?.(data);
  };

  const changeStatus = async (commentId: string, status: CommentItem["status"]) => {
    const { data } = await api.patch(`/comments/${commentId}/status`, { status });
    onUpdated?.(data);
  };

  return (
    <div className="space-y-3">
      {sortedComments.map((comment) => (
        <div key={comment.id} className="rounded border p-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-sm">
              <span className="rounded bg-gray-100 px-2 py-1 font-medium">
                {comment.original_author_name || "Unknown"}
              </span>
              <span className="ml-2 text-gray-500">
                {formatDateTime(comment.created_at)}
              </span>
            </div>
            <span className={`rounded px-2 py-1 text-xs ${badgeClasses[comment.status]}`}>
              {comment.status}
            </span>
          </div>

          {editingId === comment.id ? (
            <div className="space-y-2">
              <textarea
                className="w-full rounded border p-2"
                rows={3}
                value={draftText}
                onChange={(e) => setDraftText(e.target.value)}
              />
              <button className="rounded bg-black px-3 py-1 text-white" onClick={() => saveEdit(comment.id)}>
                Save
              </button>
            </div>
          ) : (
            <p className="whitespace-pre-wrap">{comment.comment_text}</p>
          )}

          <div className="mt-2 text-xs text-gray-500">
            Clause: {comment.clause_reference || "N/A"}
          </div>

          {comment.last_edited_at && (
            <div className="mt-2 text-xs text-gray-600">
              Edited by {comment.last_edited_by_name || "Unknown"}{" "}
              {formatDateTime(comment.last_edited_at)}
            </div>
          )}

          {comment.edit_history.length > 0 && (
            <button
              className="mt-2 text-xs text-blue-600 underline"
              onClick={() =>
                setExpandedHistory((prev) => ({ ...prev, [comment.id]: !prev[comment.id] }))
              }
            >
              {expandedHistory[comment.id] ? "Hide edit history" : "View edit history"}
            </button>
          )}

          {expandedHistory[comment.id] && (
            <div className="mt-2 space-y-2 rounded bg-gray-50 p-2">
              {comment.edit_history.map((h) => (
                <div key={h.id} className="rounded border p-2 text-xs">
                  <div>
                    Edited by {h.edited_by_name || "Unknown"}{" "}
                    {formatDateTime(h.edited_at)}
                  </div>
                  <div className="text-gray-600">From: {h.previous_text}</div>
                  <div className="text-gray-800">To: {h.new_text}</div>
                </div>
              ))}
            </div>
          )}

          <div className="mt-3 flex flex-wrap gap-2">
            <button className="rounded border px-2 py-1 text-sm" onClick={() => startEdit(comment)}>
              Edit
            </button>
            <button className="rounded border px-2 py-1 text-sm" onClick={() => changeStatus(comment.id, "open")}>
              Mark Open
            </button>
            <button
              className="rounded border px-2 py-1 text-sm"
              onClick={() => changeStatus(comment.id, "in_discussion")}
            >
              In Discussion
            </button>
            <button
              className="rounded border px-2 py-1 text-sm"
              onClick={() => changeStatus(comment.id, "resolved")}
            >
              Resolved
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
