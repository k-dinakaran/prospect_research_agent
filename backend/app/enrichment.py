# ================================
# 🏆 Prospect Research Agent
# Backend Enrichment Pipeline
# ================================

import os
import re
import json
import time
import ast
import traceback
from typing import Dict, List, Any
from urllib.parse import urlparse, urljoin
from difflib import SequenceMatcher

import requests
from bs4 import BeautifulSoup

from google import genai
from google.genai import types
from dotenv import load_dotenv


# ========= ENV CONFIG =========

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY", "")

MODEL_NAME = "gemini-2.5-flash"

REQUEST_TIMEOUT = 10
MAX_RELEVANT_PAGES = 8
MAX_CHARS_FOR_LLM = 12000
DELAY_BETWEEN_REQUESTS = 0.6

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
}


# ========= STRICT OUTPUT SCHEMA =========

STRICT_KEYS = [
    "website_name",
    "company_name",
    "address",
    "mobile_number",
    "mail",
    "core_service",
    "target_customer",
    "probable_pain_point",
    "outreach_opener",
]


# ========= URL HELPERS =========

def normalize_url(url: str) -> str:
    """
    Normalize raw input URL.
    """
    if not url:
        return ""

    url = url.strip()

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    parsed = urlparse(url)

    if not parsed.netloc:
        return ""

    normalized = parsed._replace(fragment="").geturl()

    if normalized.endswith("/") and parsed.path not in ("", "/"):
        normalized = normalized[:-1]

    return normalized


def get_domain(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def is_same_domain(base_url: str, candidate_url: str) -> bool:
    return get_domain(base_url) == get_domain(candidate_url)


def derive_name_from_url(url: str) -> str:
    """
    Fallback website name from domain.
    """
    try:
        domain = get_domain(url)

        if not domain:
            return ""

        main = domain.split(".")[0]
        main = main.replace("-", " ").replace("_", " ")
        return main.title()

    except Exception:
        return ""


def empty_profile(url: str = "") -> Dict[str, Any]:
    """
    Stable fallback profile.
    Never return None or missing keys.
    """
    return {
        "website_name": derive_name_from_url(url) if url else "",
        "company_name": "",
        "address": "",
        "mobile_number": "",
        "mail": [],
        "core_service": "",
        "target_customer": "",
        "probable_pain_point": "",
        "outreach_opener": "",
    }


# ========= FETCHING =========

def fetch_html(url: str) -> str:
    """
    Fetch HTML safely with browser-like headers.
    Returns empty string on failure.
    """
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

        if response.status_code >= 400:
            return ""

        text = response.text or ""
        content_type = response.headers.get("content-type", "").lower()

        if "text/html" not in content_type and "application/xhtml" not in content_type:
            if "<html" not in text[:1000].lower() and "<body" not in text[:1000].lower():
                return ""

        return text

    except Exception:
        return ""


# ========= HTML CLEANING =========

def extract_page_title(html: str) -> str:
    try:
        soup = BeautifulSoup(html, "html.parser")

        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            title = re.sub(r"\s+", " ", title)
            return title[:160]

        h1 = soup.find("h1")
        if h1:
            return h1.get_text(" ", strip=True)[:160]

        return ""

    except Exception:
        return ""


def extract_meta_text(html: str) -> str:
    """
    Extract title, meta description, OpenGraph, Twitter meta, and JSON-LD text.
    Useful when websites are JS-heavy or body text is thin.
    """
    if not html:
        return ""

    try:
        soup = BeautifulSoup(html, "html.parser")
        parts = []

        if soup.title and soup.title.string:
            parts.append(soup.title.string.strip())

        meta_selectors = [
            {"name": "description"},
            {"property": "og:title"},
            {"property": "og:description"},
            {"name": "twitter:title"},
            {"name": "twitter:description"},
        ]

        for attrs in meta_selectors:
            tag = soup.find("meta", attrs=attrs)
            if tag:
                content = tag.get("content", "").strip()
                if content:
                    parts.append(content)

        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.get_text(" ", strip=True)
            if raw and len(raw) < 5000:
                parts.append(raw)

        cleaned = []
        seen = set()

        for part in parts:
            part = re.sub(r"\s+", " ", part).strip()

            if part and part.lower() not in seen:
                seen.add(part.lower())
                cleaned.append(part)

        return "\n".join(cleaned)

    except Exception:
        return ""


def extract_contact_signal_text_from_html(html: str) -> str:
    """
    Extract contact-heavy text before removing footer/header/form.

    Many websites keep phone, email, and address inside:
    - footer
    - address tag
    - contact section
    - location section
    - icon-based contact blocks
    - mailto/tel links

    This is generic extraction logic, not company-specific hardcoding.
    """
    if not html:
        return ""

    try:
        soup = BeautifulSoup(html, "html.parser")
        contact_chunks = []

        # 1. Footer and address tags often contain phone/email/address.
        for tag in soup.find_all(["footer", "address"]):
            text = tag.get_text(" ", strip=True)
            if text:
                contact_chunks.append(text)

        # 2. Elements with contact/location-related class or id.
        contact_keywords = [
            "contact", "footer", "address", "location", "phone",
            "email", "mail", "reach", "get-in-touch", "call",
            "office", "branch", "map"
        ]

        for tag in soup.find_all(True):
            class_text = " ".join(tag.get("class", [])) if tag.get("class") else ""
            id_text = tag.get("id", "") or ""
            combined_attr = f"{class_text} {id_text}".lower()

            if any(keyword in combined_attr for keyword in contact_keywords):
                text = tag.get_text(" ", strip=True)
                if text:
                    contact_chunks.append(text)

        # 3. Preserve mailto/tel values.
        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            href_lower = href.lower()

            if href_lower.startswith(("mailto:", "tel:")):
                contact_chunks.append(href)

        # 4. Clean and dedupe.
        cleaned = []
        seen = set()

        for chunk in contact_chunks:
            chunk = re.sub(r"\s+", " ", chunk).strip()
            if not chunk:
                continue

            key = chunk.lower()
            if key in seen:
                continue

            seen.add(key)
            cleaned.append(chunk)

        return "\n".join(cleaned)

    except Exception:
        return ""


def clean_line(line: str) -> str:
    line = re.sub(r"\s+", " ", line).strip()
    return line


def is_noise_line(line: str) -> bool:
    """
    Remove common website noise.
    """
    low = line.lower().strip()

    if len(low) < 3:
        return True

    noise_phrases = [
        "accept cookies",
        "cookie policy",
        "privacy policy",
        "terms of use",
        "terms & conditions",
        "all rights reserved",
        "subscribe to our newsletter",
        "enable javascript",
        "skip to content",
        "menu",
        "close",
        "read more",
        "learn more",
        "click here",
        "sign in",
        "login",
        "follow us",
        "copyright",
        "cookie settings",
        "manage cookies",
        "your privacy",
        "gdpr",
        "ccpa",
        "do not sell",
        "accessibility",
    ]

    if any(phrase in low for phrase in noise_phrases):
        return True

    if len(low) <= 12 and low in {
        "home", "about", "services", "contact", "products",
        "solutions", "careers", "blog", "pricing", "resources",
        "company", "platform", "customers", "industries"
    }:
        return True

    return False


def extract_clean_text(html: str) -> str:
    """
    Remove raw HTML, boilerplate, scripts, navbars, and duplicate lines.
    """
    if not html:
        return ""

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup([
        "script", "style", "noscript", "svg", "canvas",
        "iframe", "header", "footer", "nav", "form"
    ]):
        tag.decompose()

    text = soup.get_text(separator="\n")
    raw_lines = [clean_line(line) for line in text.splitlines()]

    seen = set()
    cleaned_lines = []

    for line in raw_lines:
        if not line:
            continue

        if is_noise_line(line):
            continue

        key = line.lower()

        if key in seen:
            continue

        seen.add(key)
        cleaned_lines.append(line)

    final_text = "\n".join(cleaned_lines)
    final_text = re.sub(r"\n{3,}", "\n\n", final_text).strip()

    return final_text


# ========= SMART LINK DISCOVERY =========

IMPORTANT_KEYWORDS = [
    "about", "about-us", "company", "company-info", "who-we-are", "our-story",
    "contact", "contact-us", "get-in-touch", "reach-us", "connect",
    "services", "our-services", "solutions", "what-we-do", "what-we-offer",
    "products", "platform", "industries", "customers", "clients",
    "sales", "marketing", "support", "crm", "it-service-management",
    "customer-service"
]


def fuzzy_score(text: str, targets: List[str]) -> int:
    """
    Lightweight fuzzy matching score.
    Helps catch useful pages like get-in-touch, company-info, what-we-offer, etc.
    """
    if not text:
        return 0

    normalized = text.lower()
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized)

    words = normalized.split()
    best_score = 0.0

    for target in targets:
        target_clean = target.lower().replace("-", " ").replace("_", " ")

        for word in words:
            ratio = SequenceMatcher(None, word, target_clean).ratio()
            if ratio > best_score:
                best_score = ratio

        full_ratio = SequenceMatcher(None, normalized, target_clean).ratio()
        if full_ratio > best_score:
            best_score = full_ratio

    if best_score >= 0.85:
        return 5
    elif best_score >= 0.75:
        return 3
    elif best_score >= 0.65:
        return 1

    return 0


def score_link(url: str, text: str = "") -> int:
    """
    Higher score means more useful for prospect research.
    Uses keyword scoring + lightweight fuzzy matching.
    """
    combined = f"{url} {text}".lower()

    score = 0

    weighted_keywords = {
        "contact": 10,
        "contact-us": 10,
        "get-in-touch": 10,
        "reach-us": 9,
        "about": 9,
        "about-us": 9,
        "company-info": 8,
        "services": 8,
        "our-services": 8,
        "solutions": 8,
        "what-we-offer": 8,
        "products": 7,
        "industries": 7,
        "platform": 7,
        "company": 6,
        "who-we-are": 6,
        "our-story": 5,
        "customers": 4,
        "clients": 4,
        "what-we-do": 4,
        "crm": 4,
        "sales": 3,
        "marketing": 3,
        "support": 3,
        "customer-service": 3,
        "it-service-management": 3,
    }

    for keyword, weight in weighted_keywords.items():
        if keyword in combined:
            score += weight

    # Fuzzy matching for useful pages with slightly different naming.
    score += fuzzy_score(combined, IMPORTANT_KEYWORDS)

    bad_keywords = [
        "blog", "news", "press", "career", "jobs", "privacy",
        "terms", "login", "signup", "cart", "account", "wp-content",
        "tag/", "author/", "category/", "events", "webinar",
        "investor", "legal", "security", "status", "download",
        "ebook", "whitepaper", "case-study",

        # Avoid personal bio / leadership pages that dilute business context.
        "board-of-directors", "management/", "advisory-board",
        "leadership", "executive", "bio/"
    ]

    for bad in bad_keywords:
        if bad in combined:
            score -= 8

    # Penalize localized/regional pages to avoid duplicate contact pages like /fr/contactus.html.
    locale_pattern = r"/(?:[a-z]{2}|[a-z]{2}-[a-z]{2})/"
    if re.search(locale_pattern, combined):
        score -= 10

    return score


def extract_links_from_homepage(base_url: str, html: str) -> List[str]:
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    candidates = []

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()

        if not href:
            continue

        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue

        absolute = urljoin(base_url, href)
        absolute = normalize_url(absolute)

        if not absolute:
            continue

        if not is_same_domain(base_url, absolute):
            continue

        anchor_text = a.get_text(" ", strip=True)
        candidates.append((absolute, anchor_text, score_link(absolute, anchor_text)))

    candidates = sorted(candidates, key=lambda x: x[2], reverse=True)

    selected = []
    seen = set()

    for link, _, score in candidates:
        if score <= 0:
            continue

        clean_link = link.split("?")[0].rstrip("/")

        if clean_link in seen:
            continue

        seen.add(clean_link)
        selected.append(clean_link)

        if len(selected) >= MAX_RELEVANT_PAGES:
            break

    return selected


def extract_links_from_sitemap(base_url: str) -> List[str]:
    """
    Try common sitemap locations.
    """
    sitemap_urls = [
        urljoin(base_url, "/sitemap.xml"),
        urljoin(base_url, "/sitemap_index.xml"),
    ]

    selected = []

    for sitemap_url in sitemap_urls:
        xml = ""

        try:
            response = requests.get(
                sitemap_url,
                headers=HEADERS,
                timeout=REQUEST_TIMEOUT,
            )

            if response.status_code < 400:
                xml = response.text

        except Exception:
            xml = ""

        if not xml:
            continue

        try:
            soup = BeautifulSoup(xml, "xml")
            loc_tags = soup.find_all("loc")
        except Exception:
            continue

        scored = []

        for loc in loc_tags:
            link = loc.get_text(strip=True)
            link = normalize_url(link)

            if not link:
                continue

            if not is_same_domain(base_url, link):
                continue

            s = score_link(link, "")

            if s > 0:
                scored.append((link.split("?")[0].rstrip("/"), s))

        scored = sorted(scored, key=lambda x: x[1], reverse=True)

        for link, _ in scored:
            if link not in selected:
                selected.append(link)

            if len(selected) >= MAX_RELEVANT_PAGES:
                break

        if selected:
            break

    return selected[:MAX_RELEVANT_PAGES]


def build_guessed_relevant_links(base_url: str) -> List[str]:
    """
    Fallback approach for sites where sitemap/homepage links are weak.
    These are common company info paths.
    """
    paths = [
        "/about",
        "/about-us",
        "/company",
        "/company-info",
        "/who-we-are",
        "/our-story",
        "/contact",
        "/contact-us",
        "/get-in-touch",
        "/reach-us",
        "/services",
        "/our-services",
        "/solutions",
        "/what-we-do",
        "/what-we-offer",
        "/products",
        "/industries",
        "/customers",
        "/platform",
        "/sales",
        "/marketing",
        "/support",
        "/crm",
        "/customer-service",
        "/it-service-management",
    ]

    links = []

    for path in paths:
        guessed = urljoin(base_url, path)
        guessed = normalize_url(guessed)

        if guessed and guessed not in links:
            links.append(guessed)

    return links


def discover_relevant_links(base_url: str, homepage_html: str) -> List[str]:
    """
    Smart scraping:
    1. Always include homepage.
    2. Try sitemap.
    3. Add homepage-discovered relevant links.
    4. Add guessed fallback links.
    5. Use keyword + fuzzy scoring.
    6. Limit pages.
    """
    base_url = normalize_url(base_url)

    links = [base_url]
    seen = {base_url.rstrip("/")}

    sitemap_links = extract_links_from_sitemap(base_url)
    homepage_links = extract_links_from_homepage(base_url, homepage_html)
    guessed_links = build_guessed_relevant_links(base_url)

    for link in sitemap_links + homepage_links + guessed_links:
        normalized = normalize_url(link).rstrip("/")

        if not normalized:
            continue

        if normalized in seen:
            continue

        if not is_same_domain(base_url, normalized):
            continue

        # Guessed links may not have anchor text, so score by URL.
        if score_link(normalized, "") <= 0:
            continue

        seen.add(normalized)
        links.append(normalized)

        if len(links) >= MAX_RELEVANT_PAGES:
            break

    return links


# ========= FACT EXTRACTION =========

def extract_emails(text: str) -> List[str]:
    """
    Extract emails from visible cleaned text.
    """
    if not text:
        return []

    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    emails = re.findall(email_pattern, text)

    cleaned = []

    blocked_extensions = (
        ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg",
        ".css", ".js", ".ico"
    )

    for email in emails:
        email = email.strip().strip(".,;:()[]{}<>").lower()

        if any(email.endswith(ext) for ext in blocked_extensions):
            continue

        if email not in cleaned:
            cleaned.append(email)

    return cleaned[:5]


def extract_phone_numbers(text: str) -> List[str]:
    """
    Basic phone extraction from visible cleaned text.
    Kept as utility, but final flow uses extract_phone_numbers_with_context().
    """
    if not text:
        return []

    phone_pattern = r"""
        (?:
            (?:\+?\d{1,4}[\s\-().]*)?
            (?:\(?\d{2,5}\)?[\s\-().]*)?
            \d{3,5}[\s\-().]*\d{4,5}
        )
    """

    raw_numbers = re.findall(phone_pattern, text, flags=re.VERBOSE)
    cleaned = []

    for num in raw_numbers:
        n = re.sub(r"\s+", " ", num).strip()
        n = n.strip(".,;:()[]{}<>")
        digits = re.sub(r"\D", "", n)

        if len(digits) < 8 or len(digits) > 15:
            continue

        if len(set(digits)) <= 2:
            continue

        if n not in cleaned:
            cleaned.append(n)

    return cleaned[:3]


def extract_phone_numbers_with_context(text: str) -> List[str]:
    """
    Extract phone numbers only when nearby text suggests it is actually a phone number.

    Handles formats like:
    - +044-35514488
    - +91 98765 43210
    - 044-35514488
    - Phone: +044-35514488
    """
    if not text:
        return []

    lines = [clean_line(line) for line in text.splitlines() if clean_line(line)]

    phone_candidates = []

    contact_keywords = [
        "phone", "tel", "telephone", "mobile", "call",
        "contact", "support", "sales", "talk to sales",
        "customer care", "toll free", "whatsapp"
    ]

    phone_pattern = r"""
        (?:
            (?:\+?\d{1,4}[\s\-().]*)?
            (?:\(?\d{2,5}\)?[\s\-().]*)?
            \d{3,5}[\s\-().]*\d{4,5}
        )
    """

    for i, line in enumerate(lines):
        context = " ".join(lines[max(0, i - 2): min(len(lines), i + 3)]).lower()
        has_contact_context = any(keyword in context for keyword in contact_keywords)

        matches = re.findall(phone_pattern, line, flags=re.VERBOSE)

        for match in matches:
            phone = re.sub(r"\s+", " ", match).strip()
            phone = phone.strip(".,;:()[]{}<>")
            digits = re.sub(r"\D", "", phone)

            if len(digits) < 8 or len(digits) > 15:
                continue

            if len(set(digits)) <= 2:
                continue

            has_phone_format = any(symbol in phone for symbol in ["+", "(", ")", "-"])

            # Accept if it has phone-like formatting OR nearby contact context.
            if not has_phone_format and not has_contact_context:
                continue

            if phone not in phone_candidates:
                phone_candidates.append(phone)

    return phone_candidates[:3]


def extract_contacts_from_html(html_blocks: List[str]) -> Dict[str, List[str]]:
    """
    Extract emails and phone numbers from mailto: and tel: links.
    Many websites hide contact info inside href attributes.
    """
    emails = []
    phones = []

    for html in html_blocks:
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")

        for a in soup.find_all("a", href=True):
            href = a.get("href", "").strip()
            href_lower = href.lower()

            if href_lower.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip().lower()
                email = email.strip(".,;:()[]{}<>")

                if email and "@" in email and email not in emails:
                    emails.append(email)

            if href_lower.startswith("tel:"):
                phone = href.replace("tel:", "").strip()
                phone = re.sub(r"\s+", " ", phone)
                phone = phone.strip(".,;:()[]{}<>")

                digits = re.sub(r"\D", "", phone)

                if 8 <= len(digits) <= 15 and phone not in phones:
                    phones.append(phone)

    return {
        "emails": emails[:5],
        "phones": phones[:3],
    }


def extract_address_candidate(text: str) -> str:
    """
    Conservative address extraction.
    Handles labeled and unlabeled address blocks.

    This version also handles contact footer text like:
    Phone: ... Email: ... Web: ... #151 Block, Area, City-600102. Country

    No company-specific hardcoding.
    """
    if not text:
        return ""

    # Normalize text first
    normalized_text = re.sub(r"\s+", " ", text).strip()

    # Remove emails
    normalized_text = re.sub(
        r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
        " ",
        normalized_text,
    )

    # Remove URLs / websites
    normalized_text = re.sub(
        r"\b(?:https?://)?(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s,]*)?",
        " ",
        normalized_text,
    )

    # Remove phone labels + phone-like values
    normalized_text = re.sub(
        r"(?i)\b(phone|tel|telephone|mobile|call|fax)\s*[:：]?\s*\+?[\d\s\-().]{7,20}",
        " ",
        normalized_text,
    )

    # Add breaks before likely address markers to help candidate segmentation
    normalized_text = re.sub(r"(?=#\s*\d+)", "\n", normalized_text)
    normalized_text = re.sub(r"(?i)(?=\b(?:door|plot|flat|suite|floor|block)\b)", "\n", normalized_text)

    raw_lines = []
    for line in text.splitlines():
        raw_lines.append(clean_line(line))

    # Also include normalized split lines
    raw_lines.extend([clean_line(line) for line in normalized_text.splitlines()])

    lines = []
    seen = set()

    for line in raw_lines:
        if not line:
            continue

        # Remove common contact labels from the line
        line = re.sub(
            r"(?i)\b(phone|tel|telephone|mobile|call|email|mail|web|website)\s*[:：]\s*[^,|]+",
            " ",
            line,
        )
        line = re.sub(r"\s+", " ", line).strip(" ,.;:-")

        if not line:
            continue

        key = line.lower()
        if key not in seen:
            seen.add(key)
            lines.append(line)

    strong_address_keywords = [
        "headquarters",
        "corporate office",
        "registered office",
        "office address",
        "address",
        "contact us",
        "location",
        "locations",
        "visit us",
        "reach us"
    ]

    address_tokens = [
        "street", "st.", "road", "rd.", "avenue", "ave", "drive", "dr.",
        "lane", "ln", "boulevard", "blvd", "suite", "floor", "building",
        "parkway", "plaza", "industrial estate", "tower", "complex",
        "nagar", "colony", "block", "sector", "phase", "center", "centre",
        "district", "city", "state", "country", "plot", "door", "flat"
    ]

    candidates = []

    for i, line in enumerate(lines):
        context_lines = lines[max(0, i - 2): min(len(lines), i + 3)]
        context_text = " ".join(context_lines)
        context_text = re.sub(r"\s+", " ", context_text).strip(" ,.;:")
        context_low = context_text.lower()

        has_address_token = any(token in context_low for token in address_tokens)
        has_strong_context = any(keyword in context_low for keyword in strong_address_keywords)

        has_indian_pincode = bool(re.search(r"\b\d{6}\b", context_text))
        has_us_zip = bool(re.search(r"\b\d{5}(?:-\d{4})?\b", context_text))
        has_number_or_hash = bool(re.search(r"(#\s*\d+|\b\d{1,5}\b)", context_text))

        bad_context = any(bad in context_low for bad in [
            "copyright", "privacy", "terms", "invoice", "order id",
            "tracking", "version", "blog", "case study", "testimonial",
            "login", "signup"
        ])

        if bad_context:
            continue

        labeled_address = has_strong_context and (
            has_address_token or has_indian_pincode or has_us_zip
        )

        unlabeled_address = (
            (has_indian_pincode or has_us_zip)
            and has_address_token
            and has_number_or_hash
        )

        if labeled_address or unlabeled_address:
            candidate = context_text

            # Remove leftover contact fragments
            candidate = re.sub(
                r"(?i)\b(phone|tel|telephone|mobile|call|email|mail|web|website)\s*[:：]?\s*",
                " ",
                candidate,
            )

            candidate = re.sub(
                r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
                " ",
                candidate,
            )

            candidate = re.sub(
                r"\b(?:https?://)?(?:www\.)?[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/[^\s,]*)?",
                " ",
                candidate,
            )

            candidate = re.sub(r"\s+", " ", candidate).strip(" ,.;:-")

            if 20 <= len(candidate) <= 300:
                candidates.append(candidate)

    # Extra fallback: directly find an address-like segment with pincode/zip
    fallback_patterns = [
        r"(#\s*\d+[^.\n]{10,180}\b\d{6}\b[^.\n]{0,80})",
        r"(\b\d{1,5}[^.\n]{10,180}\b\d{5}(?:-\d{4})?\b[^.\n]{0,80})",
    ]

    for pattern in fallback_patterns:
        matches = re.findall(pattern, normalized_text, flags=re.IGNORECASE)

        for match in matches:
            candidate = re.sub(r"\s+", " ", match).strip(" ,.;:")
            low = candidate.lower()

            if any(token in low for token in address_tokens) and 20 <= len(candidate) <= 250:
                candidates.append(candidate)

    if not candidates:
        return ""

    # Deduplicate
    unique_candidates = []
    seen = set()

    for candidate in candidates:
        key = candidate.lower()
        if key not in seen:
            seen.add(key)
            unique_candidates.append(candidate)

    # Prefer candidate with pincode/zip and shorter clean length.
    unique_candidates = sorted(
        unique_candidates,
        key=lambda x: (
            0 if re.search(r"\b\d{5,6}(?:-\d{4})?\b", x) else 1,
            len(x)
        )
    )

    return unique_candidates[0][:250]


def extract_company_name_candidate(title: str, website_name: str) -> str:
    """
    Extract company name from title as fallback.
    """
    if not title:
        return website_name

    parts = re.split(r"\s[-|–—]\s", title)
    parts = [p.strip() for p in parts if p.strip()]

    if parts:
        candidate = parts[0]
    else:
        candidate = title.strip()

    if candidate.lower() in ["home", "homepage", "welcome"]:
        return website_name

    if len(candidate) > 80:
        return website_name

    return candidate[:120]


# ========= COMPANY SCRAPING =========

def scrape_company_context(url: str) -> Dict[str, Any]:
    """
    Scrape relevant pages and return compact evidence.
    Includes fallback meta extraction and contact signal preservation.
    """
    normalized_url = normalize_url(url)

    if not normalized_url:
        return {
            "url": url,
            "domain": "",
            "title": "",
            "pages_scraped": [],
            "combined_text": "",
            "html_blocks": [],
            "contact_signal_text": "",
            "debug_note": "Invalid URL",
        }

    homepage_html = fetch_html(normalized_url)
    title = extract_page_title(homepage_html)
    homepage_meta = extract_meta_text(homepage_html)

    relevant_links = discover_relevant_links(normalized_url, homepage_html)

    pages_scraped = []
    combined_blocks = []
    html_blocks = []
    contact_signal_blocks = []

    for page_url in relevant_links:
        html = homepage_html if page_url.rstrip("/") == normalized_url.rstrip("/") else fetch_html(page_url)

        if not html:
            continue

        html_blocks.append(html)

        contact_signal = extract_contact_signal_text_from_html(html)
        if contact_signal:
            contact_signal_blocks.append(contact_signal)

        text = extract_clean_text(html)
        meta_text = extract_meta_text(html)

        page_parts = []

        if meta_text:
            page_parts.append(f"META INFO:\n{meta_text}")

        if text:
            page_parts.append(f"VISIBLE TEXT:\n{text}")

        if not page_parts:
            continue

        page_content = "\n\n".join(page_parts)

        if len(page_content.strip()) < 80:
            continue

        pages_scraped.append(page_url)

        block = f"\n\n--- PAGE: {page_url} ---\n{page_content}"
        combined_blocks.append(block)

        time.sleep(DELAY_BETWEEN_REQUESTS)

    contact_signal_text = "\n".join(contact_signal_blocks)
    combined_text = "\n".join(combined_blocks)

    # Put contact signals at the front so phone/address/email are not lost
    # when main text is trimmed to MAX_CHARS_FOR_LLM.
    if contact_signal_text:
        combined_text = f"--- CONTACT SIGNALS ---\n{contact_signal_text}\n\n{combined_text}"

    if len(combined_text.strip()) < 300:
        fallback_parts = [
            f"Website URL: {normalized_url}",
            f"Domain: {get_domain(normalized_url)}",
            f"Page Title: {title}",
            f"Homepage Meta: {homepage_meta}",
            f"Contact Signals: {contact_signal_text}",
        ]

        fallback_text = "\n".join([
            part for part in fallback_parts
            if part and not part.endswith(": ")
        ])

        if fallback_text.strip():
            combined_text = fallback_text

    combined_text = combined_text[:MAX_CHARS_FOR_LLM]

    return {
        "url": normalized_url,
        "domain": get_domain(normalized_url),
        "title": title,
        "pages_scraped": pages_scraped,
        "combined_text": combined_text,
        "html_blocks": html_blocks,
        "contact_signal_text": contact_signal_text,
        "debug_note": f"Scraped {len(pages_scraped)} pages; evidence chars={len(combined_text)}",
    }


# ========= GEMINI AI INSIGHTS =========

def get_gemini_client():
    if not API_KEY:
        raise ValueError("Please set GEMINI_API_KEY in your environment variables.")

    return genai.Client(api_key=API_KEY)


def safe_json_loads(text: str) -> Dict[str, Any]:
    """
    Parse JSON even if model accidentally returns extra text.
    """
    if not text:
        return {}

    text = text.strip()

    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)

    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return {}

    return {}


def generate_ai_insights(
    context: Dict[str, Any],
    deterministic_facts: Dict[str, Any],
) -> Dict[str, str]:
    """
    Gemini should only generate business reasoning fields.
    Contact details stay deterministic.
    """
    evidence = context.get("combined_text", "")

    if not evidence:
        return {
            "company_name": deterministic_facts.get("company_name", ""),
            "core_service": "",
            "target_customer": "",
            "probable_pain_point": "",
            "outreach_opener": "",
        }

    client = get_gemini_client()

    prompt = f"""
You are a careful B2B prospect research analyst.

You are given CLEANED WEBSITE EVIDENCE scraped from a company website.

Your job:
Extract/generate only these fields:
- company_name
- core_service
- target_customer
- probable_pain_point
- outreach_opener

VERY IMPORTANT RULES:
1. Use only the evidence provided.
2. Do NOT invent email, phone number, or address.
3. Do NOT invent services that are not supported by evidence.
4. If evidence is insufficient for a field, return an empty string.
5. The outreach_opener must:
   - start with "Hi team,"
   - be one sentence only
   - be maximum 35 words
   - not end with a question
   - mention a specific observed service or market from the evidence
   - sound like a B2B cold outreach opener
6. Return valid JSON only.
7. No markdown. No explanation. No extra keys.
8. Avoid hype words and avoid making numerical claims unless the evidence contains numbers.
9. Keep the probable_pain_point realistic and based on the company's service, not exaggerated.
10. If the website appears to be a known company but the evidence is thin, use only the title/meta/domain evidence. Do not use outside knowledge.

Known deterministic facts extracted by code:
{json.dumps(deterministic_facts, indent=2)}

Cleaned website evidence:
\"\"\"
{evidence}
\"\"\"

Return exactly this JSON structure:
{{
  "company_name": "",
  "core_service": "",
  "target_customer": "",
  "probable_pain_point": "",
  "outreach_opener": ""
}}
"""

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            ),
        )

        parsed = safe_json_loads(response.text)

        return {
            "company_name": str(parsed.get("company_name", "") or ""),
            "core_service": str(parsed.get("core_service", "") or ""),
            "target_customer": str(parsed.get("target_customer", "") or ""),
            "probable_pain_point": str(parsed.get("probable_pain_point", "") or ""),
            "outreach_opener": str(parsed.get("outreach_opener", "") or ""),
        }

    except Exception as e:
        print(f"[Gemini Error] {e}")

        return {
            "company_name": deterministic_facts.get("company_name", ""),
            "core_service": "",
            "target_customer": "",
            "probable_pain_point": "",
            "outreach_opener": "",
        }


# ========= SCHEMA VALIDATION =========

def validate_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enforce exact schema.
    """
    validated = {}

    for key in STRICT_KEYS:
        if key == "mail":
            value = profile.get(key, [])

            if isinstance(value, list):
                cleaned_emails = []

                for item in value:
                    if isinstance(item, str) and item.strip():
                        item = item.strip().lower()

                        if item not in cleaned_emails:
                            cleaned_emails.append(item)

                validated[key] = cleaned_emails

            elif isinstance(value, str) and value.strip():
                validated[key] = [value.strip().lower()]
            else:
                validated[key] = []

        else:
            value = profile.get(key, "")

            if value is None:
                value = ""

            validated[key] = str(value).strip()

    return validated


# ========= REQUIRED FUNCTION =========

def enrich_company(url: str) -> dict:
    """
    Input: Company URL
    Output: Structured company profile (STRICT FORMAT)
    """

    try:
        normalized_url = normalize_url(url)

        if not normalized_url:
            return empty_profile(url)

        context = scrape_company_context(normalized_url)

        title = context.get("title", "")
        combined_text = context.get("combined_text", "")
        contact_signal_text = context.get("contact_signal_text", "")

        print(f"[Debug] {normalized_url} -> {context.get('debug_note', '')}")
        print(f"[Debug] Pages scraped: {context.get('pages_scraped', [])}")

        website_name = derive_name_from_url(normalized_url)
        company_name_candidate = extract_company_name_candidate(title, website_name)

        # Use contact signals + cleaned evidence for deterministic extraction.
        fact_text = f"{contact_signal_text}\n\n{combined_text}"

        emails_from_text = extract_emails(fact_text)
        phones_from_text = extract_phone_numbers_with_context(fact_text)

        html_contacts = extract_contacts_from_html(context.get("html_blocks", []))

        emails = []
        for email in html_contacts.get("emails", []) + emails_from_text:
            if email and email not in emails:
                emails.append(email)

        phones = []

        # Prefer tel: phones because they are more reliable than random text numbers.
        for phone in html_contacts.get("phones", []):
            if phone and phone not in phones:
                phones.append(phone)

        # Only use context-aware text phones if no tel: phone exists.
        if not phones:
            for phone in phones_from_text:
                digits = re.sub(r"\D", "", phone)

                if len(digits) < 8 or len(digits) > 15:
                    continue

                if phone and phone not in phones:
                    phones.append(phone)

        emails = emails[:5]
        phones = phones[:3]

        address = extract_address_candidate(fact_text)

        deterministic_facts = {
            "website_name": website_name,
            "company_name": company_name_candidate,
            "address": address,
            "mobile_number": phones[0] if phones else "",
            "mail": emails,
            "source_url": normalized_url,
            "pages_scraped": context.get("pages_scraped", []),
        }

        ai_insights = generate_ai_insights(context, deterministic_facts)

        profile = {
            "website_name": website_name,
            "company_name": ai_insights.get("company_name") or company_name_candidate,
            "address": address,
            "mobile_number": phones[0] if phones else "",
            "mail": emails,
            "core_service": ai_insights.get("core_service", ""),
            "target_customer": ai_insights.get("target_customer", ""),
            "probable_pain_point": ai_insights.get("probable_pain_point", ""),
            "outreach_opener": ai_insights.get("outreach_opener", ""),
        }

        return validate_profile(profile)

    except Exception as e:
        print(f"[Error processing {url}] {e}")
        traceback.print_exc()
        return empty_profile(url)


# ========= OPTIONAL LOCAL CLI TEST =========

def parse_url_array(raw_input_text: str) -> List[str]:
    """
    Supports manual CLI testing.
    """
    raw_input_text = raw_input_text.strip()

    if not raw_input_text:
        return []

    try:
        parsed = json.loads(raw_input_text)
    except Exception:
        try:
            parsed = ast.literal_eval(raw_input_text)
        except Exception:
            raise ValueError("Input must be a JSON array of URLs.")

    if not isinstance(parsed, list):
        raise ValueError("Input must be a list/array of URLs.")

    urls = []

    for item in parsed:
        if isinstance(item, str) and item.strip():
            urls.append(item.strip())

    return urls


if __name__ == "__main__":

    print("=== Prospect Research Agent ===")
    print("Paste a JSON array of company URLs.")
    print('Example: ["https://www.zoho.com", "https://www.freshworks.com"]')
    print()

    raw_urls = input("Paste JSON array of company URLs: ")

    try:
        urls = parse_url_array(raw_urls)
    except Exception as e:
        print(f"Invalid input: {e}")
        urls = []

    results = []

    for idx, url in enumerate(urls, start=1):
        print(f"\n[{idx}/{len(urls)}] Processing: {url}")

        try:
            data = enrich_company(url)
            results.append(data)
            print("Done.")

        except Exception as e:
            print(f"Error processing {url}: {e}")
            results.append(empty_profile(url))

    with open("results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("\n=== FINAL OUTPUT ===\n")
    print(json.dumps(results, indent=2, ensure_ascii=False))

    print("\nSaved results to results.json")