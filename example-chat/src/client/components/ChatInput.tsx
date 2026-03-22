import React, { useCallback, useRef, useState } from "react";

interface Props {
  onSend: (message: string) => void;
  disabled: boolean;
  scale?: number;
}

export function ChatInput({ onSend, disabled, scale = 1 }: Props) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, disabled, onSend]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  const handleInput = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    const el = e.target;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 200) + "px";
  }, []);

  return (
    <div style={styles.container}>
      <div style={styles.inputRow}>
        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything... (memories persist across conversations)"
          disabled={disabled}
          rows={1}
          style={{ ...styles.textarea, fontSize: Math.round(14 * scale) }}
        />
        <button
          onClick={handleSubmit}
          disabled={disabled || !value.trim()}
          style={{
            ...styles.button,
            fontSize: Math.round(14 * scale),
            ...(disabled || !value.trim() ? styles.buttonDisabled : {}),
          }}
        >
          Send
        </button>
      </div>
      <p style={styles.hint}>
        Shift+Enter for newline. DSE memory tools: retrieve, store, search, graph.
      </p>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    padding: "16px 24px",
    borderTop: "1px solid #e5e7eb",
    backgroundColor: "#fff",
  },
  inputRow: {
    display: "flex",
    gap: 8,
    alignItems: "flex-end",
  },
  textarea: {
    flex: 1,
    padding: "10px 14px",
    borderRadius: 12,
    border: "1px solid #d1d5db",
    fontSize: 14,
    lineHeight: 1.5,
    resize: "none" as const,
    outline: "none",
    fontFamily: "inherit",
    maxHeight: 200,
  },
  button: {
    padding: "10px 20px",
    borderRadius: 12,
    border: "none",
    backgroundColor: "#7c3aed",
    color: "#fff",
    fontSize: 14,
    fontWeight: 500,
    cursor: "pointer",
    transition: "background-color 0.15s",
    whiteSpace: "nowrap" as const,
  },
  buttonDisabled: {
    backgroundColor: "#c4b5fd",
    cursor: "not-allowed",
  },
  hint: {
    marginTop: 6,
    fontSize: 11,
    color: "#9ca3af",
    textAlign: "center" as const,
  },
};
