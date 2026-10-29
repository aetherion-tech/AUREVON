import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  use: { baseURL: "https://127.0.0.1:5174", ignoreHTTPSErrors: true },
  webServer: {
    command: "..\\backend\\.venv\\Scripts\\python.exe tools/test_server.py",
    url: "https://127.0.0.1:5174/dashboard/",
    ignoreHTTPSErrors: true,
    reuseExistingServer: false,
    timeout: 60000,
  },
});
