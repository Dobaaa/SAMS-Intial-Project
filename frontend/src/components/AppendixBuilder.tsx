import { useEffect, useMemo, useState } from "react";

import { api } from "../lib/api";
import { formatNumber } from "../lib/formatNumber";

export type AppendixRow = {
  field_id: string;
  row_label: string;
  clause_ref: string;
  current_value: string | null;
  is_modified_from_default: boolean;
  auto_source_field_id: string | null;
  show_in_appendix: boolean;
  admin_extra_note: string | null;
  sort_order: number;
};

type Props = {
  agreementId: string;
  /** When provided, triggers a reload whenever the key changes (e.g. after saving Step 2/3). */
  refreshKey?: string | number;
};

export default function AppendixBuilder({ agreementId, refreshKey }: Props) {
  const [rows, setRows] = useState<AppendixRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savingField, setSavingField] = useState<string | null>(null);
  const [editingField, setEditingField] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<string>("");

  const startEdit = (row: AppendixRow) => {
    setEditingField(row.field_id);
    setEditDraft(row.current_value ?? "");
  };

  const cancelEdit = () => {
    setEditingField(null);
    setEditDraft("");
  };

  const saveValueEdit = async (row: AppendixRow) => {
    setSavingField(row.field_id);
    try {
      const { data } = await api.put(`/agreements/${agreementId}/fields`, {
        values: { [row.field_id]: editDraft },
      });
      // Backend may cascade other field values (e.g. C-> A); reload via api
      // call to AppendixBuilder is implicit through parent refreshKey, but
      // we also patch the local state for the edited row immediately so the
      // value shows up without flicker even before the parent re-renders.
      setRows((prev) =>
        prev.map((r) =>
          r.field_id === row.field_id ? { ...r, current_value: editDraft } : r
        )
      );
      if (data?.values && typeof data.values === "object") {
        const cascaded: Record<string, string> = data.values;
        setRows((prev) =>
          prev.map((r) =>
            cascaded[r.field_id] !== undefined
              ? { ...r, current_value: cascaded[r.field_id] }
              : r
          )
        );
      }
      setEditingField(null);
      setEditDraft("");
    } catch (err) {
      console.error(err);
      setError(`Failed to save value for ${row.field_id}.`);
    } finally {
      setSavingField(null);
    }
  };

  const sortedRows = useMemo(
    () => [...rows].sort((a, b) => a.sort_order - b.sort_order),
    [rows]
  );

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!agreementId) return;
      setLoading(true);
      setError(null);
      try {
        const { data } = await api.get<AppendixRow[]>(`/agreements/${agreementId}/appendix`);
        if (!cancelled) setRows(data);
      } catch (err) {
        if (!cancelled) {
          console.error(err);
          setError("Failed to load appendix configuration.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [agreementId, refreshKey]);

  const patchRow = async (fieldId: string, patch: Partial<AppendixRow>) => {
    setSavingField(fieldId);
    try {
      await api.put(`/agreements/${agreementId}/appendix/${fieldId}`, {
        show_in_appendix: patch.show_in_appendix,
        admin_extra_note: patch.admin_extra_note,
        sort_order: patch.sort_order,
      });
      setRows((prev) =>
        prev.map((row) => (row.field_id === fieldId ? { ...row, ...patch } : row))
      );
    } catch (err) {
      console.error(err);
      setError(`Failed to save changes for ${fieldId}.`);
    } finally {
      setSavingField(null);
    }
  };

  const move = (fieldId: string, direction: -1 | 1) => {
    const index = sortedRows.findIndex((r) => r.field_id === fieldId);
    const swapWith = index + direction;
    if (index < 0 || swapWith < 0 || swapWith >= sortedRows.length) return;
    const a = sortedRows[index];
    const b = sortedRows[swapWith];
    void patchRow(a.field_id, { sort_order: b.sort_order });
    void patchRow(b.field_id, { sort_order: a.sort_order });
  };

  if (loading) {
    return <div className="text-sm text-sky-700">Loading appendix…</div>;
  }

  return (
    <div className="space-y-3">
      {error && (
        <div className="rounded border border-red-300 bg-red-50 p-2 text-sm text-red-700">
          {error}
        </div>
      )}
      <p className="text-sm text-sky-700">
        Appendix rows auto-populate from the Form/Conditions values you entered.
        Toggle visibility, add notes, or reorder rows. Admin overrides typed in
        the respective A-field inputs are preserved.
      </p>
      <table className="w-full border-collapse overflow-hidden rounded-lg border border-sky-100">
        <thead>
          <tr className="bg-sky-50 text-left text-sky-900">
            <th className="border p-2 w-20">Order</th>
            <th className="border p-2 w-20">Clause</th>
            <th className="border p-2">Item</th>
            <th className="border p-2">Value</th>
            <th className="border p-2 w-28">Show</th>
            <th className="border p-2">Admin Note</th>
          </tr>
        </thead>
        <tbody>
          {sortedRows.map((row, index) => (
            <tr key={row.field_id} className={!row.show_in_appendix ? "bg-gray-50 text-gray-400" : ""}>
              <td className="border border-sky-100 p-2 align-top">
                <div className="flex items-center gap-1">
                  <span className="font-mono text-xs">{row.sort_order}</span>
                  <button
                    type="button"
                    className="rounded border border-sky-200 px-1 text-xs hover:bg-sky-50 disabled:opacity-40"
                    disabled={index === 0 || savingField !== null}
                    onClick={() => move(row.field_id, -1)}
                    aria-label="Move up"
                  >
                    ↑
                  </button>
                  <button
                    type="button"
                    className="rounded border border-sky-200 px-1 text-xs hover:bg-sky-50 disabled:opacity-40"
                    disabled={index === sortedRows.length - 1 || savingField !== null}
                    onClick={() => move(row.field_id, 1)}
                    aria-label="Move down"
                  >
                    ↓
                  </button>
                </div>
              </td>
              <td className="border border-sky-100 p-2 align-top font-mono text-xs">
                {row.clause_ref}
              </td>
              <td className="border border-sky-100 p-2 align-top">
                <div className="font-medium">{row.row_label}</div>
                <div className="text-xs text-gray-500">
                  {row.field_id}
                  {row.auto_source_field_id && (
                    <span> · auto from {row.auto_source_field_id}</span>
                  )}
                </div>
              </td>
              <td className="border border-sky-100 p-2 align-top whitespace-pre-wrap">
                {editingField === row.field_id ? (
                  <div className="space-y-1">
                    <textarea
                      className="w-full rounded border border-sky-300 p-1 text-sm"
                      rows={2}
                      value={editDraft}
                      onChange={(e) => setEditDraft(e.target.value)}
                    />
                    <div className="flex gap-1">
                      <button
                        type="button"
                        className="rounded bg-sky-600 px-2 py-0.5 text-xs text-white hover:bg-sky-700 disabled:opacity-50"
                        disabled={savingField !== null}
                        onClick={() => void saveValueEdit(row)}
                      >
                        {savingField === row.field_id ? "Saving…" : "Save"}
                      </button>
                      <button
                        type="button"
                        className="rounded border border-sky-300 px-2 py-0.5 text-xs text-sky-700 hover:bg-sky-50"
                        onClick={cancelEdit}
                      >
                        Cancel
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <div>
                      {row.current_value ? (
                        formatNumber(row.current_value)
                      ) : (
                        <span className="text-gray-400">(empty)</span>
                      )}
                    </div>
                    <button
                      type="button"
                      className="rounded border border-sky-200 px-2 py-0.5 text-xs text-sky-700 hover:bg-sky-50"
                      onClick={() => startEdit(row)}
                    >
                      Edit
                    </button>
                  </div>
                )}
              </td>
              <td className="border border-sky-100 p-2 align-top text-center">
                <label className="inline-flex items-center gap-1 text-xs">
                  <input
                    type="checkbox"
                    checked={row.show_in_appendix}
                    onChange={(e) =>
                      void patchRow(row.field_id, { show_in_appendix: e.target.checked })
                    }
                    disabled={savingField !== null}
                  />
                  {row.show_in_appendix ? "shown" : "hidden"}
                </label>
              </td>
              <td className="border border-sky-100 p-2 align-top">
                <textarea
                  className="w-full rounded border border-sky-200 p-1 text-xs"
                  rows={2}
                  placeholder="Optional note (rendered beneath the value in the PDF)"
                  value={row.admin_extra_note ?? ""}
                  onChange={(e) =>
                    setRows((prev) =>
                      prev.map((r) =>
                        r.field_id === row.field_id ? { ...r, admin_extra_note: e.target.value } : r
                      )
                    )
                  }
                  onBlur={(e) =>
                    void patchRow(row.field_id, { admin_extra_note: e.target.value })
                  }
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
