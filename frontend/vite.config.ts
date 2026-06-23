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
});
