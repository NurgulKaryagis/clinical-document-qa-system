from unittest.mock import patch

from presidio_analyzer import RecognizerResult

from app.validation.query_validator import QueryValidationResult, validate_query


def mock_results(*entities):
    return [
        RecognizerResult(entity_type, start, end, score)
        for entity_type, start, end, score in entities
    ]


# --- Scenario 1: no entities detected at all ---

def test_no_entities_is_valid():
    with patch("app.validation.query_validator.analyzer.analyze", return_value=mock_results()):
        result = validate_query("List contraindications for lisinopril.")

    assert result == QueryValidationResult(is_valid=True)


# --- Scenario 2: a non-PERSON entity alone does not trigger rejection ---

def test_non_person_entity_is_valid():
    query = "On Monday, check the dosage."
    with patch(
        "app.validation.query_validator.analyzer.analyze",
        return_value=mock_results(("DATE_TIME", 3, 9, 0.85)),
    ):
        result = validate_query(query)

    assert result == QueryValidationResult(is_valid=True)


# --- Scenario 3: a real PERSON entity is rejected ---

def test_person_entity_is_rejected():
    query = "Is it safe for John Smith?"
    with patch(
        "app.validation.query_validator.analyzer.analyze",
        return_value=mock_results(("PERSON", 15, 25, 0.85)),
    ):
        result = validate_query(query)

    assert result.is_valid is False
    assert result.rejection_message is not None


# --- Scenario 4: an allowlisted term flagged as PERSON is still valid ---

def test_allowlisted_person_entity_is_valid():
    query = "Is Xarelto safe with grapefruit juice?"
    with patch(
        "app.validation.query_validator.analyzer.analyze",
        return_value=mock_results(("PERSON", 3, 10, 0.85)),
    ):
        result = validate_query(query)

    assert result == QueryValidationResult(is_valid=True)


def test_allowlist_match_is_case_insensitive():
    query = "Is XARELTO safe with grapefruit juice?"
    with patch(
        "app.validation.query_validator.analyzer.analyze",
        return_value=mock_results(("PERSON", 3, 10, 0.85)),
    ):
        result = validate_query(query)

    assert result == QueryValidationResult(is_valid=True)


# --- Scenario 5: entity order must not matter (regression for the original loop bug) ---

def test_person_after_non_person_entity_is_still_rejected():
    query = "On Monday, John Smith asked about metformin dosage."
    with patch(
        "app.validation.query_validator.analyzer.analyze",
        return_value=mock_results(
            ("DATE_TIME", 3, 9, 0.85),
            ("PERSON", 11, 21, 0.85),
        ),
    ):
        result = validate_query(query)

    assert result.is_valid is False


def test_person_after_allowlisted_person_is_still_rejected():
    query = "Xarelto was prescribed instead of what John Smith takes."
    with patch(
        "app.validation.query_validator.analyzer.analyze",
        return_value=mock_results(
            ("PERSON", 0, 7, 0.85),
            ("PERSON", 39, 49, 0.85),
        ),
    ):
        result = validate_query(query)

    assert result.is_valid is False
