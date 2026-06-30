"""Self-Healing AI Agent for Agentic Payment Processing.

This module contains the key differentiator of the platform: an AI-powered
self-healing system that diagnoses payment processing errors, generates
plain-English explanations, suggests fixes, and re-runs workflows after
human approval.

Components:
    - error_context_builder: Captures error details and retrieves historical context
    - diagnosis_handler: Uses Bedrock Claude for root cause analysis
    - explanation_generator: Transforms technical diagnosis into plain English
    - fix_suggestion_handler: Produces SuggestedFix for user presentation
    - fix_application_handler: Applies approved fixes and triggers re-runs
    - rejection_handler: Escalates rejected fixes to manual processing

Audit Event Types:
    - SELF_HEALING_TRIGGERED: Error context built, self-healing initiated
    - SELF_HEALING_DIAGNOSIS: Claude diagnosis completed
    - SELF_HEALING_FIX_SUGGESTED: Fix suggestion generated
    - SELF_HEALING_FIX_APPLIED: Approved fix applied, workflow re-run started
    - SELF_HEALING_FIX_REJECTED: Fix rejected by user
    - SELF_HEALING_ESCALATION: Payment escalated to manual processing
"""

from lambdas.self_healing.error_context_builder import build_error_context
from lambdas.self_healing.diagnosis_handler import handler as diagnosis_handler
from lambdas.self_healing.explanation_generator import generate_plain_english_explanation
from lambdas.self_healing.fix_suggestion_handler import handler as fix_suggestion_handler
from lambdas.self_healing.fix_application_handler import handler as fix_application_handler
from lambdas.self_healing.rejection_handler import handle_rejection

__all__ = [
    "build_error_context",
    "diagnosis_handler",
    "generate_plain_english_explanation",
    "fix_suggestion_handler",
    "fix_application_handler",
    "handle_rejection",
]
