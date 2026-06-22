import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // listen on 0.0.0.0 for docker
    port: 5173,
  },
});
