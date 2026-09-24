import { defineConfig } from '@playwright/test'

// 本机无 root 安装系统库时，从 apt 解包到 /tmp/chromelibs 的库通过
// LD_LIBRARY_PATH 提供；容器/CI 中该目录不存在时保持原样，无副作用。
const LOCAL_LIB = '/tmp/chromelibs/usr/lib/aarch64-linux-gnu:' +
  '/tmp/chromelibs/lib/aarch64-linux-gnu'

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'retain-on-failure',
    launchOptions: {
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
      env: { ...process.env, LD_LIBRARY_PATH: `${process.env.LD_LIBRARY_PATH ?? ''}:${LOCAL_LIB}` },
    },
  },
  webServer: [
    {
      command: 'python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: true,
      timeout: 30_000,
    },
    {
      command: 'npm run dev -- --port 5173',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
})
