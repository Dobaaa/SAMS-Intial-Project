import { useMemo, useState } from "react";

import FieldInput from "../components/FieldInput";
import { api } from "../lib/api";
type MasterField = {
  id: string;
  template_id: string;
  field_id: string;
  field_label: string;
  input_type: string;
  default_value?: string | null;
  is_required: boolean;
  show_in_appendix: boolean;
  sort_order: number;
};

function tenPercentOf(value: string): string {
  const n = parseFloat(value.replace(/,/g, "").trim());
  if (!Number.isFinite(n)) return "";
  return (n * 0.1).toFixed(2);
}

const fallbackFields: MasterField[] = [
  { id: "F01", template_id: "fallback", field_id: "F01", field_label: "Day of signing", input_type: "date", is_required: true, show_in_appendix: false, sort_order: 1 },
  { id: "F02", template_id: "fallback", field_id: "F02", field_label: "Subcontractor company name", input_type: "text", is_required: true, show_in_appendix: false, sort_order: 2 },
  { id: "F03", template_id: "fallback", field_id: "F03", field_label: "Subcontractor PO Box", input_type: "text", is_required: false, show_in_appendix: false, sort_order: 3 },
  { id: "F04", template_id: "fallback", field_id: "F04", field_label: "Trade Licence Number", input_type: "text", is_required: false, show_in_appendix: false, sort_order: 4 },
  { id: "F05", template_id: "fallback", field_id: "F05", field_label: "Employer Name", input_type: "text", is_required: true, show_in_appendix: false, sort_order: 5 },
  { id: "F06", template_id: "fallback", field_id: "F06", field_label: "Project Name / Details", input_type: "textarea", is_required: true, show_in_appendix: false, sort_order: 6 },
  { id: "F07", template_id: "fallback", field_id: "F07", field_label: "Project Location", input_type: "text", is_required: true, show_in_appendix: false, sort_order: 7 },
  { id: "F08", template_id: "fallback", field_id: "F08", field_label: "Subcontract Price (AED)", input_type: "number", is_required: true, show_in_appendix: false, sort_order: 8 },
];

export default function AgreementCreate() {
  const [step, setStep] = useState(1);
  const [agreementId, setAgreementId] = useState<string>("");
  const [reference, setReference] = useState("");
  const [fields, setFields] = useState<MasterField[]>([]);
  const [values, setValues] = useState<Record<string, string>>({});
  const [project, setProject] = useState({
    project_name: "",
    project_code: "",
    project_location: "",
    employer_name: "",
    engineer_name: "",
  });
  const [subcontractor, setSubcontractor] = useState({
    company_name: "",
    po_box: "",
    trade_licence_no: "",
    contact_person: "",
    email: "",
    phone: "",
    address: "",
  });
  const [fieldLoadWarning, setFieldLoadWarning] = useState("");

  const formFields = useMemo(() => fields.filter((f) => /^F\d+/.test(f.field_id)).sort((a, b) => a.sort_order - b.sort_order), [fields]);
  const conditionFields = useMemo(() => fields.filter((f) => /^C\d+/.test(f.field_id)).sort((a, b) => a.sort_order - b.sort_order), [fields]);
  const appendixFields = useMemo(() => fields.filter((f) => /^A\d+/.test(f.field_id)).sort((a, b) => a.sort_order - b.sort_order), [fields]);

  const onChangeValue = (fieldId: string, value: string) => {
    const next = { ...values, [fieldId]: value };
    // Auto-populate dependent fields only if they currently hold their
    // cascaded value (or are empty). If the Admin has explicitly overridden
    // A01/A02/A07/C03 in the Appendix Builder, editing the source field
    // should NOT wipe out that override.
    const isAutoFollow = (target: string, previousSource: string) =>
      (values[target] ?? "") === "" || (values[target] ?? "") === previousSource;

    if (fieldId === "F02" && isAutoFollow("A01", values.F02 ?? "")) {
      next.A01 = value;
    }
    if (fieldId === "F05" && isAutoFollow("A02", values.F05 ?? "")) {
      next.A02 = value;
    }
    if (fieldId === "F08") {
      if (isAutoFollow("A07", values.F08 ?? "")) {
        next.A07 = value;
      }
      const pct = tenPercentOf(value);
      const prevPct = tenPercentOf(values.F08 ?? "");
      if ((values.C03 ?? "") === "" || values.C03 === prevPct) {
        next.C03 = pct;
      }
    }
    setValues(next);
  };

  const loadTemplateFields = async () => {
    try {
      const { data } = await api.get("/masters/");
      const active = [data.form?.[0], data.conditions?.[0], data.appendix?.[0]].filter(Boolean);
      const allFields: MasterField[] = [];
      for (const tpl of active) {
        const fieldsResp = await api.get(`/masters/fields/${tpl.id}`);
        if (Array.isArray(fieldsResp.data)) {
          allFields.push(...fieldsResp.data);
        }
      }
      if (allFields.length === 0) {
        setFields(fallbackFields);
        setFieldLoadWarning("No active master fields found. Showing fallback Form inputs (F01-F08).");
      } else {
        setFields(allFields);
        setFieldLoadWarning("");
      }
    } catch (error) {
      console.error("Failed to load master fields", error);
      setFields(fallbackFields);
      setFieldLoadWarning("Failed to load master fields from backend. Showing fallback Form inputs (F01-F08).");
    }
  };

  const createDraft = async () => {
    const { data } = await api.post("/agreements/", { project, subcontractor, reference_number: reference || undefined });
    setAgreementId(data.id);
    setReference(data.reference_number);
    await loadTemplateFields();
    setStep(2);
  };

  const saveFields = async () => {
    if (!agreementId) return;
    await api.put(`/agreements/${agreementId}/fields`, { values });
  };

  const submitForReview = async () => {
    if (!agreementId) return;
    await saveFields();
    await api.post(`/agreements/${agreementId}/submit`);
    alert("Submitted for internal review.");
  };

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-5">
      <h1 className="text-3xl font-bold text-sky-900">Agreement Creation Wizard</h1>
      <p className="text-sm text-sky-700">Step {step} / 5</p>
      {fieldLoadWarning && (
        <div className="rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800">
          {fieldLoadWarning}
        </div>
      )}

      {step === 1 && (
        <div className="space-y-3 rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
          <h2 className="font-semibold">Step 1: Project + Subcontractor</h2>
          <div className="grid grid-cols-2 gap-2">
            <input className="rounded-lg border border-sky-200 p-2" placeholder="Project name" value={project.project_name} onChange={(e) => setProject({ ...project, project_name: e.target.value })} />
            <input className="rounded-lg border border-sky-200 p-2" placeholder="Project code" value={project.project_code} onChange={(e) => setProject({ ...project, project_code: e.target.value })} />
            <input className="rounded-lg border border-sky-200 p-2" placeholder="Location" value={project.project_location} onChange={(e) => setProject({ ...project, project_location: e.target.value })} />
            <input className="rounded-lg border border-sky-200 p-2" placeholder="Employer" value={project.employer_name} onChange={(e) => setProject({ ...project, employer_name: e.target.value })} />
            <input className="rounded-lg border border-sky-200 p-2" placeholder="Engineer" value={project.engineer_name} onChange={(e) => setProject({ ...project, engineer_name: e.target.value })} />
            <input className="rounded-lg border border-sky-200 p-2" placeholder="Reference override (optional)" value={reference} onChange={(e) => setReference(e.target.value)} />
            <input className="rounded-lg border border-sky-200 p-2" placeholder="Company name" value={subcontractor.company_name} onChange={(e) => setSubcontractor({ ...subcontractor, company_name: e.target.value })} />
            <input className="rounded-lg border border-sky-200 p-2" placeholder="PO Box" value={subcontractor.po_box} onChange={(e) => setSubcontractor({ ...subcontractor, po_box: e.target.value })} />
            <input className="rounded-lg border border-sky-200 p-2" placeholder="Trade licence no" value={subcontractor.trade_licence_no} onChange={(e) => setSubcontractor({ ...subcontractor, trade_licence_no: e.target.value })} />
            <input className="rounded-lg border border-sky-200 p-2" placeholder="Contact person" value={subcontractor.contact_person} onChange={(e) => setSubcontractor({ ...subcontractor, contact_person: e.target.value })} />
            <input className="rounded-lg border border-sky-200 p-2" placeholder="Email" value={subcontractor.email} onChange={(e) => setSubcontractor({ ...subcontractor, email: e.target.value })} />
          </div>
          <button className="rounded-lg bg-sky-600 px-3 py-2 text-white hover:bg-sky-700" onClick={createDraft}>
            Create Draft
          </button>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-2 rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
          <h2 className="font-semibold">Step 2: Form Fields (F01-F08)</h2>
          {formFields.map((field) => (
            <div key={field.id}>
              <label className="mb-1 block text-sm">{field.field_id} - {field.field_label}</label>
              <FieldInput field={field} value={values[field.field_id] ?? ""} onChange={onChangeValue} />
            </div>
          ))}
          <button className="rounded-lg bg-sky-600 px-3 py-2 text-white hover:bg-sky-700" onClick={async () => { await saveFields(); setStep(3); }}>
            Next
          </button>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-2 rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
          <h2 className="font-semibold">Step 3: Conditions Fields (C01-C13)</h2>
          {conditionFields.map((field) => (
            <div key={field.id}>
              <label className="mb-1 block text-sm">{field.field_id} - {field.field_label}</label>
              <FieldInput field={field} value={values[field.field_id] ?? ""} onChange={onChangeValue} />
            </div>
          ))}
          <button className="rounded-lg bg-sky-600 px-3 py-2 text-white hover:bg-sky-700" onClick={async () => { await saveFields(); setStep(4); }}>
            Next
          </button>
        </div>
      )}

      {step === 4 && (
        <div className="space-y-2 rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
          <h2 className="font-semibold">Step 4: Appendix Builder</h2>
          {appendixFields.map((field) => (
            <div key={field.id} className="rounded-lg border border-sky-100 p-2">
              <div className="font-medium">{field.field_id} - {field.field_label}</div>
              <FieldInput field={field} value={values[field.field_id] ?? ""} onChange={onChangeValue} />
            </div>
          ))}
          <button className="rounded-lg bg-sky-600 px-3 py-2 text-white hover:bg-sky-700" onClick={async () => { await saveFields(); setStep(5); }}>
            Next
          </button>
        </div>
      )}

      {step === 5 && (
        <div className="space-y-2 rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
          <h2 className="font-semibold">Step 5: Review</h2>
          <div className="rounded-lg border border-sky-100 bg-sky-50/50 p-2">Reference Number: {reference || "Auto-generated after draft creation"}</div>
          {fields
            .sort((a, b) => a.sort_order - b.sort_order)
            .map((field) => {
              const changed = (values[field.field_id] ?? "") !== (field.default_value ?? "");
              return (
                <div key={field.id} className={`rounded-lg border border-sky-100 p-2 ${changed ? "bg-amber-100" : ""}`}>
                  <strong>{field.field_id}</strong> - {field.field_label}: {values[field.field_id] ?? ""}
                </div>
              );
            })}
          <button className="rounded-lg bg-emerald-600 px-3 py-2 text-white hover:bg-emerald-700" onClick={submitForReview}>
            Submit for Review
          </button>
        </div>
      )}
    </div>
  );
}
