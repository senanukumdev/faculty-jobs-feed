import hashlib
import json
import os
import time
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
EXCLUDED_COUNTRIES = {"china", "prc", "people's republic of china", "beijing", "shanghai"}

TARGET_COUNTRY_KEYWORDS = {
    "india": "India", "tamil nadu": "India", "karnataka": "India", "maharashtra": "India",
    "kerala": "India", "telangana": "India", "gujarat": "India", "west bengal": "India",
    "chennai": "India", "bengaluru": "India", "bangalore": "India", "delhi": "India",
    "mumbai": "India", "hyderabad": "India", "pune": "India", "kolkata": "India", "trichy": "India",
    "uae": "UAE", "dubai": "UAE", "abu dhabi": "UAE", "sharjah": "UAE",
    "saudi arabia": "Saudi Arabia", "riyadh": "Saudi Arabia", "jeddah": "Saudi Arabia",
    "oman": "Oman", "muscat": "Oman", "qatar": "Qatar", "doha": "Qatar",
    "kuwait": "Kuwait", "bahrain": "Bahrain",
    "uzbekistan": "Uzbekistan", "samarkand": "Uzbekistan", "tashkent": "Uzbekistan",
    "kazakhstan": "Kazakhstan", "almaty": "Kazakhstan", "astana": "Kazakhstan", "kyrgyzstan": "Kyrgyzstan",
    "kenya": "Kenya", "nairobi": "Kenya", "nigeria": "Nigeria", "lagos": "Nigeria",
    "ethiopia": "Ethiopia", "addis ababa": "Ethiopia", "south africa": "South Africa",
    "egypt": "Egypt", "cairo": "Egypt", "ghana": "Ghana", "rwanda": "Rwanda",
    "singapore": "Singapore", "malaysia": "Malaysia", "kuala lumpur": "Malaysia",
    "japan": "Japan", "tokyo": "Japan", "south korea": "South Korea", "seoul": "South Korea",
    "thailand": "Thailand", "vietnam": "Vietnam", "indonesia": "Indonesia"
}

CITY_STATE_MAP = {
    "chennai": ("Chennai", "Tamil Nadu"), "coimbatore": ("Coimbatore", "Tamil Nadu"),
    "trichy": ("Tiruchirappalli", "Tamil Nadu"), "madurai": ("Madurai", "Tamil Nadu"),
    "salem": ("Salem", "Tamil Nadu"), "vellore": ("Vellore", "Tamil Nadu"),
    "bengaluru": ("Bengaluru", "Karnataka"), "bangalore": ("Bengaluru", "Karnataka"),
    "hyderabad": ("Hyderabad", "Telangana"), "mumbai": ("Mumbai", "Maharashtra"),
    "pune": ("Pune", "Maharashtra"), "delhi": ("New Delhi", "Delhi"),
    "kolkata": ("Kolkata", "West Bengal"), "kochi": ("Kochi", "Kerala"),
    "dubai": ("Dubai", "Dubai"), "abu dhabi": ("Abu Dhabi", "Abu Dhabi"),
    "muscat": ("Muscat", "Muscat"), "doha": ("Doha", "Doha"), "riyadh": ("Riyadh", "Riyadh"),
    "samarkand": ("Samarkand", "Samarkand"), "tashkent": ("Tashkent", "Tashkent"),
    "nairobi": ("Nairobi", "Nairobi"), "singapore": ("Singapore", "Singapore"),
    "kuala lumpur": ("Kuala Lumpur", "Kuala Lumpur")
}

SUBJECT_KEYWORDS = {
    "Computer Science": ["computer science", "cse", "data science", "artificial intelligence", "software", "computing", "it "],
    "Engineering": ["engineering", "mechanical", "civil", "electrical", "electronics", "ece", "eee", "aerospace"],
    "Life Sciences": ["biology", "biotechnology", "life science", "biochemistry", "medicine", "pharmacy", "nursing"],
    "Management": ["management", "business", "mba", "commerce", "economics", "finance", "accounting", "marketing"],
    "Physics": ["physics", "chemistry", "mathematics", "maths", "statistics"]
}

RSS_SOURCES = [
    # India (FacultyPlus)
    {"url": "https://www.facultyplus.com/feed/", "country": "India", "subject": "General", "require_match": False},
    {"url": "https://www.facultyplus.com/category/engineering/cse/feed/", "country": "India", "subject": "Computer Science", "require_match": False},
    {"url": "https://www.facultyplus.com/category/engineering/feed/", "country": "India", "subject": "Engineering", "require_match": False},
    # India Universities & Portals (Google News RSS)
    {"url": "https://news.google.com/rss/search?q=%22faculty+recruitment%22+OR+%22assistant+professor%22+India+university&hl=en-IN&gl=IN&ceid=IN:en", "country": "India", "subject": "General", "require_match": False},
    # Gulf Countries (UAE, Oman, Qatar, Saudi Arabia, Kuwait, Bahrain)
    {"url": "https://news.google.com/rss/search?q=(professor+OR+lecturer+OR+faculty)+university+(UAE+OR+Dubai+OR+Oman+OR+Qatar+OR+%22Saudi+Arabia%22)&hl=en-IN&gl=IN&ceid=IN:en", "country": "", "subject": "General", "require_match": True},
    # Central Asia & Africa
    {"url": "https://news.google.com/rss/search?q=(professor+OR+lecturer+OR+faculty)+university+(Uzbekistan+OR+Kazakhstan+OR+Kenya+OR+Nigeria+OR+%22South+Africa%22+OR+Ethiopia)&hl=en-IN&gl=IN&ceid=IN:en", "country": "", "subject": "General", "require_match": True},
    # Asia excluding China
    {"url": "https://news.google.com/rss/search?q=(%22assistant+professor%22+OR+lecturer+OR+%22research+assistant%22)+university+(Singapore+OR+Malaysia+OR+Japan+OR+%22South+Korea%22)+-China&hl=en-IN&gl=IN&ceid=IN:en", "country": "", "subject": "General", "require_match": True},
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

    for item in root.findall("./channel/item")[:20]:
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

        city, state = detect_city_state(combined)
        subject = detect_subject(combined, source["subject"])

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
            "city": city,
            "state": state,
            "country": country,
            "subjectArea": subject,
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
        time.sleep(4)

    existing.sort(key=lambda j: j.get("postedDate", ""), reverse=True)

    with open("jobs.json", "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)

    print(f"Total active jobs in jobs.json: {len(existing)}")
