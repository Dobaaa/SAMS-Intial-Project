import { useMemo, useState } from "react";

type Props = {
  title: string;
  data: unknown;
  cached?: boolean;
  onConfirm: (data: unknown) => void;
};

export default function AIReviewPanel({ title, data, cached = false, onConfirm }: Props) {
  const [confirmed, setConfirmed] = useState(false);
  const pretty = useMemo(() => JSON.stringify(data, null, 2), [data]);

  const handleConfirm = () => {
    setConfirmed(true);
    onConfirm(data);
  };

  return (
    <div className="rounded border p-3">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-lg font-semibold">{title}</h3>
        <span className="rounded bg-gray-100 px-2 py-1 text-xs">
          {cached ? "Cached result" : "Fresh result"}
        </span>
      </div>

      <p className="mb-2 text-sm text-amber-700">
        AI outputs are suggestions only. Human confirmation is required before saving any action.
      </p>

      <pre className="max-h-72 overflow-auto rounded bg-gray-50 p-2 text-xs">{pretty}</pre>

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          className="rounded bg-black px-3 py-2 text-white disabled:opacity-50"
          onClick={handleConfirm}
          disabled={confirmed}
        >
          {confirmed ? "Confirmed" : "Confirm AI Suggestion"}
        </button>
        {confirmed && <span className="text-sm text-green-700">Confirmed by reviewer</span>}
      </div>
    </div>
  );
}
