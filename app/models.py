from datetime import datetime
from sqlalchemy import Column,String, Integer, ForeignKey, Text, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

class Review(Base):
    __tablename__ = "reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    files: Mapped[list["ReviewFile"]] = relationship(back_populates="review", cascade="all, delete-orphan")
    issues: Mapped[list["ReviewIssue"]] = relationship(back_populates="review", cascade="all, delete-orphan")

class ReviewFile(Base):
    __tablename__ = "review_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"), index=True, nullable=False)
    filename: Mapped[str] = mapped_column(String(512), nullable=False)
    language: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    review: Mapped["Review"] = relationship(back_populates="files")
    issues: Mapped[list["ReviewIssue"]] = relationship(back_populates="file", cascade="all, delete-orphan")

class ReviewIssue(Base):
    __tablename__ = "review_issues"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[int] = mapped_column(ForeignKey("reviews.id"), index=True, nullable=False)
    file_id: Mapped[int | None] = mapped_column(ForeignKey("review_files.id"), index=True, nullable=True)
    rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False) 
    message: Mapped[str] = mapped_column(Text, nullable=False)
    line: Mapped[int | None] = mapped_column(Integer, nullable=True)

    review: Mapped["Review"] = relationship(back_populates="issues")
    file: Mapped["ReviewFile"] = relationship(back_populates="issues")
