import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach } from "vitest";
import { cleanup } from "@testing-library/react";

import { api } from "./lib/api";
import { useAuth } from "./stores/auth";

// Reset DOM + in-memory store + persisted state + any mock axios adapter
// between every test so suites can't leak into each other.
afterEach(() => {
  cleanup();
  useAuth.getState().clear();
  localStorage.clear();
  sessionStorage.clear();
  delete api.defaults.adapter;
});

beforeEach(() => {
  useAuth.getState().clear();
  localStorage.clear();
});
