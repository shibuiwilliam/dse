import React from "react";
import type { ChatMessage } from "../types.js";

interface Props {
  message: ChatMessage;
  scale?: number;
}

export function MessageBubble({ message, scale = 1 }: Props) {
  const isUser = message.role === "user";

  return (
    <div style={{ ...styles.row, justifyContent: isUser ? "flex-end" : "flex-start" }}>
      <div
        style={{
          ...styles.bubble,
          ...(isUser ? styles.userBubble : styles.assistantBubble),
          fontSize: Math.round(14 * scale),
        }}
      >
        {!isUser && <span style={{ ...styles.label, fontSize: Math.round(11 * scale) }}>Claude + DSE</span>}
        <div style={styles.content}>
          {message.content.split("\n").map((line, i) => (
            <p key={i} style={{ margin: line ? "4px 0" : "12px 0" }}>
              {line || "\u00A0"}
            </p>
          ))}
        </div>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  row: {
    display: "flex",
    marginBottom: 16,
  },
  bubble: {
    maxWidth: "75%",
    padding: "12px 16px",
    borderRadius: 16,
    fontSize: 14,
    lineHeight: 1.6,
    wordBreak: "break-word" as const,
  },
  userBubble: {
    backgroundColor: "#7c3aed",
    color: "#fff",
    borderBottomRightRadius: 4,
  },
  assistantBubble: {
    backgroundColor: "#fff",
    color: "#111827",
    border: "1px solid #e5e7eb",
    borderBottomLeftRadius: 4,
  },
  label: {
    display: "block",
    fontSize: 11,
    fontWeight: 600,
    color: "#8b5cf6",
    marginBottom: 4,
  },
  content: {
    whiteSpace: "pre-wrap" as const,
  },
};
