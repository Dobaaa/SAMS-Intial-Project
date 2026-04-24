import { afterEach, describe, expect, it, vi } from "vitest";
import type { AxiosRequestConfig } from "axios";

import { api } from "./api";
import { useAuth, type AuthUser } from "../stores/auth";

const admin: AuthUser = {
  id: "u1",
  name: "Admin",
  email: "admin@test.local",
  role: "admin",
};

type CapturedConfig = AxiosRequestConfig & { headers?: Record<string, string> };

function installAdapter(responder: (config: CapturedConfig) => Promise<unknown>) {
  const captured: CapturedConfig[] = [];
  const adapter = vi.fn(async (config: CapturedConfig) => {
    captured.push(config);
    return responder(config);
  });
  api.defaults.adapter = adapter as unknown as typeof api.defaults.adapter;
  return { captured, adapter };
}

afterEach(() => {
  delete api.defaults.adapter;
});

describe("api client — request interceptor", () => {
  it("injects Bearer token when auth store has an access token", async () => {
    useAuth.getState().setSession(
      { accessToken: "mytoken", refreshToken: "r" },
      admin
    );
    const { captured } = installAdapter(async (config) => ({
      data: { ok: true },
      status: 200,
      statusText: "OK",
      headers: {},
      config,
    }));

    await api.get("/ping");
    expect(captured[0].headers?.Authorization).toBe("Bearer mytoken");
  });

  it("sends no Authorization header when store is empty", async () => {
    const { captured } = installAdapter(async (config) => ({
      data: { ok: true },
      status: 200,
      statusText: "OK",
      headers: {},
      config,
    }));

    await api.get("/ping");
    expect(captured[0].headers?.Authorization).toBeUndefined();
  });

  // TODO: cover the 401 -> refresh -> retry -> clear-session path. The
  // current happy-dom + axios adapter-mocking setup double-counts calls
  // when mixed with the response interceptor, which makes the test flaky
  // in ways that don't reflect real behavior. Revisit with msw or
  // axios-mock-adapter once Node >= 20.19 is available (unblocks
  // vitest 4 + jsdom 27 with real XHR).
});
