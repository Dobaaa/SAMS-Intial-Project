import { useMemo, useState } from "react";

type Kind = "comparison" | "risks" | "summary" | "suggestions" | "validation" | "grammar";

type Props = {
  title: string;
  data: unknown;
  kind?: Kind;
  cached?: boolean;
  onConfirm: (data: unknown) => void;
};

export default function AIReviewPanel({ title, data, kind, cached = false, onConfirm }: Props) {
  const [confirmed, setConfirmed] = useState(false);
  const [showRaw, setShowRaw] = useState(false);
  const pretty = useMemo(() => JSON.stringify(data, null, 2), [data]);

  const handleConfirm = () => {
    setConfirmed(true);
    onConfirm(data);
  };

  return (
    <div className="rounded border bg-white p-3 shadow-sm">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-lg font-semibold">{title}</h3>
        <span
          className={`rounded px-2 py-1 text-xs ${
            cached ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"
          }`}
        >
          {cached ? "Cached" : "Fresh"}
        </span>
      </div>

      <p className="mb-3 text-xs text-amber-700">
        AI suggestion only. A human reviewer must confirm before any action.
      </p>

      <div className="mb-3">{renderBody(data, kind)}</div>

      <div className="flex items-center gap-3 text-xs">
        <button
          type="button"
          className="rounded bg-black px-3 py-1.5 text-white disabled:opacity-50"
          onClick={handleConfirm}
          disabled={confirmed}
        >
          {confirmed ? "Confirmed" : "Confirm"}
        </button>
        {confirmed && <span className="text-green-700">Confirmed by reviewer</span>}
        <button
          type="button"
          className="ml-auto text-gray-500 underline hover:text-gray-700"
          onClick={() => setShowRaw((v) => !v)}
        >
          {showRaw ? "Hide raw JSON" : "Show raw JSON"}
        </button>
      </div>

      {showRaw && <pre className="mt-2 max-h-72 overflow-auto rounded bg-gray-50 p-2 text-xs">{pretty}</pre>}
    </div>
  );
}

function renderBody(data: unknown, kind?: Kind) {
  if (data == null) {
    return <p className="text-sm text-gray-500">No data returned.</p>;
  }

  if (kind === "comparison" && Array.isArray(data)) {
    return <ComparisonList rows={data as ComparisonRow[]} />;
  }
  if (kind === "risks" && Array.isArray(data)) {
    return <RiskList rows={data as RiskRow[]} />;
  }
  if (kind === "suggestions" && Array.isArray(data)) {
    return <SuggestionList rows={data as SuggestionRow[]} />;
  }
  if (kind === "validation" && Array.isArray(data)) {
    return <ValidationList rows={data as ValidationRow[]} />;
  }
  if (kind === "grammar" && Array.isArray(data)) {
    return <GrammarList rows={data as GrammarRow[]} />;
  }
  if (kind === "summary") {
    return <SummaryView value={data} />;
  }
  return <SummaryView value={data} />;
}

// ----- Comparison -----

type ComparisonRow = {
  clause_number?: string;
  clause_title?: string;
  change_summary?: string;
  implication?: string;
};

function ComparisonList({ rows }: { rows: ComparisonRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-gray-500">No clause modifications detected.</p>;
  }
  return (
    <ul className="space-y-2">
      {rows.map((row, i) => (
        <li key={i} className="rounded border border-gray-200 bg-gray-50 p-2">
          <div className="mb-1 flex items-baseline gap-2">
            <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-mono text-indigo-800">
              {row.clause_number || "—"}
            </span>
            <span className="text-sm font-medium">{row.clause_title || "Untitled clause"}</span>
          </div>
          {row.change_summary && (
            <p className="text-sm">
              <span className="font-semibold text-gray-700">What changed: </span>
              <span className="text-gray-800">{row.change_summary}</span>
            </p>
          )}
          {row.implication && (
            <p className="mt-1 text-sm">
              <span className="font-semibold text-gray-700">Implication: </span>
              <span className="text-gray-800">{row.implication}</span>
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

// ----- Risks -----

type RiskRow = {
  clause_number?: string;
  risk_score?: number;
  risk_explanation?: string;
};

function RiskList({ rows }: { rows: RiskRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-gray-500">No risks identified.</p>;
  }
  return (
    <ul className="space-y-2">
      {rows.map((row, i) => (
        <li key={i} className="rounded border border-gray-200 bg-gray-50 p-2">
          <div className="mb-1 flex items-center gap-2">
            <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-mono text-indigo-800">
              {row.clause_number || "—"}
            </span>
            <RiskBadge score={row.risk_score} />
          </div>
          {row.risk_explanation && <p className="text-sm text-gray-800">{row.risk_explanation}</p>}
        </li>
      ))}
    </ul>
  );
}

function RiskBadge({ score }: { score?: number }) {
  const s = typeof score === "number" ? score : 0;
  const labels = ["Unknown", "None", "Low", "Medium", "High", "Critical"];
  const styles = [
    "bg-gray-100 text-gray-700",
    "bg-emerald-100 text-emerald-800",
    "bg-emerald-100 text-emerald-800",
    "bg-amber-100 text-amber-800",
    "bg-orange-100 text-orange-800",
    "bg-red-100 text-red-800",
  ];
  const idx = s >= 1 && s <= 5 ? s : 0;
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${styles[idx]}`}>
      Risk: {labels[idx]} {idx > 0 ? `(${s}/5)` : ""}
    </span>
  );
}

// ----- Suggestions -----

type SuggestionRow = {
  comment_id?: string;
  suggested_response?: string;
};

function SuggestionList({ rows }: { rows: SuggestionRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-gray-500">No suggestions generated.</p>;
  }
  return (
    <ul className="space-y-2">
      {rows.map((row, i) => (
        <li key={row.comment_id || i} className="rounded border border-gray-200 bg-gray-50 p-2">
          {row.comment_id && (
            <div className="mb-1 text-[10px] font-mono text-gray-500">#{row.comment_id.slice(0, 8)}</div>
          )}
          <p className="whitespace-pre-wrap text-sm text-gray-800">
            {row.suggested_response || "—"}
          </p>
        </li>
      ))}
    </ul>
  );
}

// ----- Validation -----

type ValidationRow = {
  comment_id?: string;
  is_addressed?: boolean;
  explanation?: string;
};

function ValidationList({ rows }: { rows: ValidationRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-gray-500">No comments to validate.</p>;
  }
  return (
    <ul className="space-y-2">
      {rows.map((row, i) => (
        <li key={row.comment_id || i} className="rounded border border-gray-200 bg-gray-50 p-2">
          <div className="mb-1 flex items-center gap-2">
            {row.comment_id && (
              <span className="text-[10px] font-mono text-gray-500">#{row.comment_id.slice(0, 8)}</span>
            )}
            <span
              className={`rounded px-2 py-0.5 text-xs font-medium ${
                row.is_addressed
                  ? "bg-emerald-100 text-emerald-800"
                  : "bg-red-100 text-red-800"
              }`}
            >
              {row.is_addressed ? "Addressed" : "Not addressed"}
            </span>
          </div>
          {row.explanation && <p className="text-sm text-gray-800">{row.explanation}</p>}
        </li>
      ))}
    </ul>
  );
}

// ----- Grammar -----

type GrammarRow = {
  field_id?: string;
  field_label?: string;
  original_text?: string;
  suggested_text?: string;
  issue_type?: string;
  explanation?: string;
};

const ISSUE_STYLES: Record<string, string> = {
  grammar: "bg-amber-100 text-amber-800",
  spelling: "bg-red-100 text-red-800",
  punctuation: "bg-orange-100 text-orange-800",
  clarity: "bg-sky-100 text-sky-800",
  legal_wording: "bg-purple-100 text-purple-800",
};

function GrammarList({ rows }: { rows: GrammarRow[] }) {
  if (rows.length === 0) {
    return <p className="text-sm text-emerald-700">No grammar or wording issues detected.</p>;
  }
  return (
    <ul className="space-y-3">
      {rows.map((row, i) => {
        const style = ISSUE_STYLES[row.issue_type ?? ""] ?? "bg-gray-100 text-gray-700";
        return (
          <li key={i} className="rounded border border-gray-200 bg-gray-50 p-2">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span className="rounded bg-indigo-100 px-2 py-0.5 text-xs font-mono text-indigo-800">
                {row.field_id || "—"}
              </span>
              <span className="text-sm font-medium">{row.field_label || ""}</span>
              {row.issue_type && (
                <span className={`rounded px-2 py-0.5 text-xs font-medium capitalize ${style}`}>
                  {row.issue_type.replace(/_/g, " ")}
                </span>
              )}
            </div>
            {row.original_text && (
              <p className="text-sm">
                <span className="font-semibold text-gray-700">Original: </span>
                <span className="text-red-700 line-through">{row.original_text}</span>
              </p>
            )}
            {row.suggested_text && (
              <p className="mt-0.5 text-sm">
                <span className="font-semibold text-gray-700">Suggested: </span>
                <span className="text-emerald-700">{row.suggested_text}</span>
              </p>
            )}
            {row.explanation && (
              <p className="mt-1 text-xs text-gray-600">{row.explanation}</p>
            )}
          </li>
        );
      })}
    </ul>
  );
}

// ----- Summary / generic object -----

function SummaryView({ value }: { value: unknown }) {
  if (typeof value === "string") {
    return <p className="whitespace-pre-wrap text-sm text-gray-800">{value}</p>;
  }
  if (Array.isArray(value)) {
    if (value.length === 0) return <p className="text-sm text-gray-500">No items.</p>;
    return (
      <ul className="list-disc space-y-1 pl-5 text-sm text-gray-800">
        {value.map((item, i) => (
          <li key={i}>{renderInline(item)}</li>
        ))}
      </ul>
    );
  }
  if (value && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>);
    if (entries.length === 0) return <p className="text-sm text-gray-500">No items.</p>;
    return (
      <dl className="space-y-2 text-sm">
        {entries.map(([key, val]) => (
          <div key={key} className="rounded border border-gray-200 bg-gray-50 p-2">
            <dt className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-600">
              {humanize(key)}
            </dt>
            <dd className="text-gray-800">
              {typeof val === "string" || typeof val === "number" || typeof val === "boolean" ? (
                <span className="whitespace-pre-wrap">{String(val)}</span>
              ) : (
                <SummaryView value={val} />
              )}
            </dd>
          </div>
        ))}
      </dl>
    );
  }
  return <p className="text-sm text-gray-500">{String(value)}</p>;
}

function renderInline(value: unknown): React.ReactNode {
  if (value == null) return "—";
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((v) => renderInline(v)).join(", ");
  }
  // For nested objects in a list item, render compactly: key: value, key: value
  return Object.entries(value as Record<string, unknown>)
    .map(([k, v]) => `${humanize(k)}: ${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join(" · ");
}

function humanize(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
