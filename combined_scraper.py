"""
Costa Rica Job Scraper - DEBUGGED VERSION
With better waits, screenshots, and flexible selectors
"""

import csv
import time
import random
import re
from datetime import datetime
from playwright.sync_api import sync_playwright
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class JobScraper:
    """Unified job scraper with debugging"""
    
    FIELDS = [
        'source_site', 'title', 'company', 'description', 'category', 'type', 'tag',
        'featured', 'featured_image', 'filled', 'urgent',
        'expiry_date', 'application_deadline_date', 'posting_date',
        'location', 'address', 'map_location',
        'salary', 'salary_type', 'max_salary',
        'experience', 'career_level', 'qualification', 'gender',
        'apply_type', 'apply_url', 'apply_email',
        'video_url', 'photos', 'url'
    ]
    
    def __init__(self):
        self.jobs = []
        self.debug_mode = True
    
    def scrape_all_sites(self, max_per_site=20):
        """Scrape all 4 sites"""
        logger.info("\n" + "="*70)
        logger.info("COSTA RICA JOBS - DEBUGGED SCRAPER")
        logger.info("="*70 + "\n")
        
        with sync_playwright() as p:
            # Launch with better settings
            browser = p.chromium.launch(
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage'
                ]
            )
            
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='es-CR',
                timezone_id='America/Costa_Rica'
            )
            
            # Add stealth
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            page = context.new_page()
            
            try:
                # Scrape each site
                self.scrape_elempleo(page, max_per_site)
                self.scrape_computrabajo(page, max_per_site)
                self.scrape_indeed(page, max_per_site)
                self.scrape_jooble(page, max_per_site)
                
            except KeyboardInterrupt:
                logger.info("\n\nStopped by user")
            finally:
                time.sleep(3)
                browser.close()
        
        return self.jobs
    
    def _wait_and_debug(self, page, site_name):
        """Wait for page and take debug screenshot"""
        time.sleep(5)
        screenshot_path = f'debug_{site_name.replace(".", "_")}.png'
        page.screenshot(path=screenshot_path, full_page=True)
        logger.info(f"📸 Screenshot saved: {screenshot_path}")
        
        # Get page info
        title = page.title()
        logger.info(f"Page title: {title}")
        
        # Count common elements
        divs = page.locator('div').count()
        articles = page.locator('article').count()
        links = page.locator('a').count()
        logger.info(f"Page has: {divs} divs, {articles} articles, {links} links")
    
    def _find_elements_debug(self, page, selector_sets):
        """Try multiple selectors and log what's found"""
        for selectors in selector_sets:
            selector_str = ', '.join(selectors) if isinstance(selectors, list) else selectors
            try:
                count = page.locator(selector_str).count()
                if count > 0:
                    logger.info(f"  ✓ Found {count} elements with: {selector_str}")
                    return page.locator(selector_str).all()
                else:
                    logger.debug(f"  ✗ 0 elements with: {selector_str}")
            except Exception as e:
                logger.debug(f"  ✗ Error with {selector_str}: {e}")
        return []
    
    # ==================== ELEMPLEO.COM ====================
    
    def scrape_elempleo(self, page, max_jobs):
        site = 'elempleo.com'
        logger.info(f"\n{'='*70}")
        logger.info(f"SCRAPING: {site}")
        logger.info(f"{'='*70}")
        
        try:
            logger.info("Navigating to elempleo.com...")
            page.goto("https://www.elempleo.com/cr/ofertas-empleo/", 
                     wait_until='networkidle', 
                     timeout=60000)
            
            self._wait_and_debug(page, site)
            
            # Try to find job cards
            logger.info("Looking for job cards...")
            selector_sets = [
                ['.js-joboffer-result'],
                ['article'],
                ['[class*="result"]'],
                ['[class*="offer"]'],
                ['[class*="job"]'],
                ['div[class*="item"]'],
            ]
            
            cards = self._find_elements_debug(page, selector_sets)
            
            if not cards:
                logger.error("❌ No job cards found - check screenshot")
                return
            
            logger.info(f"✅ Found {len(cards)} job cards")
            
            count = 0
            for idx, card in enumerate(cards[:max_jobs], 1):
                try:
                    job = self._init_job(site)
                    
                    # Get all text for debugging
                    card_text = card.inner_text()
                    lines = [l.strip() for l in card_text.split('\n') if l.strip()]
                    
                    if len(lines) >= 2:
                        job['title'] = lines[0]
                        job['company'] = lines[1] if len(lines) > 1 else ''
                        
                        # Location often has "San José", "Heredia", etc
                        for line in lines:
                            if any(city in line for city in ['San José', 'Heredia', 'Cartago', 'Alajuela', 'Limón']):
                                job['location'] = line
                                break
                        
                        # Look for salary
                        for line in lines:
                            if '₡' in line or '$' in line or 'colones' in line.lower():
                                job['salary'] = line
                                break
                        
                        # Look for experience
                        exp_match = re.search(r'(\d+)\s*años?', card_text.lower())
                        if exp_match:
                            job['experience'] = f"{exp_match.group(1)} años"
                    
                    # Get URL
                    link = card.locator('a').first
                    if link.count() > 0:
                        href = link.get_attribute('href')
                        if href:
                            job['url'] = href if href.startswith('http') else f"https://www.elempleo.com{href}"
                    
                    job['apply_type'] = 'email'
                    job['apply_email'] = 'info@elempleo.com'
                    
                    if job['title']:
                        self.jobs.append(job)
                        count += 1
                        logger.info(f"  [{count}] ✓ {job['title'][:60]}")
                    
                except Exception as e:
                    logger.error(f"  [{idx}] Error: {e}")
            
            logger.info(f"✅ {site}: Scraped {count} jobs")
            
        except Exception as e:
            logger.error(f"❌ {site} failed: {e}")
    
    # ==================== COMPUTRABAJO.COM ====================
    
    def scrape_computrabajo(self, page, max_jobs):
        site = 'computrabajo.com'
        logger.info(f"\n{'='*70}")
        logger.info(f"SCRAPING: {site}")
        logger.info(f"{'='*70}")
        
        try:
            logger.info("Navigating to computrabajo.com...")
            page.goto("https://cr.computrabajo.com/", 
                     wait_until='networkidle',
                     timeout=60000)
            
            self._wait_and_debug(page, site)
            
            # Try to find job cards
            logger.info("Looking for job cards...")
            selector_sets = [
                ['article'],
                ['.bRS'],
                ['[data-tracking]'],
                ['.js-o-link'],
                ['[class*="result"]'],
                ['div.box'],
            ]
            
            cards = self._find_elements_debug(page, selector_sets)
            
            if not cards:
                logger.error("❌ No job cards found - check screenshot")
                return
            
            logger.info(f"✅ Found {len(cards)} job cards")
            
            count = 0
            for idx, card in enumerate(cards[:max_jobs], 1):
                try:
                    job = self._init_job(site)
                    
                    # Get all text
                    card_text = card.inner_text()
                    lines = [l.strip() for l in card_text.split('\n') if l.strip()]
                    
                    if len(lines) >= 2:
                        # First significant line is usually title
                        job['title'] = lines[0]
                        job['company'] = lines[1] if len(lines) > 1 else ''
                        
                        # Parse other fields from text
                        for line in lines:
                            # Location
                            if any(city in line for city in ['San José', 'Heredia', 'Cartago', 'Alajuela', 'Costa Rica']):
                                job['location'] = line
                            
                            # Salary
                            if '₡' in line or '$' in line or 'salario' in line.lower():
                                job['salary'] = line
                            
                            # Date
                            if 'hace' in line.lower() or 'hoy' in line.lower():
                                job['posting_date'] = line
                    
                    # Get URL
                    link = card.locator('a').first
                    if link.count() > 0:
                        href = link.get_attribute('href')
                        if href:
                            job['url'] = href if href.startswith('http') else f"https://cr.computrabajo.com{href}"
                    
                    if job['title']:
                        self.jobs.append(job)
                        count += 1
                        logger.info(f"  [{count}] ✓ {job['title'][:60]}")
                    
                except Exception as e:
                    logger.error(f"  [{idx}] Error: {e}")
            
            logger.info(f"✅ {site}: Scraped {count} jobs")
            
        except Exception as e:
            logger.error(f"❌ {site} failed: {e}")
    
    # ==================== INDEED.COM ====================
    
    def scrape_indeed(self, page, max_jobs):
        site = 'indeed.com'
        logger.info(f"\n{'='*70}")
        logger.info(f"SCRAPING: {site}")
        logger.info(f"{'='*70}")
        
        try:
            logger.info("Navigating to indeed.com...")
            page.goto("https://cr.indeed.com/jobs?q=&l=Costa+Rica", 
                     wait_until='networkidle',
                     timeout=60000)
            
            self._wait_and_debug(page, site)
            
            # Try to find job cards
            logger.info("Looking for job cards...")
            selector_sets = [
                ['li.job_seen_beacon'],
                ['div.job_seen_beacon'],
                ['div[data-jk]'],
                ['div.jobsearch-SerpJobCard'],
                ['div[class*="result"]'],
                ['td.resultContent'],
            ]
            
            cards = self._find_elements_debug(page, selector_sets)
            
            if not cards:
                logger.error("❌ No job cards found - check screenshot")
                return
            
            logger.info(f"✅ Found {len(cards)} job cards")
            
            count = 0
            for idx, card in enumerate(cards[:max_jobs], 1):
                try:
                    job = self._init_job(site)
                    
                    # Get all text
                    card_text = card.inner_text()
                    lines = [l.strip() for l in card_text.split('\n') if l.strip()]
                    
                    if len(lines) >= 2:
                        job['title'] = lines[0]
                        job['company'] = lines[1] if len(lines) > 1 else ''
                        
                        # Parse location and salary
                        for line in lines:
                            # Location
                            if 'Costa Rica' in line or any(city in line for city in ['San José', 'Heredia']):
                                job['location'] = line
                            
                            # Salary
                            if '$' in line or '₡' in line or 'año' in line.lower():
                                if any(char.isdigit() for char in line):
                                    job['salary'] = line
                        
                        # Description is usually further down
                        if len(lines) > 3:
                            job['description'] = ' '.join(lines[3:6])
                    
                    # Get URL
                    link = card.locator('a').first
                    if link.count() > 0:
                        href = link.get_attribute('href')
                        if href:
                            job['url'] = href if href.startswith('http') else f"https://cr.indeed.com{href}"
                    
                    if job['title']:
                        self.jobs.append(job)
                        count += 1
                        logger.info(f"  [{count}] ✓ {job['title'][:60]}")
                    
                except Exception as e:
                    logger.error(f"  [{idx}] Error: {e}")
            
            logger.info(f"✅ {site}: Scraped {count} jobs")
            
        except Exception as e:
            logger.error(f"❌ {site} failed: {e}")
    
    # ==================== JOOBLE.ORG ====================
    
    def scrape_jooble(self, page, max_jobs):
        site = 'jooble.org'
        logger.info(f"\n{'='*70}")
        logger.info(f"SCRAPING: {site}")
        logger.info(f"{'='*70}")
        
        try:
            logger.info("Navigating to jooble.org...")
            page.goto("https://cr.jooble.org/", 
                     wait_until='networkidle',
                     timeout=60000)
            
            self._wait_and_debug(page, site)
            
            # Try to find job cards
            logger.info("Looking for job cards...")
            selector_sets = [
                ['article'],
                ['div[class*="vacancy"]'],
                ['div[class*="job"]'],
                ['div[class*="result"]'],
                ['[data-test*="vacancy"]'],
            ]
            
            cards = self._find_elements_debug(page, selector_sets)
            
            if not cards:
                logger.error("❌ No job cards found - check screenshot")
                return
            
            logger.info(f"✅ Found {len(cards)} job cards")
            
            count = 0
            for idx, card in enumerate(cards[:max_jobs], 1):
                try:
                    job = self._init_job(site)
                    
                    # Get all text
                    card_text = card.inner_text()
                    lines = [l.strip() for l in card_text.split('\n') if l.strip()]
                    
                    if len(lines) >= 1:
                        job['title'] = lines[0]
                        job['company'] = lines[1] if len(lines) > 1 else ''
                        
                        # Parse other info
                        for line in lines:
                            if 'Costa Rica' in line or any(city in line for city in ['San José', 'Heredia']):
                                job['location'] = line
                            
                            if '$' in line or '₡' in line:
                                job['salary'] = line
                    
                    # Get URL
                    link = card.locator('a').first
                    if link.count() > 0:
                        href = link.get_attribute('href')
                        if href:
                            job['url'] = href if href.startswith('http') else f"https://cr.jooble.org{href}"
                    
                    if job['title']:
                        self.jobs.append(job)
                        count += 1
                        logger.info(f"  [{count}] ✓ {job['title'][:60]}")
                    
                except Exception as e:
                    logger.error(f"  [{idx}] Error: {e}")
            
            logger.info(f"✅ {site}: Scraped {count} jobs")
            
        except Exception as e:
            logger.error(f"❌ {site} failed: {e}")
    
    # ==================== HELPER METHODS ====================
    
    def _init_job(self, site):
        """Initialize job dictionary"""
        job = {field: '' for field in self.FIELDS}
        job['source_site'] = site
        job['featured'] = False
        job['filled'] = False
        job['urgent'] = False
        return job
    
    def save_to_csv(self, filename='costarica_jobs.csv'):
        """Save jobs to CSV"""
        if not self.jobs:
            logger.warning("⚠️  No jobs to save")
            return None
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=self.FIELDS)
                writer.writeheader()
                writer.writerows(self.jobs)
            
            logger.info(f"\n✅ Saved {len(self.jobs)} jobs to {filename}")
            return filename
        except Exception as e:
            logger.error(f"❌ Error saving CSV: {e}")
            return None
    
    def print_summary(self):
        """Print summary statistics"""
        if not self.jobs:
            print("\n⚠️  No jobs scraped")
            return
        
        print("\n" + "="*70)
        print("📊 SCRAPING SUMMARY")
        print("="*70)
        
        # Count by site
        site_counts = {}
        for job in self.jobs:
            site = job['source_site']
            site_counts[site] = site_counts.get(site, 0) + 1
        
        print("\nJobs per site:")
        for site, count in sorted(site_counts.items()):
            print(f"  {site:20s} : {count:3d} jobs")
        
        print(f"\n📈 Total jobs: {len(self.jobs)}")
        
        # Field coverage
        print("\n📋 Field coverage (important fields):")
        important_fields = ['title', 'company', 'location', 'salary', 'description',
                          'experience', 'posting_date', 'url']
        
        for field in important_fields:
            count = sum(1 for job in self.jobs if job.get(field) and str(job[field]).strip())
            pct = (count / len(self.jobs)) * 100
            bar = '█' * int(pct / 2)
            print(f"  {field:20s} : {count:3d}/{len(self.jobs)} ({pct:5.1f}%) {bar}")
        
        print("="*70)


def main():
    """Main execution"""
    scraper = JobScraper()
    
    print("\n🚀 Starting Costa Rica Jobs Scraper...")
    print("💡 Browser will stay open - watch the scraping happen!")
    print("📸 Screenshots saved for debugging")
    print("⏸️  Press Ctrl+C to stop early\n")
    
    jobs = scraper.scrape_all_sites(max_per_site=20)
    
    if jobs:
        # Save results
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'costarica_jobs_{timestamp}.csv'
        scraper.save_to_csv(filename)
        
        # Show summary
        scraper.print_summary()
        
        print(f"\n✅ Complete! Output: {filename}")
    else:
        print("\n⚠️  No jobs scraped. Check the debug screenshots:")
        print("  - debug_elempleo_com.png")
        print("  - debug_computrabajo_com.png")
        print("  - debug_indeed_com.png")
        print("  - debug_jooble_org.png")


if __name__ == "__main__":
    main()