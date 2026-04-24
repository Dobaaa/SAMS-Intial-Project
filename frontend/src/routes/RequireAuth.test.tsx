import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import RequireAuth from "./RequireAuth";
import { api } from "../lib/api";
import { useAuth } from "../stores/auth";

afterEach(() => {
  delete api.defaults.adapter;
  useAuth.getState().clear();
});

function renderWithAuth(initialPath = "/protected") {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route path="/login" element={<div>Login page</div>} />
        <Route element={<RequireAuth />}>
          <Route path="/protected" element={<div>Secret content</div>} />
        </Route>
        <Route element={<RequireAuth roles={["admin"]} />}>
          <Route path="/admin-only" element={<div>Admin page</div>} />
        </Route>
      </Routes>
    </MemoryRouter>
  );
}

describe("<RequireAuth />", () => {
  it("redirects to /login when there is no token", () => {
    renderWithAuth("/protected");
    expect(screen.getByText("Login page")).toBeInTheDocument();
  });

  it("renders the child route when a token is present and user is loaded", () => {
    useAuth.getState().setSession(
      { accessToken: "at", refreshToken: "rt" },
      { id: "u1", name: "Admin", email: "a@b", role: "admin" }
    );
    renderWithAuth("/protected");
    expect(screen.getByText("Secret content")).toBeInTheDocument();
  });

  it("hydrates user from /auth/me when token is present but user is missing", async () => {
    useAuth.getState().setSession(
      { accessToken: "at", refreshToken: "rt" },
      { id: "tmp", name: "tmp", email: "tmp@x", role: "admin" }
    );
    useAuth.setState({ user: null });

    api.defaults.adapter = vi.fn(async (config) => ({
      data: { id: "u1", name: "Hydrated", email: "hydrated@test.local", role: "admin" },
      status: 200,
      statusText: "OK",
      headers: {},
      config,
    })) as unknown as typeof api.defaults.adapter;

    renderWithAuth("/protected");
    // Component renders immediately with Outlet; /auth/me runs and hydrates the store.
    await waitFor(() => {
      expect(useAuth.getState().user?.email).toBe("hydrated@test.local");
    });
  });

  it("blocks with 'no permission' message when role does not match", () => {
    useAuth.getState().setSession(
      { accessToken: "at", refreshToken: "rt" },
      { id: "u1", name: "OM", email: "om@x", role: "operation_manager" }
    );
    renderWithAuth("/admin-only");
    expect(screen.getByText(/do not have permission/i)).toBeInTheDocument();
  });
});
