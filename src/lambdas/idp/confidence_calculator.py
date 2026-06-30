"""
Confidence score calculation for IDP extraction results.

Combines Textract confidence, field completeness, and entity match rate
with configurable weights to produce a single confidence score in [0.0, 1.0].

This is a utility module, not a Lambda handler.
"""

# Confidence score weights
TEXTRACT_WEIGHT = 0.4
FIELD_COMPLETENESS_WEIGHT = 0.35
ENTITY_MATCH_WEIGHT = 0.25

# Required fields for payment processing
REQUIRED_FIELDS = ["payee_name", "amount", "currency", "payment_type", "payee_account"]
TOTAL_REQUIRED_FIELDS = len(REQUIRED_FIELDS)


def calculate_confidence(
    textract_confidence: float,
    structured_data: dict,
    entities: list[dict],
) -> float:
    """Calculate overall confidence score for an extraction.

    Combines three weighted factors:
    - Textract confidence (weight 0.4): Average OCR confidence from Textract
    - Field completeness (weight 0.35): Ratio of populated required fields
    - Entity match rate (weight 0.25): Ratio of entities matching extracted fields

    Args:
        textract_confidence: Average confidence from Textract (0.0 to 1.0).
        structured_data: Dict of extracted payment fields.
        entities: List of entity dicts with {type, text, score} from Comprehend.

    Returns:
        Combined confidence score clamped to [0.0, 1.0].
    """
    field_completeness = _calculate_field_completeness(structured_data)
    entity_match_rate = _calculate_entity_match_rate(structured_data, entities)

    confidence = (
        textract_confidence * TEXTRACT_WEIGHT
        + field_completeness * FIELD_COMPLETENESS_WEIGHT
        + entity_match_rate * ENTITY_MATCH_WEIGHT
    )

    # Clamp to [0.0, 1.0]
    return max(0.0, min(1.0, confidence))


def _calculate_field_completeness(structured_data: dict) -> float:
    """Calculate the ratio of populated required fields.

    Args:
        structured_data: Dict of extracted payment fields.

    Returns:
        Ratio between 0.0 and 1.0 representing how many required fields
        are populated.
    """
    if not structured_data:
        return 0.0

    populated_count = 0
    for field_name in REQUIRED_FIELDS:
        value = structured_data.get(field_name)
        if value is not None and value != "" and value != 0 and value != 0.0:
            populated_count += 1

    return populated_count / TOTAL_REQUIRED_FIELDS


def _calculate_entity_match_rate(structured_data: dict, entities: list[dict]) -> float:
    """Calculate the ratio of entities that match extracted fields.

    Checks if entity text values can be found in the extracted structured data,
    indicating agreement between NLP entity extraction and the final result.

    Args:
        structured_data: Dict of extracted payment fields.
        entities: List of entity dicts with {type, text, score}.

    Returns:
        Ratio between 0.0 and 1.0 representing how many entities have
        matching values in the extracted fields.
    """
    if not entities:
        return 0.0

    # Build a set of extracted values (lowercased) for matching
    extracted_values = set()
    for key, value in structured_data.items():
        if value is not None and isinstance(value, str) and value.strip():
            extracted_values.add(value.lower().strip())
        elif value is not None and isinstance(value, (int, float)):
            extracted_values.add(str(value))

    matched_count = 0
    for entity in entities:
        entity_text = entity.get("text", "").lower().strip()
        if not entity_text:
            continue

        # Check if entity text appears in any extracted value
        for extracted_val in extracted_values:
            if entity_text in extracted_val or extracted_val in entity_text:
                matched_count += 1
                break

    return matched_count / len(entities)
