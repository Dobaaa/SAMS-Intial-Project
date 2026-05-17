import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";

import { ToastProvider } from "./components/Toast";
import AgreementCompare from "./pages/AgreementCompare";
import AgreementCreate from "./pages/AgreementCreate";
import AgreementDocument from "./pages/AgreementDocument";
import Archive from "./pages/Archive";
import CommentsResolution from "./pages/CommentsResolution";
import Dashboard from "./pages/Dashboard";
import Login from "./pages/Login";
import MasterTemplates from "./pages/MasterTemplates";
import UserManagement from "./pages/UserManagement";
import WorkflowReview from "./pages/WorkflowReview";
import AppLayout from "./routes/AppLayout";
import RequireAuth from "./routes/RequireAuth";

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
            <Route path="/workflow" element={<WorkflowReview />} />
            <Route path="/resolution" element={<CommentsResolution />} />
            <Route path="/archive" element={<Archive />} />
            <Route index element={<Navigate to="/workflow" replace />} />
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      </ToastProvider>
    </BrowserRouter>
  );
}
