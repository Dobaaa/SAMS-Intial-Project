import axios from "axios";
import { useMemo, useState } from "react";

import FieldInput from "../components/FieldInput";
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

const api = axios.create({ baseURL: "/api" });

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

  const formFields = useMemo(() => fields.filter((f) => /^F\d+/.test(f.field_id)).sort((a, b) => a.sort_order - b.sort_order), [fields]);
  const conditionFields = useMemo(() => fields.filter((f) => /^C\d+/.test(f.field_id)).sort((a, b) => a.sort_order - b.sort_order), [fields]);
  const appendixFields = useMemo(() => fields.filter((f) => /^A\d+/.test(f.field_id)).sort((a, b) => a.sort_order - b.sort_order), [fields]);

  const onChangeValue = (fieldId: string, value: string) => {
    const next = { ...values, [fieldId]: value };
    if (fieldId === "F02") next.A01 = value;
    if (fieldId === "F05") next.A02 = value;
    if (fieldId === "F08") {
      next.A07 = value;
      next.C03 = value;
    }
    setValues(next);
  };

  const loadTemplateFields = async () => {
    const { data } = await api.get("/masters/");
    const active = [data.form?.[0], data.conditions?.[0], data.appendix?.[0]].filter(Boolean);
    const allFields: MasterField[] = [];
    for (const tpl of active) {
      const fieldsResp = await api.get(`/masters/fields/${tpl.id}`);
      allFields.push(...fieldsResp.data);
    }
    setFields(allFields);
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
    <div className="mx-auto max-w-5xl space-y-4 p-4">
      <h1 className="text-2xl font-semibold">Agreement Creation Wizard</h1>
      <p className="text-sm text-gray-600">Step {step} / 5</p>

      {step === 1 && (
        <div className="space-y-3 rounded border p-4">
          <h2 className="font-semibold">Step 1: Project + Subcontractor</h2>
          <div className="grid grid-cols-2 gap-2">
            <input className="rounded border p-2" placeholder="Project name" value={project.project_name} onChange={(e) => setProject({ ...project, project_name: e.target.value })} />
            <input className="rounded border p-2" placeholder="Project code" value={project.project_code} onChange={(e) => setProject({ ...project, project_code: e.target.value })} />
            <input className="rounded border p-2" placeholder="Location" value={project.project_location} onChange={(e) => setProject({ ...project, project_location: e.target.value })} />
            <input className="rounded border p-2" placeholder="Employer" value={project.employer_name} onChange={(e) => setProject({ ...project, employer_name: e.target.value })} />
            <input className="rounded border p-2" placeholder="Engineer" value={project.engineer_name} onChange={(e) => setProject({ ...project, engineer_name: e.target.value })} />
            <input className="rounded border p-2" placeholder="Reference override (optional)" value={reference} onChange={(e) => setReference(e.target.value)} />
            <input className="rounded border p-2" placeholder="Company name" value={subcontractor.company_name} onChange={(e) => setSubcontractor({ ...subcontractor, company_name: e.target.value })} />
            <input className="rounded border p-2" placeholder="PO Box" value={subcontractor.po_box} onChange={(e) => setSubcontractor({ ...subcontractor, po_box: e.target.value })} />
            <input className="rounded border p-2" placeholder="Trade licence no" value={subcontractor.trade_licence_no} onChange={(e) => setSubcontractor({ ...subcontractor, trade_licence_no: e.target.value })} />
            <input className="rounded border p-2" placeholder="Contact person" value={subcontractor.contact_person} onChange={(e) => setSubcontractor({ ...subcontractor, contact_person: e.target.value })} />
            <input className="rounded border p-2" placeholder="Email" value={subcontractor.email} onChange={(e) => setSubcontractor({ ...subcontractor, email: e.target.value })} />
          </div>
          <button className="rounded bg-black px-3 py-2 text-white" onClick={createDraft}>
            Create Draft
          </button>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-2 rounded border p-4">
          <h2 className="font-semibold">Step 2: Form Fields (F01-F08)</h2>
          {formFields.map((field) => (
            <div key={field.id}>
              <label className="mb-1 block text-sm">{field.field_id} - {field.field_label}</label>
              <FieldInput field={field} value={values[field.field_id] ?? ""} onChange={onChangeValue} />
            </div>
          ))}
          <button className="rounded bg-black px-3 py-2 text-white" onClick={async () => { await saveFields(); setStep(3); }}>
            Next
          </button>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-2 rounded border p-4">
          <h2 className="font-semibold">Step 3: Conditions Fields (C01-C13)</h2>
          {conditionFields.map((field) => (
            <div key={field.id}>
              <label className="mb-1 block text-sm">{field.field_id} - {field.field_label}</label>
              <FieldInput field={field} value={values[field.field_id] ?? ""} onChange={onChangeValue} />
            </div>
          ))}
          <button className="rounded bg-black px-3 py-2 text-white" onClick={async () => { await saveFields(); setStep(4); }}>
            Next
          </button>
        </div>
      )}

      {step === 4 && (
        <div className="space-y-2 rounded border p-4">
          <h2 className="font-semibold">Step 4: Appendix Builder</h2>
          {appendixFields.map((field) => (
            <div key={field.id} className="rounded border p-2">
              <div className="font-medium">{field.field_id} - {field.field_label}</div>
              <FieldInput field={field} value={values[field.field_id] ?? ""} onChange={onChangeValue} />
            </div>
          ))}
          <button className="rounded bg-black px-3 py-2 text-white" onClick={async () => { await saveFields(); setStep(5); }}>
            Next
          </button>
        </div>
      )}

      {step === 5 && (
        <div className="space-y-2 rounded border p-4">
          <h2 className="font-semibold">Step 5: Review</h2>
          <div className="rounded border p-2">Reference Number: {reference || "Auto-generated after draft creation"}</div>
          {fields
            .sort((a, b) => a.sort_order - b.sort_order)
            .map((field) => {
              const changed = (values[field.field_id] ?? "") !== (field.default_value ?? "");
              return (
                <div key={field.id} className={`rounded border p-2 ${changed ? "bg-amber-100" : ""}`}>
                  <strong>{field.field_id}</strong> - {field.field_label}: {values[field.field_id] ?? ""}
                </div>
              );
            })}
          <button className="rounded bg-green-700 px-3 py-2 text-white" onClick={submitForReview}>
            Submit for Review
          </button>
        </div>
      )}
    </div>
  );
}
