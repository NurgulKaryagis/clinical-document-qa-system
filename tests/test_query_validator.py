from unittest.mock import patch

import pytest
from presidio_analyzer import RecognizerResult

from app.validation.query_validator import (
    QueryValidationResult,
    dob_recognizer,
    mrn_recognizer,
    validate_query,
)


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


# --- Scenario 6: identifier entities are rejected, at any score (ADR-003 revision) ---

@pytest.mark.parametrize("entity_type", ["US_SSN", "UK_NHS", "US_PASSPORT", "US_ITIN", "MRN", "DATE_OF_BIRTH"])
def test_identifier_entity_is_rejected(entity_type):
    query = "Patient identifier 943 476 5919 on apixaban, renal dosing?"
    with patch(
        "app.validation.query_validator.analyzer.analyze",
        return_value=mock_results((entity_type, 19, 31, 0.05)),
    ):
        result = validate_query(query)

    assert result.is_valid is False


def test_allowlist_does_not_suppress_identifier():
    query = "Xarelto dosing?"
    with patch(
        "app.validation.query_validator.analyzer.analyze",
        return_value=mock_results(("MRN", 0, 7, 0.9)),
    ):
        result = validate_query(query)

    assert result.is_valid is False


# --- Scenario 7: custom recognizers need a context word; bare numbers/dates pass ---

@pytest.mark.parametrize("text", [
    "Dosing for patient MRN 00482913?",
    "medical record number: A-482913, warfarin dose?",
    "record no. 4829137 metformin",
])
def test_mrn_recognizer_matches_with_context(text):
    assert mrn_recognizer.analyze(text, entities=["MRN"])


@pytest.mark.parametrize("text", [
    "Lot 00482913 of amoxicillin was recalled?",
    "Max dose of metformin is 2550 mg?",
])
def test_mrn_recognizer_ignores_bare_numbers(text):
    assert not mrn_recognizer.analyze(text, entities=["MRN"])


@pytest.mark.parametrize("text", [
    "Patient born 03/14/1958, max metformin dose?",
    "DOB: 1958-03-14, renal dosing for apixaban?",
    "date of birth March 14, 1958 on warfarin",
    "born on 14 March 1958",
])
def test_dob_recognizer_matches_with_context(text):
    assert dob_recognizer.analyze(text, entities=["DATE_OF_BIRTH"])


@pytest.mark.parametrize("text", [
    "Take amoxicillin for 7 days or 10 days?",
    "Guideline updated 03/14/2024, what changed?",
])
def test_dob_recognizer_ignores_dates_without_context(text):
    assert not dob_recognizer.analyze(text, entities=["DATE_OF_BIRTH"])
