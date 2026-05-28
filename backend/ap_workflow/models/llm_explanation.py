"""LLM explanation models for AP Workflow Agent."""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Integer
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import relationship

from ap_workflow.database.session import Base


class LLMExplanationCache(Base):
    """LLM explanation cache model storing generated explanations."""

    __tablename__ = "llm_explanation_cache"

    cache_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    cache_key = Column(String(64), nullable=False, unique=True)
    vendor_key = Column(String(100))
    exception_type = Column(String(50))
    explanation = Column(String, nullable=False)
    fallback = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_accessed_at = Column(DateTime, default=datetime.utcnow)
    ttl_expires_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=30))

    def __repr__(self) -> str:
        return f"<LLMExplanationCache(cache_id={self.cache_id}, cache_key={self.cache_key})>"


class LLMRequest(Base):
    """LLM request model storing queued LLM requests."""

    __tablename__ = "llm_requests"

    request_id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    exception_id = Column(PGUUID(as_uuid=True), ForeignKey("invoice_exceptions.exception_id"), nullable=False)
    status = Column(String(50))  # QUEUED, PROCESSING, COMPLETED, FAILED
    queue_position = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime)

    # Relationships
    exception = relationship("InvoiceException")

    def __repr__(self) -> str:
        return f"<LLMRequest(request_id={self.request_id}, exception_id={self.exception_id}, status={self.status})>"
