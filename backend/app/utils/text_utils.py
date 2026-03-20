from __future__ import annotations

from typing import Any, Optional


def clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return " ".join(text.split())


def clean_multiline_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())
