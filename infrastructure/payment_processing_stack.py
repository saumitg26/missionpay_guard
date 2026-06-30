"""Main CDK stack for the MissionPay Guard Platform."""

from aws_cdk import Stack, RemovalPolicy, Duration
from aws_cdk import aws_s3 as s3
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_stepfunctions as sfn
from aws_cdk import aws_stepfunctions_tasks as sfn_tasks
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_iam as iam
from aws_cdk import aws_sns as sns
from aws_cdk import aws_s3_notifications as s3n
from constructs import Construct


class PaymentProcessingStack(Stack):
    """CDK Stack for the MissionPay Guard Platform.

    This stack provisions all AWS resources needed for the platform:
    - S3 bucket for document storage (with quarantine prefix)
    - DynamoDB tables for cases and audit trail
    - Lambda functions for processing pipeline
    - Step Functions state machine (MissionPayGuardWorkflow)
    - API Gateway for external access
    - SNS for notifications
    - IAM roles with least-privilege policies

    Architecture: Intake → Classify → Extract → ConfidenceCheck →
                  RunRiskFirewall → GenerateAIExplanation →
                  RouteApproval → SimulateDisbursement →
                  GenerateAuditPacket → Complete
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # =============================================
        # Core Resources
        # =============================================

        # S3 Bucket for document storage (quarantine prefix for new uploads)
        self.documents_bucket = s3.Bucket(
            self,
            "DocumentsBucket",
            encryption=s3.BucketEncryption.S3_MANAGED,
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            event_bridge_enabled=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Add CORS to allow presigned URL uploads from browser
        self.documents_bucket.add_cors_rule(
            allowed_methods=[s3.HttpMethods.PUT, s3.HttpMethods.GET],
            allowed_origins=["*"],
            allowed_headers=["*"],
            max_age=3600,
        )

        # DynamoDB Cases Table
        self.cases_table = dynamodb.Table(
            self,
            "CasesTable",
            table_name="missionpay-cases",
            partition_key=dynamodb.Attribute(
                name="case_id", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # DynamoDB Audit Trail Table
        self.audit_trail_table = dynamodb.Table(
            self,
            "AuditTrailTable",
            table_name="missionpay-audit-trail",
            partition_key=dynamodb.Attribute(
                name="event_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp", type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True,
            removal_policy=RemovalPolicy.DESTROY,
        )

        # GSI on audit_trail for querying by case_id
        self.audit_trail_table.add_global_secondary_index(
            index_name="case_id-index",
            partition_key=dynamodb.Attribute(
                name="case_id", type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="timestamp", type=dynamodb.AttributeType.STRING
            ),
        )

        # =============================================
        # SNS Topics
        # =============================================

        self.approval_topic = sns.Topic(
            self,
            "ApprovalNotificationTopic",
            topic_name="missionpay-approval-notifications",
            display_name="MissionPay Guard Approval Notifications",
        )

        self.notification_topic = sns.Topic(
            self,
            "PaymentNotificationTopic",
            topic_name="missionpay-notifications",
            display_name="MissionPay Guard Status Notifications",
        )

        # =============================================
        # IAM Roles
        # =============================================

        logs_policy = iam.PolicyStatement(
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
            ],
            resources=["arn:aws:logs:*:*:*"],
        )

        # --- Ingestion Role: S3 read/tag, DynamoDB write (cases, audit) ---
        ingestion_role = iam.Role(
            self,
            "IngestionLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for document ingestion Lambda",
        )
        ingestion_role.add_to_policy(logs_policy)
        ingestion_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:GetObject", "s3:HeadObject", "s3:PutObjectTagging"],
            resources=[self.documents_bucket.arn_for_objects("*")],
        ))
        ingestion_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:PutItem"],
            resources=[
                self.cases_table.table_arn,
                self.audit_trail_table.table_arn,
            ],
        ))

        # --- IDP Role: S3 read, Textract, Comprehend, Bedrock, DynamoDB write ---
        idp_role = iam.Role(
            self,
            "IDPLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for IDP pipeline Lambdas (Textract, Comprehend, Bedrock)",
        )
        idp_role.add_to_policy(logs_policy)
        idp_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:GetObject"],
            resources=[self.documents_bucket.arn_for_objects("*")],
        ))
        idp_role.add_to_policy(iam.PolicyStatement(
            actions=["textract:AnalyzeDocument"],
            resources=["*"],
        ))
        idp_role.add_to_policy(iam.PolicyStatement(
            actions=["comprehend:DetectEntities", "comprehend:DetectPiiEntities"],
            resources=["*"],
        ))
        idp_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=["arn:aws:bedrock:*::foundation-model/anthropic.*"],
        ))
        idp_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:PutItem", "dynamodb:UpdateItem"],
            resources=[
                self.cases_table.table_arn,
                self.audit_trail_table.table_arn,
            ],
        ))

        # --- Risk Firewall Role: DynamoDB read/write, Bedrock ---
        firewall_role = iam.Role(
            self,
            "FirewallLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Risk Firewall and Compliance Assistant Lambdas",
        )
        firewall_role.add_to_policy(logs_policy)
        firewall_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:Query",
            ],
            resources=[
                self.cases_table.table_arn,
                self.audit_trail_table.table_arn,
                f"{self.audit_trail_table.table_arn}/index/*",
            ],
        ))
        firewall_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=["arn:aws:bedrock:*::foundation-model/anthropic.*"],
        ))

        # --- Approval Role: DynamoDB read/write, SNS publish, SFN callback ---
        approval_role = iam.Role(
            self,
            "ApprovalLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for approval workflow Lambdas",
        )
        approval_role.add_to_policy(logs_policy)
        approval_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:Query",
            ],
            resources=[
                self.cases_table.table_arn,
                self.audit_trail_table.table_arn,
                f"{self.audit_trail_table.table_arn}/index/*",
            ],
        ))
        approval_role.add_to_policy(iam.PolicyStatement(
            actions=["sns:Publish"],
            resources=[self.approval_topic.topic_arn],
        ))
        approval_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "states:SendTaskSuccess",
                "states:SendTaskFailure",
            ],
            resources=["*"],
        ))

        # --- Exception Copilot Role: DynamoDB read/write, Bedrock ---
        exception_role = iam.Role(
            self,
            "ExceptionCopilotLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for Exception Resolution Copilot Lambdas",
        )
        exception_role.add_to_policy(logs_policy)
        exception_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
                "dynamodb:Query",
            ],
            resources=[
                self.cases_table.table_arn,
                self.audit_trail_table.table_arn,
                f"{self.audit_trail_table.table_arn}/index/*",
            ],
        ))
        exception_role.add_to_policy(iam.PolicyStatement(
            actions=["bedrock:InvokeModel"],
            resources=["arn:aws:bedrock:*::foundation-model/anthropic.*"],
        ))

        # --- Disbursement Role: DynamoDB read/write ---
        disbursement_role = iam.Role(
            self,
            "DisbursementLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for disbursement simulation Lambda",
        )
        disbursement_role.add_to_policy(logs_policy)
        disbursement_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "dynamodb:GetItem",
                "dynamodb:PutItem",
                "dynamodb:UpdateItem",
            ],
            resources=[
                self.cases_table.table_arn,
                self.audit_trail_table.table_arn,
            ],
        ))

        # --- Document Access Role: S3 read, DynamoDB read ---
        document_access_role = iam.Role(
            self,
            "DocumentAccessLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for secure document access Lambda",
        )
        document_access_role.add_to_policy(logs_policy)
        document_access_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:GetObject"],
            resources=[self.documents_bucket.arn_for_objects("*")],
        ))
        document_access_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:GetItem"],
            resources=[self.cases_table.table_arn],
        ))

        # --- Notifications Role: SNS publish, DynamoDB write (audit) ---
        notifications_role = iam.Role(
            self,
            "NotificationsLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for notifications Lambda",
        )
        notifications_role.add_to_policy(logs_policy)
        notifications_role.add_to_policy(iam.PolicyStatement(
            actions=["sns:Publish"],
            resources=[self.notification_topic.topic_arn],
        ))
        notifications_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:PutItem"],
            resources=[self.audit_trail_table.table_arn],
        ))

        # --- API Status Lambda Role: DynamoDB read ---
        api_status_role = iam.Role(
            self,
            "ApiStatusLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for case status API Lambda",
        )
        api_status_role.add_to_policy(logs_policy)
        api_status_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:GetItem"],
            resources=[self.cases_table.table_arn],
        ))

        # --- List Cases Lambda Role: DynamoDB scan ---
        list_cases_role = iam.Role(
            self,
            "ListCasesLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for list cases API Lambda",
        )
        list_cases_role.add_to_policy(logs_policy)
        list_cases_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:Scan"],
            resources=[self.cases_table.table_arn],
        ))

        # --- Create Case Lambda Role: DynamoDB write, S3 write, Audit write ---
        create_case_role = iam.Role(
            self,
            "CreateCaseLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for create case API Lambda",
        )
        create_case_role.add_to_policy(logs_policy)
        create_case_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:PutItem"],
            resources=[
                self.cases_table.table_arn,
                self.audit_trail_table.table_arn,
            ],
        ))
        create_case_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:PutObject", "s3:GetObject"],
            resources=[self.documents_bucket.arn_for_objects("*")],
        ))

        # --- Submit Decision Lambda Role: DynamoDB read/write, Audit write ---
        submit_decision_role = iam.Role(
            self,
            "SubmitDecisionLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for submit decision API Lambda",
        )
        submit_decision_role.add_to_policy(logs_policy)
        submit_decision_role.add_to_policy(iam.PolicyStatement(
            actions=["dynamodb:GetItem", "dynamodb:UpdateItem", "dynamodb:PutItem"],
            resources=[
                self.cases_table.table_arn,
                self.audit_trail_table.table_arn,
            ],
        ))

        # =============================================
        # Lambda Functions
        # =============================================

        lambda_runtime = _lambda.Runtime.PYTHON_3_12
        lambda_timeout = Duration.seconds(60)
        lambda_code = _lambda.Code.from_asset("src")

        common_env = {
            "CASES_TABLE_NAME": self.cases_table.table_name,
            "AUDIT_TABLE_NAME": self.audit_trail_table.table_name,
        }

        # --- Document Ingestion Lambda ---
        self.ingestion_fn = _lambda.Function(
            self,
            "IngestionFunction",
            function_name="missionpay-ingestion",
            runtime=lambda_runtime,
            handler="lambdas.ingestion.handler.handler",
            code=lambda_code,
            role=ingestion_role,
            timeout=lambda_timeout,
            environment={
                **common_env,
                "RAW_DOCUMENTS_BUCKET": self.documents_bucket.bucket_name,
            },
        )

        # --- IDP Pipeline Lambdas ---
        self.textract_fn = _lambda.Function(
            self,
            "TextractFunction",
            function_name="missionpay-textract",
            runtime=lambda_runtime,
            handler="lambdas.idp.textract_handler.handler",
            code=lambda_code,
            role=idp_role,
            timeout=Duration.seconds(120),
            environment=common_env,
        )

        self.comprehend_fn = _lambda.Function(
            self,
            "ComprehendFunction",
            function_name="missionpay-comprehend",
            runtime=lambda_runtime,
            handler="lambdas.idp.comprehend_handler.handler",
            code=lambda_code,
            role=idp_role,
            timeout=Duration.seconds(120),
            environment=common_env,
        )

        self.bedrock_extraction_fn = _lambda.Function(
            self,
            "BedrockExtractionFunction",
            function_name="missionpay-bedrock-extraction",
            runtime=lambda_runtime,
            handler="lambdas.idp.bedrock_extraction_handler.handler",
            code=lambda_code,
            role=idp_role,
            timeout=Duration.seconds(120),
            environment=common_env,
        )

        self.store_case_fn = _lambda.Function(
            self,
            "StoreCaseFunction",
            function_name="missionpay-store-case",
            runtime=lambda_runtime,
            handler="lambdas.idp.store_payment_handler.handler",
            code=lambda_code,
            role=idp_role,
            timeout=lambda_timeout,
            environment=common_env,
        )

        # --- Risk Firewall Lambda (KEY DIFFERENTIATOR) ---
        self.risk_firewall_fn = _lambda.Function(
            self,
            "RiskFirewallFunction",
            function_name="missionpay-risk-firewall",
            runtime=lambda_runtime,
            handler="lambdas.validation.risk_firewall.handler",
            code=lambda_code,
            role=firewall_role,
            timeout=lambda_timeout,
            environment=common_env,
        )

        # --- Compliance Assistant Lambda ---
        self.compliance_assistant_fn = _lambda.Function(
            self,
            "ComplianceAssistantFunction",
            function_name="missionpay-compliance-assistant",
            runtime=lambda_runtime,
            handler="lambdas.compliance_assistant.handler.handler",
            code=lambda_code,
            role=firewall_role,
            timeout=Duration.seconds(120),
            environment=common_env,
        )

        # --- Exception Copilot Lambda ---
        self.exception_copilot_fn = _lambda.Function(
            self,
            "ExceptionCopilotFunction",
            function_name="missionpay-exception-copilot",
            runtime=lambda_runtime,
            handler="lambdas.exception_copilot.handler.handler",
            code=lambda_code,
            role=exception_role,
            timeout=Duration.seconds(120),
            environment=common_env,
        )

        # --- Approval Lambdas ---
        self.auto_approve_fn = _lambda.Function(
            self,
            "AutoApproveFunction",
            function_name="missionpay-auto-approve",
            runtime=lambda_runtime,
            handler="lambdas.approval.auto_approve_handler.handler",
            code=lambda_code,
            role=approval_role,
            timeout=lambda_timeout,
            environment={
                **common_env,
                "APPROVAL_SNS_TOPIC_ARN": self.approval_topic.topic_arn,
            },
        )

        self.manager_review_fn = _lambda.Function(
            self,
            "ManagerReviewFunction",
            function_name="missionpay-manager-review",
            runtime=lambda_runtime,
            handler="lambdas.approval.manager_review_handler.handler",
            code=lambda_code,
            role=approval_role,
            timeout=lambda_timeout,
            environment={
                **common_env,
                "APPROVAL_SNS_TOPIC_ARN": self.approval_topic.topic_arn,
            },
        )

        self.director_review_fn = _lambda.Function(
            self,
            "DirectorReviewFunction",
            function_name="missionpay-director-review",
            runtime=lambda_runtime,
            handler="lambdas.approval.director_review_handler.handler",
            code=lambda_code,
            role=approval_role,
            timeout=lambda_timeout,
            environment={
                **common_env,
                "APPROVAL_SNS_TOPIC_ARN": self.approval_topic.topic_arn,
            },
        )

        # --- Disbursement Lambda ---
        self.disbursement_fn = _lambda.Function(
            self,
            "DisbursementFunction",
            function_name="missionpay-disbursement",
            runtime=lambda_runtime,
            handler="lambdas.disbursement.handler.handler",
            code=lambda_code,
            role=disbursement_role,
            timeout=Duration.seconds(30),
            environment=common_env,
        )

        # --- Notifications Lambda ---
        self.notification_fn = _lambda.Function(
            self,
            "NotificationFunction",
            function_name="missionpay-notification",
            runtime=lambda_runtime,
            handler="lambdas.notifications.handler.handler",
            code=lambda_code,
            role=notifications_role,
            timeout=lambda_timeout,
            environment={
                **common_env,
                "NOTIFICATION_TOPIC_ARN": self.notification_topic.topic_arn,
            },
        )

        # --- Case Status API Lambda ---
        self.case_status_fn = _lambda.Function(
            self,
            "CaseStatusFunction",
            function_name="missionpay-case-status",
            runtime=lambda_runtime,
            handler="lambdas.api.payment_status_handler.handler",
            code=lambda_code,
            role=api_status_role,
            timeout=Duration.seconds(10),
            environment=common_env,
        )

        # --- Document Access Lambda ---
        self.document_access_fn = _lambda.Function(
            self,
            "DocumentAccessFunction",
            function_name="missionpay-document-access",
            runtime=lambda_runtime,
            handler="lambdas.api.document_access_handler.handler",
            code=lambda_code,
            role=document_access_role,
            timeout=Duration.seconds(10),
            environment={
                **common_env,
                "RAW_DOCUMENTS_BUCKET": self.documents_bucket.bucket_name,
            },
        )

        # --- List Cases API Lambda ---
        self.list_cases_fn = _lambda.Function(
            self,
            "ListCasesFunction",
            function_name="missionpay-list-cases",
            runtime=lambda_runtime,
            handler="lambdas.api.list_cases_handler.handler",
            code=lambda_code,
            role=list_cases_role,
            timeout=Duration.seconds(10),
            environment=common_env,
        )

        # --- Create Case API Lambda ---
        self.create_case_fn = _lambda.Function(
            self,
            "CreateCaseFunction",
            function_name="missionpay-create-case",
            runtime=lambda_runtime,
            handler="lambdas.api.create_case_handler.handler",
            code=lambda_code,
            role=create_case_role,
            timeout=Duration.seconds(30),
            environment={
                **common_env,
                "RAW_DOCUMENTS_BUCKET": self.documents_bucket.bucket_name,
            },
        )

        # --- Submit Decision API Lambda ---
        self.submit_decision_fn = _lambda.Function(
            self,
            "SubmitDecisionFunction",
            function_name="missionpay-submit-decision",
            runtime=lambda_runtime,
            handler="lambdas.api.submit_decision_handler.handler",
            code=lambda_code,
            role=submit_decision_role,
            timeout=Duration.seconds(10),
            environment=common_env,
        )

        # =============================================
        # Step Functions State Machine - MissionPayGuardWorkflow
        # =============================================

        # --- Task States ---

        # Classify and Extract chain
        textract_task = sfn_tasks.LambdaInvoke(
            self,
            "TextractTask",
            lambda_function=self.textract_fn,
            output_path="$.Payload",
            retry_on_service_exceptions=True,
        )

        comprehend_task = sfn_tasks.LambdaInvoke(
            self,
            "ComprehendTask",
            lambda_function=self.comprehend_fn,
            output_path="$.Payload",
            retry_on_service_exceptions=True,
        )

        bedrock_extraction_task = sfn_tasks.LambdaInvoke(
            self,
            "BedrockExtractionTask",
            lambda_function=self.bedrock_extraction_fn,
            output_path="$.Payload",
            retry_on_service_exceptions=True,
        )

        store_case_task = sfn_tasks.LambdaInvoke(
            self,
            "StoreCaseTask",
            lambda_function=self.store_case_fn,
            output_path="$.Payload",
            retry_on_service_exceptions=True,
        )

        # Exception Copilot (confidence check failure path)
        exception_copilot_task = sfn_tasks.LambdaInvoke(
            self,
            "ExceptionCopilotTask",
            lambda_function=self.exception_copilot_fn,
            output_path="$.Payload",
            retry_on_service_exceptions=True,
        )

        # Risk Firewall
        risk_firewall_task = sfn_tasks.LambdaInvoke(
            self,
            "RiskFirewallTask",
            lambda_function=self.risk_firewall_fn,
            output_path="$.Payload",
            retry_on_service_exceptions=True,
        )

        # AI Explanation
        compliance_assistant_task = sfn_tasks.LambdaInvoke(
            self,
            "ComplianceAssistantTask",
            lambda_function=self.compliance_assistant_fn,
            output_path="$.Payload",
            retry_on_service_exceptions=True,
        )

        # Approval tasks
        auto_approve_task = sfn_tasks.LambdaInvoke(
            self,
            "AutoApproveTask",
            lambda_function=self.auto_approve_fn,
            output_path="$.Payload",
            retry_on_service_exceptions=True,
        )

        manager_review_task = sfn_tasks.LambdaInvoke(
            self,
            "ManagerReviewTask",
            lambda_function=self.manager_review_fn,
            integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
            payload=sfn.TaskInput.from_object({
                "case_id": sfn.JsonPath.string_at("$.case_id"),
                "risk_level": sfn.JsonPath.string_at("$.risk_level"),
                "task_token": sfn.JsonPath.task_token,
            }),
            result_path="$.approval_result",
        )

        finance_hitl_review_task = sfn_tasks.LambdaInvoke(
            self,
            "FinanceHITLReviewTask",
            lambda_function=self.director_review_fn,
            integration_pattern=sfn.IntegrationPattern.WAIT_FOR_TASK_TOKEN,
            payload=sfn.TaskInput.from_object({
                "case_id": sfn.JsonPath.string_at("$.case_id"),
                "risk_level": sfn.JsonPath.string_at("$.risk_level"),
                "firewall_result": sfn.JsonPath.object_at("$.firewall_result"),
                "task_token": sfn.JsonPath.task_token,
            }),
            result_path="$.approval_result",
        )

        # Disbursement simulation
        disbursement_task = sfn_tasks.LambdaInvoke(
            self,
            "DisbursementSimulationTask",
            lambda_function=self.disbursement_fn,
            output_path="$.Payload",
            retry_on_service_exceptions=True,
        )

        # Audit packet / notification
        notify_task = sfn_tasks.LambdaInvoke(
            self,
            "GenerateAuditPacketTask",
            lambda_function=self.notification_fn,
            output_path="$.Payload",
            retry_on_service_exceptions=True,
        )

        # --- Terminal States ---
        rejected_state = sfn.Fail(
            self,
            "Rejected",
            cause="Payment case was rejected during firewall or approval",
            error="CaseRejected",
        )

        success_state = sfn.Succeed(self, "CaseComplete")

        # --- Choice States ---

        # ConfidenceCheck: route to Exception Copilot if confidence < 0.85
        confidence_check = sfn.Choice(self, "ConfidenceCheck")
        confidence_check.when(
            sfn.Condition.number_less_than("$.extraction_confidence", 0.85),
            exception_copilot_task,
        ).otherwise(risk_firewall_task)

        # After Exception Copilot, continue to firewall (human resolved)
        exception_copilot_task.next(risk_firewall_task)

        # After Risk Firewall, generate AI explanation
        risk_firewall_task.next(compliance_assistant_task)

        # After AI Explanation, route approval
        approval_routing = sfn.Choice(self, "ApprovalRouting")
        approval_routing.when(
            sfn.Condition.string_equals(
                "$.firewall_result.routing_recommendation", "standard"
            ),
            auto_approve_task,
        ).when(
            sfn.Condition.string_equals(
                "$.firewall_result.routing_recommendation", "manager"
            ),
            manager_review_task,
        ).when(
            sfn.Condition.string_equals(
                "$.firewall_result.routing_recommendation", "finance_compliance_hitl"
            ),
            finance_hitl_review_task,
        ).otherwise(manager_review_task)

        compliance_assistant_task.next(approval_routing)

        # After approval → disbursement simulation
        auto_approve_task.next(disbursement_task)
        manager_review_task.next(disbursement_task)
        finance_hitl_review_task.next(disbursement_task)

        # After disbursement → audit packet → complete
        disbursement_task.next(notify_task)
        notify_task.next(success_state)

        # --- Build the extraction chain ---
        extract_chain = (
            textract_task
            .next(comprehend_task)
            .next(bedrock_extraction_task)
            .next(store_case_task)
            .next(confidence_check)
        )

        # --- State Machine ---
        self.state_machine = sfn.StateMachine(
            self,
            "MissionPayGuardWorkflow",
            state_machine_name="MissionPayGuardWorkflow",
            definition_body=sfn.DefinitionBody.from_chainable(extract_chain),
            timeout=Duration.hours(24),
        )

        # Grant S3 trigger role permission to start the state machine
        s3_trigger_role = iam.Role(
            self,
            "S3TriggerLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            description="Role for S3 event trigger Lambda",
        )
        s3_trigger_role.add_to_policy(logs_policy)
        s3_trigger_role.add_to_policy(iam.PolicyStatement(
            actions=["s3:GetObject", "s3:HeadObject"],
            resources=[self.documents_bucket.arn_for_objects("*")],
        ))
        s3_trigger_role.add_to_policy(iam.PolicyStatement(
            actions=["states:StartExecution"],
            resources=[self.state_machine.state_machine_arn],
        ))

        # --- S3 Trigger Lambda Function ---
        self.s3_trigger_fn = _lambda.Function(
            self,
            "S3TriggerFunction",
            function_name="missionpay-s3-trigger",
            runtime=lambda_runtime,
            handler="lambdas.s3_trigger.handler.handler",
            code=lambda_code,
            role=s3_trigger_role,
            timeout=Duration.seconds(30),
            environment={
                "STATE_MACHINE_ARN": self.state_machine.state_machine_arn,
            },
        )

        # Wire S3 event notification to trigger Lambda on object creation in quarantine/
        self.documents_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.s3_trigger_fn),
            s3.NotificationKeyFilter(prefix="quarantine/"),
        )

        # =============================================
        # API Gateway
        # =============================================

        self.api = apigateway.RestApi(
            self,
            "MissionPayGuardApi",
            rest_api_name="MissionPay Guard API",
            description="API for MissionPay Guard payment processing platform",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )

        # /cases
        cases_resource = self.api.root.add_resource("cases")

        # GET /cases — list all cases
        cases_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self.list_cases_fn),
        )

        # POST /cases — create new case
        cases_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(self.create_case_fn),
        )

        # /cases/{id}
        case_id_resource = cases_resource.add_resource("{id}")

        # /cases/{id}/status
        status_resource = case_id_resource.add_resource("status")
        status_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self.case_status_fn),
        )

        # /cases/{id}/documents
        docs_resource = case_id_resource.add_resource("documents")
        docs_resource.add_method(
            "GET",
            apigateway.LambdaIntegration(self.document_access_fn),
        )

        # /cases/{id}/decision
        decision_resource = case_id_resource.add_resource("decision")
        decision_resource.add_method(
            "POST",
            apigateway.LambdaIntegration(self.submit_decision_fn),
        )
