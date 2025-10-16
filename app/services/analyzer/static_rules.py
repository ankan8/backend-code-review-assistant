from __future__ import annotations
import ast
from dataclasses import dataclass
from typing import List, Optional
@dataclass
class Finding:
    rule_id: str
    severity: str   
    message: str
    line: Optional[int] = None
@dataclass
class RuleFinding:
    rule_id: str
    severity: str  
    message: str
    line: int | None = None
def check_python_syntax(filename: str, content: str) -> List[Finding]:
    """Report SyntaxError locations for .py files using Python's AST parser."""
    if not filename.endswith(".py"):
        return []
    try:
        ast.parse(content, filename=filename)
        return []
    except SyntaxError as e:
        return [Finding(
            rule_id="PY_SYNTAX_ERROR",
            severity="error",
            message=f"{e.msg}",
            line=e.lineno or None,
        )]

def run_static_rules(filename: str, language: str | None, content: str) -> list[RuleFinding]:
    findings: list[RuleFinding] = []
    lines = content.splitlines()

    for idx, line in enumerate(lines, start=1):
        if len(line) > 120:
            findings.append(RuleFinding("STYLE_LONG_LINE", "info",
                                        f"Line exceeds 120 chars ({len(line)}). Consider wrapping.", idx))

    for idx, line in enumerate(lines, start=1):
        if "TODO" in line and "@" not in line:
            findings.append(RuleFinding("DOC_TODO_NO_OWNER", "warn",
                                        "TODO without an owner (e.g., TODO @alice: ...).", idx))

    secret_markers = ["AWS_SECRET_ACCESS_KEY", "BEGIN PRIVATE KEY", "password=", "passwd="]
    for idx, line in enumerate(lines, start=1):
        if any(m in line for m in secret_markers):
            findings.append(RuleFinding("SEC_SECRET_LEAK", "error",
                                        "Possible secret in source. Remove and rotate credentials.", idx))

    if (language == "python") and "print(" in content and "if __name__" not in content:
        findings.append(RuleFinding("PY_DEBUG_PRINT", "info",
                                    "Debug prints found. Gate under `if __name__ == '__main__':` or use logging.", None))

    if "except:" in content and "pass" in content:
        findings.append(RuleFinding("ERR_SWALLOW", "warn",
                                    "Bare except with pass swallows errors; catch specific exceptions.", None))
    findings += check_python_syntax(filename, content)
    return findings
