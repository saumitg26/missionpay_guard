#!/usr/bin/env python3
"""CDK app entry point for the Agentic Payment Processing Platform."""

import aws_cdk as cdk

from payment_processing_stack import PaymentProcessingStack

app = cdk.App()

PaymentProcessingStack(
    app,
    "AgenticPaymentProcessingStack",
    env=cdk.Environment(
        account=app.node.try_get_context("account") or None,
        region=app.node.try_get_context("region") or "us-east-1",
    ),
    description="Agentic Payment Processing Platform - Serverless AWS infrastructure for automated federal payment processing with AI",
)

app.synth()
