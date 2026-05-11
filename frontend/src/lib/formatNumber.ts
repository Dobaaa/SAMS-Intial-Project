/**
 * Format a value for display.
 *
 * Returns the value with thousands separators (comma) and dot decimal when
 * it's parseable as a number. Free-form text ("60 days PDC", an empty
 * string, an arbitrary clause body) is returned verbatim so the function
 * is safe to call from anywhere on the form / review screens.
 *
 * Pure display helper — never mutate persisted values. The DB always stores
 * raw input. Reformat at render time only.
 */
export function formatNumber(raw: string | number | null | undefined): string {
  if (raw === null || raw === undefined) return "";
  const text = String(raw).trim();
  if (!text) return "";

  // Strip user-typed thousand separators so the parse always works on
  // "1,000,000" or "1 000 000.50". Don't be clever with locales — BGCC's
  // agreements are denominated in AED and authored in en-UAE-ish.
  const cleaned = text.replace(/,/g, "").replace(/\s+/g, "");
  if (!/^-?\d+(\.\d+)?$/.test(cleaned)) {
    return text;
  }

  const n = Number(cleaned);
  if (!Number.isFinite(n)) return text;

  // Whole numbers render without a trailing .00. Decimals show 2 dp.
  if (Number.isInteger(n)) {
    return n.toLocaleString("en-US");
  }
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
