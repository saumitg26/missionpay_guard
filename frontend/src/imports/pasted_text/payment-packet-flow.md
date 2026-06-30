Overall flow
The system takes a federal payment packet from intake to simulated disbursement decision:
Secure document intake
→ payment case created
→ documents stored in encrypted S3
→ Step Functions starts the payment workflow
→ Textract extracts and structures messy document data
→ payment packet conversion engine normalizes the data
→ DynamoDB stores the structured payment case
→ rules engine validates the case
→ risk engine scores and routes the case
→ Bedrock payment operations assistant explains issues and guides reviewers
→ humans review high-risk or low-confidence cases
→ approval workflow completes
→ payment is simulated
→ audit evidence and status history are generated
The important idea is:
Raw documents live in S3. Structured payment case data lives in DynamoDB. Step Functions controls the workflow. Textract converts messy documents into usable data. The rules engine handles validation and risk. Bedrock helps users understand and resolve issues, but humans approve risky decisions. Payment execution is simulated for the prototype.
Secure Document Intake
The user starts by submitting payment documents through a portal, email intake, fax adapter, or agency API.
For the hackathon MVP, the main path is:
User logs in
→ creates or selects a payment case
→ uploads a payment packet
→ backend creates a paymentCaseId
→ documents are stored in an encrypted S3 intake vault
→ case metadata is created in DynamoDB
This is where invoices, purchase orders, contract references, vendor forms, banking information, and justification documents enter the system.
The key security point is that users do not directly access the document store. They upload through a controlled backend layer, and the documents are stored privately in S3 with encryption and access controls.
Payment Case Orchestration
Once the payment case is created and documents are uploaded, the main workflow begins.
This is handled by:
S3 / API trigger → AWS Step Functions
Step Functions controls the full payment process:
ingest
→ classify
→ extract
→ normalize
→ validate
→ score risk
→ generate explanation
→ route approval
→ wait for human review if needed
→ simulate payment
→ generate audit record
This is important because payment processing needs a controlled and auditable sequence. Step Functions makes the process easier to trace, test, and explain to judges.
Intelligent Document Processing
The uploaded documents go through intelligent document processing.
This layer uses Amazon Textract to extract text, tables, forms, handwriting, key fields, and confidence scores from uploaded documents.
Textract extracts fields such as:
vendor name
invoice number
invoice amount
purchase order number
contract ID
payment date
banking information
line items
supporting document references
confidence scores
The system also classifies the document type, such as invoice, purchase order, contract support, vendor form, payment form, or justification memo.
The result is structured payment data that can be reviewed, validated, and stored.
Payment Packet Conversion Engine
This is one of the main differentiators.
Most basic demos stop at:
OCR → AI summary → approval workflow
MissionPay Guard adds a payment packet conversion layer.
This layer turns messy federal payment documentation into a clean, structured payment case. It maps extracted fields from different documents into one payment record, identifies missing or conflicting information, and prepares the case for validation and electronic processing.
The system does not claim to replace Treasury payment controls. Instead, it improves the agency-side preparation process before payment submission.
It helps answer:
Can we turn this messy payment packet into a complete, reviewable, audit-ready case?
This layer checks:
What documents were submitted?
Which document is the invoice?
Which document is the purchase order?
Which fields were extracted with high confidence?
Which fields need human confirmation?
Is the payment packet missing support?
Are the extracted values consistent across documents?
Is the case ready for validation and approval routing?
This makes the app more than OCR. It becomes a payment preparation and readiness system.
Validation and Risk Scoring
After the payment packet is converted into structured data, the rules engine validates the case.
The rules engine checks things like:
Does the invoice number exist?
Does the invoice match the purchase order?
Does the vendor match the payment record?
Is the invoice amount within the allowed amount?
Is the contract ID present when required?
Is the invoice number a possible duplicate?
Did banking information change?
Are critical fields below the confidence threshold?
Are required supporting documents missing?
Is the case urgent or routine?
Then the risk engine calculates the risk level and recommended route.
The key point is that validation is deterministic. The AI does not approve or reject the payment. The rules engine decides whether the case is low, medium, or high risk.
Bedrock Payment Operations Assistant
Amazon Bedrock is used as a trained payment operations assistant.
Its job is not to blindly approve payments. Its job is to help users understand the case and move faster, especially if they are new to the job or unfamiliar with the payment process.
The assistant can:
Explain why a payment is risky
Explain which rule failed
Explain what evidence is missing
Guide the reviewer on the next step
Draft a message requesting missing documents
Summarize the case for an approver
Create an audit-friendly explanation
Answer workflow questions from the reviewer
Example:
“This case is high risk because the invoice amount has low extraction confidence, the contract ID is missing, and the vendor banking information changed. A finance reviewer should confirm the invoice amount, and a compliance reviewer should verify the banking change before payment simulation.”
This gives the app a strong AI feature without making it unsafe. The AI helps people understand and resolve issues, while the system keeps approval decisions controlled.
Exception Resolution
If something goes wrong, the system does not secretly fix the payment.
Instead:
Exception detected
→ Bedrock explains the issue
→ reviewer opens the source document
→ reviewer confirms or corrects the extracted field
→ workflow revalidates the case
→ correction is saved to the audit trail
Example:
Textract reads an invoice amount as $80,000, but the confidence score is low. The system flags the field, shows the reviewer the document preview, and asks the reviewer to confirm or correct the value.
The key line is:
AI explains. Human confirms. The audit trail records everything.
This makes the system safer and more realistic for government payment processing.
Approval Workflow
Approval is based on risk, not just payment amount.
The system routes cases like this:
Low risk → standard approval
Medium risk → finance review
High risk → finance review + compliance review + final approver
Risk is calculated using multiple factors:
payment amount
extraction confidence
missing documents
validation failures
vendor mismatch
duplicate invoice warning
banking information change
mission urgency
human corrections
This means two payments with the same dollar amount can route differently.
Example:
A $9,000 invoice from a known vendor with complete documents and high confidence can go through standard approval.
A $9,000 invoice with changed banking information and low-confidence extraction can be escalated to compliance review.
That is a strong demo moment because it shows the app is not using a simple amount-only workflow.
Payment Simulation
After the case passes validation and approval, the system simulates payment execution.
For the hackathon prototype, MissionPay Guard should not claim real Treasury payment integration.
The correct explanation is:
“For the prototype, payment execution is simulated through a sandbox payment trigger. In production, this layer would integrate with approved federal payment systems.”
The simulated payment step should generate:
simulated disbursement ID
payment status
payment timestamp
approval record
audit event
This lets the app demonstrate the full payment process without pretending to move real government funds.
Case Storage and Audit Evidence
The system uses both DynamoDB and S3, but for different purposes.
DynamoDB stores structured payment case data:
payment case ID
vendor name
invoice number
invoice amount
purchase order number
contract ID
risk score
risk level
validation results
workflow status
approval status
reviewer actions
audit timeline metadata
S3 stores documents and evidence:
raw uploaded documents
Textract output JSON
document previews
audit packet
evidence bundle
The correct architecture explanation is:
“We do not store raw documents in DynamoDB. DynamoDB stores structured payment case data and pointers to secure S3 evidence objects.”
The audit trail should show every major action:
case created
document uploaded
fields extracted
validation completed
risk score generated
AI explanation generated
human correction made
approval action taken
payment simulated
audit packet generated
Secure Dashboard
The dashboard is where users manage and review the payment case.
It should show:
payment status
uploaded documents
extracted fields
confidence scores
validation results
risk score
approval route
AI explanation
human review actions
audit timeline
document preview
simulated payment result
The dashboard should not expose public S3 links.
The safer pattern is:
Dashboard requests document preview
→ backend checks user role
→ backend generates temporary access
→ user views only authorized files
This supports the security story and makes the app feel more production-ready.
Current Differentiator
The current differentiator is not that MissionPay Guard replaces Treasury payment systems. The differentiator is that it makes the agency-side payment process faster, clearer, and easier to operate before final disbursement.
MissionPay Guard combines three things:
messy payment document conversion
trained payment operations assistance
risk-aware human review and audit tracking
It is a full payment processing prototype, but the unique value is that it helps agencies convert scattered payment documents into structured cases, helps new or busy staff understand what to do, explains why a payment is risky, and creates a clean audit trail from intake to simulated disbursement.
The simplest explanation is:
MissionPay Guard is an AWS-powered payment processing system with an AI payment operations assistant that converts messy payment packets into structured cases, explains risk, guides reviewers, routes approvals, simulates payment, and generates audit-ready evidence.

