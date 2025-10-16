from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List,Dict,Any
from ..deps import get_db
from ..utils.file_utils import safe_decode, sniff_language
from ..schemas import ReviewOut
from ..models import Review,ReviewFile,ReviewIssue
from ..services.analyzer.orchestrator import analyze_review
from fastapi.responses import JSONResponse
from ..db import SessionLocal

from ..services.analyzer.llm_client import summarize_review



router = APIRouter(prefix="/api/v1/reviews", tags=["reviews"])
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/upload", response_model=ReviewOut)
async def upload_and_review(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db)
):
    if not files:
        raise HTTPException(status_code=400, detail="No files received.")

    prepared: list[tuple[str, str, str | None]] = []
    for f in files:
        content = await f.read()
        text = safe_decode(content)
        lang = sniff_language(f.filename)
        prepared.append((f.filename, text, lang))

    review = analyze_review(db, prepared)
    return review

@router.get("/{review_id}", response_model=ReviewOut)
def get_review(review_id: int, db: Session = Depends(get_db)):
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review

@router.get("/", response_model=list[ReviewOut])
def list_reviews(db: Session = Depends(get_db)):
    return db.query(Review).order_by(Review.id.desc()).all()

@router.delete("/{review_id}")
def delete_review(review_id: int, db: Session = Depends(get_db)):
    review = db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    db.delete(review)
    db.commit()
    return {"status": "deleted", "id": review_id}

def _serialize_review(r: Review) -> dict:
    return {
        "id": r.id,
        "created_at": r.created_at.isoformat() if getattr(r, "created_at", None) else None,
        "summary": r.summary or "",
        "llm_used": bool(getattr(r, "llm_used", False)),
        "files": [
            {"id": f.id, "filename": f.filename, "language": f.language}
            for f in getattr(r, "files", [])
        ],
        "issues": [
            {
                "id": i.id,
                "rule_id": i.rule_id,
                "severity": i.severity,
                "message": i.message,
                "line": i.line,
                "file_id": i.file_id,
            }
            for i in getattr(r, "issues", [])
        ],
    }

@router.get("/{review_id}/export", response_class=JSONResponse)
def export_review(review_id: int, db: Session = Depends(get_db)):
    r = db.query(Review).filter(Review.id == review_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Review not found")
    return JSONResponse(content=_serialize_review(r), media_type="application/json")
def create_review_from_files(db: Session, files: List[Dict[str, Any]]) -> Review:
    """
    files = [{ "filename": str, "content": bytes }, ...]
    """
    # 1) Persist the review and files
    review = Review(summary="", llm_used=False)
    db.add(review)
    db.flush()

    persisted_files: List[ReviewFile] = []
    for f in files:
        rf = ReviewFile(
            review_id=review.id,
            filename=f["filename"],
            language=_guess_lang(f["filename"]),
            content=f["content"],  # if you store content; if not, remove
        )
        db.add(rf)
        persisted_files.append(rf)
    db.flush()

    # 2) Run static analysis over ALL files
    issues: List[ReviewIssue] = []
    from ..services.analyzer.static_rules import run_static_rules  # your static rules
    for rf in persisted_files:
        content = rf.content.decode("utf-8", errors="replace") if isinstance(rf.content, (bytes, bytearray)) else (rf.content or "")
        for finding in run_static_rules(rf.filename, rf.language, content):
            issue = ReviewIssue(
                review_id=review.id,
                file_id=rf.id,
                rule_id=finding.rule_id,
                severity=finding.severity,
                message=finding.message,
                line=finding.line,
            )
            db.add(issue)
            issues.append(issue)
    db.flush()

    # 3) LLM summary over ALL files + ALL issues (if LLM configured)
    try:
        # Build in-memory payload (don’t re-read from DB if you already have it)
        llm_files = []
        for rf in persisted_files:
            llm_files.append({
                "filename": rf.filename,
                "language": rf.language,
                "text": (rf.content.decode("utf-8", errors="replace")
                         if isinstance(rf.content, (bytes, bytearray)) else (rf.content or "")),
            })

        # Pull issues into plain dicts for the prompt
        llm_issues = [{
            "file": next((x.filename for x in persisted_files if x.id == i.file_id), None),
            "rule_id": i.rule_id,
            "severity": i.severity,
            "message": i.message,
            "line": i.line,
        } for i in issues]

        summary = summarize_review(files=llm_files, issues=llm_issues)
        if summary:
            review.summary = summary
            review.llm_used = True
    except Exception as e:
        # LLM failure → keep static-only summary
        review.summary = (
            "Summary:\n"
            "- Could not reach LLM. Use static findings to prioritize fixes.\n"
            f"- Error: {e}"
        )
        review.llm_used = False

    db.commit()
    db.refresh(review)
    return review


def _guess_lang(filename: str) -> str:
    lower = filename.lower()
    if lower.endswith(".py"): return "python"
    if lower.endswith(".js"): return "javascript"
    if lower.endswith(".ts"): return "typescript"
    if lower.endswith(".jsx"): return "jsx"
    if lower.endswith(".tsx"): return "tsx"
    if lower.endswith(".java"): return "java"
    if lower.endswith(".go"): return "go"
    if lower.endswith(".rs"): return "rust"
    return "plain"