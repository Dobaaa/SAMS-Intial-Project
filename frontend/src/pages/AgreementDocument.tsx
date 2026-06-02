/**
 * Document view — Phase 3 deliverable for Rev 01 item 16.
 *
 * Side-by-side layout: rendered 42-page SCA PDF on the left, grouped
 * field editor on the right. Admin can edit any field, save, and watch
 * the PDF iframe reload with the regenerated output without leaving the
 * page or walking back through the wizard.
 *
 * Out of scope (deferred to Phase 4): editing clause prose (the legal
 * boilerplate text in the master docx). Only field VALUES are editable
 * here — the master template wording is intentionally read-only because
 * one clause edit in the wrong place would mis-render every future
 * agreement.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { formatDateTime } from "../lib/formatDate";

import AppendixBuilder from "../components/AppendixBuilder";
import ClauseRevisionsPanel from "../components/ClauseRevisionsPanel";
import FieldInput from "../components/FieldInput";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { useAuth } from "../stores/auth";

type MasterField = {
  id: string;
  template_id: string;
  field_id: string;
  field_label: string;
  clause_number?: string | null;
  input_type: string;
  is_required: boolean;
  default_value?: string | null;
  show_in_appendix: boolean;
  auto_source_field_id?: string | null;
  sort_order: number;
};

type AgreementBundle = {
  id: string;
  reference_number: string;
  current_status: string;
  is_executed: boolean;
  project: Record<string, unknown>;
  subcontractor: Record<string, unknown>;
  values: Record<string, string>;
};

type ReviewerComment = {
  id: string;
  original_author_name?: string | null;
  created_at?: string | null;
  comment_text: string;
  clause_reference?: string | null;
  status: string;
};

type FieldGroup = {
  title: string;
  prefix: "F" | "C";
  blurb: string;
};

const FIELD_GROUPS: FieldGroup[] = [
  {
    title: "Form fields (F)",
    prefix: "F",
    blurb:
      "Cover-page identifiers (project, parties, signing date) and the contract price. Anything here flows into Page 1 of the PDF and the Form section.",
  },
  {
    title: "Conditions fields (C)",
    prefix: "C",
    blurb:
      "Commercial terms used inside the 15 Conditions clauses — payment days, retention, security type, jurisdiction, etc.",
  },
];

const STATUSES_LOCKED_FOR_EDIT = new Set([
  "draft_forwarded_to_subcontractor",
  "under_subcontractor_review",
  "under_subcontractor_signature",
  "under_gm_signature",
  "completed",
]);

export default function AgreementDocument() {
  const { id: agreementId } = useParams<{ id: string }>();
  const toast = useToast();
  const currentUser = useAuth((s) => s.user);
  /** Only admin can edit field values from this view. PD/Accounts/OM/GM
   *  see the same PDF + field list + revisions panel read-only — they do
   *  their workflow on /workflow and /compare. */
  const isAdmin = currentUser?.role === "admin";

  const [bundle, setBundle] = useState<AgreementBundle | null>(null);
  const [fields, setFields] = useState<MasterField[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [pdfUrl, setPdfUrl] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<string | null>(null);
  const [regenerating, setRegenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [comments, setComments] = useState<ReviewerComment[]>([]);
  const [resolvingId, setResolvingId] = useState<string | null>(null);

  const editingLocked =
    !isAdmin ||
    !bundle ||
    bundle.is_executed ||
    STATUSES_LOCKED_FOR_EDIT.has(bundle.current_status);

  // ----------------------------- comments -----------------------------
  const loadComments = useCallback(async () => {
    if (!agreementId || !isAdmin) return;
    try {
      const { data } = await api.get(`/agreements/${agreementId}/comments`);
      setComments((data as ReviewerComment[]) ?? []);
    } catch {
      // non-fatal
    }
  }, [agreementId, isAdmin]);

  const resolveComment = async (commentId: string) => {
    setResolvingId(commentId);
    try {
      await api.patch(`/comments/${commentId}/status`, { status: "resolved" });
      setComments((prev) =>
        prev.map((c) => (c.id === commentId ? { ...c, status: "resolved" } : c)),
      );
      toast.success("Comment marked resolved.");
    } catch {
      toast.error("Failed to resolve comment.");
    } finally {
      setResolvingId(null);
    }
  };

  // ----------------------------- data load -----------------------------
  const reloadPdf = useCallback(async () => {
    if (!agreementId) return;
    try {
      const resp = await api.get(`/pdf/${agreementId}/preview`, {
        responseType: "blob",
      });
      const url = URL.createObjectURL(resp.data as Blob);
      setPdfUrl((prev) => {
        if (prev) URL.revokeObjectURL(prev);
        return url;
      });
    } catch {
      // No PDF rendered yet — generate one, then retry once.
      try {
        await api.post(`/pdf/${agreementId}/generate`);
        const retry = await api.get(`/pdf/${agreementId}/preview`, {
          responseType: "blob",
        });
        const url = URL.createObjectURL(retry.data as Blob);
        setPdfUrl((prev) => {
          if (prev) URL.revokeObjectURL(prev);
          return url;
        });
      } catch (err) {
        console.error("Failed to load PDF", err);
      }
    }
  }, [agreementId]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!agreementId) return;
      setLoading(true);
      setError(null);
      try {
        const [bundleResp, mastersResp] = await Promise.all([
          api.get<AgreementBundle>(`/agreements/${agreementId}`),
          api.get<{
            form?: Array<{ id: string }>;
            conditions?: Array<{ id: string }>;
            appendix?: Array<{ id: string }>;
          }>("/masters/"),
        ]);
        if (cancelled) return;
        setBundle(bundleResp.data);
        setValues(bundleResp.data.values ?? {});
        setDrafts(bundleResp.data.values ?? {});

        // /masters/ returns active templates grouped by type but WITHOUT the
        // field catalog — fields live on a separate endpoint per template id.
        // Mirror AgreementCreate.loadTemplateFields() so we end up with one
        // flat MasterField[] across F/C/A.
        const active = [
          mastersResp.data.form?.[0],
          mastersResp.data.conditions?.[0],
          mastersResp.data.appendix?.[0],
        ].filter((t): t is { id: string } => Boolean(t));
        const allFields: MasterField[] = [];
        for (const tpl of active) {
          const fieldsResp = await api.get<MasterField[]>(
            `/masters/fields/${tpl.id}`
          );
          if (Array.isArray(fieldsResp.data)) allFields.push(...fieldsResp.data);
        }
        if (!cancelled) setFields(allFields);
        await reloadPdf();
        if (!cancelled) await loadComments();
      } catch (err) {
        console.error(err);
        if (!cancelled) setError("Failed to load the agreement.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [agreementId, reloadPdf, loadComments]);

  // Revoke the blob URL when the component unmounts so we don't leak.
  useEffect(() => {
    return () => {
      if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // -------------------------- field grouping ---------------------------
  const groupedFields = useMemo(() => {
    return FIELD_GROUPS.map((group) => ({
      group,
      fields: fields
        .filter((f) => f.field_id.startsWith(group.prefix))
        .sort((a, b) => a.sort_order - b.sort_order),
    }));
  }, [fields]);

  // ------------------------------ saves --------------------------------
  const setDraft = (fieldId: string, value: string) =>
    setDrafts((prev) => ({ ...prev, [fieldId]: value }));

  const saveField = async (field: MasterField) => {
    if (!agreementId) return;
    const newValue = drafts[field.field_id] ?? "";
    if (newValue === (values[field.field_id] ?? "")) {
      toast.info(`${field.field_id} unchanged.`);
      return;
    }
    setSaving(field.field_id);
    try {
      await api.put(`/agreements/${agreementId}/fields`, {
        values: { [field.field_id]: newValue },
      });
      setValues((prev) => ({ ...prev, [field.field_id]: newValue }));
      toast.success(`Saved ${field.field_id}.`);
      setRegenerating(true);
      await api.post(`/pdf/${agreementId}/generate`);
      await reloadPdf();
    } catch (err) {
      console.error(err);
      toast.error(`Failed to save ${field.field_id}.`);
    } finally {
      setSaving(null);
      setRegenerating(false);
    }
  };

  const resetDraft = (fieldId: string) =>
    setDrafts((prev) => ({ ...prev, [fieldId]: values[fieldId] ?? "" }));

  // ------------------------------ render -------------------------------
  if (loading) {
    return <div className="p-6 text-sky-700">Loading agreement…</div>;
  }
  if (error || !bundle) {
    return (
      <div className="space-y-3 p-6">
        <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          {error ?? "Agreement not found."}
        </div>
        <Link className="text-sky-700 underline" to="/dashboard">
          ← Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="flex h-[calc(100vh-4.5rem)] flex-col">
      {/* Header strip */}
      <div className="flex items-center justify-between border-b border-sky-100 bg-sky-50/40 px-4 py-2">
        <div>
          <h1 className="text-base font-semibold text-sky-900">
            Document — {bundle.reference_number}
          </h1>
          <p className="text-xs text-sky-700">
            Status: <strong>{bundle.current_status}</strong>
            {editingLocked && (
              <span className="ml-2 rounded bg-amber-100 px-2 py-0.5 text-amber-800">
                {isAdmin ? "read-only (status locks editing)" : "read-only (reviewer view)"}
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {regenerating && (
            <span className="text-xs text-sky-700">Regenerating PDF…</span>
          )}
          <Link
            className="rounded border border-sky-300 px-3 py-1 text-sm text-sky-700 hover:bg-sky-50"
            to="/dashboard"
          >
            Done
          </Link>
        </div>
      </div>

      {/* Two-pane body */}
      <div className="grid flex-1 grid-cols-2 overflow-hidden">
        {/* Left: live PDF preview */}
        <div className="border-r border-sky-100 bg-sky-50/20">
          {pdfUrl ? (
            <iframe
              src={pdfUrl}
              title="Generated agreement PDF"
              className="h-full w-full"
            />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-sky-700">
              Rendering preview…
            </div>
          )}
        </div>

        {/* Right pane: editor for admin, read-only summary for reviewers. */}
        {isAdmin ? (
          <div className="overflow-y-auto bg-white p-4">
            <div className="space-y-6">
              {groupedFields.map(({ group, fields: fs }) => (
                <section
                  key={group.prefix}
                  className="rounded-xl border border-sky-100 bg-white p-3 shadow-sm"
                >
                  <h2 className="text-sm font-semibold text-sky-900">{group.title}</h2>
                  <p className="mb-3 text-xs text-sky-700">{group.blurb}</p>
                  <div className="space-y-2">
                    {fs.length === 0 && (
                      <p className="text-xs text-gray-500">
                        No fields configured for this section.
                      </p>
                    )}
                    {fs.map((field) => {
                      const draft = drafts[field.field_id] ?? "";
                      const committed = values[field.field_id] ?? "";
                      const dirty = draft !== committed;
                      return (
                        <div key={field.id} className="rounded border border-sky-100 p-2">
                          <label className="mb-1 block text-xs font-medium text-sky-800">
                            {field.field_id} — {field.field_label}
                            {field.clause_number && (
                              <span className="ml-1 text-gray-500">
                                · clause {field.clause_number}
                              </span>
                            )}
                            {field.is_required && (
                              <span className="ml-1 text-red-600">*</span>
                            )}
                          </label>
                          <FieldInput
                            field={field}
                            value={draft}
                            onChange={(_, value) => setDraft(field.field_id, value)}
                          />
                          {dirty && !editingLocked && (
                            <div className="mt-2 flex gap-2">
                              <button
                                type="button"
                                className="rounded bg-sky-600 px-3 py-1 text-xs text-white hover:bg-sky-700 disabled:opacity-50"
                                disabled={saving !== null}
                                onClick={() => void saveField(field)}
                              >
                                {saving === field.field_id ? "Saving…" : "Save & regenerate"}
                              </button>
                              <button
                                type="button"
                                className="rounded border border-sky-300 px-3 py-1 text-xs text-sky-700 hover:bg-sky-50"
                                onClick={() => resetDraft(field.field_id)}
                              >
                                Discard
                              </button>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </section>
              ))}

              {/* Appendix editor reuses the Builder so the override / Reset-to-Auto
                  semantics match the wizard. AppendixBuilder regenerates itself
                  via its refreshKey when our drafts state changes. */}
              <section className="rounded-xl border border-sky-100 bg-white p-3 shadow-sm">
                <h2 className="text-sm font-semibold text-sky-900">
                  Appendix rows (A)
                </h2>
                <p className="mb-3 text-xs text-sky-700">
                  Auto-derived from F/C values above. Override any row to lock a
                  custom value; the cascade will leave it alone on subsequent
                  edits.
                </p>
                <AppendixBuilder
                  agreementId={agreementId!}
                  refreshKey={JSON.stringify(values)}
                />
                <p className="mt-3 text-xs text-gray-500">
                  Appendix edits don't auto-trigger a PDF regeneration — use the
                  "Save & regenerate" button on any field above (or
                  <span className="font-mono"> Refresh preview</span> below) to
                  re-render.
                </p>
                <button
                  type="button"
                  className="mt-2 rounded border border-sky-300 px-3 py-1 text-xs text-sky-700 hover:bg-sky-50 disabled:opacity-50"
                  disabled={regenerating}
                  onClick={async () => {
                    setRegenerating(true);
                    try {
                      await api.post(`/pdf/${agreementId}/generate`);
                      await reloadPdf();
                      toast.success("PDF regenerated.");
                    } catch {
                      toast.error("Failed to regenerate PDF.");
                    } finally {
                      setRegenerating(false);
                    }
                  }}
                >
                  {regenerating ? "Regenerating…" : "Refresh preview"}
                </button>
              </section>

              {/* Clause revisions — admin's edit surface for proposing/tracking. */}
              <section className="rounded-xl border border-sky-100 bg-white p-3 shadow-sm">
                <h2 className="text-sm font-semibold text-sky-900">
                  Clause revisions
                </h2>
                <p className="mb-3 text-xs text-sky-700">
                  Per-agreement edits to the master template prose. Each
                  revision starts as <em>pending</em> and applies to the
                  rendered PDF once a reviewer accepts it. Withdraw any
                  pending revision to drop it before review.
                </p>
                <ClauseRevisionsPanel
                  agreementId={agreementId!}
                  mode="edit"
                  onChange={async () => {
                    setRegenerating(true);
                    try {
                      await api.post(`/pdf/${agreementId}/generate`);
                      await reloadPdf();
                    } finally {
                      setRegenerating(false);
                    }
                  }}
                />
              </section>

              {/* Reviewer comments — admin resolves these before resubmitting */}
              {comments.length > 0 && (
                <section className="rounded-xl border border-sky-100 bg-white p-3 shadow-sm">
                  <div className="mb-3 flex items-center justify-between">
                    <h2 className="text-sm font-semibold text-sky-900">Reviewer Comments</h2>
                    <div className="flex gap-2 text-xs">
                      <span className="rounded-full bg-red-100 px-2 py-0.5 font-semibold text-red-700">
                        {comments.filter((c) => c.status !== "resolved").length} pending
                      </span>
                      <span className="rounded-full bg-green-100 px-2 py-0.5 font-semibold text-green-700">
                        {comments.filter((c) => c.status === "resolved").length} resolved
                      </span>
                    </div>
                  </div>
                  <p className="mb-3 text-xs text-sky-700">
                    Address each comment by editing the relevant fields above, then mark it resolved.
                    Once all comments are resolved, resubmit the agreement for review.
                  </p>
                  <div className="space-y-2">
                    {comments.map((comment) => {
                      const isPending = comment.status !== "resolved";
                      return (
                        <div
                          key={comment.id}
                          className={`rounded border p-3 text-sm ${
                            isPending
                              ? "border-red-200 bg-red-50"
                              : "border-green-200 bg-green-50 opacity-70"
                          }`}
                        >
                          <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-semibold">
                                {comment.original_author_name || "Reviewer"}
                              </span>
                              <span className="text-xs text-gray-500">
                                {formatDateTime(comment.created_at)}
                              </span>
                              {comment.clause_reference && (
                                <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-mono text-indigo-700">
                                  {comment.clause_reference}
                                </span>
                              )}
                            </div>
                            <span
                              className={`rounded-full px-2 py-0.5 text-xs font-semibold ${
                                isPending
                                  ? "bg-red-100 text-red-700"
                                  : "bg-green-100 text-green-700"
                              }`}
                            >
                              {isPending ? "Pending" : "Resolved"}
                            </span>
                          </div>
                          <p className="whitespace-pre-wrap text-gray-800">
                            {comment.comment_text}
                          </p>
                          {isPending && (
                            <button
                              type="button"
                              className="mt-2 rounded border border-green-400 bg-white px-3 py-1 text-xs font-semibold text-green-700 hover:bg-green-50 disabled:opacity-50"
                              disabled={resolvingId === comment.id}
                              onClick={() => void resolveComment(comment.id)}
                            >
                              {resolvingId === comment.id ? "Resolving…" : "Mark Resolved"}
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </section>
              )}
            </div>
          </div>
        ) : (
          /* Non-admin: pure read-only field-values summary. No inputs, no
             editor surfaces, no buttons. Reviewers do their accept/reject
             work on /agreements/:id/compare, which is linked below. */
          <div className="overflow-y-auto bg-white p-4">
            <div className="mb-3 rounded border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
              <strong>Reviewer view (read-only).</strong> Editing field values
              and proposing clause revisions are admin-only. To accept or
              reject pending clause revisions, switch to the side-by-side
              comparison view.
              <div className="mt-2">
                <Link
                  to={`/agreements/${agreementId}/compare`}
                  className="inline-block rounded border border-amber-300 bg-white px-3 py-1 text-amber-900 hover:bg-amber-100"
                >
                  Open Compare view →
                </Link>
              </div>
            </div>
            {groupedFields.map(({ group, fields: fs }) => (
              <section
                key={group.prefix}
                className="mb-4 rounded-xl border border-sky-100 bg-white p-3 shadow-sm"
              >
                <h2 className="text-sm font-semibold text-sky-900">{group.title}</h2>
                <p className="mb-3 text-xs text-sky-700">{group.blurb}</p>
                <dl className="space-y-1">
                  {fs.map((field) => {
                    const v = values[field.field_id] ?? "";
                    return (
                      <div
                        key={field.id}
                        className="grid grid-cols-3 gap-2 rounded border border-sky-50 px-2 py-1 text-xs"
                      >
                        <dt className="col-span-1 font-medium text-sky-800">
                          {field.field_id}
                          <span className="block text-[10px] font-normal text-gray-500">
                            {field.field_label}
                          </span>
                        </dt>
                        <dd
                          className="col-span-2 whitespace-pre-wrap break-words"
                          style={{ wordBreak: "break-word" }}
                        >
                          {v ? (
                            <span>{v}</span>
                          ) : (
                            <span className="text-gray-400">—</span>
                          )}
                        </dd>
                      </div>
                    );
                  })}
                </dl>
              </section>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
