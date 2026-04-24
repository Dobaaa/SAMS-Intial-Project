import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import Login from "./Login";
import { api } from "../lib/api";
import { useAuth } from "../stores/auth";

function renderLogin(initialEntries: string[] = ["/login"]) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/dashboard" element={<div>Dashboard!</div>} />
        <Route path="/archive" element={<div>Archive!</div>} />
      </Routes>
    </MemoryRouter>
  );
}

afterEach(() => {
  delete api.defaults.adapter;
  useAuth.getState().clear();
});

describe("<Login />", () => {
  it("renders email + password + submit", () => {
    renderLogin();
    expect(screen.getByRole("heading", { name: /sams sign in/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeInTheDocument();
  });

  it("logs in and redirects to /dashboard on success", async () => {
    api.defaults.adapter = vi.fn(async (config) => ({
      data: {
        access_token: "at",
        refresh_token: "rt",
        user: {
          id: "u1",
          name: "Admin",
          email: "admin@test.local",
          role: "admin",
        },
      },
      status: 200,
      statusText: "OK",
      headers: {},
      config,
    })) as unknown as typeof api.defaults.adapter;

    renderLogin();
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/email/i), "admin@test.local");
    await user.type(screen.getByLabelText(/password/i), "adminpass1");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText("Dashboard!")).toBeInTheDocument();
    });
    expect(useAuth.getState().accessToken).toBe("at");
    expect(useAuth.getState().user?.role).toBe("admin");
  });

  // TODO: error-message rendering on 401. After the happy-path test's
  // navigate('/dashboard'), the next render doesn't reliably reset to
  // /login under happy-dom + userEvent 14 on Node 20.17 -- the error test's
  // DOM still shows /dashboard. Revisit when we can switch to jsdom 27
  // under Node >= 20.19.
});
