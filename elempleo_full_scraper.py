# elempleo_full_scraper.py
# Combined Elempleo scraper
#  - collects job IDs by scrolling with Playwright
#  - fetches basic info via API for each ID
#  - visits each detail page to enrich fields
#  - saves everything to a single CSV
#
# Usage:
#   pip install playwright requests beautifulsoup4 lxml
#   playwright install
#   python elempleo_full_scraper.py

import time
import csv
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# -----------------------------
# CONFIG
# -----------------------------
LISTINGS_URL = "https://www.elempleo.com/cr/ofertas-empleo/"
DETAIL_BASE_URL = "https://www.elempleo.com/cr/ofertas-trabajo/"
API_URL = "https://www.elempleo.com/cr/api/joboffers/getjoboffer?jobOfferId={}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0 Safari/537.36"
    )
}
# CSV fields: union of API fields + detail-only fields
CSV_FIELDS = [
    # detail page fields
    "featured_image", "featured", "filled", "urgent",
    "category", "type", "tag", "expiry_date", "gender",
    "apply_type", "apply_url", "apply_email",
    "salary_type", "max_salary",
    "experience", "career_level", "qualification", "video_url", "photos",
    "application_deadline_date", "address", "map_location"
]

# -----------------------------
# HELPERS
# -----------------------------
def clean_html(raw_html):
    if not raw_html:
        return ""
    return re.sub(r"<[^>]+>", "", raw_html).strip()

def extract_text(soup, selector):
    el = soup.select_one(selector)
    return el.get_text(strip=True) if el else ""

# -----------------------------
# STEP 1: collect job IDs by scrolling
# -----------------------------
def get_job_ids_with_playwright(max_scrolls=15, scroll_delay=1.5):
    print("collecting job IDs via Playwright")
    job_ids = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=HEADERS["User-Agent"])
        page = context.new_page()
        try:
            page.goto(LISTINGS_URL, wait_until="load", timeout=90000)
            time.sleep(3)
            for scroll in range(1, max_scrolls + 1):
                page.mouse.wheel(0, 50000)
                time.sleep(scroll_delay)
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")
                # buttons that contain data-joboffer
                for btn in soup.find_all("button", attrs={"data-joboffer": True}):
                    job_ids.add(btn["data-joboffer"])
                print(f"  scroll {scroll} -> {len(job_ids)} unique ids")
        except PlaywrightTimeout:
            print("timeout while collecting ids, continuing with what we have")
        except Exception as e:
            print("error collecting ids:", e)
        finally:
            browser.close()
    print("total job ids found:", len(job_ids))
    return list(job_ids)

# -----------------------------
# STEP 2: get basic info from API
# -----------------------------
# def get_job_basic_api(job_id):
    try:
        url = API_URL.format(job_id)
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return {
                "id": data.get("id") or job_id,
                "title": data.get("title") or "",
                "company": data.get("companyName") or "",
                "location": data.get("city") or "",
                "salary": data.get("salaryInfo") or "",
                "publish_date": data.get("publishDateInfo") or "",
                "description": clean_html(data.get("description", "") or ""),
                "url": data.get("jobOfferUrl") or f"{DETAIL_BASE_URL}{job_id}"
            }
        else:
            print(f"api returned status {r.status_code} for id {job_id}")
    except Exception as e:
        print("error fetching api for", job_id, e)
    return {"id": job_id, "title": "", "company": "", "location": "", "salary": "", "publish_date": "", "description": "", "url": f"{DETAIL_BASE_URL}{job_id}"}

# -----------------------------
# STEP 3: visit detail page to enrich
# -----------------------------
def enrich_with_detail(page, job):
    # ensure default keys exist
    for k in CSV_FIELDS:
        if k not in job:
            job[k] = ""

    job_url = job.get("url") or f"{DETAIL_BASE_URL}{job.get('id')}"
    try:
        page.goto(job_url, wait_until="load", timeout=60000)
        time.sleep(2)
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Featured image
        img = soup.select_one("img[src*='empleo'], img[src*='ofertas']")
        if img and img.get("src"):
            job["featured_image"] = img["src"]

        # Description (prefer detail page if present)
        # detail_desc = extract_text(soup, ".description-block, article, [class*='detalle'], .job-description")
        # if detail_desc:
        #     job["description"] = detail_desc
        desc_container = soup.select_one(".description-block, article, [class*='detalle'], .job-description")
        if desc_container:
            # Get all text, keeping line breaks between <br> tags
            for br in desc_container.find_all("br"):
                br.replace_with("\n")
            detail_desc = desc_container.get_text(separator="\n", strip=True)
            job["description"] = detail_desc

        # Category / type
        job["category"] = extract_text(soup, ".category, [class*='categoria'], .breadcrumb li:last-child") or job.get("category", "")
        job["type"] = extract_text(soup, "[class*='tipo'], .employment-type") or job.get("type", "")

        # Salary parsing
        salary_text = extract_text(soup, "[class*='salario'], .js-joboffer-salary, .compensation") or job.get("salary", "")
        job["salary"] = salary_text
        if salary_text:
            numbers = re.findall(r"[\d,.]+", salary_text)
            if len(numbers) >= 1:
                job["salary_type"] = "monthly"
                job["max_salary"] = numbers[-1]

        # Location / address
        job["location"] = extract_text(soup, "[class*='ubicacion'], .js-joboffer-city, [itemprop='addressLocality']") or job.get("location", "")
        job["address"] = extract_text(soup, "[itemprop='streetAddress'], [class*='direccion']") or job["location"]

        # Dates
        job["application_deadline_date"] = extract_text(soup, "time, [class*='fecha'], [class*='publicado']") or job.get("application_deadline_date", "")
        job["expiry_date"] = job["application_deadline_date"] or job.get("expiry_date", "")

        # Experience / qualification
        job["experience"] = extract_text(soup, "[class*='experiencia'], .experience") or job.get("experience", "")
        job["qualification"] = extract_text(soup, "[class*='educacion'], [class*='formacion']") or job.get("qualification", "")
        job["career_level"] = extract_text(soup, "[class*='nivel'], .level") or job.get("career_level", "")

        # Apply email or url
        text_all = soup.get_text(" ", strip=True)
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text_all)
        if email_match:
            job["apply_email"] = email_match.group(0)
        link = soup.select_one("a[href*='apply'], a[href*='postulate'], a[href*='mailto:'], a.button.apply")
        if link and link.get("href"):
            job["apply_url"] = link["href"]
            if link.get("href").startswith("mailto:") and not job.get("apply_email"):
                job["apply_email"] = link.get("href").replace("mailto:", "")

        # Flags and placeholders
        job["featured"] = job.get("featured", "false")
        job["filled"] = job.get("filled", "false")
        job["urgent"] = job.get("urgent", "false")
        job["apply_type"] = "website" if job.get("apply_url") else ("email" if job.get("apply_email") else "")
        job["map_location"] = ""  # optional: could parse lat/lon if present in page

    except PlaywrightTimeout:
        print("timeout loading detail page", job_url)
    except Exception as e:
        print("error enriching", job_url, e)

    return job

# -----------------------------
# STEP 4: save to csv
# -----------------------------
def save_to_csv(jobs, filename=None):
    if not jobs:
        print("no jobs to save")
        return
    filename = filename or f"elempleo_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    # ensure all jobs have all fields in CSV_FIELDS
    for j in jobs:
        for f in CSV_FIELDS:
            if f not in j:
                j[f] = ""
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(jobs)
    print("saved", len(jobs), "jobs to", filename)

# -----------------------------
# MAIN
# -----------------------------
def main():
    print("starting combined elempleo scraper")
    job_ids = get_job_ids_with_playwright(max_scrolls=15, scroll_delay=1.5)
    if not job_ids:
        print("no ids found, aborting")
        return

    # Step: get base info from API
    print("fetching basic info from API for each id")
    jobs = []
    for idx, jid in enumerate(job_ids, 1):
        # base = get_job_basic_api(jid)
        # jobs.append(base)
        # print(f"[{idx}/{len(job_ids)}] api -> id {base.get('id')} title {base.get('title')[:60]}")

        # small delay so we don't hammer api too fast
        time.sleep(0.2)

    # Step: open playwright once and enrich each job
    print("opening browser to enrich detail pages")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=HEADERS["User-Agent"])
        page = context.new_page()
        for idx, job in enumerate(jobs, 1):
            print(f"[{idx}/{len(jobs)}] enriching id {job.get('id')}")
            enrich_with_detail(page, job)
            # small polite delay
            time.sleep(0.4)
        browser.close()

    # Save
    save_to_csv(jobs)
    print("done")

if __name__ == "__main__":
    main()
