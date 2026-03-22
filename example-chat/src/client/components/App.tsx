import React, { useCallback, useRef, useState } from "react";
import type { ChatMessage, MemoryStatus, ToolActivity } from "../types.js";
import { ChatInput } from "./ChatInput.js";
import { FontSizeSelector, type FontSize, FONT_SCALE } from "./FontSizeSelector.js";
import { MessageBubble } from "./MessageBubble.js";
import { Sidebar } from "./Sidebar.js";

function generateSessionId(): string {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function App() {
  const [sessionId] = useState(() => generateSessionId());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [toolActivity, setToolActivity] = useState<ToolActivity[]>([]);
  const [lastMemoryStatus, setLastMemoryStatus] = useState<MemoryStatus | null>(null);
  const [turnCount, setTurnCount] = useState(0);
  const [fontSize, setFontSize] = useState<FontSize>("medium");
  const bottomRef = useRef<HTMLDivElement>(null);

  const scale = FONT_SCALE[fontSize];

  const scrollToBottom = useCallback(() => {
    setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }, []);

  const sendMessage = useCallback(
    async (text: string) => {
      const userMsg: ChatMessage = { role: "user", content: text };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);
      setToolActivity([]);
      setLastMemoryStatus(null);
      scrollToBottom();

      let assistantText = "";

      try {
        const res = await fetch("/api/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, sessionId }),
        });

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response stream");

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";

          for (const line of lines) {
            if (!line.startsWith("data: ")) continue;
            const data = line.slice(6).trim();
            if (data === "[DONE]") continue;

            try {
              const event = JSON.parse(data);

              if (event.type === "text") {
                assistantText += event.content;
                setMessages((prev) => {
                  const next = [...prev];
                  const last = next[next.length - 1];
                  if (last?.role === "assistant") {
                    return [...next.slice(0, -1), { ...last, content: assistantText }];
                  }
                  return [...next, { role: "assistant", content: assistantText }];
                });
                scrollToBottom();
              }

              if (event.type === "tool_use") {
                setToolActivity((prev) => [
                  ...prev,
                  { tool: event.tool, status: "running", input: event.input },
                ]);
              }

              if (event.type === "tool_result") {
                setToolActivity((prev) =>
                  prev.map((t) =>
                    t.status === "running" ? { ...t, status: "done" } : t,
                  ),
                );
              }

              if (event.type === "memory_status") {
                setLastMemoryStatus({
                  stored_by_claude: event.stored_by_claude,
                  fallback_triggered: event.fallback_triggered,
                });
              }

              if (event.type === "done") {
                if (event.turn) setTurnCount(event.turn);
              }

              if (event.type === "error") {
                setMessages((prev) => [
                  ...prev,
                  { role: "assistant", content: `Error: ${event.error}` },
                ]);
              }
            } catch {
              // Skip malformed JSON
            }
          }
        }
      } catch (err) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: `Connection error: ${err}` },
        ]);
      }

      setIsLoading(false);
    },
    [scrollToBottom, sessionId],
  );

  return (
    <div style={styles.container}>
      <Sidebar
        toolActivity={toolActivity}
        memoryStatus={lastMemoryStatus}
        sessionId={sessionId}
        turnCount={turnCount}
        scale={scale}
      />
      <div style={styles.main}>
        <header style={styles.header}>
          <h1 style={styles.title}>DSE Chat</h1>
          <span style={styles.subtitle}>AI Assistant with Persistent Memory</span>
          <FontSizeSelector value={fontSize} onChange={setFontSize} />
          <span style={styles.sessionBadge}>Session: {sessionId.slice(0, 16)}...</span>
        </header>

        <div style={styles.messages}>
          {messages.length === 0 && (
            <div style={styles.welcome}>
              <h2 style={{ ...styles.welcomeTitle, fontSize: Math.round(24 * scale) }}>Welcome to DSE Chat</h2>
              <p style={{ ...styles.welcomeText, fontSize: Math.round(15 * scale) }}>
                I'm an AI assistant with persistent memory powered by DSE.
                Every conversation is remembered — I store what you tell me,
                what I advise, and the context of our sessions. Try asking me
                something, then come back later and ask "what do you remember?"
              </p>
              <div style={styles.suggestions}>
                {[
                  "Remember that I prefer dark mode and use vim keybindings",
                  "What do you remember about me?",
                  "I'm working on Project Alpha, the deadline is next Friday",
                  "What have we discussed in previous sessions?",
                ].map((s) => (
                  <button
                    key={s}
                    style={{ ...styles.suggestion, fontSize: Math.round(13 * scale) }}
                    onClick={() => sendMessage(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <MessageBubble key={i} message={msg} scale={scale} />
          ))}

          {isLoading && messages[messages.length - 1]?.role !== "assistant" && (
            <div style={{ ...styles.thinking, fontSize: Math.round(14 * scale) }}>
              <span style={styles.dot}>●</span> Thinking & checking memory...
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        <ChatInput onSend={sendMessage} disabled={isLoading} scale={scale} />
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    height: "100vh",
    backgroundColor: "#f9fafb",
  },
  main: {
    flex: 1,
    display: "flex",
    flexDirection: "column",
    minWidth: 0,
  },
  header: {
    padding: "16px 24px",
    borderBottom: "1px solid #e5e7eb",
    backgroundColor: "#fff",
    display: "flex",
    alignItems: "baseline",
    gap: 12,
  },
  title: {
    fontSize: 20,
    fontWeight: 600,
    color: "#111827",
  },
  subtitle: {
    fontSize: 13,
    color: "#6b7280",
  },
  sessionBadge: {
    marginLeft: "auto",
    fontSize: 11,
    color: "#9ca3af",
    fontFamily: "monospace",
    backgroundColor: "#f3f4f6",
    padding: "2px 8px",
    borderRadius: 4,
  },
  messages: {
    flex: 1,
    overflowY: "auto",
    padding: "24px",
  },
  welcome: {
    maxWidth: 600,
    margin: "60px auto",
    textAlign: "center" as const,
  },
  welcomeTitle: {
    fontSize: 24,
    fontWeight: 600,
    color: "#111827",
    marginBottom: 8,
  },
  welcomeText: {
    fontSize: 15,
    color: "#6b7280",
    lineHeight: 1.6,
    marginBottom: 24,
  },
  suggestions: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: 8,
    justifyContent: "center",
  },
  suggestion: {
    padding: "8px 16px",
    borderRadius: 20,
    border: "1px solid #d1d5db",
    backgroundColor: "#fff",
    cursor: "pointer",
    fontSize: 13,
    color: "#374151",
    transition: "all 0.15s",
  },
  thinking: {
    padding: "12px 16px",
    color: "#6b7280",
    fontSize: 14,
  },
  dot: {
    color: "#8b5cf6",
  },
};
