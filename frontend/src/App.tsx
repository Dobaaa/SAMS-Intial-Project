import { Navigate, Route, BrowserRouter, Routes } from "react-router-dom";

import { ToastProvider } from "./components/Toast";
import AgreementCreate from "./pages/AgreementCreate";
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
