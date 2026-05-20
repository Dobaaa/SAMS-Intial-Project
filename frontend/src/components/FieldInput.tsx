type FieldDef = {
  field_id: string;
  field_label: string;
  input_type: string;
};

type Props = {
  field: FieldDef;
  value: string;
  onChange: (fieldId: string, value: string) => void;
  invalid?: boolean;
};

export default function FieldInput({ field, value, onChange, invalid = false }: Props) {
  // Red border + tint when the field is flagged as a missing mandatory input
  // by the wizard's validation (see AgreementCreate).
  const cls = `w-full rounded border p-2${invalid ? " border-red-500 bg-red-50" : ""}`;
  if (field.field_id === "C02") {
    return (
      <select
        className={cls}
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

  if (field.field_id === "C14") {
    // Performance Security instrument the subcontractor will provide. Bank
    // Guarantee is the standard contractual form; Company Security Cheque
    // is the BGCC-internal alternative for smaller-value subcontracts.
    return (
      <select
        className={cls}
        value={value}
        onChange={(e) => onChange(field.field_id, e.target.value)}
      >
        <option value="">Select security type</option>
        <option value="Bank Guarantee Cheque">Bank Guarantee Cheque</option>
        <option value="Company Security Cheque">Company Security Cheque</option>
      </select>
    );
  }

  if (field.input_type === "date") {
    return (
      <input
        type="date"
        className={cls}
        value={value}
        onChange={(e) => onChange(field.field_id, e.target.value)}
      />
    );
  }

  if (field.input_type === "number") {
    return (
      <input
        type="number"
        className={cls}
        value={value}
        onChange={(e) => onChange(field.field_id, e.target.value)}
      />
    );
  }

  if (field.input_type === "textarea" || field.input_type === "multifield" || field.input_type === "table") {
    return (
      <textarea
        className={cls}
        value={value}
        onChange={(e) => onChange(field.field_id, e.target.value)}
        rows={3}
      />
    );
  }

  return (
    <input
      type="text"
      className={cls}
      value={value}
      onChange={(e) => onChange(field.field_id, e.target.value)}
    />
  );
}
