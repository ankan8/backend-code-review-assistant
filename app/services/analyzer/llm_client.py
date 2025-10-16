from __future__ import annotations
from typing import Tuple, List, Dict, Any
from ...config import get_settings
import os
import json
import math
import requests

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")  # works for mistral-compatible too if you set base
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "mistral-small-latest")
MAX_TOTAL_CHARS = 120_000
PER_FILE_HARD_CAP = 20_000

settings = get_settings()

SYSTEM_INSTRUCTIONS = """You are a senior code reviewer.
Combine static-findings with your own reasoning to produce a concise, actionable review.
Prioritize correctness, security, and maintainability. Use bullet points. Reference filenames and line numbers when possible.
If multiple files interact, call out cross-file issues explicitly.
"""

SYSTEM_PROMPT = (
    "You are a senior code reviewer. Read the provided code excerpts and static-rule findings. "
    "Return 4–10 concise, prioritized bullets with actionable, code-aware feedback. "
    "Point to specific files/lines when possible. Prefer concrete fixes over generic advice. "
    "If excerpts are partial, acknowledge uncertainty briefly."
)

USER_TEMPLATE = """Context
- Files attached: {file_count}
- Static issues detected: {issue_count}

Static issues (top 10-by-severity):
{top_findings}

Code excerpts (truncated for length):
{code_previews}

Task
Given the issues and the code excerpts above, write a short, practical review:
- Focus on likely defects, security risks, performance pitfalls, and readability.
- Reference specific filenames/lines if visible in excerpts.
- Suggest concrete refactors or tests.
"""

def _format_findings(issues: List[Dict]) -> str:
    order = {"error": 0, "warn": 1, "info": 2}
    tops = sorted(issues, key=lambda x: order.get(x.get("severity","info"), 99))[:10]
    if not tops:
        return "- None"
    lines = []
    for i in tops:
        loc = ""
        if i.get("filename"):
            if i.get("line"):
                loc = f" ({i['filename']}:{i['line']})"
            else:
                loc = f" ({i['filename']})"
        lines.append(f"- [{i['severity'].upper()}] {i['rule_id']}: {i['message']}{loc}")
    return "\n".join(lines)

def _format_previews(blocks: List[Dict]) -> str:
    if not blocks:
        return "- No code provided."
    parts = []
    for b in blocks:
        header = f"--- {b['filename']} [{b.get('language','unknown')}] ---"
        body = f"```{b.get('language','')}\n{b['preview']}\n```"
        parts.append(header + "\n" + body)
    return "\n\n".join(parts)

def _fallback(issues: List[Dict], msg: str | None = None) -> Tuple[str, bool]:
    base = [
        "- Prioritize highest-severity items first.",
        "- Add/expand tests for edge cases and error paths.",
        "- Improve docs and inline comments where logic is non-obvious.",
    ] if issues else ["- No critical issues from static checks; still consider tests and a brief manual review."]
    text = "Summary:\n" + "\n".join(base)
    if msg:
        text = f"Summary (LLM fallback due to error):\n- {msg}\n" + "\n".join(base)
    return (text, False)

def call_llm_summarize(issues: List[Dict], file_blocks: List[Dict]) -> Tuple[str, bool]:
    if not settings.openai_enabled or not settings.openai_api_key:
        return _fallback(issues)

    try:
        from openai import OpenAI
        from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
        import httpx

        client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url or None)

        @retry(
            reraise=True,
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=0.6, min=0.5, max=4),
            retry=retry_if_exception_type(httpx.HTTPStatusError),
        )
        def _call():
            user_msg = USER_TEMPLATE.format(
                file_count = len(file_blocks),
                issue_count = len(issues),
                top_findings = _format_findings(issues),
                code_previews = _format_previews(file_blocks),
            )
            resp = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.2,
                max_tokens=500,
            )
            return resp.choices[0].message.content.strip()

        return (_call(), True)

    except Exception as e:
        msg = str(e)
        if "401" in msg:
            return _fallback(issues, "Unauthorized (401): bad API key or project key not allowed.")
        if "429" in msg:
            return _fallback(issues, "Rate limit or quota exceeded (429): check billing/limits.")
        if "insufficient_quota" in msg:
            return _fallback(issues, "Insufficient quota: add billing credit.")
        return _fallback(issues, msg[:200])
    
def _trim_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    # Try to end on a line boundary
    cut = text[:limit]
    last_nl = cut.rfind("\n")
    if last_nl > limit * 0.8:
        cut = cut[:last_nl]
    return cut + "\n\n# [truncated]\n"

def _pack_files(files: List[Dict[str, Any]]) -> str:
    """
    Produces a single string containing all files with per-file caps
    and a global budget.
    """
    if not files:
        return "No files provided."

    # Fair-share per-file budget within MAX_TOTAL_CHARS
    per_file_budget = min(PER_FILE_HARD_CAP, math.floor(MAX_TOTAL_CHARS / max(1, len(files))))

    parts = []
    for f in files:
        name = f.get("filename") or "unknown"
        lang = f.get("language") or ""
        text = f.get("text") or ""
        text = _trim_text(text, per_file_budget)
        fence = lang if isinstance(lang, str) else ""
        parts.append(f"### {name}\n```{fence}\n{text}\n```\n")
    payload = "\n".join(parts)

    # Hard global cap as safety
    return _trim_text(payload, MAX_TOTAL_CHARS)

def _pack_issues(issues: List[Dict[str, Any]]) -> str:
    if not issues:
        return "No static issues detected."
    lines = []
    for i in issues:
        file = i.get("file") or "?"
        sev = i.get("severity") or "info"
        rid = i.get("rule_id") or "RULE"
        msg = i.get("message") or ""
        line = i.get("line")
        if line:
            lines.append(f"- [{sev.upper()}] {rid} in {file}:{line} — {msg}")
        else:
            lines.append(f"- [{sev.upper()}] {rid} in {file} — {msg}")
    return "\n".join(lines)

def summarize_review(files: List[Dict[str, Any]], issues: List[Dict[str, Any]]) -> str:
    """
    files: [{ filename, language, text }]
    issues: [{ file, rule_id, severity, message, line }]
    """
    if not OPENAI_API_KEY or not OPENAI_BASE_URL or not OPENAI_MODEL:
        return ""

    files_blob = _pack_files(files)
    issues_blob = _pack_issues(issues)

    user_prompt = f"""Project files (truncated when necessary):

{files_blob}

Static findings:
{issues_blob}

Write a concise, high-signal review:
- Group by theme (Correctness, Security, API design, Performance, Maintainability).
- Quote short code snippets or line refs when needed.
- Be specific and actionable; propose quick fixes.
- If something is fine, say so briefly.
"""

    # Mistral/OpenAI-compatible Chat Completions
    url = f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENAI_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }

    resp = requests.post(url, headers=headers, data=json.dumps(payload), timeout=60)
    if resp.status_code != 200:
        raise RuntimeError(f"LLM error {resp.status_code}: {resp.text}")

    data = resp.json()
    # OpenAI/Mistral style
    content = data["choices"][0]["message"]["content"]
    return content.strip()
