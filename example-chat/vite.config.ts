import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  root: "src/client",
  build: {
    outDir: "../../dist/client",
  },
  server: {
    port: 4001,
    proxy: {
      "/api": "http://localhost:4000",
    },
  },
});
