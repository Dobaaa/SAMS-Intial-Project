import { useEffect, useMemo, useState } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Placeholder from "@tiptap/extension-placeholder";

import FieldCatalog, { type MasterField } from "../components/FieldCatalog";
import { api } from "../lib/api";

type Template = {
  id: string;
  type: "form" | "conditions" | "appendix";
  version_number: string;
  version_date: string;
  is_active: boolean;
  notes?: string | null;
};

export default function MasterTemplates() {
  const [grouped, setGrouped] = useState<Record<string, Template[]>>({});
  const [selectedTemplate, setSelectedTemplate] = useState<Template | null>(null);
  const [fields, setFields] = useState<MasterField[]>([]);
  const [versionNumber, setVersionNumber] = useState("v1.0");
  const [versionDate, setVersionDate] = useState(new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");

  const editor = useEditor({
    extensions: [StarterKit, Placeholder.configure({ placeholder: "Edit legal template HTML content..." })],
    content: "<p>Start template content...</p>",
  });

  const currentType = useMemo(() => selectedTemplate?.type ?? "form", [selectedTemplate]);

  const loadTemplates = async () => {
    const { data } = await api.get("/masters/");
    setGrouped(data);
    const first = data.form?.[0] ?? data.conditions?.[0] ?? data.appendix?.[0] ?? null;
    if (first) setSelectedTemplate(first);
  };

  const loadTemplateDetails = async (templateId: string) => {
    const { data } = await api.get(`/masters/${templateId}`);
    setFields(data.fields);
    if (editor) editor.commands.setContent(data.template.content_html || "<p></p>");
  };

  useEffect(() => {
    void loadTemplates();
  }, []);

  useEffect(() => {
    if (selectedTemplate) {
      void loadTemplateDetails(selectedTemplate.id);
    }
  }, [selectedTemplate]);

  const createVersion = async () => {
    await api.post("/masters/", {
      type: currentType,
      version_number: versionNumber,
      version_date: versionDate,
      content_html: editor?.getHTML() ?? "",
      notes,
    });
    await loadTemplates();
  };

  const createField = async (payload: Omit<MasterField, "id">) => {
    await api.post("/masters/fields/", payload);
    if (selectedTemplate) await loadTemplateDetails(selectedTemplate.id);
  };
  const updateField = async (id: string, payload: Omit<MasterField, "id">) => {
    await api.put(`/masters/fields/${id}`, payload);
    if (selectedTemplate) await loadTemplateDetails(selectedTemplate.id);
  };
  const deleteField = async (id: string) => {
    await api.delete(`/masters/fields/${id}`);
    if (selectedTemplate) await loadTemplateDetails(selectedTemplate.id);
  };

  return (
    <div className="space-y-4 p-4">
      <details className="rounded-xl border border-sky-200 bg-sky-50/60 p-3 shadow-sm">
        <summary className="cursor-pointer text-sm font-semibold text-sky-900">
          About the Masters section — full guide (open me before you change anything)
        </summary>
        <div className="mt-3 space-y-4 text-sm text-sky-900">

          <div>
            <div className="font-semibold text-base">What is the Masters section?</div>
            <p>
              Every subcontract agreement BGCC issues is built from <strong>three
              master templates</strong>: the <em>Form of Subcontract Agreement</em>
              (the cover + signature page), the <em>Conditions of Subcontract
              Agreement</em> (the 14 clause sections of legal terms), and the
              <em> Appendix to the Subcontract Agreement</em> (the summary table
              of all the variable values). The Masters section is where you
              maintain those three templates: their <em>legal text</em> (the
              boilerplate that appears the same on every agreement) and their
              <em> field catalog</em> (the specific spots in the text that admin
              fills in per agreement). Think of it as editing the parent
              document, not any specific agreement.
            </p>
          </div>

          <div>
            <div className="font-semibold text-base">Why this matters</div>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                Admin <strong>never re-types the legal boilerplate</strong> for a
                new agreement — it's already in the master. Admin only fills in
                the <code>[Insert]</code>-style slots, called <em>fields</em>.
              </li>
              <li>
                When BGCC's legal team updates a clause, you change it
                <strong> once in the master</strong> and every future agreement
                uses the new wording. Old agreements stay frozen on whichever
                version they were created from.
              </li>
              <li>
                The wizard, the workflow PDF preview, and the final signed PDF
                all read from the masters. There is no other source of truth.
              </li>
            </ul>
          </div>

          <div>
            <div className="font-semibold text-base">1. The three template types</div>
            <table className="w-full border-collapse text-xs">
              <thead className="bg-sky-100">
                <tr>
                  <th className="border border-sky-200 p-1 text-left">Type</th>
                  <th className="border border-sky-200 p-1 text-left">Field IDs</th>
                  <th className="border border-sky-200 p-1 text-left">What it contains</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td className="border border-sky-200 p-1"><strong>Form</strong></td>
                  <td className="border border-sky-200 p-1"><code>F01–F09</code></td>
                  <td className="border border-sky-200 p-1">
                    The first page (party names, project, scope, subcontract price)
                    plus the closing signature block.
                  </td>
                </tr>
                <tr>
                  <td className="border border-sky-200 p-1"><strong>Conditions</strong></td>
                  <td className="border border-sky-200 p-1"><code>C01–C14</code></td>
                  <td className="border border-sky-200 p-1">
                    The 14 clause sections: scope details, payment terms,
                    retention, programme, defects, LDs, variations, insurance, etc.
                  </td>
                </tr>
                <tr>
                  <td className="border border-sky-200 p-1"><strong>Appendix</strong></td>
                  <td className="border border-sky-200 p-1"><code>A01–A23</code></td>
                  <td className="border border-sky-200 p-1">
                    The summary table of every variable used in the agreement
                    (most rows auto-pull from F/C fields above).
                  </td>
                </tr>
              </tbody>
            </table>
          </div>

          <div>
            <div className="font-semibold text-base">2. Template Versions — how the audit trail works</div>
            <p>
              Each master has a list of <em>versions</em>. Exactly one version per
              type is <strong>active</strong> at any time — that's the version
              every new agreement is built from. Older versions stay queryable
              forever so any agreement created against them can still regenerate
              its PDF exactly as it was first issued.
            </p>
            <p>
              When you click <em>Save As New Version</em>:
            </p>
            <ol className="list-decimal pl-5 space-y-1">
              <li>A new row is inserted with your edits.</li>
              <li>The new version is auto-marked <em>active</em>.</li>
              <li>The previous active version is auto-flipped to <em>archived</em>.</li>
              <li>Future agreements use the new version. Historic agreements are not touched.</li>
            </ol>
            <p>
              Version numbers are free-form (e.g. <code>v1.1</code>, <code>2026-Q3</code>,
              <code>post-legal-review</code>). They show up in the audit log.
            </p>
          </div>

          <div>
            <div className="font-semibold text-base">3. The Field Catalog — fields and input types</div>
            <p>
              Each field has:
            </p>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                <strong>Field ID</strong>: a permanent code, e.g. <code>F02</code>,
                <code> C03</code>, <code>A07</code>. The first letter says which
                template type it belongs to (F/C/A). The number is its
                position in the catalog. Once set, do not change the ID — PDFs
                and historic data look it up by this string.
              </li>
              <li>
                <strong>Label</strong>: what admin sees in the wizard
                (e.g. "Subcontract Price (AED)"). Edit freely — it's display only.
              </li>
              <li>
                <strong>Clause number</strong>: the clause/section in the legal
                text where the value appears (e.g. <code>3.1</code> for
                Subcontract Price). Used by the deviation report and the
                appendix's clause column.
              </li>
              <li>
                <strong>Input type</strong>: drives the wizard widget — one of
                <code> text</code>, <code>textarea</code>, <code>number</code>,
                <code> date</code>, <code>dropdown</code>, <code>multifield</code>.
              </li>
              <li>
                <strong>auto_source_field_id</strong>: optional. If set, this
                field's value is pulled automatically from the named source field.
                Example: <code>A07</code>'s source is <code>F08</code> — the
                appendix's "Subcontract Price" row mirrors whatever was entered
                as F08. Admin can still override per-agreement on Step 4.
              </li>
              <li>
                <strong>show_in_appendix</strong>: whether this field renders as
                a row in the Appendix PDF section. Used for all <code>A##</code>
                fields and a handful of F/C fields the appendix summarises.
              </li>
              <li>
                <strong>is_required</strong>: blocks <em>Submit for Review</em>
                until admin enters a value.
              </li>
              <li>
                <strong>default_value</strong>: optional. Pre-fills the wizard
                input so admin only has to override the unusual cases.
              </li>
            </ul>
          </div>

          <div>
            <div className="font-semibold text-base">
              4. Placeholders — how the value lands in the PDF
            </div>
            <p>
              Inside the template HTML you write <code>{"{{F02}}"}</code>,
              <code> {"{{C03}}"}</code>, <code>{"{{A07}}"}</code>, etc. anywhere
              the rendered PDF should substitute the agreement-specific value.
              On render the engine walks the field catalog and replaces every
              <code> {"{{FIELD_ID}}"}</code> with the entered value, HTML-escaped.
              Numeric fields are formatted with thousands separators automatically
              (e.g. <code>{"{{F08}}"}</code> renders as <code>1,000,000.00</code>).
              Tokens with no matching field stay in the output, so a stray
              <code> {"{{F99}}"}</code> is visible in the PDF — that's deliberate
              so typos surface immediately.
            </p>
          </div>

          <div>
            <div className="font-semibold text-base">
              5. Appendix overrides — auto vs locked rows
            </div>
            <p>
              Most appendix rows are <strong>auto-derived</strong> from their
              source field (e.g. <code>A07</code> from <code>F08</code>). On
              Step 4 of the wizard, admin can click <em>Edit</em> on a row to
              lock a custom value. Once locked, future changes to the source
              field will <strong>not</strong> overwrite the row. Click <em>Reset
              to Auto</em> on a locked row to re-link it to the source and
              re-pull the current value. The Masters section doesn't expose
              per-agreement override state — that lives on each agreement's
              Appendix Builder.
            </p>
          </div>

          <div>
            <div className="font-semibold text-base">6. A simple scenario — adding a new clause</div>
            <p>
              Legal asks you to add a <em>Performance Bond Type</em> dropdown
              with two options ("Bank Guarantee" and "Company Undated Cheque")
              to the Conditions template. Walk:
            </p>
            <ol className="list-decimal pl-5 space-y-1">
              <li>
                Open <em>Masters → Conditions → (current active version)</em>.
              </li>
              <li>
                In the Conditions HTML body, paste the new paragraph where it
                should appear. Use <code>{"{{C14}}"}</code> at the spot where
                the chosen option's text should land.
              </li>
              <li>
                In the Field Catalog, click <em>Add Field</em>. Set Field ID =
                <code> C14</code>, label = "Performance Bond Type", input type =
                <code> dropdown</code>, options = <code>"Bank Guarantee","Company Undated Cheque"</code>.
              </li>
              <li>
                Mark <em>show_in_appendix = true</em> if you want it to also
                appear as an Appendix row.
              </li>
              <li>
                Click <em>Save As New Version</em>. The new Conditions version
                is now active.
              </li>
              <li>
                Create a new test agreement. Step 3 will now show the
                <em> Performance Bond Type</em> dropdown. Whatever admin picks
                lands in the Conditions PDF wherever <code>{"{{C14}}"}</code>
                was placed, and (if you ticked show_in_appendix) on the appendix.
              </li>
              <li>
                Open any agreement created <em>before</em> the change — it still
                shows the previous version's text without <code>{"{{C14}}"}</code>,
                with no broken references.
              </li>
            </ol>
          </div>

          <div>
            <div className="font-semibold text-base">7. Things to be careful about</div>
            <ul className="list-disc pl-5 space-y-1">
              <li>
                Never change an existing field's <strong>Field ID</strong>. If
                you absolutely must, add a new field with a fresh ID and
                deprecate the old one (set <code>is_required=false</code> and
                stop referencing it).
              </li>
              <li>
                Removing a field that historic agreements still reference will
                render those PDFs with an empty value. Prefer deactivation over
                deletion.
              </li>
              <li>
                The first letter of the Field ID matters: <code>F</code>-fields
                appear in the Form template, <code>C</code>-fields in the
                Conditions template, <code>A</code>-fields in the Appendix. Don't
                cross-cut.
              </li>
              <li>
                If you edit the template HTML by mistake and save, click <em>Save
                As New Version</em> with a fresh wording and the previous text
                stays available — there's no destructive overwrite.
              </li>
            </ul>
          </div>

        </div>
      </details>

      <div className="grid grid-cols-12 gap-4">
      <aside className="col-span-3 space-y-4 rounded border p-3">
        <h2 className="text-lg font-semibold">Template Versions</h2>
        {(["form", "conditions", "appendix"] as const).map((type) => (
          <div key={type}>
            <h3 className="mb-2 font-medium capitalize">{type}</h3>
            <div className="space-y-2">
              {(grouped[type] ?? []).map((tpl) => (
                <button
                  key={tpl.id}
                  className={`w-full rounded border p-2 text-left ${selectedTemplate?.id === tpl.id ? "bg-gray-100" : ""}`}
                  onClick={() => setSelectedTemplate(tpl)}
                >
                  {tpl.version_number} - {tpl.version_date} {tpl.is_active ? "(active)" : ""}
                </button>
              ))}
            </div>
          </div>
        ))}
      </aside>

      <main className="col-span-9 space-y-4">
        <div className="space-y-2 rounded border p-3">
          <h2 className="text-lg font-semibold">Template Editor</h2>
          <div className="grid grid-cols-3 gap-2">
            <input className="rounded border p-2" value={versionNumber} onChange={(e) => setVersionNumber(e.target.value)} placeholder="Version number" />
            <input className="rounded border p-2" type="date" value={versionDate} onChange={(e) => setVersionDate(e.target.value)} />
            <input className="rounded border p-2" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Notes" />
          </div>
          <div className="min-h-48 rounded border p-3">
            <EditorContent editor={editor} />
          </div>
          <button className="rounded bg-black px-3 py-2 text-white" onClick={createVersion}>
            Save As New Version
          </button>
        </div>

        {selectedTemplate && (
          <FieldCatalog
            fields={fields}
            templateId={selectedTemplate.id}
            onCreate={createField}
            onUpdate={updateField}
            onDelete={deleteField}
          />
        )}
      </main>
      </div>
    </div>
  );
}
