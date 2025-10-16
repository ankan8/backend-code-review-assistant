import re
from pathlib import Path

EXT_TO_LANG = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".go": "go",
    ".java": "java",
    ".cpp": "cpp",
    ".c": "c",
    ".rs": "rust",
}

def sniff_language(filename: str) -> str | None:
    return EXT_TO_LANG.get(Path(filename).suffix.lower())

def safe_decode(b: bytes) -> str:
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("latin-1", errors="replace")

def count_lines(text: str) -> int:
    return text.count("\n") + 1 if text else 0

def guess_is_minified(text: str) -> bool:
    if count_lines(text) <= 3 and len(text) > 500:
        return True
    return bool(re.search(r"[;{}]{20,}", text))
