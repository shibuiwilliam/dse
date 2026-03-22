export interface ChatMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ToolActivity {
  tool: string;
  status: "running" | "done";
  input?: unknown;
}

export interface MemoryStatus {
  stored_by_claude: boolean;
  fallback_triggered: boolean;
}
