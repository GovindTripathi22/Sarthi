from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow() -> datetime:
    """Return timezone-aware UTC timestamp for all persisted entities."""
    return datetime.now(timezone.utc)


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./autopatch_local.db")

engine_kwargs: Dict[str, Any] = {"future": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    """Declarative base for all 21 normalized AutoPatch database tables."""
    pass


class User(Base):
    """Table 1: Platform users with hashed passwords."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Workspace(Base):
    """Table 2: Multi-tenant workspace boundary and governance policy settings."""
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    approval_policy: Mapped[str] = mapped_column(String(64), default="STRICT_TWO_STAGE")
    demo_mode: Mapped[bool] = mapped_column(Boolean, default=True)
    drift_active: Mapped[bool] = mapped_column(Boolean, default=False)
    upstream_failure_mode: Mapped[str] = mapped_column(String(64), default="NONE")
    llm_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    github_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    business_assumptions: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorkspaceMember(Base):
    """Table 3: Workspace RBAC role assignments (Admin, Reviewer, Operator, Viewer)."""
    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uq_workspace_user"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="Operator")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Integration(Base):
    """Table 4: Explicitly registered upstream API integrations routed through AutoPatch."""
    __tablename__ = "integrations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    base_url: Mapped[str] = mapped_column(String(512), nullable=False)
    proxy_route: Mapped[str] = mapped_column(String(512), nullable=False)
    health_route: Mapped[str] = mapped_column(String(255), default="/health")
    auth_method: Mapped[str] = mapped_column(String(255), default="Bearer Token")
    repository: Mapped[str] = mapped_column(String(255), nullable=False)
    target_adapter_file: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="HEALTHY")
    monitoring_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    latency_threshold_ms: Mapped[int] = mapped_column(Integer, default=450)
    error_rate_threshold_pct: Mapped[float] = mapped_column(Float, default=5.0)
    active_contract_version: Mapped[str] = mapped_column(String(64), default="v2.1.0")
    doc_ingestion_status: Mapped[str] = mapped_column(String(64), default="INDEXED")
    last_success_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_incident_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntegrationSecret(Base):
    """Table 5: Encrypted secret references and masked previews (never returned in plaintext)."""
    __tablename__ = "integration_secrets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    integration_id: Mapped[Optional[str]] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"), nullable=True)
    secret_type: Mapped[str] = mapped_column(String(64), nullable=False)
    encrypted_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    masked_preview: Mapped[str] = mapped_column(String(64), nullable=False)
    rotated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApiContractVersion(Base):
    """Table 6: Versioned OpenAPI / JSON Schema contracts per integration."""
    __tablename__ = "api_contract_versions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"), index=True)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    is_baseline: Mapped[bool] = mapped_column(Boolean, default=False)
    schema_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    diff_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DocumentationSource(Base):
    """Table 7: Ingested migration guides, OpenAPI specs, and release notes with SHA-256 deduplication."""
    __tablename__ = "documentation_sources"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(64), default="MIGRATION_GUIDE")
    version: Mapped[str] = mapped_column(String(64), default="v2.2")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DocumentChunk(Base):
    """Table 8: Semantic chunk metadata linked to Qdrant vector points."""
    __tablename__ = "document_chunks"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    doc_id: Mapped[str] = mapped_column(ForeignKey("documentation_sources.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    text_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[List[str]] = mapped_column(JSON, default=list)
    qdrant_point_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)


class RequestEvent(Base):
    """Table 9: Sanitized API gateway request telemetry and validation outcomes."""
    __tablename__ = "request_events"
    __table_args__ = (Index("ix_req_workspace_ts", "workspace_id", "timestamp"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"), index=True)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    normalized_route: Mapped[str] = mapped_column(String(512), nullable=False)
    upstream_host: Mapped[str] = mapped_column(String(255), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    error_classification: Mapped[str] = mapped_column(String(64), default="NONE")
    schema_validation_result: Mapped[str] = mapped_column(String(64), default="PASS")
    correlation_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    incident_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    sanitized_headers: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    sanitized_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class SchemaDriftEvent(Base):
    """Table 10: Detailed structural contract mismatch records."""
    __tablename__ = "schema_drift_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"), index=True)
    request_event_id: Mapped[str] = mapped_column(ForeignKey("request_events.id", ondelete="CASCADE"))
    baseline_version: Mapped[str] = mapped_column(String(64), nullable=False)
    missing_required: Mapped[List[str]] = mapped_column(JSON, default=list)
    unexpected_fields: Mapped[List[str]] = mapped_column(JSON, default=list)
    type_mismatches: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    suspected_renames: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Incident(Base):
    """Table 11: Aggregated operational or schema-drift incidents."""
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"), index=True)
    integration_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), default="CRITICAL")
    status: Mapped[str] = mapped_column(String(64), default="DETECTED", index=True)
    failure_type: Mapped[str] = mapped_column(String(64), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(512), nullable=False)
    first_occurrence: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    diagnosed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    proposed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    recovered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_occurrence: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    failure_count: Mapped[int] = mapped_column(Integer, default=1)
    assigned_reviewer: Mapped[str] = mapped_column(String(255), default="Elena Rostova (Admin)")
    workflow_state: Mapped[str] = mapped_column(String(64), default="DETECTED")
    error_trace: Mapped[str] = mapped_column(Text, nullable=False)
    sanitized_payload: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    contract_diff: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)


class IncidentEvent(Base):
    """Table 12: Chronological forensic timeline entries per incident."""
    __tablename__ = "incident_events"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    event_description: Mapped[str] = mapped_column(Text, nullable=False)


class AgentRun(Base):
    """Table 13: 11-Node LangGraph self-healing repair workflow run."""
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    integration_id: Mapped[str] = mapped_column(ForeignKey("integrations.id", ondelete="CASCADE"), index=True)
    repository: Mapped[str] = mapped_column(String(255), nullable=False)
    base_branch: Mapped[str] = mapped_column(String(128), default="main")
    target_file: Mapped[str] = mapped_column(String(512), nullable=False)
    checkpoint_id: Mapped[str] = mapped_column(String(128), nullable=False)
    execution_mode: Mapped[str] = mapped_column(String(128), default="DEMO_FALLBACK_DETERMINISTIC")
    current_node_index: Mapped[int] = mapped_column(Integer, default=9)
    workflow_state: Mapped[str] = mapped_column(String(64), default="AWAITING_APPROVAL", index=True)
    iteration_count: Mapped[int] = mapped_column(Integer, default=1)
    max_iterations: Mapped[int] = mapped_column(Integer, default=3)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.96)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    rag_retrieval: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    root_cause_hypothesis: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    repair_plan: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    nodes_state: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    revision_notes: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AgentRunCheckpoint(Base):
    """Table 14: Persistent LangGraph state checkpoints for resumable human-in-the-loop pauses."""
    __tablename__ = "agent_run_checkpoints"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    node_index: Mapped[int] = mapped_column(Integer, nullable=False)
    node_name: Mapped[str] = mapped_column(String(128), nullable=False)
    serialized_state: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PatchArtifact(Base):
    """Table 15: Generated code diff and unified patch artifacts."""
    __tablename__ = "patch_artifacts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    target_file: Mapped[str] = mapped_column(String(512), nullable=False)
    baseline_code: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_code: Mapped[str] = mapped_column(Text, nullable=False)
    unified_diff: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    scope_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TestRun(Base):
    """Table 16: Isolated sandbox regression test execution records."""
    __tablename__ = "test_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    sandbox_id: Mapped[str] = mapped_column(String(128), nullable=False)
    container_profile: Mapped[str] = mapped_column(String(512), nullable=False)
    is_patched_run: Mapped[bool] = mapped_column(Boolean, default=True)
    static_analysis_passed: Mapped[bool] = mapped_column(Boolean, default=True)
    change_scope_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    passed_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    runtime_ms: Mapped[int] = mapped_column(Integer, default=0)
    results_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    raw_log: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GithubPullRequest(Base):
    """Table 17: GitHub PR metadata or local patch export records (with idempotency constraint)."""
    __tablename__ = "github_pull_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), unique=True)
    mode: Mapped[str] = mapped_column(String(64), default="LOCAL_PATCH_EXPORT")
    pr_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    branch: Mapped[str] = mapped_column(String(255), nullable=False)
    commit_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(64), default="OPEN")
    pr_body: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ApprovalRequest(Base):
    """Table 18: Human review approval or rejection records enforced by RBAC."""
    __tablename__ = "approval_requests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    reviewer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    reviewer_role: Mapped[str] = mapped_column(String(64), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    reason_or_comment: Mapped[str] = mapped_column(Text, nullable=False)
    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DeploymentRecord(Base):
    """Table 19: Explicit Stage-2 Admin production deployment authorization records."""
    __tablename__ = "deployment_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_run_id: Mapped[str] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    authorized_by: Mapped[str] = mapped_column(String(255), nullable=False)
    environment: Mapped[str] = mapped_column(String(128), default="production-us-east-1")
    verification_status: Mapped[str] = mapped_column(String(64), default="VERIFIED_RECOVERY")
    deployed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UsageRecord(Base):
    """Table 20: Token consumption, sandbox runtime, and cost ledger per workspace."""
    __tablename__ = "usage_records"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    agent_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    provider: Mapped[str] = mapped_column(String(64), default="deterministic_demo")
    model: Mapped[str] = mapped_column(String(64), default="gpt-4o-mini")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    sandbox_runtime_ms: Mapped[int] = mapped_column(Integer, default=0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    """Table 21: Immutable workspace governance and security audit log."""
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target: Mapped[str] = mapped_column(String(255), nullable=False)
    outcome: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False)


def init_db() -> None:
    """Create all 21 tables if they do not exist."""
    Base.metadata.create_all(bind=engine)
