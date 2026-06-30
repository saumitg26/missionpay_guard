"""
Data models for the MissionPay Guard Platform.

Defines all core data structures used throughout the payment processing pipeline,
including payment cases, risk firewall results, exception records, and audit events.
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional


class CaseStatus(Enum):
    """Payment case lifecycle states."""
    INTAKE = "intake"
    CLASSIFYING = "classifying"
    EXTRACTING = "extracting"
    VALIDATING = "validating"
    RISK_SCORING = "risk_scoring"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    EXCEPTION = "exception"
    REJECTED = "rejected"
    DISBURSEMENT_SIMULATED = "disbursement_simulated"
    COMPLETED = "completed"


class RiskLevel(Enum):
    """Risk classification levels from firewall assessment."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DocumentType(Enum):
    """Supported document types for ingestion."""
    INVOICE = "invoice"
    PURCHASE_ORDER = "purchase_order"
    CONTRACT_SUPPORT = "contract_support"
    PAYMENT_FORM = "payment_form"
    JUSTIFICATION_MEMO = "justification_memo"


@dataclass
class PaymentCase:
    """A payment case flowing through the MissionPay Guard pipeline."""
    case_id: str
    status: str  # CaseStatus value
    documents: list = field(default_factory=list)  # S3 keys
    extracted_fields: dict = field(default_factory=dict)
    vendor_name: str = ""
    invoice_number: str = ""
    invoice_amount: float = 0.0
    purchase_order_number: str = ""
    contract_id: str = ""
    payment_details: dict = field(default_factory=dict)
    document_type: str = ""
    extraction_confidence: float = 0.0
    # Risk firewall results
    risk_level: str = ""
    risk_score: float = 0.0
    risk_factors: list = field(default_factory=list)
    firewall_checks: dict = field(default_factory=dict)
    # Workflow
    approval_route: str = ""
    approved_by: str = ""
    approval_reasoning: str = ""
    # Exception handling
    exceptions: list = field(default_factory=list)
    # Metadata
    submitted_by: str = ""
    submitted_at: str = ""
    updated_at: str = ""
    source_channel: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for DynamoDB serialization."""
        return asdict(self)


@dataclass
class RiskFirewallResult:
    """Result from the Spend Provenance + Payment Risk Firewall."""
    case_id: str
    risk_level: str
    risk_score: float
    checks_passed: list = field(default_factory=list)
    checks_failed: list = field(default_factory=list)
    checks_warning: list = field(default_factory=list)
    requires_human_review: bool = False
    routing_recommendation: str = ""  # "standard", "manager", "finance_compliance_hitl"

    def to_dict(self) -> dict:
        """Convert to dictionary for DynamoDB serialization."""
        return asdict(self)


@dataclass
class ExceptionRecord:
    """Record of an exception requiring human resolution."""
    exception_id: str
    case_id: str
    exception_type: str  # "low_confidence", "validation_failure", "anomaly_detected"
    description: str
    ai_explanation: str = ""
    ai_recommendation: str = ""
    human_decision: str = ""  # "corrected", "approved_as_is", "rejected"
    corrected_data: dict = field(default_factory=dict)
    resolved_by: str = ""
    resolved_at: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for DynamoDB serialization."""
        return asdict(self)


@dataclass
class AuditEvent:
    """Immutable audit trail event for compliance tracking."""
    event_id: str
    case_id: str
    event_type: str
    actor: str
    action: str
    details: dict = field(default_factory=dict)
    timestamp: str = ""
    previous_state: Optional[str] = None
    new_state: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for DynamoDB serialization."""
        return asdict(self)
