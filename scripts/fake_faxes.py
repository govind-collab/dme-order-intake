"""Draw three made-up faxed DME orders as image-only PDFs and read them with the real extractor.

Owns the fake fax pages and a one-off check that the extractor reports a missing NPI, a
two-digit year and conflicting dates of birth instead of guessing. Every person, address and
phone number is made up, and the NPI is the example number from the CMS documentation. The
PDFs are written to scripts/out/, which git ignores. Run from the repo root with
`python -m scripts.fake_faxes`; it makes three paid Claude API calls.
"""

import random
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.extractor import extract_with_claude
from app.services.intake import review_field

OUT_DIR = Path(__file__).parent / "out"
PAGE_SIZE = (1700, 2200)  # US letter at 200 dpi, a common fax resolution
BODY_FONT = ImageFont.load_default(size=36)
HEADER_FONT = ImageFont.load_default(size=26)

FAXES: dict[str, list[list[str]]] = {
    "no_npi": [
        [
            "FAX COVER SHEET",
            "",
            "To:      Northgate Medical Supply",
            "Fax:     555-0190",
            "From:    Willowbrook Family Practice",
            "Phone:   555-0147",
            "Pages:   2 including this cover",
            "Re:      New CPAP order",
            "",
            "CONFIDENTIAL. This fax is meant only for the recipient named",
            "above. If you received it in error, call us and destroy it.",
        ],
        [
            "WILLOWBROOK FAMILY PRACTICE",
            "STANDARD WRITTEN ORDER - DURABLE MEDICAL EQUIPMENT",
            "",
            "Patient name:    Tobias Fennimore",
            "Date of birth:   09/17/1971",
            "Address:         88 Larkspur Court, Fairview, OH 45000",
            "",
            "Item:   E0601  CPAP device",
            "Item:   A7030  Full face mask, 1 per 3 months",
            "Diagnosis:  G47.33  Obstructive sleep apnea",
            "Length of need:  99 months",
            "",
            "Ordering physician:  Dr. Miriam Castellanos, MD",
            "Phone: 555-0147        Fax: 555-0148",
            "",
            "Signature:  M. Castellanos               Date: 11/02/2026",
        ],
    ],
    "two_digit_year": [
        [
            "LAKESIDE PULMONARY ASSOCIATES",
            "DME PRESCRIPTION",
            "",
            "Patient:   Delphine Okonkwo-Marsh",
            "DOB:       03/14/62",
            "MRN:       LPA-20417",
            "",
            "Equipment:  E1390  Oxygen concentrator, 2 L/min continuous",
            "Diagnosis:  J44.9  COPD",
            "",
            "Prescriber:  Samuel Achterberg, DO",
            "NPI:         1234567893",
            "",
            "Signature:  S. Achterberg               Date: 11/01/2026",
        ],
    ],
    "conflicting_dob": [
        [
            "RIVERBEND SLEEP CENTER",
            "ORDER FOR DURABLE MEDICAL EQUIPMENT",
            "",
            "Patient:        Rosalind Thackeray",
            "Date of birth:  07/22/1958",
            "",
            "Item:   E0601  CPAP device with heated humidifier",
            "Diagnosis:  G47.33  Obstructive sleep apnea",
            "",
            "Ordering provider:  Dr. Kwame Adjei, MD",
            "NPI:  1234567893",
            "",
            "Signature:  K. Adjei                    Date: 10/30/2026",
        ],
        [
            "RIVERBEND SLEEP CENTER - PROGRESS NOTE",
            "",
            "Patient:  Rosalind Thackeray        DOB:  07/22/1985",
            "Visit date:  10/28/2026",
            "Referring physician:  Dr. Helen Moriarty",
            "",
            "Follow-up for obstructive sleep apnea. Home sleep test",
            "showed AHI of 31. Patient agrees to start CPAP therapy.",
            "Fitted for a nasal pillow mask in clinic today.",
            "",
            "Electronically signed by Dr. Kwame Adjei, MD",
        ],
    ],
}


def draw_page(lines: list[str], header: str, rng: random.Random) -> Image.Image:
    """Return one 1-bit fax page with a header line, a slight skew and speckle noise."""
    page = Image.new("L", PAGE_SIZE, 255)
    draw = ImageDraw.Draw(page)
    draw.text((60, 30), header, font=HEADER_FONT, fill=0)
    for row, line in enumerate(lines):
        draw.text((150, 170 + row * 64), line, font=BODY_FONT, fill=0)
    page = page.rotate(rng.uniform(-1.0, 1.0), resample=Image.Resampling.BICUBIC, fillcolor=255)
    for _ in range(5000):
        page.putpixel((rng.randrange(PAGE_SIZE[0]), rng.randrange(PAGE_SIZE[1])), 0)
    return page.convert("1")


def write_fax(name: str, pages: list[list[str]], rng: random.Random) -> Path:
    """Draw a fax's pages, save them as an image-only PDF and return its path."""
    images = [
        draw_page(lines, f"FROM: 555-0148   11/03/2026 09:14   PAGE {number}/{len(pages)}", rng)
        for number, lines in enumerate(pages, start=1)
    ]
    path = OUT_DIR / f"{name}.pdf"
    images[0].save(path, save_all=True, append_images=images[1:], resolution=200)
    return path


def show_reading(path: Path) -> None:
    """Print each field of one PDF as the extractor read it and as the order would store it."""
    started = time.perf_counter()
    reading = extract_with_claude(path.read_bytes())
    print(f"\n{path.name}  (model call {time.perf_counter() - started:.1f}s)")
    for field, read in reading:
        stored, report = review_field(field, read)
        print(f"  {field}: read {read.value!r}, issue {read.issue}, page {read.page}")
        print(f"      quote {read.quote!r}")
        print(f"      -> {report.status}, stored {stored!r}, reason {report.reason!r}")


def main() -> None:
    """Write the three fake faxes and print what the extractor makes of each."""
    OUT_DIR.mkdir(exist_ok=True)
    rng = random.Random(7)
    for name, pages in FAXES.items():
        show_reading(write_fax(name, pages, rng))


if __name__ == "__main__":
    main()
