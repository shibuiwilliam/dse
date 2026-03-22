import React from "react";

export type FontSize = "small" | "medium" | "large";

export const FONT_SCALE: Record<FontSize, number> = {
  small: 0.85,
  medium: 1,
  large: 1.2,
};

const OPTIONS: { value: FontSize; label: string }[] = [
  { value: "small", label: "A" },
  { value: "medium", label: "A" },
  { value: "large", label: "A" },
];

interface Props {
  value: FontSize;
  onChange: (size: FontSize) => void;
}

export function FontSizeSelector({ value, onChange }: Props) {
  return (
    <div style={styles.container}>
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          style={{
            ...styles.button,
            fontSize: opt.value === "small" ? 11 : opt.value === "medium" ? 14 : 18,
            ...(value === opt.value ? styles.active : {}),
          }}
          title={`${opt.value} font size`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    display: "flex",
    gap: 2,
    marginLeft: 12,
    backgroundColor: "#f3f4f6",
    borderRadius: 6,
    padding: 2,
  },
  button: {
    border: "none",
    background: "transparent",
    cursor: "pointer",
    padding: "2px 8px",
    borderRadius: 4,
    color: "#6b7280",
    fontWeight: 600,
    lineHeight: 1,
    transition: "all 0.15s",
  },
  active: {
    backgroundColor: "#fff",
    color: "#7c3aed",
    boxShadow: "0 1px 2px rgba(0,0,0,0.08)",
  },
};
