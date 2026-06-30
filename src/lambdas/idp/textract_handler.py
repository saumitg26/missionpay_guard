"""
Textract Lambda handler for Intelligent Document Processing.

Receives {document_id, s3_bucket, s3_key} from Step Functions,
calls Amazon Textract AnalyzeDocument API with FORMS and TABLES features,
and parses the response into raw_text, form_fields, and tables.
"""

import logging
from typing import Any

import boto3

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def get_textract_client():
    """Return a boto3 Textract client."""
    return boto3.client("textract")


def extract_raw_text(blocks: list[dict]) -> str:
    """Concatenate all LINE block text into raw text.

    Args:
        blocks: List of Textract Block objects.

    Returns:
        Concatenated text from all LINE blocks.
    """
    lines = []
    for block in blocks:
        if block.get("BlockType") == "LINE":
            text = block.get("Text", "")
            if text:
                lines.append(text)
    return "\n".join(lines)


def extract_form_fields(blocks: list[dict]) -> list[dict]:
    """Extract key-value pairs from KEY_VALUE_SET blocks.

    Args:
        blocks: List of Textract Block objects.

    Returns:
        List of dicts with {key, value, confidence} for each form field.
    """
    # Build a map of block IDs for lookup
    block_map = {block["Id"]: block for block in blocks}

    # Find KEY blocks and their VALUE relationships
    key_blocks = []
    for block in blocks:
        if block.get("BlockType") == "KEY_VALUE_SET" and "KEY" in block.get("EntityTypes", []):
            key_blocks.append(block)

    form_fields = []
    for key_block in key_blocks:
        key_text = _get_text_from_relationships(key_block, block_map, "CHILD")
        value_text = ""
        value_confidence = key_block.get("Confidence", 0.0)

        # Find the VALUE block via VALUE relationship
        for relationship in key_block.get("Relationships", []):
            if relationship.get("Type") == "VALUE":
                for value_id in relationship.get("Ids", []):
                    value_block = block_map.get(value_id, {})
                    value_text = _get_text_from_relationships(value_block, block_map, "CHILD")
                    value_confidence = (key_block.get("Confidence", 0.0) + value_block.get("Confidence", 0.0)) / 2

        if key_text:
            form_fields.append({
                "key": key_text,
                "value": value_text,
                "confidence": value_confidence,
            })

    return form_fields


def _get_text_from_relationships(block: dict, block_map: dict, relationship_type: str) -> str:
    """Extract text from a block's child relationships (WORD/SELECTION_ELEMENT blocks).

    Args:
        block: The parent block.
        block_map: Map of block IDs to block objects.
        relationship_type: The relationship type to follow (e.g., CHILD).

    Returns:
        Concatenated text from child blocks.
    """
    words = []
    for relationship in block.get("Relationships", []):
        if relationship.get("Type") == relationship_type:
            for child_id in relationship.get("Ids", []):
                child_block = block_map.get(child_id, {})
                if child_block.get("BlockType") == "WORD":
                    words.append(child_block.get("Text", ""))
                elif child_block.get("BlockType") == "SELECTION_ELEMENT":
                    if child_block.get("SelectionStatus") == "SELECTED":
                        words.append("[SELECTED]")
    return " ".join(words)


def extract_tables(blocks: list[dict]) -> list[list[list[str]]]:
    """Extract table data from TABLE and CELL blocks.

    Args:
        blocks: List of Textract Block objects.

    Returns:
        List of tables, where each table is a list of rows,
        and each row is a list of cell text values.
    """
    block_map = {block["Id"]: block for block in blocks}

    tables = []
    for block in blocks:
        if block.get("BlockType") == "TABLE":
            table = _extract_single_table(block, block_map)
            if table:
                tables.append(table)

    return tables


def _extract_single_table(table_block: dict, block_map: dict) -> list[list[str]]:
    """Extract a single table from a TABLE block.

    Args:
        table_block: A TABLE block from Textract.
        block_map: Map of block IDs to block objects.

    Returns:
        A list of rows, where each row is a list of cell text values.
    """
    rows: dict[int, dict[int, str]] = {}

    for relationship in table_block.get("Relationships", []):
        if relationship.get("Type") == "CHILD":
            for cell_id in relationship.get("Ids", []):
                cell_block = block_map.get(cell_id, {})
                if cell_block.get("BlockType") == "CELL":
                    row_index = cell_block.get("RowIndex", 1)
                    col_index = cell_block.get("ColumnIndex", 1)
                    cell_text = _get_text_from_relationships(cell_block, block_map, "CHILD")
                    if row_index not in rows:
                        rows[row_index] = {}
                    rows[row_index][col_index] = cell_text

    # Convert to list of lists, sorted by row and column index
    result = []
    for row_idx in sorted(rows.keys()):
        row_data = rows[row_idx]
        row = [row_data.get(col_idx, "") for col_idx in sorted(row_data.keys())]
        result.append(row)

    return result


def calculate_textract_confidence(blocks: list[dict]) -> float:
    """Calculate the average confidence score across all blocks.

    Args:
        blocks: List of Textract Block objects.

    Returns:
        Average confidence as a float between 0.0 and 1.0.
        Returns 0.0 if no blocks have confidence values.
    """
    confidences = [
        block["Confidence"] / 100.0
        for block in blocks
        if "Confidence" in block
    ]
    if not confidences:
        return 0.0
    return sum(confidences) / len(confidences)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """Lambda handler for Textract document analysis.

    Args:
        event: Step Functions input with {document_id, s3_bucket, s3_key}.
        context: Lambda context (unused).

    Returns:
        Dict with {document_id, raw_text, form_fields, tables, textract_confidence}.
    """
    document_id = event["document_id"]
    s3_bucket = event["s3_bucket"]
    s3_key = event["s3_key"]

    logger.info("Processing document %s from s3://%s/%s", document_id, s3_bucket, s3_key)

    client = get_textract_client()

    response = client.analyze_document(
        Document={"S3Object": {"Bucket": s3_bucket, "Name": s3_key}},
        FeatureTypes=["FORMS", "TABLES"],
    )

    blocks = response.get("Blocks", [])

    raw_text = extract_raw_text(blocks)
    form_fields = extract_form_fields(blocks)
    tables = extract_tables(blocks)
    textract_confidence = calculate_textract_confidence(blocks)

    logger.info(
        "Textract extraction complete for %s: %d chars, %d form fields, %d tables, confidence=%.3f",
        document_id,
        len(raw_text),
        len(form_fields),
        len(tables),
        textract_confidence,
    )

    return {
        "document_id": document_id,
        "raw_text": raw_text,
        "form_fields": form_fields,
        "tables": tables,
        "textract_confidence": textract_confidence,
    }
