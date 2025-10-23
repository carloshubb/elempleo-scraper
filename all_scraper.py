# elempleo_detail_scraper.py
# -----------------------------
# Automatically collects ALL job IDs from Elempleo (Costa Rica)
# and scrapes each job’s detail page with automatic pagination.
# -----------------------------

import time
import csv
import re
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------
BASE_URL = "https://www.elempleo.com/cr/ofertas-empleo/"
DETAIL_BASE_URL = "https://www.elempleo.com/cr/ofertas-trabajo/"

HEADERS = [
    "_job_featured_image","_job_title", "_job_featured", "_job_filled", "_job_urgent", "_job_description",
    "_job_category", "_job_type", "_job_tag", "_job_expiry_date", "_job_gender",
    "_job_apply_type", "_job_apply_url", "_job_apply_email",
    "_job_salary_type", "_job_salary", "_job_max_salary",
    "_job_experience", "_job_career_level", "_job_qualification", "_job_video_url", "_job_photos",
    "_job_application_deadline_date", "_job_address", "_job_location", "_job_map_location"
]

# ---------------------------------------------------------------
# 1️⃣ Automatically collect job IDs with pagination
# ---------------------------------------------------------------
def get_job_ids_with_playwright_auto(delay=2.5, max_pages=100):
    """Automatically navigate pages and collect all job IDs from Elempleo listings."""
    print("🚀 Launching browser to collect ALL job IDs (auto pagination)...")
    job_ids = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(BASE_URL, wait_until="networkidle", timeout=90000)
            time.sleep(delay)
            page_number = 1
            while True:
                print(f"🌍 Scraping listing page {page_number} …")
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")

                # Extract job-offer IDs
                buttons = soup.find_all("button", attrs={"data-joboffer": True})
                if not buttons:
                    print("⚠️ No job buttons found on page. Stopping.")
                    break
                for btn in buttons:
                    job_id = btn.get("data-joboffer")
                    if job_id:
                        job_ids.add(job_id)
                print(f"  ✓ Collected {len(job_ids)} unique job IDs so far.")

                # Try to find “Next” link
                next_link = None
                # Try different ways: link with text “Siguiente”, link with aria-label, or class
                anchor_candidates = page.locator("a")
                # loop through anchors to find one that likely is next
                found_next = False
                for i in range(anchor_candidates.count()):
                    a_elem = anchor_candidates.nth(i)
                    txt = a_elem.inner_text().strip()
                    if txt.lower() in ("siguiente", ">", "»", "next"):
                        next_link = a_elem
                        found_next = True
                        break
                if not found_next:
                    print("🚫 ‘Next’ link not found. Ending pagination.")
                    break

                # Click next
                print("➡️ Clicking next page …")
                next_link.click()
                time.sleep(delay)
                page_number += 1
                if page_number > max_pages:
                    print(f"⚠️ Reached max_pages = {max_pages}, stopping.")
                    break

            print(f"\n✅ Total job IDs collected: {len(job_ids)}")
        except Exception as e:
            print(f"❌ Error during pagination: {e}")
        finally:
            browser.close()
    return list(job_ids)

# ---------------------------------------------------------------
# 2️⃣ Helper function to extract text safely
# ---------------------------------------------------------------
def extract_text(soup, selector):
    el = soup.select_one(selector)
    if el:
        return el.get_text(strip=True)
    return ""

# ---------------------------------------------------------------
# 3️⃣ Scrape details for one job
# ---------------------------------------------------------------
def get_job_details(page, job_url):
    """Visit job URL and extract key fields"""
    job = {key: "" for key in HEADERS}
    try:
        page.goto(job_url, wait_until="load", timeout=60000)
        time.sleep(3)
        html = page.content()
        soup = BeautifulSoup(html, "html.parser")

        # Featured image
        img = soup.select_one("img[src*='empleo'], img[src*='ofertas']")
        if img:
            job["_job_featured_image"] = img["src"]

        # Description
        desc_container = soup.select_one(".description-block span")
        if desc_container:
            for br in desc_container.find_all("br"):
                br.replace_with("\n")

            parts = []
            for child in desc_container.children:
                if child.name == "p":
                    parts.append(child.get_text(strip=True))
                elif child.name == "ul":
                    for li in child.find_all("li"):
                        parts.append(f"• {li.get_text(strip=True)}")
                elif child.string and child.string.strip():
                    parts.append(child.string.strip())

            detail_desc = "\n".join(parts)
            detail_desc = re.sub(r"\n+", "\n", detail_desc)
            job["_job_description"] = detail_desc

        job["_job_title"] = extract_text(soup, ".category, [class*='categoria'], .breadcrumb li:last-child")
        job["_job_category"] = extract_text(soup, ".js-position-area")

        # Job type
        job_type = "Tiempo completo"
        span = soup.find("span")
        if span:
            text = span.get_text(strip=True).lower()
            if "medio tiempo" in text:
                job_type = "Medio tiempo"
            elif "remoto" in text:
                job_type = "Remoto"
        job["_job_type"] = job_type

        # Salary
        salary_text = extract_text(soup, "[class*='salario'], .js-joboffer-salary, .compensation")
        job["_job_salary"] = salary_text
        if salary_text:
            numbers = re.findall(r"[\d,.]+", salary_text)
            if len(numbers) >= 1:
                job["_job_salary_type"] = "Mensual"
                job["_job_max_salary"] = numbers[-1]

        # Location
        job["_job_location"] = extract_text(soup, "[class*='ubicacion'], .js-joboffer-city, [itemprop='addressLocality']")
        job["_job_address"] = job["_job_location"]

        # Dates
        expiry_date = datetime.today() + timedelta(days=30)
        job["_job_expiry_date"] = expiry_date.strftime("%Y-%m-%d")
        job["_job_application_deadline_date"] = expiry_date.strftime("%Y-%m-%d")

        # Experience
        data_spans = soup.select(".data-column span")
        for span in data_spans:
            text = span.get_text(strip=True)
            if "experiencia" in text.lower() or "años" in text.lower():
                job["_job_experience"] = text
                break

        # Qualification
        job["_job_qualification"] = extract_text(soup, "[class*='js-education-level'], [class*='formacion']")

        # Career level
        icon = soup.find("i", class_="fa fa-level-down fa-fw")
        if icon:
            span = icon.find_next("span")
            if span:
                job["_job_career_level"] = span.get_text(strip=True)

        # Email or apply URL
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", soup.get_text())
        if email_match:
            job["_job_apply_email"] = email_match.group(0)
        meta = soup.find("meta", attrs={"property": "og:url"})
        if meta and meta.get("content"):
            job["_job_apply_url"] = meta["content"]

        # Defaults
        job["_job_featured"] = "1"
        job["_job_filled"] = "0"
        job["_job_urgent"] = "0"
        job["_job_gender"] = ""
        job["_job_tag"] = "Costa Rica"
        job["_job_video_url"] = ""
        job["_job_photos"] = ""
        job["_job_map_location"] = ""
        job["_job_apply_type"] = "external"

        print(f"✅ Scraped job: {job['_job_title']}")
        return job

    except Exception as e:
        print(f"❌ Error scraping {job_url}: {e}")
        return job

# ---------------------------------------------------------------
# 4️⃣ MAIN SCRAPER
# ---------------------------------------------------------------
def main():
    print("\n🚀 Starting Elempleo Auto Job Scraper with Pagination...")

    # Step 1: Collect job IDs automatically
    job_ids = get_job_ids_with_playwright_auto(delay=2.5)
    if not job_ids:
        print("⚠️ No job IDs found.")
        return

    print(f"✅ Found {len(job_ids)} job IDs. Starting detail scraping...")

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for idx, job_id in enumerate(job_ids, 1):
            job_url = f"{DETAIL_BASE_URL}{job_id}"
            print(f"[{idx}/{len(job_ids)}] Scraping {job_url} ...")
            job_data = get_job_details(page, job_url)
            results.append(job_data)

        browser.close()

    # Step 2: Save results to CSV
    filename = f"elempleo_job_details_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n✅ Saved {len(results)} jobs to {filename}")
    print("🎉 Done!")


if __name__ == "__main__":
    main()
