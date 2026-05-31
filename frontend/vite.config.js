import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const tunnelMode = process.env.VITE_TUNNEL_MODE === "1";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: true,
    ...(tunnelMode ? { hmr: false } : {}),
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true
      }
    }
  }
});
