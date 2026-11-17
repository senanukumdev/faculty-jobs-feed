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

TARGET_COUNTRY_KEYWORDS = {
    "india": "India", "chennai": "India", "bengaluru": "India", "delhi": "India", "mumbai": "India",
    "uae": "UAE", "dubai": "UAE", "abu dhabi": "UAE", "sharjah": "UAE",
    "saudi arabia": "Saudi Arabia", "riyadh": "Saudi Arabia", "oman": "Oman", "muscat": "Oman",
    "qatar": "Qatar", "doha": "Qatar", "kuwait": "Kuwait", "bahrain": "Bahrain",
    "uzbekistan": "Uzbekistan", "samarkand": "Uzbekistan", "tashkent": "Uzbekistan",
    "kazakhstan": "Kazakhstan", "kyrgyzstan": "Kyrgyzstan",
    "kenya": "Kenya", "nairobi": "Kenya", "nigeria": "Nigeria", "ethiopia": "Ethiopia",
    "south africa": "South Africa", "egypt": "Egypt", "ghana": "Ghana", "rwanda": "Rwanda",
    "singapore": "Singapore", "malaysia": "Malaysia", "japan": "Japan",
    "south korea": "South Korea", "thailand": "Thailand", "vietnam": "Vietnam", "indonesia": "Indonesia"
}

RSS_SOURCES = [
    {"url": "https://www.facultyplus.com/feed/", "country": "India", "subject": "General", "require_match": False},
    {"url": "https://www.facultyplus.com/category/engineering/cse/feed/", "country": "India", "subject": "Computer Science", "require_match": False},
    {"url": "https://www.facultyplus.com/category/engineering/feed/", "country": "India", "subject": "Engineering", "require_match": False},
    {"url": "https://news.google.com/rss/search?q=faculty+recruitment+professor+India+OR+UAE+OR+Oman+OR+Uzbekistan+OR+Kenya&hl=en-IN&gl=IN&ceid=IN:en", "country": "India", "subject": "General", "require_match": False},
    {"url": "https://news.google.com/rss/search?q=%22assistant+professor%22+OR+%22lecturer%22+university+Gulf+OR+Africa+OR+Singapore+OR+Malaysia+-China&hl=en-IN&gl=IN&ceid=IN:en", "country": "", "subject": "General", "require_match": True},
    {"url": "https://www.higheredjobs.com/search/rss.cfm?JobCat=108", "country": "", "subject": "Life Sciences", "require_match": True},
    {"url": "https://www.higheredjobs.com/search/rss.cfm?JobCat=120", "country": "", "subject": "Engineering", "require_match": True},
]

def is_active(deadline_str: str) -> bool:
    try:
        return datetime.strptime(deadline_str, "%Y-%m-%d").date() >= datetime.today().date()
    except ValueError:
        return False

def detect_country(text: str, default_country: str) -> str:
    lower = text.lower()
    for kw, country_name in TARGET_COUNTRY_KEYWORDS.items():
        if kw in lower:
            return country_name
    return default_country

def load_existing_jobs(path="jobs.json"):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [j for j in json.load(f) if is_active(j.get("deadline", ""))]
    except Exception:
        return []

def fetch_rss_source(source):
    resp = requests.get(source["url"], timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    collected = []

    for item in root.findall("./channel/item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        raw_desc = item.findtext("description") or ""
        clean_desc = BeautifulSoup(raw_desc, "html.parser").get_text(" ", strip=True)[:220]
        combined = f"{title} {clean_desc}"

        if not title or not link:
            continue
        if not any(k in combined.lower() for k in ALLOWED_KEYWORDS):
            continue
        if any(c in combined.lower() for c in EXCLUDED_COUNTRIES):
            continue

        country = detect_country(combined, source["country"])
        if source["require_match"] and not country:
            continue

        pub_raw = item.findtext("pubDate")
        try:
            posted_dt = parsedate_to_datetime(pub_raw).date()
        except Exception:
            posted_dt = datetime.today().date()

        deadline_dt = posted_dt + timedelta(days=21)
        job_id = hashlib.md5(link.encode("utf-8")).hexdigest()[:10]

        collected.append({
            "id": f"job-{job_id}",
            "title": title,
            "institution": "See Official Notice",
            "city": "",
            "state": "",
            "country": country,
            "subjectArea": source["subject"],
            "postedDate": posted_dt.strftime("%Y-%m-%d"),
            "deadline": deadline_dt.strftime("%Y-%m-%d"),
            "description": clean_desc or "Click Apply to view the official notice.",
            "applyUrl": link
        })
    return collected

if __name__ == "__main__":
    existing = load_existing_jobs("jobs.json")
    seen_urls = {j.get("applyUrl") for j in existing}

    for src in RSS_SOURCES:
        try:
            found = fetch_rss_source(src)
            print(f"{src['url']} -> found {len(found)} jobs")
            for job in found:
                if job["applyUrl"] not in seen_urls and is_active(job["deadline"]):
                    existing.append(job)
                    seen_urls.add(job["applyUrl"])
        except Exception as e:
            print(f"Warning for {src['url']}: {e}")

    existing.sort(key=lambda j: j.get("postedDate", ""), reverse=True)

    with open("jobs.json", "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"Total active jobs in jobs.json: {len(existing)}")
