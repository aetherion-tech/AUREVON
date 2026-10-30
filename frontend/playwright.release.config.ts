import { defineConfig } from "@playwright/test";
import base from "./playwright.config";

export default defineConfig({
  ...base,
  webServer: {
    ...base.webServer,
    command: "..\\backend\\.venv\\Scripts\\python.exe tools/test_server.py --built",
    url: "https://127.0.0.1:5174/dashboard/",
    ignoreHTTPSErrors: true,
    reuseExistingServer: false,
    timeout: 180000,
  },
});
