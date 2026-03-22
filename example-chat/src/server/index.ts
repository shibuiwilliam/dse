/**
 * DSE Example Chat Server
 *
 * Express server that wraps the Claude Agent SDK with DSE MCP server integration.
 * Provides a streaming chat API for the React frontend.
 */
import cors from "cors";
import "dotenv/config";
import express from "express";
import { randomUUID } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chatHandler } from "./routes/chat.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = parseInt(process.env.PORT ?? "4000", 10);

const app = express();
app.use(cors());
app.use(express.json());

// Serve built frontend in production
app.use(express.static(path.join(__dirname, "../../dist/client")));

// API routes
app.post("/api/chat", chatHandler);

// Health check
app.get("/api/health", (_req, res) => {
  res.json({ status: "ok", dse_mcp: "configured" });
});

// SPA fallback
app.get("/{*path}", (_req, res) => {
  res.sendFile(path.join(__dirname, "../../dist/client/index.html"));
});

app.listen(PORT, () => {
  console.log(`DSE Example Chat running on http://localhost:${PORT}`);
  console.log(`DSE MCP: ${process.env.DSE_MCP_URL ?? "stdio → " + (process.env.DSE_BACKEND_DIR ?? "../backend")}`);
});
