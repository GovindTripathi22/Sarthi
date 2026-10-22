from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# User & Auth
class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# Integration
class IntegrationCreate(BaseModel):
    name: str
    provider: str
    base_url: str
    proxy_route: Optional[str] = None
    health_route: str = "/health"
    auth_method: str = "Bearer Token"
    repository: str = "acme-corp/commerce-integrations-service"
    target_adapter_file: str = "src/adapters/commerce_customer_adapter.py"
    latency_threshold_ms: int = 450
    error_rate_threshold_pct: float = 5.0
    active_contract_version: str = "v2.1.0"
    is_simulation_mode: bool = False


class IntegrationUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    base_url: Optional[str] = None
    health_route: Optional[str] = None
    latency_threshold_ms: Optional[int] = None
    error_rate_threshold_pct: Optional[float] = None
    monitoring_paused: Optional[bool] = None
    is_simulation_mode: Optional[bool] = None


class IntegrationResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    provider: str
    base_url: str
    proxy_route: str
    health_route: str
    auth_method: str
    repository: str
    target_adapter_file: str
    status: str
    monitoring_paused: bool
    latency_threshold_ms: int
    error_rate_threshold_pct: float
    active_contract_version: str
    doc_ingestion_status: str
    last_success_at: Optional[datetime] = None
    last_incident_at: Optional[datetime] = None
    is_simulation_mode: bool
    created_at: datetime


# Contracts & Validation
class SuspectedRename(BaseModel):
    old_field: str
    new_field: str
    confidence: float
    reason: str
    old_example: Optional[Any] = None
    new_example: Optional[Any] = None


class ContractValidationReport(BaseModel):
    valid: bool
    missing_required: List[str] = Field(default_factory=list)
    unexpected_fields: List[str] = Field(default_factory=list)
    type_mismatches: List[Dict[str, Any]] = Field(default_factory=list)
    suspected_renames: List[SuspectedRename] = Field(default_factory=list)
    schema_version: str = "v2.1.0"


class ContractImportRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    version: str
    contract_schema: Dict[str, Any] = Field(default_factory=dict, alias="schema_json")
    is_baseline: bool = False


class ContractResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    integration_id: str
    version: str
    is_baseline: bool
    contract_schema: Dict[str, Any] = Field(default_factory=dict, alias="schema_json")
    created_at: datetime


# Documentation & RAG
class DocumentIngestRequest(BaseModel):
    provider: str = "CommerceCore"
    title: str
    source_url: str = "https://docs.commercecore.internal/migrations"
    version: str = "v2.2"
    content: str


class DocumentResponse(BaseModel):
    id: str
    integration_id: str
    provider: str
    title: str
    source_url: str
    doc_type: str
    version: str
    content: str
    content_hash: str
    ingested_at: datetime


# Incident
class IncidentResponse(BaseModel):
    id: str
    workspace_id: str
    integration_id: str
    integration_name: str
    provider: str
    severity: str
    status: str
    failure_type: str
    endpoint: str
    first_occurrence: datetime
    detected_at: datetime
    diagnosed_at: Optional[datetime] = None
    proposed_at: Optional[datetime] = None
    recovered_at: Optional[datetime] = None
    last_occurrence: datetime
    failure_count: int
    assigned_reviewer: str
    workflow_state: str
    error_trace: str
    sanitized_payload: Dict[str, Any]
    contract_diff: Dict[str, Any]


# Repair & AgentRun
class RepairResponse(BaseModel):
    id: str
    incident_id: str
    workspace_id: str
    integration_id: str
    repository: str
    base_branch: str
    target_file: str
    checkpoint_id: str
    execution_mode: str
    current_node_index: int
    workflow_state: str
    iteration_count: int
    max_iterations: int
    confidence_score: float
    estimated_cost_usd: float
    input_tokens: int
    output_tokens: int
    rag_retrieval: Dict[str, Any]
    root_cause_hypothesis: Dict[str, Any]
    repair_plan: Optional[Dict[str, Any]]
    baseline_code: str
    proposed_code: str
    nodes: List[Dict[str, Any]]
    revision_notes: List[Dict[str, Any]]
    created_at: datetime
    updated_at: datetime
    approval_record: Optional[Dict[str, Any]] = None
    rejection_record: Optional[Dict[str, Any]] = None
    pull_request: Optional[Dict[str, Any]] = None
    deployment_record: Optional[Dict[str, Any]] = None
    validation_test_run: Optional[Dict[str, Any]] = None


class RepairDiffResponse(BaseModel):
    repair_id: str
    target_file: str
    baseline_code: str
    proposed_code: str
    unified_patch: str


class RevisionRequest(BaseModel):
    note: str = "Please preserve backwards compatibility."


class RejectRequest(BaseModel):
    reason: str


# Pull Request & Deployment
class DeploymentAuthorizeRequest(BaseModel):
    environment: str = "staging"


# Dashboard & Analytics
class DashboardSummaryResponse(BaseModel):
    monitored_integrations: int
    total_requests: int
    failed_requests: int
    schema_drift_events: int
    open_incidents: int
    awaiting_approval: int
    uptime_percentage: float = 99.98
    total_estimated_savings_usd: float = 0.0


class AuditLogResponse(BaseModel):
    id: str
    workspace_id: str
    timestamp: datetime
    actor: str
    role: str
    action: str
    target: str
    outcome: str
    details: str
