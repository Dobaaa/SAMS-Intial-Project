type FieldDef = {
  field_id: string;
  field_label: string;
  input_type: string;
};

type Props = {
  field: FieldDef;
  value: string;
  onChange: (fieldId: string, value: string) => void;
};

export default function FieldInput({ field, value, onChange }: Props) {
  if (field.field_id === "C02") {
    return (
      <select
        className="w-full rounded border p-2"
        value={value}
        onChange={(e) => onChange(field.field_id, e.target.value)}
      >
        <option value="">Select quantity type</option>
        <option value="Lump Sum">Lump Sum</option>
        <option value="Re-measurable">Re-measurable</option>
        <option value="Mixed">Mixed</option>
      </select>
    );
  }

  if (field.input_type === "date") {
    return (
      <input
        type="date"
        className="w-full rounded border p-2"
        value={value}
        onChange={(e) => onChange(field.field_id, e.target.value)}
      />
    );
  }

  if (field.input_type === "number") {
    return (
      <input
        type="number"
        className="w-full rounded border p-2"
        value={value}
        onChange={(e) => onChange(field.field_id, e.target.value)}
      />
    );
  }

  if (field.input_type === "textarea" || field.input_type === "multifield" || field.input_type === "table") {
    return (
      <textarea
        className="w-full rounded border p-2"
        value={value}
        onChange={(e) => onChange(field.field_id, e.target.value)}
        rows={3}
      />
    );
  }

  return (
    <input
      type="text"
      className="w-full rounded border p-2"
      value={value}
      onChange={(e) => onChange(field.field_id, e.target.value)}
    />
  );
}
