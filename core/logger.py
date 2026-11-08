"""
MIKE Structured Logging System.
Supports console output, file logging, and automatic sensitive data/secret redaction.
"""

import logging
import os
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List

from core.config import settings

# Sensitive patterns to redact from all logs
REDACT_PATTERNS = [
    (re.compile(r"AIza[0-9A-Za-z-_]{35}"), "[REDACTED_GEMINI_KEY]"),
    (re.compile(r"gsk_[0-9A-Za-z]{48,64}"), "[REDACTED_GROQ_KEY]"),
    (re.compile(r"(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*['\"]?([^\s'\"]+)"), r"\1=[REDACTED]"),
    (re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"), "[REDACTED_PHONE]"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}\b"), "[REDACTED_DATE]"),
]


class SensitiveDataFilter(logging.Filter):
    """Filter that strips API keys and PII from log records before writing."""

    def __init__(self, exact_secrets: List[str] = None):
        super().__init__()
        self.exact_secrets = [s for s in (exact_secrets or []) if s and len(s) > 4]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.sanitize(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.sanitize(str(v)) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.sanitize(str(v)) for v in record.args)
        return True

    def sanitize(self, text: str) -> str:
        for secret in self.exact_secrets:
            text = text.replace(secret, "[REDACTED_SECRET]")
        for pattern, replacement in REDACT_PATTERNS:
            text = pattern.sub(replacement, text)
        return text


def setup_logger(name: str = "MIKE") -> logging.Logger:
    """Configures and returns a centralized logger instance."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Gather any known secrets to redact exactly
    known_secrets = [
        s for s in [
            settings.gemini_api_key,
            settings.groq_api_key,
            settings.spotify_client_secret,
            settings.profile_encryption_key,
        ] if s
    ]
    redaction_filter = SensitiveDataFilter(exact_secrets=known_secrets)

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | [%(name)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(redaction_filter)
    logger.addHandler(console_handler)

    # 2. File Handler (Rotating)
    try:
        settings.logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = settings.logs_dir / "mike.log"
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setLevel(log_level)
        file_formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] (%(filename)s:%(lineno)d) - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(redaction_filter)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Failed to initialize rotating file logger: {e}")

    logger.propagate = False
    return logger


# Global logger instance
logger = setup_logger("MIKE")

