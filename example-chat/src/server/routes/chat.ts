/**
 * Chat route handler — streams Claude Agent SDK responses as SSE.
 *
 * Connects to DSE via MCP (HTTP or stdio) to give Claude persistent memory.
 * Every request-response pair is stored in DSE as episodic memory.
 */
import { query } from "@anthropic-ai/claude-agent-sdk";
import type { Request, Response } from "express";
import path from "node:path";

// ── DSE connection config ───────────────────────────────────────────

const DSE_MCP_URL = process.env.DSE_MCP_URL ?? "";
const DSE_BACKEND_DIR = path.resolve(
  process.env.DSE_BACKEND_DIR ?? path.join(process.cwd(), "..", "backend"),
);
const NAMESPACE = process.env.DSE_NAMESPACE ?? "user:engineer-dev";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function buildMcpServerConfig(): any {
  if (DSE_MCP_URL) {
    // HTTP transport — connect to a running DSE MCP server (make run-all)
    return {
      type: "http",
      url: DSE_MCP_URL,
    };
  }
  // stdio transport — spawn DSE MCP as a subprocess
  return {
    command: "uv",
    args: ["run", "--directory", DSE_BACKEND_DIR, "python", "-m", "dse.mcp"],
    env: {
      USE_MOCK_LLM: process.env.USE_MOCK_LLM ?? "false",
      USE_MOCK_SEARCH: process.env.USE_MOCK_SEARCH ?? "false",
      APP_ENV: "local",
    },
  };
}

// ── System prompt ───────────────────────────────────────────────────

const SYSTEM_PROMPT = `You are a helpful AI assistant with access to a persistent memory system called DSE (Dynamic Search Engine for Agentic Memory).

You have MCP tools connected to DSE. The current namespace is "${NAMESPACE}".

## Available tools:

### Memory retrieval
- **retrieve_memories** — Semantic search using the cascade retrieval pipeline (BM25 + kNN + graph expansion). ALWAYS call this first.
- **search_memories** — Direct text search on the Elasticsearch index.
- **get_memory** — Fetch a single memory by UUID.
- **get_related_memories** — Follow Neo4j graph edges to find related memories (COMPLEMENTS, DERIVES, CAUSES, etc.).

### Memory storage
- **store_memory** — Create a new memory with auto-generated embedding, summary, and graph node.
- **update_memory** — Partially update an existing memory's fields.
- **delete_memory** — Permanently remove a memory from all stores.

### Graph relations
- **create_memory_relation** — Create a typed edge between two memories (SUPERSEDED_BY, COMPLEMENTS, CONTRADICTS, DERIVES, CAUSES, REFERENCES, HAS_CHILD, TEMPORALLY_PRECEDES).

### Namespaces
- **list_namespaces** — Show all available namespaces in DSE.
- **get_namespace** — Get stats for a specific namespace.

### Session context
- **working_memory_add** — Append a conversation turn to the Redis Stream session buffer.
- **working_memory_get** — Read recent turns from the session buffer.

## MANDATORY behavior:

1. **Every turn**: Call retrieve_memories BEFORE answering, using namespace "${NAMESPACE}".
2. **When user shares info**: Call store_memory (semantic for facts/prefs, episodic for events, procedural for rules, prospective for reminders). Always set namespace="${NAMESPACE}".
3. **When asked "what do you remember"**: Call search_memories with broad terms. Be honest.
4. **When you give advice**: Store it as episodic memory for future reference.
5. **Transparency**: Say "I found in my memory..." or "I'm saving this for later..." to be clear.

## Memory types:
- **episodic** — events, conversations, decisions
- **semantic** — lasting facts, preferences, knowledge
- **procedural** — rules, checklists, how-tos
- **prospective** — reminders, deadlines, future tasks`;

// ── Session tracking ────────────────────────────────────────────────

const sessions = new Map<string, string>();
const turnCounters = new Map<string, number>();

function buildPrompt(userMessage: string, sessionId: string, turnNumber: number): string {
  return `[Session: ${sessionId}, Turn: ${turnNumber}]

User message: ${userMessage}

Steps:
1. Call retrieve_memories with namespace="${NAMESPACE}" and a query based on the user's message.
2. Answer the user using retrieved context.
3. If the user shared any fact, preference, or instruction, call store_memory to save it (namespace="${NAMESPACE}").
4. Call working_memory_add to log this turn (session_id="${sessionId}").`;
}

// ── Handler ─────────────────────────────────────────────────────────

export async function chatHandler(req: Request, res: Response): Promise<void> {
  const { message, sessionId = "default" } = req.body as {
    message: string;
    sessionId?: string;
  };

  if (!message) {
    res.status(400).json({ error: "message is required" });
    return;
  }

  const turn = (turnCounters.get(sessionId) ?? 0) + 1;
  turnCounters.set(sessionId, turn);

  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");

  const existingSession = sessions.get(sessionId);
  const prompt = buildPrompt(message, sessionId, turn);

  try {
    const options: Record<string, unknown> = {
      systemPrompt: SYSTEM_PROMPT,
      mcpServers: { dse: buildMcpServerConfig() },
      allowedTools: ["mcp__dse__*"],
      permissionMode: "bypassPermissions",
      ...(existingSession ? { resume: existingSession } : {}),
    };

    let capturedSessionId: string | undefined;
    let assistantText = "";
    const toolsCalled: string[] = [];

    for await (const msg of query({ prompt, options })) {
      const m = msg as Record<string, unknown>;

      if (m.type === "system" && m.subtype === "init") {
        capturedSessionId = m.session_id as string;
        sessions.set(sessionId, capturedSessionId);
      }

      if (m.type === "assistant" && m.message) {
        const content = (m.message as Record<string, unknown>)
          .content as Array<Record<string, unknown>>;
        for (const block of content) {
          if (block.type === "text" && typeof block.text === "string") {
            assistantText += block.text;
            res.write(`data: ${JSON.stringify({ type: "text", content: block.text })}\n\n`);
          }
          if (block.type === "tool_use") {
            const toolName = block.name as string;
            toolsCalled.push(toolName);
            res.write(
              `data: ${JSON.stringify({ type: "tool_use", tool: toolName, input: block.input })}\n\n`,
            );
          }
        }
      }

      if (m.type === "tool_result") {
        res.write(
          `data: ${JSON.stringify({ type: "tool_result", tool: (m as Record<string, unknown>).tool_use_id })}\n\n`,
        );
      }

      if (m.type === "result") {
        res.write(
          `data: ${JSON.stringify({
            type: "done",
            result: (m as Record<string, unknown>).result,
            subtype: (m as Record<string, unknown>).subtype,
            tools_used: toolsCalled,
            turn,
          })}\n\n`,
        );
      }
    }

    // Guaranteed memory fallback
    const storeUsed = toolsCalled.some((t) => t.includes("store_memory"));
    const wmUsed = toolsCalled.some((t) => t.includes("working_memory_add"));

    if (!storeUsed || !wmUsed) {
      storeFallback(message, assistantText, sessionId, turn, storeUsed, wmUsed).catch((err) => {
        console.error("Fallback memory store failed:", err);
      });
    }

    res.write(
      `data: ${JSON.stringify({
        type: "memory_status",
        stored_by_claude: storeUsed,
        fallback_triggered: !storeUsed || !wmUsed,
      })}\n\n`,
    );
  } catch (err) {
    const errorMsg = err instanceof Error ? err.message : "Unknown error";
    res.write(`data: ${JSON.stringify({ type: "error", error: errorMsg })}\n\n`);
  }

  res.write("data: [DONE]\n\n");
  res.end();
}

// ── Fallback memory store ───────────────────────────────────────────

async function storeFallback(
  userMsg: string,
  assistantMsg: string,
  sessionId: string,
  turn: number,
  alreadyStored: boolean,
  alreadyWM: boolean,
): Promise<void> {
  const tasks: string[] = [];

  if (!alreadyStored) {
    tasks.push(
      `Call store_memory: namespace="${NAMESPACE}", content_text="Turn ${turn} — User: ${userMsg.slice(0, 200)} | Assistant: ${assistantMsg.slice(0, 300)}", memory_type="episodic", source_type="observation", tags=["conversation","session:${sessionId}","turn:${turn}"]`,
    );
  }
  if (!alreadyWM) {
    tasks.push(
      `Call working_memory_add: session_id="${sessionId}", content="Turn ${turn}: ${userMsg.slice(0, 100)}", role="system"`,
    );
  }

  const fallbackPrompt = `Execute these memory operations:\n${tasks.join("\n")}`;

  for await (const _ of query({
    prompt: fallbackPrompt,
    options: {
      mcpServers: { dse: buildMcpServerConfig() },
      allowedTools: ["mcp__dse__store_memory", "mcp__dse__working_memory_add"],
      permissionMode: "bypassPermissions",
    },
  })) {
    // Consume silently
  }
}
