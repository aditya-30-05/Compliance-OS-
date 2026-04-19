"""
Input sanitization utilities.
Prevents XSS, injection, and cleans user-supplied text.
"""

import re
import html


def sanitize_text(text: str, max_length: int = 50000) -> str:
    """Sanitize user input text: escape HTML, limit length."""
    if not text:
        return ""
    text = text[:max_length]
    text = html.escape(text)
    return text.strip()


def sanitize_filename(filename: str) -> str:
    """Remove path traversal and unsafe characters from filenames."""
    filename = filename.replace("\\", "/").split("/")[-1]
    filename = re.sub(r'[^\w\s\-\.]', '', filename)
    filename = filename.strip(". ")
    return filename or "unnamed_file"


def sanitize_email(email: str) -> str:
    """Lowercase and strip email."""
    return email.lower().strip()
