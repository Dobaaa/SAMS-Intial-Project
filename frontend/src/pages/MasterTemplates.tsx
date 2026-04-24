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
    <div className="grid grid-cols-12 gap-4 p-4">
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
  );
}
