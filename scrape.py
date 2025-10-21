import time
import csv
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

BASE_URL = "https://www.elempleo.com/cr/ofertas-empleo/"
API_URL = "https://www.elempleo.com/cr/api/joboffers/getjoboffer?jobOfferId={}"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/119.0 Safari/537.36"
    )
}


# ---------------------------------------------------------------
# STEP 1: Collect all jobOffer IDs (data-joboffer)
# ---------------------------------------------------------------
def get_job_ids_with_playwright(max_scrolls=12, scroll_delay=1.5):
    """Scroll through the Elempleo listings and extract all data-joboffer IDs."""
    print("🚀 Launching browser to collect job IDs...")
    job_ids = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent=HEADERS["User-Agent"])
        page = context.new_page()

        try:
            page.goto(BASE_URL, wait_until="load", timeout=90000)
            time.sleep(5)

            for scroll in range(1, max_scrolls + 1):
                page.mouse.wheel(0, 50000)
                time.sleep(scroll_delay)

                html = page.content()
                soup = BeautifulSoup(html, "html.parser")

                for btn in soup.find_all("button", attrs={"data-joboffer": True}):
                    job_ids.add(btn["data-joboffer"])

                print(f"  ✓ Scroll {scroll}: {len(job_ids)} unique IDs")

            print(f"\n✅ Total job IDs found: {len(job_ids)}")

        except PlaywrightTimeout:
            print("⚠️ Timeout reached while loading the page. Try increasing timeout.")
        except Exception as e:
            print(f"❌ Error while collecting IDs: {e}")
        finally:
            browser.close()

    return list(job_ids)


# ---------------------------------------------------------------
# STEP 2: Fetch job details via JSON API
# ---------------------------------------------------------------
def get_job_details(job_id):
    """Fetch one job's details using Elempleo API."""
    try:
        url = API_URL.format(job_id)
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code == 200:
            data = r.json()
            return {
                "id": data.get("id"),
                "title": data.get("title"),
                "company": data.get("companyName"),
                "location": data.get("city"),
                "salary": data.get("salaryInfo"),
                "publish_date": data.get("publishDateInfo"),
                "description": clean_html(data.get("description", "")),
                "url": data.get("jobOfferUrl"),
            }
        else:
            print(f"⚠️ Skipped job {job_id} (status {r.status_code})")
    except Exception as e:
        print(f"❌ Error fetching job {job_id}: {e}")
    return None


def clean_html(raw_html):
    """Remove HTML tags from description."""
    return re.sub(r"<[^>]+>", "", raw_html or "").strip()


# ---------------------------------------------------------------
# STEP 3: Save all jobs to CSV
# ---------------------------------------------------------------
def save_to_csv(jobs):
    if not jobs:
        print("⚠️ No jobs to save.")
        return

    filename = f"elempleo_jobs_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    with open(filename, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=jobs[0].keys())
        writer.writeheader()
        writer.writerows(jobs)

    print(f"💾 Saved {len(jobs)} jobs to {filename}")


# ---------------------------------------------------------------
# MAIN SCRAPER LOGIC
# ---------------------------------------------------------------
def main():
    print("\n🚀 Starting Elempleo JSON API Scraper (Final Version)...")

    # Step 1: Collect job IDs
    job_ids = get_job_ids_with_playwright(max_scrolls=15, scroll_delay=1.5)
    if not job_ids:
        print("⚠️ No job IDs found. Please check site structure.")
        return

    # Step 2: Fetch details via API
    jobs = []
    for idx, job_id in enumerate(job_ids, 1):
        job = get_job_details(job_id)
        if job:
            jobs.append(job)
            print(f"[{idx}/{len(job_ids)}] ✓ {job['title'][:60]}")
        time.sleep(0.3)

    print(f"\n✅ Total jobs collected: {len(jobs)}")

    # Step 3: Save results
    save_to_csv(jobs)
    print("\n🎉 Scraping complete!")


if __name__ == "__main__":
    main()
