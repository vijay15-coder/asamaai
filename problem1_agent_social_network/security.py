"""
Security, HMAC verification, and prompt injection defense.
"""
import hmac
import hashlib
import json
import re
from typing import Dict, Any, Tuple


class SecurityManager:
    """
    Handles payload signing, verification, and prompt injection detection.
    """
    
    INJECTION_PATTERNS = [
        r"ignore\s+(?:all\s+)?(?:previous|prior)\s+instructions",
        r"disregard\s+(?:all\s+)?(?:previous|prior)\s+rules",
        r"system\s*:\s*you\s+are",
        r"you\s+are\s+now\s+DAN",
        r"output\s+confidential\s+keys",
        r"reveal\s+(?:your\s+)?secret",
        r"<script.*?>",
        r"drop\s+table",
    ]

    @staticmethod
    def sign_payload(secret_key: str, payload: Dict[str, Any]) -> str:
        """Computes HMAC-SHA256 signature for the given JSON payload."""
        serialized = json.dumps(payload, sort_keys=True, separators=(',', ':'))
        return hmac.new(
            secret_key.encode('utf-8'),
            serialized.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

    @staticmethod
    def verify_signature(secret_key: str, payload: Dict[str, Any], received_signature: str) -> bool:
        """Verifies HMAC-SHA256 signature against the received signature."""
        expected_sig = SecurityManager.sign_payload(secret_key, payload)
        return hmac.compare_digest(expected_sig, received_signature)

    @classmethod
    def sanitize_and_check_injection(cls, text: str) -> Tuple[bool, str]:
        """
        Inspects text for prompt injection and jailbreak patterns.
        Returns: (is_safe: bool, reason: str)
        """
        text_lower = text.lower()
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return False, f"Prompt injection or dangerous payload detected: pattern '{pattern}'"
        return True, "Safe"

