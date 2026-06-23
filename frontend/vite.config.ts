/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The dev server proxies /api -> the backend so the browser talks to one origin
// (no CORS, no backend change). In docker VITE_PROXY_TARGET points at the backend
// service; locally it defaults to localhost:8000.
const proxyTarget = process.env.VITE_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // listen on 0.0.0.0 for docker
    port: 5173,
    proxy: {
      "/api": { target: proxyTarget, changeOrigin: true },
    },
  },
  build: {
    // Recharts is an inherently large dep (~540 kB minified) and pulls in react,
    // so manual chunking can't get any single chunk under the default 500 kB and
    // only introduces circular-chunk churn. Raise the advisory limit instead.
    chunkSizeWarningLimit: 800,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
  },
});
