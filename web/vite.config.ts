import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// 本地 dev：/api 与 /health 代理到 compose 中的 api 服务；生产由 nginx 提供静态包。
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
});
