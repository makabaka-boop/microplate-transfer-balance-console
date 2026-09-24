import { defineConfig, devices } from "@playwright/test";

/**
 * 浏览器测试刻意保持极小：仅覆盖一次真实提交与结果展示。
 * 计算正确性、409/422、守恒性质全部由后端 pytest 负责。
 */
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:5173",
    trace: "off",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
});
