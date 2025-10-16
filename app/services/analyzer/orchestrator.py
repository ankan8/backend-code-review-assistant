from sqlalchemy.orm import Session
from .static_rules import run_static_rules
from .llm_client import call_llm_summarize
from ...models import Review, ReviewFile, ReviewIssue
from ...config import get_settings

settings = get_settings()

def _make_preview_blocks(files: list[tuple[str, str, str | None]]) -> list[dict]:
    """
    Build per-file previews constrained by settings.llm_per_file_chars and total budget.
    Returns list of dicts: {filename, language, preview}
    """
    per_file = settings.llm_per_file_chars
    total_budget = settings.llm_total_chars

    blocks: list[dict] = []
    remaining = total_budget

    for (filename, content, lang) in files:
        if remaining <= 0:
            break
        if len(content) <= per_file:
            preview = content
        else:
            head = content[: per_file // 2]
            tail = content[-(per_file // 2):]
            preview = head + "\n...\n" + tail

        if len(preview) > remaining:
            preview = preview[:remaining]
        blocks.append({"filename": filename, "language": lang or "unknown", "preview": preview})
        remaining -= len(preview)
    return blocks

def analyze_review(db: Session, files: list[tuple[str, str, str | None]]) -> Review:
    """
    files: list of tuples (filename, content, language)
    """
    review = Review(llm_used=False)
    db.add(review)
    db.flush()

    all_issue_dicts: list[dict] = []
    file_records: list[ReviewFile] = []

    for filename, content, lang in files:
        rf = ReviewFile(review_id=review.id, filename=filename, content=content, language=lang)
        db.add(rf)
        db.flush()
        file_records.append(rf)

        for f in run_static_rules(filename, lang, content):
            issue = ReviewIssue(
                review_id=review.id,
                file_id=rf.id,
                rule_id=f.rule_id,
                severity=f.severity,
                message=f.message,
                line=f.line,
            )
            db.add(issue)
            db.flush()
            all_issue_dicts.append({
                "rule_id": f.rule_id,
                "severity": f.severity,
                "message": f.message,
                "line": f.line,
                "file_id": rf.id,
                "filename": filename,
                "language": lang or "unknown",
            })

    file_blocks = _make_preview_blocks([(fr.filename, fr.content, fr.language) for fr in file_records])

    summary, llm_used = call_llm_summarize(
        issues=all_issue_dicts,
        file_blocks=file_blocks,   
    )
    review.summary = summary
    review.llm_used = llm_used
    db.commit()
    db.refresh(review)
    return review
