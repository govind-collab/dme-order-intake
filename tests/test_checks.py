"""Tests for the name, date-of-birth and NPI checks.

Owns the edge cases of each rule: check digits, leading digits, non-ASCII digits, the 130-year
boundary, curly apostrophes and placeholders.
"""

from datetime import date

import pytest

from app.checks import dob_problem, name_problem, npi_problem

TODAY = date(2026, 11, 10)


@pytest.mark.parametrize("npi", ["1234567893", "2000000002"])
def test_valid_npis_pass(npi: str) -> None:
    """Expect NPIs with a correct check digit to pass."""
    assert npi_problem(npi) is None


@pytest.mark.parametrize(
    ("npi", "reason"),
    [
        ("1234567890", "check digit"),
        ("3234567893", "start with 1 or 2"),
        ("123456789", "10 digits"),
        ("12345678931", "10 digits"),
        ("12345abcde", "10 digits"),
        ("１２３４５６７８９３", "10 digits"),
    ],
)
def test_invalid_npis_are_rejected_with_reason(npi: str, reason: str) -> None:
    """Expect each malformed NPI to fail with the matching reason."""
    problem = npi_problem(npi)

    assert problem is not None and reason in problem


@pytest.mark.parametrize("dob", [TODAY, date(1980, 2, 29), date(1895, 11, 11)])
def test_plausible_dates_of_birth_pass(dob: date) -> None:
    """Expect today, a leap day and exactly 130 years ago to pass."""
    assert dob_problem(dob, TODAY) is None


@pytest.mark.parametrize(
    ("dob", "reason"),
    [(date(2026, 11, 11), "future"), (date(1895, 11, 10), "more than 130 years")],
)
def test_implausible_dates_of_birth_are_rejected(dob: date, reason: str) -> None:
    """Expect tomorrow and 131 years ago to fail with the matching reason."""
    problem = dob_problem(dob, TODAY)

    assert problem is not None and reason in problem


@pytest.mark.parametrize(
    "name", ["Ada", "O'Brien-Smith", "O’Brien", "D‘Angelo", "Mary Ann", "José", "Raj, Arjun D.P.M."]
)
def test_real_names_pass(name: str) -> None:
    """Expect names with apostrophes, hyphens, accents and commas to pass."""
    assert name_problem(name) is None


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        ("Ada2", "only contain letters"),
        ("N/A", "only contain letters"),
        ("...", "no letters"),
        ("Unknown", "placeholder"),
        ("patient.", "placeholder"),
    ],
)
def test_non_names_are_rejected(name: str, reason: str) -> None:
    """Expect digits, slashes, punctuation only and placeholders to fail."""
    problem = name_problem(name)

    assert problem is not None and reason in problem
