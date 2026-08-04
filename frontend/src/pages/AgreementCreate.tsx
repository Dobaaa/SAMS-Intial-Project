import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import AppendixBuilder from "../components/AppendixBuilder";
import FieldInput from "../components/FieldInput";
import { useToast } from "../components/Toast";
import { api } from "../lib/api";
import { formatNumber } from "../lib/formatNumber";
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
  auto_source_field_id?: string | null;
};

function pctOf(base: string, pct: string): string {
  const b = parseFloat(base.replace(/,/g, "").trim());
  const p = parseFloat(pct.replace(/,/g, "").trim());
  if (!Number.isFinite(b) || !Number.isFinite(p)) return "";
  return (b * p / 100).toFixed(2);
}

// F02-F08 duplicate the project / subcontractor inputs collected on Step 1
// (sub company / PO box / trade licence / employer / project name / location /
// price). Step 2 hides these and the values are synced via buildStep1FieldSync.
// F08 (Subcontract Price) is intentionally kept in Step 2 so admin enters it
// alongside the other Form fields — it is per-agreement, never autofilled.
const STEP1_DUPLICATE_F_FIELDS = new Set(["F02", "F03", "F04", "F05", "F06", "F07"]);

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
  const { id: routeId } = useParams<{ id?: string }>();
  const isEditMode = Boolean(routeId);
  const navigate = useNavigate();
  const toast = useToast();

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
  const [hydrating, setHydrating] = useState(false);
  const [subcontractorOptions, setSubcontractorOptions] = useState<
    Array<{
      id: string;
      company_name: string;
      po_box: string;
      trade_licence_no: string;
      contact_person: string;
      email: string;
      phone: string;
      address: string;
    }>
  >([]);
  const [subSearch, setSubSearch] = useState("");
  // Predefined-project picker (BGCC seeded projects). Selecting one autofills
  // the project fields + reference; "others" lets the admin type a new project
  // which is saved to the projects table on draft creation.
  const [projectOptions, setProjectOptions] = useState<
    Array<{
      id: string;
      project_name: string;
      project_code: string;
      project_location: string;
      employer_name: string;
      engineer_name: string;
      reference: string;
    }>
  >([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string>("");
  const [projectSearch, setProjectSearch] = useState<string>("");
  const projectLocked = Boolean(selectedProjectId) && selectedProjectId !== "others";
  // Filter the dropdown by site no OR project name (case-insensitive). Always
  // keep the currently-selected project visible so the picker doesn't blank out.
  const filteredProjectOptions = projectOptions.filter((p) => {
    if (p.id === selectedProjectId) return true;
    const q = projectSearch.trim().toLowerCase();
    if (!q) return true;
    return (
      p.project_code.toLowerCase().includes(q) ||
      p.project_name.toLowerCase().includes(q)
    );
  });
  // Mandatory-field validation errors, keyed by field_id (master fields) or
  // "project.<x>" / "subcontractor.<x>" (Step 1 party inputs). Populated when
  // the user tries to advance/submit with required fields blank; each entry
  // clears as soon as its field is filled.
  const [errors, setErrors] = useState<Record<string, string>>({});

  const clearError = (key: string) =>
    setErrors((prev) => {
      if (!(key in prev)) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });

  // Step 2 only asks for header-level F fields that AREN'T already collected
  // as project/subcontractor in Step 1 (see STEP1_DUPLICATE_F_FIELDS above).
  // The user requested no repeated inputs.
  const formFields = useMemo(
    () =>
      fields
        .filter((f) => /^F\d+/.test(f.field_id))
        .filter((f) => !STEP1_DUPLICATE_F_FIELDS.has(f.field_id))
        .sort((a, b) => a.sort_order - b.sort_order),
    [fields]
  );
  const conditionFields = useMemo(() => fields.filter((f) => /^C\d+/.test(f.field_id)).sort((a, b) => a.sort_order - b.sort_order), [fields]);
  const appendixFields = useMemo(() => fields.filter((f) => /^A\d+/.test(f.field_id)).sort((a, b) => a.sort_order - b.sort_order), [fields]);
  // A-fields with no auto_source_field_id are the ones admin MUST type in
  // (e.g. A03 Engineer, A15 Commencement Date, A17 Subcontract works completion).
  // A05 (Main Contractor address) is excluded — only Subcontractor address (A06) appears.
  const manualAppendixFields = useMemo(
    () => appendixFields.filter((f) => !f.auto_source_field_id && f.field_id !== "A05"),
    [appendixFields]
  );

  const onChangeValue = (fieldId: string, value: string) => {
    if (value.trim()) clearError(fieldId);
    const next = { ...values, [fieldId]: value };

    // A field is "auto-following" its source if it's empty OR still equals
    // whatever the source used to hold. That's the signal that admin has
    // not manually overridden the cascaded value.
    const isAutoFollow = (target: string, previousSourceVal: string) =>
      (values[target] ?? "") === "" || (values[target] ?? "") === previousSourceVal;

    // C03_PCT × F08 → C03 (Advance Payment amount).
    // Recompute C03 whenever F08 or C03_PCT changes, as long as C03
    // still equals the previously auto-computed value (i.e. admin hasn't
    // manually overridden it).
    if (fieldId === "F08" || fieldId === "C03_PCT") {
      const f08Val = fieldId === "F08" ? value : (values.F08 ?? "");
      const pctVal = fieldId === "C03_PCT" ? value : (next.C03_PCT ?? values.C03_PCT ?? "10");
      const computed = pctOf(f08Val, pctVal);
      const prevF08 = fieldId === "F08" ? (values.F08 ?? "") : f08Val;
      const prevPct = fieldId === "C03_PCT" ? (values.C03_PCT ?? "10") : pctVal;
      const prevComputed = pctOf(prevF08, prevPct);
      if ((values.C03 ?? "") === "" || values.C03 === prevComputed) {
        next.C03 = computed;
      }
    }

    // Generic cascade driven by master_fields.auto_source_field_id. Two
    // passes so chained sources propagate (F08 -> C03 -> A09: pass 1 fills
    // C03 from F08, pass 2 fills A09 from C03). The 10% target handled
    // above is skipped here so the percentage compute wins.
    // C03 is handled by the special compute above — skip generic cascade.
    const tenPctTargets = new Set(["C03"]);
    for (let pass = 0; pass < 2; pass++) {
      for (const f of fields) {
        const src = f.auto_source_field_id;
        if (!src) continue;
        const target = f.field_id;
        if (tenPctTargets.has(target)) continue;
        const srcVal = next[src] ?? "";
        if (!srcVal) continue;
        const oldSrcVal = pass === 0 ? (values[src] ?? "") : "";
        if (isAutoFollow(target, oldSrcVal)) {
          next[target] = srcVal;
        }
      }
    }

    setValues(next);
  };

  const isBlank = (v?: string) => !v || !v.trim();

  // Step 1's Project + Subcontractor inputs map to required Form fields
  // (F06/F07/F05/F02). They're plain inputs (not FieldInput), so they're
  // validated by their own keys rather than via the master-field list.
  const validateStep1 = (): Record<string, string> => {
    const e: Record<string, string> = {};
    if (isBlank(project.project_name)) e["project.project_name"] = "Project name is required.";
    if (isBlank(project.project_code)) e["project.project_code"] = "Site number is required (used in the reference number).";
    if (isBlank(project.project_location)) e["project.project_location"] = "Project location is required.";
    if (isBlank(project.employer_name)) e["project.employer_name"] = "Employer is required.";
    if (isBlank(subcontractor.company_name)) e["subcontractor.company_name"] = "Subcontractor company name is required.";
    for (const f of manualAppendixFields) {
      if (f.is_required && isBlank(values[f.field_id])) {
        e[f.field_id] = `${f.field_id} — ${f.field_label} is required.`;
      }
    }
    return e;
  };

  // Generic required-field check over a list of master fields (Steps 2 & 3).
  const validateFieldList = (list: MasterField[]): Record<string, string> => {
    const e: Record<string, string> = {};
    for (const f of list) {
      if (f.is_required && isBlank(values[f.field_id])) {
        e[f.field_id] = `${f.field_id} — ${f.field_label} is required.`;
      }
    }
    return e;
  };

  // Full sweep used at submit time so the Review step lists every outstanding
  // mandatory field, regardless of which step it lives on.
  const validateAll = (): Record<string, string> => ({
    ...validateStep1(),
    ...validateFieldList(formFields),
    ...validateFieldList(conditionFields),
  });

  // Run `validator`; if anything is missing, surface it and stop. Returns true
  // when the caller is clear to proceed.
  const passesValidation = (validator: () => Record<string, string>): boolean => {
    const found = validator();
    setErrors(found);
    if (Object.keys(found).length > 0) {
      toast.error("Please fill all mandatory fields highlighted below.");
      return false;
    }
    return true;
  };

  const goToStep = (n: number) => {
    setErrors({});
    setStep(n);
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

  // Step 1's project + subcontractor data IS the source of truth for F02-F08
  // (sub company, PO box, trade licence, employer, project name, location,
  // price). We push those values into the field-values map immediately after
  // creating/updating the draft so Step 2/3/4 see them cascaded into A01,
  // A02, A04, A06, A07 etc., and the user never re-types the same info.
  const buildStep1FieldSync = (): Record<string, string> => {
    const out: Record<string, string> = {};
    if (subcontractor.company_name) out.F02 = subcontractor.company_name;
    if (subcontractor.po_box) out.F03 = subcontractor.po_box;
    if (subcontractor.trade_licence_no) out.F04 = subcontractor.trade_licence_no;
    if (project.employer_name) out.F05 = project.employer_name;
    if (project.project_name) out.F06 = project.project_name;
    if (project.project_location) out.F07 = project.project_location;
    // F08 (price) is intentionally not synced — admin enters it explicitly
    // in Step 2 alongside F01 (signing date) + F09 (scope title).
    // A06 gets the full subcontractor address for notices (overrides the F03
    // PO-Box-only cascade when the admin enters the full address).
    if (subcontractor.address) out.A06 = subcontractor.address;
    // A03 (Engineer/Consultant) cascades from the project's engineer field.
    // Admin can still override it by typing in the appendix inputs section;
    // the manual value wins (manualAppendixFields loop runs after this).
    if (project.engineer_name) out.A03 = project.engineer_name;
    return out;
  };

  const createDraft = async () => {
    if (!passesValidation(validateStep1)) return;
    try {
      const { data } = await api.post("/agreements/", {
        project: { ...project, reference: reference || undefined },
        subcontractor,
        reference_number: reference || undefined,
      });
      setAgreementId(data.id);
      setReference(data.reference_number);
      // Sync F02-F07 from Step 1's project/subcontractor inputs, plus any
      // manual appendix fields admin filled on Step 1 (A03/A05/A15/A17 etc.).
      const payload: Record<string, string> = { ...buildStep1FieldSync() };
      for (const f of manualAppendixFields) {
        const v = values[f.field_id];
        if (v !== undefined && v !== "") payload[f.field_id] = v;
      }
      if (Object.keys(payload).length > 0) {
        const { data: putData } = await api.put(`/agreements/${data.id}/fields`, { values: payload });
        if (putData?.values && typeof putData.values === "object") {
          setValues((prev) => ({ ...prev, ...putData.values }));
        }
      }
      setStep(2);
    } catch (err: unknown) {
      const e = err as { response?: { status?: number; data?: { detail?: string } } };
      if (e?.response?.status === 409) {
        toast.error(e.response.data?.detail ?? "Reference number conflict — leave the field blank to auto-generate.");
      } else {
        toast.error("Failed to create draft. See console for details.");
        console.error(err);
      }
    }
  };

  // Load master fields once on mount (regardless of new vs. edit mode) so
  // Step 1 can render the manual appendix inputs (A03/A05/A15/A17) before
  // the draft has been created.
  useEffect(() => {
    void loadTemplateFields();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load saved projects (incl. BGCC predefined) once for the Step 1 dropdown.
  useEffect(() => {
    if (isEditMode) return; // picker only makes sense for fresh drafts
    (async () => {
      try {
        const { data } = await api.get("/projects/");
        setProjectOptions(Array.isArray(data) ? data : []);
      } catch (err) {
        console.warn("Failed to load projects", err);
      }
    })();
  }, [isEditMode]);

  // Pick a predefined project -> autofill all project fields + reference and
  // lock them. "others" clears the fields for manual entry; the new project is
  // saved to the projects table when the draft is created.
  const applyProjectSelection = (id: string) => {
    setSelectedProjectId(id);
    setErrors({});
    if (id === "others") {
      setProject({ project_name: "", project_code: "", project_location: "", employer_name: "", engineer_name: "" });
      setReference("");
      return;
    }
    if (!id) return;
    const p = projectOptions.find((o) => o.id === id);
    if (!p) return;
    setProject({
      project_name: p.project_name || "",
      project_code: p.project_code || "",
      project_location: p.project_location || "",
      employer_name: p.employer_name || "",
      engineer_name: p.engineer_name || "",
    });
    setReference(p.reference || "");
    // Pre-fill A03 (Engineer/Consultant) in the appendix inputs from the
    // project record so admin sees it populated rather than having to
    // re-type it below in the appendix section.
    if (p.engineer_name) setValues((prev) => ({ ...prev, A03: p.engineer_name! }));
  };

  // Subcontractor picker: debounce the search input and call the list
  // endpoint so admin can pick an existing subcontractor instead of re-typing
  // company name / PO box / trade licence / contact details. Contract price
  // (F08) is NEVER copied — that's per-agreement.
  useEffect(() => {
    if (isEditMode) return; // picker only makes sense for fresh drafts
    const handle = setTimeout(async () => {
      try {
        const { data } = await api.get("/subcontractors/", {
          params: subSearch ? { search: subSearch } : undefined,
        });
        setSubcontractorOptions(Array.isArray(data) ? data : []);
      } catch (err) {
        console.warn("Failed to load subcontractors", err);
      }
    }, 250);
    return () => clearTimeout(handle);
  }, [subSearch, isEditMode]);

  const applySubcontractor = (
    pick: (typeof subcontractorOptions)[number] | null
  ) => {
    if (!pick) return;
    setSubcontractor({
      company_name: pick.company_name || "",
      po_box: pick.po_box || "",
      trade_licence_no: pick.trade_licence_no || "",
      contact_person: pick.contact_person || "",
      email: pick.email || "",
      phone: pick.phone || "",
      address: pick.address || "",
    });
    toast.success(`Pre-filled subcontractor details from ${pick.company_name}.`);
  };

  // Edit-existing-draft hydration: when route is /agreements/:id/edit, pull
  // the agreement detail (project, subcontractor, reference, value map) and
  // start at Step 1 with all state pre-populated so admin can amend any
  // input — project, subcontractor, or the manual appendix fields.
  useEffect(() => {
    if (!routeId) return;
    let cancelled = false;
    (async () => {
      setHydrating(true);
      try {
        const { data } = await api.get(`/agreements/${routeId}`);
        if (cancelled) return;
        setAgreementId(data.id);
        setReference(data.reference_number ?? "");
        if (data.project) setProject(data.project);
        if (data.subcontractor) setSubcontractor(data.subcontractor);
        if (data.values && typeof data.values === "object") setValues(data.values);
        await loadTemplateFields();
        setStep(1);
      } catch (err) {
        console.error("Failed to hydrate existing draft", err);
        setFieldLoadWarning("Could not load the existing draft. Returning to a fresh wizard.");
      } finally {
        if (!cancelled) setHydrating(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId]);

  // Step 1 in edit mode: PATCH parties + PUT manual appendix values, then
  // advance to Step 2. Skips the POST /agreements/ used for fresh drafts.
  const saveStep1Edit = async () => {
    if (!agreementId) return;
    if (!passesValidation(validateStep1)) return;
    try {
      await api.patch(`/agreements/${agreementId}/parties`, { project, subcontractor });
      const payload: Record<string, string> = { ...buildStep1FieldSync() };
      for (const f of manualAppendixFields) {
        const v = values[f.field_id];
        if (v !== undefined) payload[f.field_id] = v;
      }
      if (Object.keys(payload).length > 0) {
        const { data: putData } = await api.put(`/agreements/${agreementId}/fields`, { values: payload });
        if (putData?.values && typeof putData.values === "object") {
          setValues((prev) => ({ ...prev, ...putData.values }));
        }
      }
      setStep(2);
    } catch (err: unknown) {
      const e = err as { response?: { status?: number; data?: { detail?: string } } };
      if (e?.response?.status === 409) {
        toast.error(e.response.data?.detail ?? "Project code conflict.");
      } else {
        toast.error("Failed to save changes. See console for details.");
        console.error(err);
      }
    }
  };

  const saveFields = async () => {
    if (!agreementId) return;
    const { data } = await api.put(`/agreements/${agreementId}/fields`, { values });
    // Backend cascades F02→A01, F08→C03→A09, etc. The PUT response carries
    // the full post-cascade value map; merge it back so Steps 4 and 5 reflect
    // the DB truth instead of stale client state.
    if (data?.values && typeof data.values === "object") {
      setValues((prev) => ({ ...prev, ...data.values }));
    }
  };

  const submitForReview = async () => {
    if (!agreementId) return;
    if (!passesValidation(validateAll)) return;
    try {
      await saveFields();
      await api.post(`/agreements/${agreementId}/submit`);
      toast.success(`Agreement ${reference || agreementId} submitted for internal review.`);
      navigate("/dashboard");
    } catch (err: unknown) {
      const e = err as { response?: { status?: number; data?: { detail?: string } } };
      toast.error(e?.response?.data?.detail ?? "Failed to submit for review. See console for details.");
      console.error(err);
    }
  };

  const renderErrorBanner = () => {
    const msgs = Object.values(errors);
    if (msgs.length === 0) return null;
    return (
      <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-red-800">
        <p className="mb-1 font-semibold">
          {msgs.length} mandatory field{msgs.length > 1 ? "s" : ""} still need attention:
        </p>
        <ul className="ml-5 list-disc space-y-0.5">
          {msgs.map((m) => (
            <li key={m}>{m}</li>
          ))}
        </ul>
      </div>
    );
  };

  return (
    <div className="mx-auto max-w-5xl space-y-5 p-5">
      <h1 className="text-3xl font-bold text-sky-900">
        {isEditMode ? "Edit Agreement Draft" : "Agreement Creation Wizard"}
      </h1>
      <p className="text-sm text-sky-700">
        Step {step} / 5
        {reference ? <> — <span className="font-mono">{reference}</span></> : null}
      </p>
      {hydrating && (
        <div className="rounded border border-sky-200 bg-sky-50 p-2 text-sm text-sky-800">
          Loading existing draft…
        </div>
      )}
      {fieldLoadWarning && (
        <div className="rounded border border-amber-300 bg-amber-50 p-2 text-sm text-amber-800">
          {fieldLoadWarning}
        </div>
      )}

      {step === 1 && (
        <div className="space-y-4 rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
          <h2 className="font-semibold">
            Step 1: Project + Subcontractor
            {isEditMode && <span className="ml-2 text-xs font-normal text-sky-600">(editing)</span>}
          </h2>

          {renderErrorBanner()}

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-sky-800">Project</h3>

            {!isEditMode && (
              <div className="space-y-1 rounded-lg border border-sky-100 bg-sky-50/50 p-3">
                <label className="block text-xs font-semibold text-sky-800">Select a project</label>
                <input
                  type="text"
                  className="w-full rounded border p-2 text-sm"
                  placeholder="Search by site no or project name…"
                  value={projectSearch}
                  onChange={(e) => setProjectSearch(e.target.value)}
                />
                <select
                  className="w-full rounded border p-2"
                  value={selectedProjectId}
                  onChange={(e) => applyProjectSelection(e.target.value)}
                >
                  <option value="">— Select a project —</option>
                  {filteredProjectOptions.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.project_code} · {p.project_name}
                    </option>
                  ))}
                  <option value="others">Others (enter manually)</option>
                </select>
                {projectSearch.trim() && (() => {
                  const q = projectSearch.trim().toLowerCase();
                  const n = projectOptions.filter(
                    (p) =>
                      p.project_code.toLowerCase().includes(q) ||
                      p.project_name.toLowerCase().includes(q)
                  ).length;
                  return (
                    <p className="text-xs text-sky-700">
                      {n} match{n === 1 ? "" : "es"}{n === 0 ? " — pick “Others” to enter manually" : ""}
                    </p>
                  );
                })()}
                <p className="text-xs text-sky-700">
                  {projectLocked
                    ? "Project details autofilled from the selected project. Choose “Others” to enter a new project."
                    : "Pick a predefined project to autofill its details, or “Others” to type a new one (it’s saved when you create the draft)."}
                </p>
              </div>
            )}

            <div>
              <label className="mb-1 block text-sm">Project name <span className="text-red-500">*</span></label>
              <input readOnly={projectLocked} className={`w-full rounded border p-2${projectLocked ? " bg-gray-100" : ""}${errors["project.project_name"] ? " border-red-500 bg-red-50" : ""}`} value={project.project_name} onChange={(e) => { if (e.target.value.trim()) clearError("project.project_name"); setProject({ ...project, project_name: e.target.value }); }} />
              {errors["project.project_name"] && <p className="mt-1 text-xs text-red-600">{errors["project.project_name"]}</p>}
            </div>
            <div>
              <label className="mb-1 block text-sm">Site number (used as the {`{SITE_NO}`} part of the reference, e.g. SAG-2026-319-001) <span className="text-red-500">*</span></label>
              <input readOnly={projectLocked} className={`w-full rounded border p-2${projectLocked ? " bg-gray-100" : ""}${errors["project.project_code"] ? " border-red-500 bg-red-50" : ""}`} value={project.project_code} onChange={(e) => { if (e.target.value.trim()) clearError("project.project_code"); setProject({ ...project, project_code: e.target.value }); }} />
              {errors["project.project_code"] && <p className="mt-1 text-xs text-red-600">{errors["project.project_code"]}</p>}
            </div>
            <div>
              <label className="mb-1 block text-sm">Location <span className="text-red-500">*</span></label>
              <input readOnly={projectLocked} className={`w-full rounded border p-2${projectLocked ? " bg-gray-100" : ""}${errors["project.project_location"] ? " border-red-500 bg-red-50" : ""}`} value={project.project_location} onChange={(e) => { if (e.target.value.trim()) clearError("project.project_location"); setProject({ ...project, project_location: e.target.value }); }} />
              {errors["project.project_location"] && <p className="mt-1 text-xs text-red-600">{errors["project.project_location"]}</p>}
            </div>
            <div>
              <label className="mb-1 block text-sm">Employer <span className="text-red-500">*</span></label>
              <input readOnly={projectLocked} className={`w-full rounded border p-2${projectLocked ? " bg-gray-100" : ""}${errors["project.employer_name"] ? " border-red-500 bg-red-50" : ""}`} value={project.employer_name} onChange={(e) => { if (e.target.value.trim()) clearError("project.employer_name"); setProject({ ...project, employer_name: e.target.value }); }} />
              {errors["project.employer_name"] && <p className="mt-1 text-xs text-red-600">{errors["project.employer_name"]}</p>}
            </div>
            <div>
              <label className="mb-1 block text-sm">Engineer / Consultant</label>
              <input className="w-full rounded border p-2" value={project.engineer_name} onChange={(e) => setProject({ ...project, engineer_name: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-sm">Reference number override (optional, auto-generated otherwise)</label>
              <input readOnly={projectLocked} className={`w-full rounded border p-2${projectLocked ? " bg-gray-100" : ""}`} value={reference} onChange={(e) => setReference(e.target.value)} />
            </div>
          </section>

          <section className="space-y-2">
            <h3 className="text-sm font-semibold text-sky-800">Subcontractor</h3>

            {!isEditMode && (
              <div className="space-y-2 rounded-lg border border-sky-100 bg-sky-50/50 p-3">
                <label className="block text-xs font-semibold text-sky-800">
                  Search existing subcontractors (optional)
                </label>
                <input
                  type="text"
                  className="w-full rounded border p-2 text-sm"
                  placeholder="Type a company name to filter..."
                  value={subSearch}
                  onChange={(e) => setSubSearch(e.target.value)}
                />
                {subcontractorOptions.length > 0 && (
                  <select
                    className="w-full rounded border p-2 text-sm"
                    defaultValue=""
                    onChange={(e) => {
                      const pick = subcontractorOptions.find((o) => o.id === e.target.value) ?? null;
                      applySubcontractor(pick);
                    }}
                  >
                    <option value="">— Pick a subcontractor to auto-fill —</option>
                    {subcontractorOptions.map((opt) => (
                      <option key={opt.id} value={opt.id}>
                        {opt.company_name}
                        {opt.trade_licence_no ? ` · TL ${opt.trade_licence_no}` : ""}
                      </option>
                    ))}
                  </select>
                )}
                <p className="text-xs text-sky-700">
                  Picks pre-fill company / PO box / trade licence / contact / email / phone / address.
                  Subcontract price stays blank — it's always entered per agreement.
                </p>
              </div>
            )}

            <div>
              <label className="mb-1 block text-sm">Company name <span className="text-red-500">*</span></label>
              <input className={`w-full rounded border p-2${errors["subcontractor.company_name"] ? " border-red-500 bg-red-50" : ""}`} value={subcontractor.company_name} onChange={(e) => { if (e.target.value.trim()) clearError("subcontractor.company_name"); setSubcontractor({ ...subcontractor, company_name: e.target.value }); }} />
              {errors["subcontractor.company_name"] && <p className="mt-1 text-xs text-red-600">{errors["subcontractor.company_name"]}</p>}
            </div>
            <div>
              <label className="mb-1 block text-sm">PO Box</label>
              <input className="w-full rounded border p-2" value={subcontractor.po_box} onChange={(e) => setSubcontractor({ ...subcontractor, po_box: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-sm">Trade licence no</label>
              <input className="w-full rounded border p-2" value={subcontractor.trade_licence_no} onChange={(e) => setSubcontractor({ ...subcontractor, trade_licence_no: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-sm">Contact person</label>
              <input className="w-full rounded border p-2" value={subcontractor.contact_person} onChange={(e) => setSubcontractor({ ...subcontractor, contact_person: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-sm">Email</label>
              <input className="w-full rounded border p-2" value={subcontractor.email} onChange={(e) => setSubcontractor({ ...subcontractor, email: e.target.value })} />
            </div>
            <div>
              <label className="mb-1 block text-sm">
                Full address for notices (A06 — Appendix communication address)
              </label>
              <textarea
                className="w-full rounded border p-2"
                rows={3}
                placeholder={"M/s. Company LLC\nP.O. Box 12345\nDubai, UAE"}
                value={subcontractor.address}
                onChange={(e) => setSubcontractor({ ...subcontractor, address: e.target.value })}
              />
              <p className="mt-0.5 text-xs text-sky-700">
                Multi-line address used in the appendix "Communications Address for Serving of Notices" row (A06).
              </p>
            </div>
          </section>

          {manualAppendixFields.length > 0 && (
            <section className="space-y-2">
              <h3 className="text-sm font-semibold text-sky-800">
                Required appendix inputs ({manualAppendixFields.length})
              </h3>
              <p className="text-xs text-sky-700">
                These appendix rows have no source field elsewhere — fill them in here so they
                propagate into the rest of the wizard.
              </p>
              {manualAppendixFields.map((field) => (
                <div key={field.id}>
                  <label className="mb-1 block text-sm">
                    {field.field_id} — {field.field_label}
                    {field.is_required && <span className="text-red-500"> *</span>}
                    </label>
                  <FieldInput field={field} value={values[field.field_id] ?? ""} onChange={onChangeValue} invalid={Boolean(errors[field.field_id])} />
                  {errors[field.field_id] && <p className="mt-1 text-xs text-red-600">{errors[field.field_id]}</p>}
                </div>
              ))}
            </section>
          )}

          <button
            className="rounded-lg bg-sky-600 px-3 py-2 text-white hover:bg-sky-700"
            onClick={isEditMode ? saveStep1Edit : createDraft}
          >
            {isEditMode ? "Save & Continue" : "Create Draft"}
          </button>
        </div>
      )}

      {step === 2 && (
        <div className="space-y-2 rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
          <h2 className="font-semibold">Step 2: Form of Agreement Header</h2>
          <p className="text-sm text-sky-700">
            Project details, subcontractor identity, employer and engineer
            entered in Step 1 are already attached. Enter the Subcontract Price
            and any remaining Form fields below.
          </p>
          {formFields.length === 0 ? (
            <div className="rounded border border-sky-100 bg-sky-50/50 p-2 text-sm text-sky-700">
              No additional Form fields to enter. Click Next to continue.
            </div>
          ) : (
            <>
              {renderErrorBanner()}
              {formFields.map((field) => (
                <div key={field.id}>
                  <label className="mb-1 block text-sm">
                    {field.field_id} - {field.field_label}
                    {field.is_required && <span className="text-red-500"> *</span>}
                  </label>
                  <FieldInput field={field} value={values[field.field_id] ?? ""} onChange={onChangeValue} invalid={Boolean(errors[field.field_id])} />
                  {errors[field.field_id] && <p className="mt-1 text-xs text-red-600">{errors[field.field_id]}</p>}
                </div>
              ))}
            </>
          )}
          <div className="flex gap-2">
            <button
              className="rounded-lg border border-sky-300 px-3 py-2 text-sky-700 hover:bg-sky-50"
              onClick={() => goToStep(1)}
            >
              Back
            </button>
            <button className="rounded-lg bg-sky-600 px-3 py-2 text-white hover:bg-sky-700" onClick={async () => { if (!passesValidation(() => validateFieldList(formFields))) return; await saveFields(); goToStep(3); }}>
              Next
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div className="space-y-2 rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
          <h2 className="font-semibold">Step 3: Conditions Fields (C01-C15)</h2>
          {renderErrorBanner()}
          {conditionFields.map((field) => (
            <div key={field.id}>
              <label className="mb-1 block text-sm">
                {field.field_id} - {field.field_label}
                {field.is_required && <span className="text-red-500"> *</span>}
              </label>
              <FieldInput field={field} value={values[field.field_id] ?? ""} onChange={onChangeValue} invalid={Boolean(errors[field.field_id])} />
              {errors[field.field_id] && <p className="mt-1 text-xs text-red-600">{errors[field.field_id]}</p>}
            </div>
          ))}
          <div className="flex gap-2">
            <button
              className="rounded-lg border border-sky-300 px-3 py-2 text-sky-700 hover:bg-sky-50"
              onClick={() => goToStep(2)}
            >
              Back
            </button>
            <button className="rounded-lg bg-sky-600 px-3 py-2 text-white hover:bg-sky-700" onClick={async () => { if (!passesValidation(() => validateFieldList(conditionFields))) return; await saveFields(); goToStep(4); }}>
              Next
            </button>
          </div>
        </div>
      )}

      {step === 4 && (
        <div className="space-y-4 rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
          <div>
            <h2 className="font-semibold">Step 4: Appendix Builder</h2>
            <p className="text-sm text-sky-700">
              Each appendix row is shown below with its current value. Use the Edit button on
              each row to amend the value, toggle visibility, add an admin note, or reorder.
              Required inputs (rows without a source field) can also be filled here.
            </p>
          </div>

          {agreementId && (
            <AppendixBuilder agreementId={agreementId} refreshKey={JSON.stringify(values)} />
          )}

          <div className="flex gap-2">
            <button
              className="rounded-lg border border-sky-300 px-3 py-2 text-sky-700 hover:bg-sky-50"
              onClick={() => goToStep(3)}
            >
              Back
            </button>
            <button
              className="rounded-lg bg-sky-600 px-3 py-2 text-white hover:bg-sky-700"
              onClick={async () => {
                await saveFields();
                goToStep(5);
              }}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {step === 5 && (
        <div className="space-y-2 rounded-xl border border-sky-100 bg-white p-4 shadow-sm">
          <h2 className="font-semibold">Step 5: Review</h2>
          {renderErrorBanner()}
          <div className="rounded-lg border border-sky-100 bg-sky-50/50 p-2">Reference Number: {reference || "Auto-generated after draft creation"}</div>
          {fields
            .sort((a, b) => a.sort_order - b.sort_order)
            .map((field) => {
              const changed = (values[field.field_id] ?? "") !== (field.default_value ?? "");
              const raw = values[field.field_id] ?? "";
              const display = field.input_type === "number" ? formatNumber(raw) : raw;
              return (
                <div key={field.id} className={`rounded-lg border border-sky-100 p-2 ${changed ? "bg-amber-100" : ""}`}>
                  <strong>{field.field_id}</strong> - {field.field_label}: {display}
                </div>
              );
            })}
          <div className="flex gap-2">
            <button
              className="rounded-lg border border-sky-300 px-3 py-2 text-sky-700 hover:bg-sky-50"
              onClick={() => goToStep(4)}
            >
              Back
            </button>
            <button className="rounded-lg bg-emerald-600 px-3 py-2 text-white hover:bg-emerald-700" onClick={submitForReview}>
              Submit for Review
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
