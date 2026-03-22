from __future__ import annotations

import pytest

from dse.core.enums import PIIPolicy
from dse.core.exceptions import PIIDetectedError
from dse.infrastructure.pii import PIIGuard


class TestPIIGuard:
    def test_no_pii(self) -> None:
        guard = PIIGuard(PIIPolicy.ANONYMIZE)
        result = guard.process("This is normal text without PII")
        assert not result.pii_detected
        assert result.content == "This is normal text without PII"

    def test_detect_email(self) -> None:
        guard = PIIGuard(PIIPolicy.ANONYMIZE)
        result = guard.process("Contact me at user@example.com please")
        assert result.pii_detected
        assert "email" in result.pii_types
        assert "[EMAIL_REDACTED]" in result.content
        assert "user@example.com" not in result.content

    def test_detect_phone_jp(self) -> None:
        guard = PIIGuard(PIIPolicy.ANONYMIZE)
        result = guard.process("電話番号: 09012345678")
        assert result.pii_detected
        assert "phone_jp" in result.pii_types

    def test_detect_credit_card(self) -> None:
        guard = PIIGuard(PIIPolicy.ANONYMIZE)
        result = guard.process("Card: 4111-1111-1111-1111")
        assert result.pii_detected
        assert "credit_card" in result.pii_types

    def test_block_policy(self) -> None:
        guard = PIIGuard(PIIPolicy.BLOCK)
        with pytest.raises(PIIDetectedError) as exc_info:
            guard.process("Email: user@example.com")
        assert "email" in exc_info.value.pii_types

    def test_tokenize_policy(self) -> None:
        guard = PIIGuard(PIIPolicy.TOKENIZE)
        result = guard.process("Email: user@example.com")
        assert result.pii_detected
        assert "[PII_TOKEN_email_0]" in result.content

    def test_multiple_pii_types(self) -> None:
        guard = PIIGuard(PIIPolicy.ANONYMIZE)
        result = guard.process("user@example.com called from 09012345678")
        assert result.pii_detected
        assert "email" in result.pii_types
        assert "phone_jp" in result.pii_types
