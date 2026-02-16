"""
SQLAlchemy Models for Council News Bot.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, JSON, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    council_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    date: Mapped[Optional[str]] = mapped_column(String, nullable=True) # Stored as string in legacy DB
    excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String, default="new", index=True)
    
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    posted_to_handle: Mapped[Optional[str]] = mapped_column(String, nullable=True)

class CouncilHealth(Base):
    __tablename__ = "council_health"
    
    council_id: Mapped[str] = mapped_column(String, primary_key=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    disabled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    consecutive_empty_runs: Mapped[int] = mapped_column(Integer, default=0)

class ScraperStats(Base):
    __tablename__ = "scraper_stats"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    council_id: Mapped[str] = mapped_column(String, nullable=False)
    run_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    articles_found: Mapped[int] = mapped_column(Integer, default=0)
    articles_saved: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

class LogEvent(Base):
    __tablename__ = "log_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    council_id: Mapped[Optional[str]] = mapped_column(String, index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class RunSummary(Base):
    __tablename__ = "run_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    state: Mapped[str] = mapped_column(String, index=True, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    councils_scraped: Mapped[int] = mapped_column(Integer, default=0)
    articles_found: Mapped[int] = mapped_column(Integer, default=0)
    articles_posted: Mapped[int] = mapped_column(Integer, default=0)
    errors_count: Mapped[int] = mapped_column(Integer, default=0)
    warnings_count: Mapped[int] = mapped_column(Integer, default=0)
