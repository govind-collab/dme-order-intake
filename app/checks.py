"""Plausibility checks for the five order fields.

Owns the name, date-of-birth and NPI rules shared by manual orders and uploads. Each check returns a
reason when the value fails and None when it passes, so callers can say why a value was refused
without echoing the value.
"""

import re
import unicodedata
from datetime import date

MAX_AGE_YEARS = 130
# Scans turn ' into curly quotes, - into other dashes and spaces into no-break spaces
NAME_PUNCTUATION = frozenset("  '‘’-‐‑‒–—.,")
# Only phrases that are never a name. Single words that are also real surnames (Null, Na,
# None, Doctor) are deliberately left out.
LABEL_PHRASES = frozenset(
    {
        "n a",
        "not provided",
        "not available",
        "not applicable",
        "not given",
        "none given",
        "see above",
        "same as above",
        "name",
        "patient name",
        "first name",
        "last name",
        "provider name",
        "physician name",
    }
)
PLACEHOLDER_WORDS = frozenset({"unknown", "illegible", "tbd", "dob"})


def name_problem(name: str) -> str | None:
    """Return why a name is not a plausible person's name, or None if it is.

    Letters from any alphabet are allowed with their combining accents, plus spaces, hyphens and
    dashes, periods, commas and straight or curly apostrophes. Labels such as "Not provided",
    "N.A." or "Patient Name", and names made only of words like "unknown", are refused.
    """
    if not any(char.isalpha() for char in name):
        return "name has no letters"
    if not all(
        char.isalpha() or char in NAME_PUNCTUATION or unicodedata.category(char).startswith("M")
        for char in name
    ):
        return (
            "name may only contain letters, accents, spaces, hyphens, apostrophes, periods "
            "and commas"
        )
    words = re.sub(r"[\W_]+", " ", name.lower()).split()
    if " ".join(words) in LABEL_PHRASES or set(words) <= PLACEHOLDER_WORDS:
        return "name is a label or placeholder, not a name"
    return None


def dob_problem(dob: date, today: date) -> str | None:
    """Return why a date of birth is implausible on `today`, or None if it is plausible.

    A date after `today` or more than 130 years before it is refused. `today` is passed in so
    the rule can be tested on fixed dates.
    """
    if dob > today:
        return "date of birth is in the future"
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age > MAX_AGE_YEARS:
        return f"date of birth is more than {MAX_AGE_YEARS} years ago"
    return None


def npi_problem(npi: str) -> str | None:
    """Return why an NPI is not valid, or None if it is.

    A valid NPI is ten ASCII digits starting with 1 or 2 whose last digit is the Luhn check
    digit computed with the 80840 prefix. Only the first failing rule is reported.
    """
    if not re.fullmatch(r"[0-9]{10}", npi):
        return "NPI must be exactly 10 digits"
    if npi[0] not in "12":
        return "NPI must start with 1 or 2"
    # Luhn check over the NPI prefixed with 80840; that prefix always contributes 24
    total = 24
    for position, digit in enumerate(reversed(npi[:9])):
        value = int(digit) * 2 if position % 2 == 0 else int(digit)
        total += value - 9 if value > 9 else value
    if (10 - total % 10) % 10 != int(npi[9]):
        return "NPI fails the check digit"
    return None
