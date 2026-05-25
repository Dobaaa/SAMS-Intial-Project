/**
 * Role helpers shared across reviewer-facing surfaces (Workflow Review
 * rail, Comments & Resolution internal-comment list, etc.).
 *
 * The backend stores roles as lowercase RoleEnum values
 * (``project_director``, ``operation_manager``…). The UI almost always
 * wants the human-readable label.
 */

const ROLE_LABELS: Record<string, string> = {
  admin: "Admin",
  project_director: "Project Director",
  accounts: "Accounts",
  operation_manager: "Operation Manager",
  gm: "General Manager",
  quality_surveyor: "Quantity Surveyor",
  estimator: "Sr. Estimator",
  project_manager: "Project Manager",
};

export function humanRole(value: string | null | undefined): string {
  if (!value) return "";
  return (
    ROLE_LABELS[value] ??
    value
      .split("_")
      .map((w) => (w ? w.charAt(0).toUpperCase() + w.slice(1) : w))
      .join(" ")
  );
}
