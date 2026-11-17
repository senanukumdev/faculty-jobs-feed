import hashlib
import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

ALLOWED_KEYWORDS = [
    "research assistant", "teaching assistant", "lecturer",
    "assistant professor", "associate professor", "professor",
    "faculty", "teaching", "academic", "fellow"
]
EXCLUDED_COUNTRIES = {"china", "prc", "people's republic of china", "beijing", "shanghai"}

TARGET_COUNTRY_KEYWORDS = {
    "india": "India", "tamil nadu": "India", "karnataka": "India", "maharashtra": "India",
    "kerala": "India", "telangana": "India", "chennai": "India", "bengaluru": "India",
    "delhi": "India", "mumbai": "India", "hyderabad": "India", "pune": "India",
    "uae": "UAE", "united arab emirates": "UAE", "dubai": "UAE", "abu dhabi": "UAE", "sharjah": "UAE",
    "saudi arabia": "Saudi Arabia", "riyadh": "Saudi Arabia", "jeddah": "Saudi Arabia",
    "oman": "Oman", "muscat": "Oman", "qatar": "Qatar", "doha": "Qatar",
    "kuwait": "Kuwait", "bahrain": "Bahrain",
    "uzbekistan": "Uzbekistan", "samarkand": "Uzbekistan", "tashkent": "Uzbekistan",
    "kazakhstan": "Kazakhstan", "kyrgyzstan": "Kyrgyzstan",
    "kenya": "Kenya", "nairobi": "Kenya", "nigeria": "Nigeria", "ethiopia": "Ethiopia",
    "south africa": "South Africa", "egypt": "Egypt", "ghana": "Ghana", "rwanda": "Rwanda", "morocco": "Morocco",
    "singapore": "Singapore", "malaysia": "Malaysia", "japan": "Japan",
    "south korea": "South Korea", "thailand": "Thailand", "vietnam": "Vietnam", "indonesia": "Indonesia"
}

CITY_STATE_MAP = {
    "chennai": ("Chennai", "Tamil Nadu"), "coimbatore": ("Coimbatore", "Tamil Nadu"),
    "trichy": ("Tiruchirappalli", "Tamil Nadu"), "bengaluru": ("Bengaluru", "Karnataka"),
    "hyderabad": ("Hyderabad", "Telangana"), "mumbai": ("Mumbai", "Maharashtra"),
    "delhi": ("New Delhi", "Delhi"), "dubai": ("Dubai", "Dubai"), "abu dhabi": ("Abu Dhabi", "Abu Dhabi"),
    "muscat": ("Muscat", "Muscat"), "doha": ("Doha", "Doha"), "riyadh": ("Riyadh", "Riyadh"),
    "samarkand": ("Samarkand", "Samarkand"), "nairobi": ("Nairobi", "Nairobi"),
    "singapore": ("Singapore", "Singapore"), "kuala lumpur": ("Kuala Lumpur", "Kuala Lumpur")
}

SUBJECT_KEYWORDS = {
    "Computer Science": ["computer science", "cse", "data science", "artificial intelligence", "software", "computing"],
    "Engineering": ["engineering", "mechanical", "civil", "electrical", "electronics", "ece", "eee"],
    "Life Sciences": ["biology", "biotechnology", "life science", "biochemistry", "medicine", "pharmacy", "nursing"],
    "Management": ["management", "business", "mba", "commerce", "economics", "finance", "accounting", "marketing"],
    "Physics": ["physics", "chemistry", "mathematics", "maths", "statistics"]
}

RSS_SOURCES = [
    {"source": "FacultyPlus", "url": "https://www.facultyplus.com/feed/", "country": "India", "subject": "General"},
    {"source": "FacultyPlus", "url": "https://www.facultyplus.com/category/engineering/cse/feed/", "country": "India", "subject": "Computer Science"},
    {"source": "FacultyPlus", "url": "https://www.facultyplus.com/category/engineering/feed/", "country": "India", "subject": "Engineering"},
]

HTML_SOURCES = [
    # Abroad job boards
    {"source": "THEunijobs", "url": "https://www.timeshighereducation.com/unijobs/listings/middle-east/", "href_match": "/unijobs/listing/", "country": "UAE", "require_match": False},
    {"source": "THEunijobs", "url": "https://www.timeshighereducation.com/unijobs/listings/asia/", "href_match": "/unijobs/listing/", "country": "", "require_match": True},
    {"source": "jobs.ac.uk", "url": "https://www.jobs.ac.uk/categories/jobs-in-the-united-arab-emirates/1", "href_match": "/job/", "country": "UAE", "require_match": False},
    {"source": "AcademicPositions", "url": "https://academicpositions.com/find-jobs", "href_match": "/ad/", "country": "", "require_match": True},
    {"source": "AKADEUS", "url": "https://akadeus.com/", "href_match": "/announcement/", "country": "", "require_match": True},
    # Indian portals (ranked above FacultyPlus)
    {"source": "ServiceSetu", "url": "https://www.servicesetu.org/jobs/faculty", "href_match": "servicesetu.org/", "country": "India", "require_match": False},
    {"source": "UGC", "url": "https://curec.samarth.ac.in/index.php/search/site/search", "href_match": "curec.samarth.ac.in", "country": "India", "require_match": False},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9"
}

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

def detect_city_state(text: str):
    lower = text.lower()
    for kw, (city, state) in CITY_STATE_MAP.items():
        if kw in lower:
            return city, state
    return "", ""

def detect_subject(text: str, default_subject: str) -> str:
    if default_subject != "General":
        return default_subject
    lower = text.lower()
    for subject, kws in SUBJECT_KEYWORDS.items():
        if any(k in lower for k in kws):
            return subject
    return "General"

def make_job(source_name, title, link, desc, country, city, state, subject, posted_dt):
    deadline_dt = posted_dt + timedelta(days=21)
    job_id = hashlib.md5(link.encode("utf-8")).hexdigest()[:10]
    return {
        "id": f"job-{job_id}",
        "source": source_name,
        "title": title[:160],
        "institution": source_name,
        "city": city,
        "state": state,
        "country": country,
        "subjectArea": subject,
        "postedDate": posted_dt.strftime("%Y-%m-%d"),
        "deadline": deadline_dt.strftime("%Y-%m-%d"),
        "description": desc or f"Click Apply to view the full listing on {source_name}.",
        "applyUrl": link
    }

def fetch_rss_source(src):
    resp = requests.get(src["url"], timeout=20, headers=HEADERS)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)
    collected = []
    for item in root.findall("./channel/item")[:25]:
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        clean_desc = BeautifulSoup(item.findtext("description") or "", "html.parser").get_text(" ", strip=True)[:220]
        combined = f"{title} {clean_desc}"
        if not title or not link:
            continue
        if not any(k in combined.lower() for k in ALLOWED_KEYWORDS):
            continue
        if any(c in combined.lower() for c in EXCLUDED_COUNTRIES):
            continue
        country = detect_country(combined, src["country"])
        city, state = detect_city_state(combined)
        subject = detect_subject(combined, src["subject"])
        try:
            posted_dt = parsedate_to_datetime(item.findtext("pubDate")).date()
        except Exception:
            posted_dt = datetime.today().date()
        collected.append(make_job(src["source"], title, link, clean_desc, country, city, state, subject, posted_dt))
    return collected

def fetch_html_source(src):
    resp = requests.get(src["url"], timeout=20, headers=HEADERS)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    collected = []
    seen = set()
    today_dt = datetime.today().date()

    for a in soup.find_all("a", href=True):
        href = urljoin(src["url"], a["href"].strip())
        if src["href_match"] not in href or href in seen or href == src["url"]:
            continue
        title = a.get_text(" ", strip=True)
        if len(title) < 12:
            continue
        parent_text = a.parent.get_text(" ", strip=True) if a.parent else title
        combined = f"{title} {parent_text}"
        if not any(k in combined.lower() for k in ALLOWED_KEYWORDS):
            continue
        if any(c in combined.lower() for c in EXCLUDED_COUNTRIES):
            continue
        country = detect_country(combined, src["country"])
        if src["require_match"] and not country:
            continue
        city, state = detect_city_state(combined)
        subject = detect_subject(combined, "General")
        seen.add(href)
        collected.append(make_job(src["source"], title, href, parent_text[:220], country, city, state, subject, today_dt))
        if len(collected) >= 20:
            break
    return collected

def load_existing_jobs(path="jobs.json"):
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [j for j in json.load(f) if is_active(j.get("deadline", ""))]
    except Exception:
        return []

def sort_priority(job):
    country = (job.get("country") or "").strip().lower()
    source = (job.get("source") or "").strip().lower()
    if country and country != "india":
        tier = 3  # Foreign jobs first
    elif source != "facultyplus":
        tier = 2  # UGC / ServiceSetu middle
    else:
        tier = 1  # FacultyPlus lower
    return (tier, job.get("postedDate", ""))

if __name__ == "__main__":
    existing = load_existing_jobs("jobs.json")
    seen_urls = {j.get("applyUrl") for j in existing}

    for src in HTML_SOURCES + RSS_SOURCES:
        try:
            found = fetch_rss_source(src) if "feed" in src["url"] else fetch_html_source(src)
            print(f"{src['source']} ({src['url']}) -> found {len(found)} jobs")
            for job in found:
                if job["applyUrl"] not in seen_urls and is_active(job["deadline"]):
                    existing.append(job)
                    seen_urls.add(job["applyUrl"])
        except Exception as e:
            print(f"Warning for {src['source']}: {e}")
        time.sleep(2)

    existing.sort(key=sort_priority, reverse=True)

    with open("jobs.json", "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"Total active jobs in jobs.json: {len(existing)}")
