type Step = {
  id: string;
  step_name: string;
  step_order: number;
  role_required: string;
  status: string;
  acted_at?: string | null;
};

type Props = {
  steps: Step[];
};

const statusColor: Record<string, string> = {
  approved: "bg-green-100 text-green-700",
  returned: "bg-red-100 text-red-700",
  pending: "bg-amber-100 text-amber-700",
  skipped: "bg-gray-100 text-gray-700",
};

export default function WorkflowTimeline({ steps }: Props) {
  return (
    <div className="rounded border p-3">
      <h3 className="mb-2 text-lg font-semibold">Workflow Timeline</h3>
      <div className="space-y-2">
        {steps
          .sort((a, b) => a.step_order - b.step_order)
          .map((step) => (
            <div key={step.id} className="flex items-center justify-between rounded border p-2">
              <div>
                <div className="font-medium">
                  {step.step_order}. {step.step_name} ({step.role_required})
                </div>
                <div className="text-xs text-gray-500">
                  {step.acted_at ? new Date(step.acted_at).toLocaleString() : "No action yet"}
                </div>
              </div>
              <span className={`rounded px-2 py-1 text-xs ${statusColor[step.status] ?? "bg-gray-100 text-gray-700"}`}>
                {step.status}
              </span>
            </div>
          ))}
      </div>
    </div>
  );
}
