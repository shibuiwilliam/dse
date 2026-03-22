from __future__ import annotations

import json

import structlog
from google import genai

from dse.config import settings

logger = structlog.get_logger(__name__)


def _chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks on paragraph boundaries."""
    text = text.strip()
    if not text:
        return []

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        if current and len(current) + len(para) + 2 > chunk_size:
            chunks.append(current.strip())
            current = (
                current[-overlap:] + "\n\n" + para
                if overlap > 0 and len(current) > overlap
                else para
            )
        else:
            current = current + "\n\n" + para if current else para

    if current.strip():
        chunks.append(current.strip())

    # Force-split chunks that are still too long
    final: list[str] = []
    for chunk in chunks:
        if len(chunk) <= chunk_size * 1.5:
            final.append(chunk)
        else:
            for i in range(0, len(chunk), chunk_size - overlap):
                piece = chunk[i : i + chunk_size]
                if piece.strip():
                    final.append(piece.strip())
    return final


class LLMService:
    """Gemini LLM client for reasoning tasks."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_llm_model

    async def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        """Generate text from a prompt."""
        config = genai.types.GenerateContentConfig(
            response_mime_type="application/json" if json_mode else "text/plain",
        )
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        return response.text or ""

    async def generate_json(self, prompt: str) -> dict[str, object]:
        """Generate a JSON response from a prompt. Parses and returns as dict."""
        raw = await self.generate(prompt, json_mode=True)
        return json.loads(raw)  # type: ignore[no-any-return]

    async def classify_relation(
        self,
        summary_a: str,
        summary_b: str,
    ) -> dict[str, object]:
        """Classify the relationship between two memories."""
        prompt = f"""以下の2つのメモリの関係を分類してください。

Memory A: {summary_a}
Memory B: {summary_b}

以下のJSONのみを返してください:
{{"type": "SUPERSEDES|COMPLEMENTS|CONTRADICTS|DERIVES|CAUSES|REFERENCES|NONE", "confidence": 0.0-1.0, "reason": "..."}}"""
        result = await self.generate(prompt, json_mode=True)
        return json.loads(result)  # type: ignore[no-any-return]

    async def detect_contradiction(
        self,
        summary_a: str,
        summary_b: str,
    ) -> dict[str, object]:
        """Determine if two memories contradict each other."""
        prompt = f"""以下の2つのメモリが矛盾しているか判定してください。

Memory A: {summary_a}
Memory B: {summary_b}

以下のJSONのみを返してください:
{{"is_contradictory": true/false, "reason": "...", "confidence": 0.0-1.0}}"""
        result = await self.generate(prompt, json_mode=True)
        return json.loads(result)  # type: ignore[no-any-return]

    async def assess_importance(self, content: str, context: str = "") -> dict[str, object]:
        """Evaluate the importance of content for memory storage."""
        prompt = f"""以下のコンテンツの重要度を評価してください。

コンテンツ: {content}
コンテキスト: {context}

以下のJSONのみを返してください:
{{"importance_score": 0.0-1.0, "memory_type": "episodic|semantic|procedural|prospective", "reason": "...", "entities": ["entity1", "entity2"]}}"""
        result = await self.generate(prompt, json_mode=True)
        return json.loads(result)  # type: ignore[no-any-return]

    async def generate_summary(self, content: str) -> str:
        """Generate a concise summary of content (150 chars max)."""
        prompt = f"""以下のコンテンツを150文字以内で要約してください。要約のみを返してください。

{content}"""
        return await self.generate(prompt)

    async def enrich_memory(self, content: str, context: str = "") -> dict[str, object]:
        """Enrich raw content by inferring summary, tags, entities, and importance.

        Returns a dict with keys: summary, tags, entities, importance_score, memory_type, reason.
        Truncates input to 4000 chars to avoid Gemini timeouts on large content.
        """
        # Truncate to avoid Gemini 503 timeouts on very large inputs
        truncated = content[:4000] if len(content) > 4000 else content
        prompt = f"""Analyze the following content and extract structured metadata for a memory system.

Content: {truncated}
Context: {context}

Return ONLY the following JSON:
{{
  "summary": "<concise summary in 150 chars or less, same language as content>",
  "tags": ["<3-7 relevant category tags, lowercase>"],
  "entities": ["<named entities: tools, models, people, orgs, datasets, etc.>"],
  "importance_score": 0.0-1.0,
  "memory_type": "episodic|semantic|procedural|prospective",
  "reason": "<brief reason for importance score>"
}}"""
        result = await self.generate(prompt, json_mode=True)
        return json.loads(result)  # type: ignore[no-any-return]

    async def extract_document_text(self, file_path: str) -> str:
        """Upload a PDF to Gemini Files API and extract full text via OCR.

        Uses the Gemini document processing API to handle scanned PDFs,
        complex layouts, tables, and images with embedded text.
        """
        from pathlib import Path

        uploaded = await self._client.aio.files.upload(file=Path(file_path))
        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=[
                uploaded,
                (
                    "Extract ALL text content from this document. "
                    "Preserve the structure: headings, paragraphs, lists, tables, code blocks. "
                    "Output the full text in Markdown format. "
                    "Do not summarize — extract everything verbatim."
                ),
            ],
        )
        return response.text or ""

    async def chunk_and_enrich_document(
        self,
        text: str,
        source_filename: str,
        chunk_size: int = 1000,
        overlap: int = 100,
    ) -> list[dict[str, object]]:
        """Chunk a document and enrich each chunk with metadata via LLM.

        Returns a list of dicts, each with: content_text, summary, tags, entities,
        importance_score, memory_type, chunk_index, total_chunks.
        """
        chunks = _chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        if not chunks:
            return []

        results: list[dict[str, object]] = []
        for i, chunk in enumerate(chunks):
            enrichment = await self.enrich_memory(
                chunk, context=f"From document: {source_filename}, chunk {i + 1}/{len(chunks)}"
            )
            results.append(
                {
                    "content_text": chunk,
                    "summary": str(enrichment.get("summary", chunk[:150])),
                    "tags": list(enrichment.get("tags", [])),
                    "entities": list(enrichment.get("entities", [])),
                    "importance_score": float(enrichment.get("importance_score", 0.5)),
                    "memory_type": str(enrichment.get("memory_type", "semantic")),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
            )
        return results

    async def extract_intent(self, query: str, task_context: str = "") -> dict[str, object]:
        """Extract search intent from a natural language query."""
        prompt = f"""以下のクエリから検索意図を抽出してください:
クエリ: {query}
タスクコンテキスト: {task_context}

以下のJSONのみを返してください:
{{"primary_intent": "...", "memory_types": ["episodic", "semantic"], "entities": ["entity1"], "time_range": null, "urgency": "high|medium|low"}}"""
        result = await self.generate(prompt, json_mode=True)
        return json.loads(result)  # type: ignore[no-any-return]


class MockLLMService(LLMService):
    """Mock LLM service for local development and testing."""

    def __init__(self) -> None:
        self._model = "mock-llm"

    async def generate(self, prompt: str, *, json_mode: bool = False) -> str:
        if json_mode:
            return '{"result": "mock"}'
        return "Mock LLM response"

    async def generate_json(self, prompt: str) -> dict[str, object]:
        # Return content signal flags for importance estimator
        if "contains_decision" in prompt:
            return {
                "contains_decision": False,
                "contains_error_correction": False,
                "contains_user_preference": False,
                "contains_factual_claim": True,
                "contains_deadline": False,
            }
        return {"result": "mock"}

    async def classify_relation(
        self,
        summary_a: str,
        summary_b: str,
    ) -> dict[str, object]:
        return {"type": "NONE", "confidence": 0.5, "reason": "mock"}

    async def detect_contradiction(
        self,
        summary_a: str,
        summary_b: str,
    ) -> dict[str, object]:
        return {"is_contradictory": False, "reason": "mock", "confidence": 0.5}

    async def assess_importance(self, content: str, context: str = "") -> dict[str, object]:
        return {
            "importance_score": 0.5,
            "memory_type": "episodic",
            "reason": "mock",
            "entities": [],
        }

    async def generate_summary(self, content: str) -> str:
        return content[:150]

    async def enrich_memory(self, content: str, context: str = "") -> dict[str, object]:
        words = content.split()
        return {
            "summary": content[:150],
            "tags": ["mock-tag"],
            "entities": [w for w in words if w[0:1].isupper() and len(w) > 2][:5],
            "importance_score": 0.5,
            "memory_type": "episodic",
            "reason": "mock enrichment",
        }

    async def extract_document_text(self, file_path: str) -> str:
        from pathlib import Path

        p = Path(file_path)
        if p.suffix.lower() == ".pdf":
            return f"[Mock PDF extraction from {p.name}] This is simulated text content."
        return p.read_text(encoding="utf-8")

    async def chunk_and_enrich_document(
        self,
        text: str,
        source_filename: str,
        chunk_size: int = 1000,
        overlap: int = 100,
    ) -> list[dict[str, object]]:
        chunks = _chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        results: list[dict[str, object]] = []
        for i, chunk in enumerate(chunks):
            results.append(
                {
                    "content_text": chunk,
                    "summary": chunk[:150],
                    "tags": ["mock-tag", f"source:{source_filename}"],
                    "entities": [],
                    "importance_score": 0.5,
                    "memory_type": "semantic",
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
            )
        return results

    async def extract_intent(self, query: str, task_context: str = "") -> dict[str, object]:
        return {
            "primary_intent": query,
            "memory_types": ["episodic", "semantic"],
            "entities": [],
            "time_range": None,
            "urgency": "medium",
        }
