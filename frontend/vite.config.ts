import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
export default defineConfig(({ command }) => {
  const localKey = fileURLToPath(
    new URL("./.local-tls/localhost-key.pem", import.meta.url),
  );
  const localCert = fileURLToPath(
    new URL("./.local-tls/localhost-cert.pem", import.meta.url),
  );
  const custom = process.env.LOCAL_TLS_KEY || process.env.LOCAL_TLS_CERT;
  const key = custom
      ? process.env.LOCAL_TLS_KEY
      : existsSync(localKey)
        ? localKey
        : undefined,
    cert = custom
      ? process.env.LOCAL_TLS_CERT
      : existsSync(localCert)
        ? localCert
        : undefined;
  if (command === "serve" && !process.env.VITEST && (!key || !cert))
    throw new Error(
      "Run npm.cmd run setup:https, or set LOCAL_TLS_KEY and LOCAL_TLS_CERT. HTTPS is required.",
    );
  return {
    plugins: [react()],
    base: "/dashboard/",
    server: {
      host: "127.0.0.1",
      port: Number(process.env.LOCAL_UI_PORT || 5173),
      strictPort: true,
      https:
        key && cert
          ? { key: readFileSync(key), cert: readFileSync(cert) }
          : undefined,
      proxy: {
        "/api": {
          target: process.env.LOCAL_API_TARGET || "http://127.0.0.1:8000",
          changeOrigin: false,
        },
        "/ws": {
          target: process.env.LOCAL_API_TARGET || "ws://127.0.0.1:8000",
          ws: true,
          changeOrigin: false,
        },
      },
    },
    test: {
      environment: "jsdom",
      include: ["src/**/*.test.{ts,tsx}"],
      restoreMocks: true,
    },
  };
});
