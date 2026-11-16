import json
from datetime import datetime
import requests
from bs4 import BeautifulSoup

ALLOWED_FACULTY_KEYWORDS = [
    "research assistant", "teaching assistant", "lecturer",
    "assistant professor", "associate professor", "professor"
]

EXCLUDED_COUNTRIES = {"china", "prc", "people's republic of china"}

def is_valid_job(title: str, country: str, deadline: str) -> bool:
    title_lower = title.lower()
    if not any(k in title_lower for k in ALLOWED_FACULTY_KEYWORDS):
        return False
    if country.strip().lower() in EXCLUDED_COUNTRIES:
        return False
    try:
        return datetime.strptime(deadline, "%Y-%m-%d").date() >= datetime.today().date()
    except ValueError:
        return False

def scrape_facultyplus_sample():
    # Starter example: fetch an announcements page and extract links/titles
    url = "https://www.facultyplus.com/"
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(resp.text, "html.parser")

    collected = []
    for idx, link in enumerate(soup.select("h2.entry-title a")[:20]):
        title = link.get_text(strip=True)
        apply_url = link["href"]
        job = {
            "id": f"fp-{idx}",
            "title": title,
            "institution": "See Official Notice",
            "city": "",
            "state": "",
            "country": "India",
            "subjectArea": "General",
            "postedDate": datetime.today().strftime("%Y-%m-%d"),
            "deadline": "2026-12-31",  # Replace with parsed deadline from detail page
            "description": "Faculty position aggregated from FacultyPlus.",
            "applyUrl": apply_url
        }
        if is_valid_job(job["title"], job["country"], job["deadline"]):
            collected.append(job)
    return collected

if __name__ == "__main__":
    jobs = scrape_facultyplus_sample()
    with open("jobs.json", "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(jobs)} active faculty jobs to jobs.json")
