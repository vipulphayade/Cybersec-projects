from __future__ import annotations

import json
import re
from html import unescape
from pathlib import Path
from urllib.parse import urldefrag

import requests
from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString


BASE_URL = "https://mysocietyclub.com/bye-laws/maharashtra-cooperative-housing-society-bye-laws/"
ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT_DIR / "dataset" / "bylaws_dataset.json"

LAW_HEADING_RE = re.compile(
    r"bye\s*law\s*no\.?\s*(\d{1,3})(?:\s*\.?\s*\(\s*([a-z])\s*\)|([a-z])\b)?\s*[:.]?",
    re.IGNORECASE,
)
INLINE_CODE_RE = re.compile(r"\b(\d{1,3})\s*\(?\s*([a-z])\s*\)?\s*:?", re.IGNORECASE)
NOISE_RE = re.compile(
    r"Search Housing Society|Disclaimer:|MySocietyClub\.com|Download MySocietyClub|"
    r"Our Company Policy|Other Related Pages|Follow us|All Rights Reserved|"
    r"Toggle navigation|Technical Support|Contact MySocietyClub",
    re.IGNORECASE,
)
STOP_WORDS = {
    "and",
    "are",
    "bye",
    "for",
    "from",
    "law",
    "member",
    "members",
    "shall",
    "society",
    "the",
    "under",
    "with",
}


def clean_text(value: str) -> str:
    value = unescape(value)
    value = value.replace("\xa0", " ")
    value = value.replace("\u2010", "-").replace("\u2011", "-")
    value = value.replace("\u2013", "-").replace("\u2014", "-")
    value = value.replace("\u2018", "'").replace("\u2019", "'")
    value = value.replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", value).strip()


def fetch_soup(session: requests.Session, url: str) -> BeautifulSoup:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def discover_pages(session: requests.Session) -> list[str]:
    soup = fetch_soup(session, BASE_URL)
    urls = {BASE_URL}
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "/bye-laws/maharashtra-cooperative-housing-society-bye-laws/" not in href:
            continue
        url, _fragment = urldefrag(href)
        if url.startswith(BASE_URL) and "appendix" not in url.lower():
            urls.add(url)
    return sorted(urls)


def parse_heading(text: str) -> tuple[str, str, str] | None:
    text = clean_text(text)
    match = LAW_HEADING_RE.search(text)
    if match:
        bylaw_number = match.group(1)
        subsection = (match.group(2) or match.group(3) or "").lower()
        title = clean_text(text[match.end() :].strip(" .:-"))
        return bylaw_number, subsection, title

    match = INLINE_CODE_RE.match(text)
    if not match:
        return None
    bylaw_number = match.group(1)
    subsection = (match.group(2) or "").lower()
    title = clean_text(text[match.end() :].strip(" .:-"))
    return bylaw_number, subsection, title


def extract_keywords(title: str, official_text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", f"{title} {official_text}".lower())
    keywords = []
    for token in tokens:
        if len(token) < 3 or token in STOP_WORDS or token in keywords:
            continue
        keywords.append(token)
        if len(keywords) >= 12:
            break
    return keywords


def get_chapter(section: Tag) -> str:
    for heading in section.find_all_previous(["h2", "h3"]):
        text = clean_text(heading.get_text(" ", strip=True))
        if text and not text.lower().startswith("bye law"):
            return text
    return ""


def sibling_text_until_next_bylaw(start: Tag) -> str:
    parts: list[str] = []
    for node in start.next_siblings:
        if isinstance(node, Tag):
            if node.name in {"h2", "h3"}:
                break
            if node.name == "h4" and LAW_HEADING_RE.search(node.get_text(" ", strip=True)):
                break
            if node.name in {"p", "li"}:
                text = clean_text(node.get_text(" ", strip=True))
                if text and not NOISE_RE.search(text):
                    parts.append(text)
            elif node.name in {"ol", "ul"}:
                for item in node.find_all("li", recursive=False):
                    text = clean_text(item.get_text(" ", strip=True))
                    if text and not NOISE_RE.search(text):
                        parts.append(text)
            elif node.name in {"div", "section", "article"}:
                chunks: list[str] = []
                for child in node.children:
                    if isinstance(child, Tag) and child.name == "h4" and LAW_HEADING_RE.search(child.get_text(" ", strip=True)):
                        break
                    if isinstance(child, NavigableString):
                        chunks.append(str(child))
                    elif isinstance(child, Tag):
                        chunks.append(child.get_text(" ", strip=True))
                text = clean_text(" ".join(chunks))
                if text and not NOISE_RE.search(text):
                    parts.append(text)
    return " ".join(parts)


def parse_page(session: requests.Session, url: str) -> list[dict[str, object]]:
    soup = fetch_soup(session, url)
    for tag in soup(["script", "style", "noscript", "form", "nav", "footer"]):
        tag.decompose()

    records: list[dict[str, object]] = []
    for section in soup.find_all("section", id=re.compile(r"bye-l(?:aw|ow)-(?:no-)?", re.IGNORECASE)):
        chapter = get_chapter(section)
        for heading in section.find_all("h4"):
            heading_text = clean_text(heading.get_text(" ", strip=True))
            parsed = parse_heading(heading_text)
            if not parsed:
                continue

            bylaw_number, subsection, title = parsed
            if not bylaw_number or (subsection and not re.fullmatch(r"[a-z]", subsection)):
                continue
            official_text = sibling_text_until_next_bylaw(heading)
            if not official_text or len(official_text) < 10:
                continue
            if not subsection and re.search(rf"bye\s*law\s*no\.?\s*{bylaw_number}\s*\(", official_text, re.IGNORECASE):
                continue

            full_code = f"{bylaw_number}({subsection})" if subsection else bylaw_number
            records.append(
                {
                    "chapter": chapter,
                    "bylaw_number": bylaw_number,
                    "subsection": subsection,
                    "full_code": full_code,
                    "title": title or f"Bye Law No {full_code}",
                    "official_text": official_text,
                    "keywords": extract_keywords(title, official_text),
                    "source_url": f"{url}#bye-law-{bylaw_number}",
                }
            )
    return records


def dedupe(records: list[dict[str, object]]) -> list[dict[str, object]]:
    by_key: dict[tuple[str, str], dict[str, object]] = {}
    duplicate_codes: set[str] = set()
    for record in records:
        key = (str(record["bylaw_number"]), str(record["subsection"]))
        current = by_key.get(key)
        if current is not None:
            duplicate_codes.add(str(record["full_code"]))
        if current is None or len(str(record["official_text"])) > len(str(current["official_text"])):
            by_key[key] = record
    if duplicate_codes:
        print(f"duplicate_full_code={sorted(duplicate_codes)}")
    return sorted(
        by_key.values(),
        key=lambda item: (int(str(item["bylaw_number"])), str(item["subsection"])),
    )


def scrape() -> list[dict[str, object]]:
    session = requests.Session()
    session.headers.update({"User-Agent": "LegalSituationAnalyzer/1.0"})
    records: list[dict[str, object]] = []
    for url in discover_pages(session):
        records.extend(parse_page(session, url))
    records = dedupe(records)
    OUTPUT_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"pages={len(discover_pages(session))}")
    print(f"records={len(records)}")
    return records


if __name__ == "__main__":
    scrape()
