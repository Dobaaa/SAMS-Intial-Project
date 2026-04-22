import { useState } from "react";

export type MasterField = {
  id: string;
  template_id: string;
  field_id: string;
  clause_number: string;
  field_label: string;
  input_type: string;
  default_value?: string | null;
  is_required: boolean;
  auto_source_field_id?: string | null;
  appendix_row_label?: string | null;
  appendix_clause_ref?: string | null;
  show_in_appendix: boolean;
  sort_order: number;
};

type FieldCatalogProps = {
  fields: MasterField[];
  templateId: string;
  onCreate: (payload: Omit<MasterField, "id">) => Promise<void>;
  onUpdate: (id: string, payload: Omit<MasterField, "id">) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
};

const inputTypes = ["text", "number", "date", "dropdown", "textarea", "multifield", "table"];

function emptyField(templateId: string): Omit<MasterField, "id"> {
  return {
    template_id: templateId,
    field_id: "",
    clause_number: "",
    field_label: "",
    input_type: "text",
    default_value: "",
    is_required: false,
    auto_source_field_id: "",
    appendix_row_label: "",
    appendix_clause_ref: "",
    show_in_appendix: true,
    sort_order: 0,
  };
}

export default function FieldCatalog({ fields, templateId, onCreate, onUpdate, onDelete }: FieldCatalogProps) {
  const [draft, setDraft] = useState<Omit<MasterField, "id">>(emptyField(templateId));
  const [editingId, setEditingId] = useState<string | null>(null);

  const handleCreate = async () => {
    await onCreate(draft);
    setDraft(emptyField(templateId));
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-semibold">Field Catalog</h3>
      <div className="grid grid-cols-2 gap-2 rounded border p-3">
        <input className="rounded border p-2" placeholder="Field ID (F01...)" value={draft.field_id} onChange={(e) => setDraft({ ...draft, field_id: e.target.value })} />
        <input className="rounded border p-2" placeholder="Clause Number" value={draft.clause_number} onChange={(e) => setDraft({ ...draft, clause_number: e.target.value })} />
        <input className="rounded border p-2" placeholder="Field Label" value={draft.field_label} onChange={(e) => setDraft({ ...draft, field_label: e.target.value })} />
        <select className="rounded border p-2" value={draft.input_type} onChange={(e) => setDraft({ ...draft, input_type: e.target.value })}>
          {inputTypes.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
        <input className="rounded border p-2" placeholder="Default value" value={draft.default_value ?? ""} onChange={(e) => setDraft({ ...draft, default_value: e.target.value })} />
        <input className="rounded border p-2" placeholder="Sort order" type="number" value={draft.sort_order} onChange={(e) => setDraft({ ...draft, sort_order: Number(e.target.value) })} />
        <label className="col-span-2 flex items-center gap-2">
          <input type="checkbox" checked={draft.is_required} onChange={(e) => setDraft({ ...draft, is_required: e.target.checked })} />
          Required
        </label>
        <button className="col-span-2 rounded bg-black px-3 py-2 text-white" onClick={handleCreate}>
          Add Field
        </button>
      </div>

      <table className="w-full border-collapse border">
        <thead>
          <tr className="bg-gray-100">
            <th className="border p-2">Field</th>
            <th className="border p-2">Clause</th>
            <th className="border p-2">Label</th>
            <th className="border p-2">Type</th>
            <th className="border p-2">Order</th>
            <th className="border p-2">Actions</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((field) => (
            <tr key={field.id}>
              <td className="border p-2">{field.field_id}</td>
              <td className="border p-2">{field.clause_number}</td>
              <td className="border p-2">{field.field_label}</td>
              <td className="border p-2">{field.input_type}</td>
              <td className="border p-2">{field.sort_order}</td>
              <td className="border p-2">
                <div className="flex gap-2">
                  <button className="rounded border px-2 py-1" onClick={() => setEditingId(editingId === field.id ? null : field.id)}>
                    Edit
                  </button>
                  <button className="rounded border px-2 py-1 text-red-600" onClick={() => onDelete(field.id)}>
                    Delete
                  </button>
                </div>
                {editingId === field.id && (
                  <button
                    className="mt-2 rounded bg-gray-800 px-2 py-1 text-white"
                    onClick={() =>
                      onUpdate(field.id, {
                        template_id: field.template_id,
                        field_id: field.field_id,
                        clause_number: field.clause_number,
                        field_label: field.field_label,
                        input_type: field.input_type,
                        default_value: field.default_value,
                        is_required: field.is_required,
                        auto_source_field_id: field.auto_source_field_id,
                        appendix_row_label: field.appendix_row_label,
                        appendix_clause_ref: field.appendix_clause_ref,
                        show_in_appendix: field.show_in_appendix,
                        sort_order: field.sort_order,
                      })
                    }
                  >
                    Save Current Row
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
