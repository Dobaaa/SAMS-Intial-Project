import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";

import { ToastProvider } from "./components/Toast";
import AgreementCompare from "./pages/AgreementCompare";
import AgreementCompareTable from "./pages/AgreementCompareTable";
import AgreementCreate from "./pages/AgreementCreate";
import AgreementDocument from "./pages/AgreementDocument";
import Archive from "./pages/Archive";
import CommentsResolution from "./pages/CommentsResolution";
import Dashboard from "./pages/Dashboard";
import GMDashboard from "./pages/GMDashboard";
import ReviewerDashboard from "./pages/ReviewerDashboard";
import Login from "./pages/Login";
import MasterTemplates from "./pages/MasterTemplates";
import UserManagement from "./pages/UserManagement";
import WorkflowReview from "./pages/WorkflowReview";
import AppLayout from "./routes/AppLayout";
import RequireAuth from "./routes/RequireAuth";
import { useAuth } from "./stores/auth";

const OBSERVER_ROLES = new Set(["admin", "quality_surveyor", "estimator", "project_manager"]);

function DefaultRedirect() {
  const role = useAuth((s) => s.user?.role);
  if (role === "admin") return <Navigate to="/dashboard" replace />;
  if (role === "gm") return <Navigate to="/gm-dashboard" replace />;
  if (role && OBSERVER_ROLES.has(role)) return <Navigate to="/workflow" replace />;
  return <Navigate to="/reviewer-dashboard" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
      <Routes>
        <Route path="/login" element={<Login />} />

        <Route element={<RequireAuth />}>
          <Route element={<AppLayout />}>
            <Route element={<RequireAuth roles={["admin"]} />}>
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/users" element={<UserManagement />} />
              <Route path="/masters" element={<MasterTemplates />} />
              <Route path="/agreements/new" element={<AgreementCreate />} />
              <Route path="/agreements/:id/edit" element={<AgreementCreate />} />
            </Route>
            {/* Rev 01 item 17-extension: side-by-side comparison + change
                tracking is available to ALL reviewer roles (GM, PD, OM,
                Accounts, Admin), not just admin. The Document view is
                also open to all five; non-admin sees it read-only — the
                field editor and Save/Regenerate buttons are hidden, and
                the clause-revisions panel switches to review mode. */}
            <Route path="/agreements/:id/document" element={<AgreementDocument />} />
            <Route path="/agreements/:id/compare" element={<AgreementCompare />} />
            <Route path="/agreements/:id/compare-table" element={<AgreementCompareTable />} />
            <Route path="/reviewer-dashboard" element={<ReviewerDashboard />} />
            <Route path="/gm-dashboard" element={<GMDashboard />} />
            <Route path="/workflow" element={<WorkflowReview />} />
            <Route path="/resolution" element={<CommentsResolution />} />
            <Route path="/archive" element={<Archive />} />
            <Route index element={<DefaultRedirect />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </ToastProvider>
    </BrowserRouter>
  );
}
