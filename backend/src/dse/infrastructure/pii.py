from __future__ import annotations

import re
from dataclasses import dataclass, field

import structlog

from dse.core.enums import PIIPolicy
from dse.core.exceptions import PIIDetectedError

logger = structlog.get_logger(__name__)


@dataclass
class PIIResult:
    """Result of PII detection and processing."""

    content: str
    pii_detected: bool
    pii_types: list[str] = field(default_factory=list)


PII_PATTERNS: dict[str, str] = {
    "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    "phone_jp": r"\b(\+?81|0)\d{9,10}\b",
    "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
    "my_number": r"\b\d{12}\b",
    "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
}


class PIIGuard:
    """Detect and process PII in memory content before storage."""

    def __init__(self, policy: PIIPolicy = PIIPolicy.ANONYMIZE) -> None:
        self._policy = policy
        self._patterns = {name: re.compile(pattern) for name, pattern in PII_PATTERNS.items()}

    def detect(self, content: str) -> list[str]:
        """Detect PII types present in the content."""
        detected: list[str] = []
        for name, pattern in self._patterns.items():
            if pattern.search(content):
                detected.append(name)
        return detected

    def process(self, content: str) -> PIIResult:
        """Process content according to the PII policy."""
        detected = self.detect(content)

        if not detected:
            return PIIResult(content=content, pii_detected=False)

        logger.warning("pii.detected", types=detected, policy=self._policy.value)

        if self._policy == PIIPolicy.BLOCK:
            raise PIIDetectedError(detected)

        if self._policy == PIIPolicy.ANONYMIZE:
            anonymized = self._anonymize(content, detected)
            return PIIResult(
                content=anonymized,
                pii_detected=True,
                pii_types=detected,
            )

        if self._policy == PIIPolicy.TOKENIZE:
            tokenized = self._tokenize(content, detected)
            return PIIResult(
                content=tokenized,
                pii_detected=True,
                pii_types=detected,
            )

        return PIIResult(content=content, pii_detected=True, pii_types=detected)

    def _anonymize(self, content: str, pii_types: list[str]) -> str:
        """Replace PII with type labels."""
        result = content
        for pii_type in pii_types:
            pattern = self._patterns[pii_type]
            label = f"[{pii_type.upper()}_REDACTED]"
            result = pattern.sub(label, result)
        return result

    def _tokenize(self, content: str, pii_types: list[str]) -> str:
        """Replace PII with deterministic tokens (reversible with vault)."""
        result = content
        counter = 0
        for pii_type in pii_types:
            pattern = self._patterns[pii_type]
            for match in pattern.finditer(content):
                token = f"[PII_TOKEN_{pii_type}_{counter}]"
                result = result.replace(match.group(), token, 1)
                counter += 1
        return result
