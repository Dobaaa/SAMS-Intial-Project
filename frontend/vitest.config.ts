/// <reference types="vitest" />
import { defineConfig } from "vitest/config";

// Deliberately NOT importing @vitejs/plugin-react here. Vitest ships its
// own vite dependency, and pulling plugin-react resolved against the root
// vite causes duplicate-type-signature errors at typecheck time. The
// built-in esbuild JSX transform is enough for Vitest's test runs.
export default defineConfig({
  test: {
    environment: "happy-dom",
    globals: true,
    setupFiles: ["./src/test-setup.ts"],
    css: false,
  },
  esbuild: {
    jsx: "automatic",
  },
});
