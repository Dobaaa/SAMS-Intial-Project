import { describe, expect, it } from "vitest";

import { useAuth, isAuthenticated, type AuthUser } from "./auth";

const admin: AuthUser = {
  id: "u1",
  name: "Admin",
  email: "admin@test.local",
  role: "admin",
};

describe("useAuth store", () => {
  it("starts empty", () => {
    expect(useAuth.getState().accessToken).toBeNull();
    expect(useAuth.getState().refreshToken).toBeNull();
    expect(useAuth.getState().user).toBeNull();
    expect(isAuthenticated()).toBe(false);
  });

  it("setSession stores tokens and user", () => {
    useAuth.getState().setSession(
      { accessToken: "aaa", refreshToken: "rrr" },
      admin
    );
    expect(useAuth.getState().accessToken).toBe("aaa");
    expect(useAuth.getState().refreshToken).toBe("rrr");
    expect(useAuth.getState().user).toEqual(admin);
    expect(isAuthenticated()).toBe(true);
  });

  it("setAccessToken replaces only the access token", () => {
    useAuth.getState().setSession({ accessToken: "aaa", refreshToken: "rrr" }, admin);
    useAuth.getState().setAccessToken("bbb");
    expect(useAuth.getState().accessToken).toBe("bbb");
    expect(useAuth.getState().refreshToken).toBe("rrr");
    expect(useAuth.getState().user).toEqual(admin);
  });

  it("clear empties the whole session", () => {
    useAuth.getState().setSession({ accessToken: "a", refreshToken: "r" }, admin);
    useAuth.getState().clear();
    expect(useAuth.getState().accessToken).toBeNull();
    expect(useAuth.getState().refreshToken).toBeNull();
    expect(useAuth.getState().user).toBeNull();
  });

  it("persists to localStorage under the sams.auth key", () => {
    useAuth.getState().setSession({ accessToken: "a", refreshToken: "r" }, admin);
    const persisted = localStorage.getItem("sams.auth");
    expect(persisted).not.toBeNull();
    const parsed = JSON.parse(persisted as string);
    expect(parsed.state.accessToken).toBe("a");
  });
});
