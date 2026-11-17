import hashlib
import json
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
import requests
from bs4 import BeautifulSoup

ALLOWED_KEYWORDS = [
    "research assistant", "teaching assistant", "lecturer",
    "assistant professor", "associate professor", "professor",
    "faculty", "teaching", "academic"
]
EXCLUDED_COUNTRIES = {"china", "prc", "people's republic of china"}

def is_active(deadline_str: str) -> bool:
    try:
        return datetime.strptime(deadline_str, "%Y-%m-%d").date() >= datetime.today().date()
    except ValueError:
        return False

def load_existing_jobs(path="jobs.json"):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [j for j in data if is_active(j.get("deadline", ""))]
    except Exception:
        return []

def fetch_facultyplus_rss():
    url = "https://www.facultyplus.com/feed/"
    resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()

    root = ET.fromstring(resp.content)
    collected = []

    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        raw_desc = item.findtext("description") or ""
        clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(" ", strip=True)[:220]

        if not title or not link:
            continue
        if not any(k in title.lower() or k in clean_desc.lower() for k in ALLOWED_KEYWORDS):
            continue
        if any(c in title.lower() or c in clean_desc.lower() for c in EXCLUDED_COUNTRIES):
            continue

        pub_raw = item.findtext("pubDate")
        try:
            posted_dt = parsedate_to_datetime(pub_raw).date()
        except Exception:
            posted_dt = datetime.today().date()

        deadline_dt = posted_dt + timedelta(days=21)
        job_id = hashlib.md5(link.encode("utf-8")).hexdigest()[:10]

        collected.append({
            "id": f"fp-{job_id}",
            "title": title,
            "institution": "See Official Notice",
            "city": "",
            "state": "",
            "country": "India",
            "subjectArea": "General",
            "postedDate": posted_dt.strftime("%Y-%m-%d"),
            "deadline": deadline_dt.strftime("%Y-%m-%d"),
            "description": clean_desc or "Click Apply to view the official notice.",
            "applyUrl": link
        })
    return collected

if __name__ == "__main__":
    existing = load_existing_jobs("jobs.json")
    seen_urls = {j.get("applyUrl") for j in existing}

    try:
        new_jobs = fetch_facultyplus_rss()
    except Exception as e:
        print(f"Fetch warning: {e}")
        new_jobs = []

    for job in new_jobs:
        if job["applyUrl"] not in seen_urls and is_active(job["deadline"]):
            existing.append(job)
            seen_urls.add(job["applyUrl"])

    existing.sort(key=lambda j: j.get("postedDate", ""), reverse=True)

    with open("jobs.json", "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"Total active jobs in jobs.json: {len(existing)}")
