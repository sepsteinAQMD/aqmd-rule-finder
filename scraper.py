"""
Scrapes the AQMD Rule Book website to discover all rule PDFs.
"""

import re
import time
import logging
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE_URL = "https://www.aqmd.gov"

# All regulation pages with their Roman numeral and human-readable name.
# Scraped from https://www.aqmd.gov/home/rules-compliance/rules/scaqmd-rule-book
REGULATION_PAGES = [
    ("/home/rules-compliance/rules/scaqmd-rule-book/proposed-rules/archived/regulation-i",
     "I", "General Provisions"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-ii",
     "II", "Permits"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-iii",
     "III", "Fees"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-iv",
     "IV", "Prohibitions"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-v",
     "V", "Toxics and Other Non-Criteria Pollutants"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-vii",
     "VII", "Amended Regulations and Hearing Board"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-viii",
     "VIII", "Enforcement"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulations-ix-and-x",
     "IX/X", "NSPS and NESHAPS"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xi",
     "XI", "Source Specific Standards"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xii",
     "XII", "Vehicle Inspection and Maintenance"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xiii",
     "XIII", "New Source Review"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xiv",
     "XIV", "Toxics"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xv",
     "XV", "Mobile Sources"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xvi",
     "XVI", "RECLAIM"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xvii",
     "XVII", "Facility Closure"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xix",
     "XIX", "Travel Demand Management"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xx",
     "XX", "RECLAIM Trading"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xxi",
     "XXI", "Solid Waste Disposal Sites"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xxii",
     "XXII", "Employee Commute Reduction"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xxiii",
     "XXIII", "Market Incentive Programs"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xxiv",
     "XXIV", "Mobile Source Emission Reduction Credits"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xxv",
     "XXV", "Airborne Toxic Control Measures"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xxvii",
     "XXVII", "Conformity"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xxx",
     "XXX", "Title V Permits"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xxxi",
     "XXXI", "Federal Source Specific Standards"),
    ("/home/rules-compliance/rules/scaqmd-rule-book/regulation-xxxv",
     "XXXV", "AIM Coatings"),
]

# Headers to mimic a real browser visit
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


def make_session():
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    return session


def _get_page(session, url, retries=3, delay=2):
    """Fetch a URL with retries, returning BeautifulSoup or None on failure."""
    for attempt in range(retries):
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            return BeautifulSoup(resp.text, "html.parser")
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
            if attempt < retries - 1:
                time.sleep(delay * (attempt + 1))
    logger.error(f"Failed to fetch {url} after {retries} attempts")
    return None


def _normalize_pdf_url(href):
    """Convert a relative or absolute href to a full PDF URL.
    Handles query strings like ?sfvrsn=... that AQMD appends to PDF URLs.
    """
    if not href:
        return None
    href = href.strip()
    # Strip query string to check extension, but keep original href for the URL
    path_part = href.split("?")[0].split("#")[0]
    if not path_part.lower().endswith(".pdf"):
        return None
    if href.startswith("http"):
        return href
    if href.startswith("//"):
        return "https:" + href
    if href.startswith("/"):
        return BASE_URL + href
    return BASE_URL + "/" + href


def _extract_rule_number_from_text(text):
    """Try to extract a rule number like '1103', '403.2', '118.1' from text."""
    # Match patterns like "Rule 1103", "Rule 403.2", "r1103", etc.
    patterns = [
        r'(?:Rule|Regulation|Reg\.?)\s+(\d+[\.\d]*[A-Za-z]?)',  # "Rule 1103", "Regulation 203"
        r'\b(\d{3,4}[\.\d]*[A-Za-z]?)\b',                        # standalone "1103", "403.2"
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1)
    return ""


def _extract_rule_number_from_filename(filename):
    """Try to extract rule number from PDF filename like 'rule-1103-...' or 'r1103.pdf'."""
    filename = filename.lower().replace(".pdf", "")
    patterns = [
        r'rule[_\-]?(\d+[\.\d]*[a-z]?)',
        r'r(\d{3,4}[\.\d]*[a-z]?)',
        r'(\d{3,4}[\.\d]*)',
    ]
    for pat in patterns:
        m = re.search(pat, filename)
        if m:
            return m.group(1)
    return ""


def _extract_amendment_date(text):
    """Extract amendment or adoption date from a text block."""
    m = re.search(
        r'\(\s*(?:Amended|Adopted|Revised)\s+([A-Za-z]+\s+\d+,?\s*\d{4})\s*\)',
        text, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()
    # fallback: just look for a date in the text
    m = re.search(r'([A-Za-z]+\s+\d+,\s*\d{4})', text)
    if m:
        return m.group(1).strip()
    return ""


def scrape_regulation_page(session, path, reg_num, reg_name, progress_cb=None):
    """
    Scrape a single regulation page and return a list of rule dicts.
    Each dict has: rule_number, title, regulation_num, regulation_name,
                   pdf_url, amendment_date
    """
    url = BASE_URL + path
    logger.info(f"Scraping regulation {reg_num}: {url}")
    soup = _get_page(session, url)
    if not soup:
        return []

    rules = []
    seen_urls = set()

    # Strategy: find all <a> tags linking to PDFs, then extract context
    for a_tag in soup.find_all("a", href=True):
        pdf_url = _normalize_pdf_url(a_tag["href"])
        if not pdf_url or pdf_url in seen_urls:
            continue

        # Skip table-of-contents PDFs (they list all rules, not individual rules)
        # Strip query string before extracting filename
        filename = pdf_url.split("/")[-1].split("?")[0].lower()
        if any(kw in filename for kw in ["toc", "table-of-contents", "table_of_contents", "addendum"]):
            continue

        seen_urls.add(pdf_url)

        # Get text from the link itself
        link_text = a_tag.get_text(separator=" ", strip=True)

        # Walk up to find the containing <td> cell, then get the sibling cell for the title.
        # AQMD uses a two-column table: [Rule number + link] | [Title + date]
        parent = a_tag.parent
        parent_text = parent.get_text(separator=" ", strip=True) if parent else ""

        # Find the row and sibling cells
        row_el = a_tag
        while row_el and row_el.name not in ("tr", "li", "div"):
            row_el = row_el.parent

        title_cell_text = ""
        row_context = ""
        if row_el:
            row_context = row_el.get_text(separator=" ", strip=True)
            cells = row_el.find_all(["td", "th"], recursive=False)
            if len(cells) >= 2:
                # First cell has the rule number/link, second has the title
                title_cell_text = cells[1].get_text(separator=" ", strip=True)

        # Extract rule number: prefer link text, then parent cell text, then filename
        rule_number = (
            _extract_rule_number_from_text(link_text)
            or _extract_rule_number_from_text(parent_text)
            or _extract_rule_number_from_filename(filename)
        )

        # Extract title from the sibling cell if available, otherwise fall back
        if title_cell_text:
            # Remove trailing date from title cell
            title = re.sub(r'\s*\([^)]*(?:Amended|Adopted|Revised)[^)]*\)\s*$', '', title_cell_text, flags=re.IGNORECASE).strip()
            title = re.sub(r'\s+', ' ', title).strip()
        else:
            # Fall back: strip rule number prefix from link text or row context
            title = re.sub(r'^(?:Rule|Regulation|Reg\.?)\s+[\d\.\w]+\s*[:–\-]?\s*', '', link_text, flags=re.IGNORECASE).strip()
            if not title or title.lower() in ("(pdf)", "pdf"):
                title = f"Rule {rule_number}" if rule_number else filename.replace("-", " ").replace("_", " ").title()

        if not title:
            title = f"Rule {rule_number}" if rule_number else filename

        # Extract amendment date from title cell or row context
        amendment_date = (
            _extract_amendment_date(title_cell_text)
            or _extract_amendment_date(row_context)
            or _extract_amendment_date(link_text)
        )

        rules.append({
            "rule_number": rule_number,
            "title": title,
            "regulation_num": reg_num,
            "regulation_name": reg_name,
            "pdf_url": pdf_url,
            "amendment_date": amendment_date,
        })

        logger.debug(f"  Found: Rule {rule_number} - {title} ({pdf_url})")

    logger.info(f"  Found {len(rules)} rules for Regulation {reg_num}")
    return rules


def scrape_all_regulations(progress_cb=None):
    """
    Scrape all regulation pages and return a complete list of rule dicts.

    progress_cb: optional callable(current, total, message) for progress updates
    """
    session = make_session()
    all_rules = []
    total = len(REGULATION_PAGES)

    for i, (path, reg_num, reg_name) in enumerate(REGULATION_PAGES):
        if progress_cb:
            progress_cb(i, total, f"Scanning Regulation {reg_num}: {reg_name}")
        rules = scrape_regulation_page(session, path, reg_num, reg_name)
        all_rules.extend(rules)
        # Be polite to the server
        time.sleep(0.5)

    if progress_cb:
        progress_cb(total, total, f"Discovered {len(all_rules)} rules across {total} regulations")

    return all_rules
