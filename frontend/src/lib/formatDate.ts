/**
 * Date / datetime display helpers.
 *
 * BGCC mandated long-form dates across the app (Rev 01 item 1): zero-padded
 * day + ordinal suffix + full month name + 4-digit year, e.g. "05th May 2026".
 * Everything that renders an ISO timestamp from the API should go through
 * these helpers so the format stays consistent across pages.
 *
 * Pure display helpers — never mutate persisted values. The DB always stores
 * ISO-8601 UTC; reformat at render time only.
 */

const MONTHS = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
];

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n);
}

function ordinalSuffix(day: number): string {
  // 11/12/13 are "th" regardless of last digit; otherwise st/nd/rd/th by last digit.
  if (day % 100 >= 11 && day % 100 <= 13) return "th";
  switch (day % 10) {
    case 1: return "st";
    case 2: return "nd";
    case 3: return "rd";
    default: return "th";
  }
}

function parse(value: string | Date | null | undefined): Date | null {
  if (value === null || value === undefined || value === "") return null;
  const d = value instanceof Date ? value : new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** Render a date as "05th May 2026". Returns "" for null/empty/unparseable. */
export function formatDate(value: string | Date | null | undefined): string {
  const d = parse(value);
  if (!d) return "";
  const day = d.getDate();
  return `${pad(day)}${ordinalSuffix(day)} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

/** Render a datetime as "05th May 2026 14:30" (24h). Returns "" for null/empty. */
export function formatDateTime(value: string | Date | null | undefined): string {
  const d = parse(value);
  if (!d) return "";
  return `${formatDate(d)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}
