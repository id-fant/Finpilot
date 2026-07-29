import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiPort = process.env.FINPILOT_DEV_API_PORT || "8000";
const apiTarget = `http://127.0.0.1:${apiPort}`;

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5500,
    strictPort: true,
    proxy: {
      "/api": apiTarget,
      "/ws": {
        target: apiTarget.replace("http:", "ws:"),
        ws: true
      }
    }
  },
  build: {
    outDir: "dist",
    sourcemap: true,
    target: "es2022"
  }
});
