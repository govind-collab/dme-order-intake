import re
from datetime import date

MAX_AGE_YEARS = 130
NAME_PUNCTUATION = frozenset(" '-.,")
PLACEHOLDER_NAMES = frozenset(
    {"unknown", "none", "null", "na", "tbd", "name", "patient", "provider", "physician", "doctor"}
)


def name_problem(name: str) -> str | None:
    if not any(char.isalpha() for char in name):
        return "name has no letters"
    if not all(char.isalpha() or char in NAME_PUNCTUATION for char in name):
        return "name may only contain letters, spaces, hyphens, apostrophes, periods and commas"
    if name.lower().strip(" .") in PLACEHOLDER_NAMES:
        return "name is a placeholder, not a name"
    return None


def dob_problem(dob: date, today: date) -> str | None:
    if dob > today:
        return "date of birth is in the future"
    age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
    if age > MAX_AGE_YEARS:
        return f"date of birth is more than {MAX_AGE_YEARS} years ago"
    return None


def npi_problem(npi: str) -> str | None:
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
