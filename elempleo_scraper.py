"""
Elempleo.com Costa Rica Job Scraper - QUICK VIEW VERSION
Clicks "Vista rápida" buttons to get full job details
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


class ElempleoQuickViewScraper:
    def __init__(self):
        self.base_url = "https://www.elempleo.com/cr/ofertas-empleo/"
        self.jobs = []
        
    def scrape(self, max_jobs=50):
        """Scrape jobs by clicking Quick View buttons"""
        logger.info("="*70)
        logger.info("ELEMPLEO.COM - QUICK VIEW SCRAPER")
        logger.info("="*70 + "\n")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                viewport={'width': 1920, 'height': 1080},
                locale='es-CR'
            )
            page = context.new_page()
            
            try:
                logger.info(f"Navigating to {self.base_url}")
                page.goto(self.base_url, wait_until='networkidle', timeout=60000)
                time.sleep(5)
                
                page.screenshot(path='elempleo_listing.png')
                logger.info("Screenshot saved: elempleo_listing.png\n")
                
                # Find all Quick View buttons
                logger.info("Looking for 'Vista rápida' buttons...")
                
                # Try different selectors for Quick View buttons
                quick_view_selectors = [
                    'button:has-text("Vista rápida")',
                    'a:has-text("Vista rápida")',
                    '[class*="quick-view"]',
                    '[class*="vista-rapida"]',
                    'button[class*="quick"]',
                    '.js-quick-view'
                ]
                
                quick_view_buttons = []
                for selector in quick_view_selectors:
                    try:
                        buttons = page.locator(selector).all()
                        if buttons:
                            logger.info(f"✓ Found {len(buttons)} buttons with selector: {selector}")
                            quick_view_buttons = buttons
                            break
                    except:
                        continue
                
                if not quick_view_buttons:
                    logger.error("❌ No 'Vista rápida' buttons found!")
                    logger.info("Looking for all buttons on page for debugging...")
                    all_buttons = page.locator('button, a[role="button"]').all()
                    logger.info(f"Total buttons found: {len(all_buttons)}")
                    for i, btn in enumerate(all_buttons[:10]):
                        text = btn.inner_text().strip()
                        if text:
                            logger.info(f"  Button {i+1}: '{text}'")
                    return []
                
                logger.info(f"\n✅ Found {len(quick_view_buttons)} Quick View buttons")
                logger.info(f"Will scrape up to {min(max_jobs, len(quick_view_buttons))} jobs\n")
                
                # Click each Quick View button and extract data
                for idx in range(min(max_jobs, len(quick_view_buttons))):
                    try:
                        # Re-locate buttons each time (DOM may refresh)
                        current_buttons = page.locator(quick_view_selectors[0]).all()
                        
                        if idx >= len(current_buttons):
                            logger.warning(f"Button {idx} no longer available")
                            break
                        
                        button = current_buttons[idx]
                        
                        logger.info(f"[{idx+1}/{min(max_jobs, len(quick_view_buttons))}] Clicking Quick View...")
                        
                        # Scroll button into view
                        button.scroll_into_view_if_needed()
                        time.sleep(0.5)
                        
                        # Click the Quick View button
                        button.click()
                        
                        # Wait for modal/popup to appear
                        time.sleep(2)
                        
                        # Take screenshot of modal
                        page.screenshot(path=f'quick_view_{idx+1}.png')
                        
                        # Extract data from the Quick View modal
                        job = self._extract_from_quick_view(page)
                        
                        if job and job['title']:
                            self.jobs.append(job)
                            logger.info(f"  ✓ {job['title'][:60]}")
                        else:
                            logger.warning(f"  ✗ No data extracted")
                        
                        # Close modal (look for close button)
                        self._close_modal(page)
                        time.sleep(1)
                        
                    except Exception as e:
                        logger.error(f"  ✗ Error on job {idx+1}: {e}")
                        self._close_modal(page)
                        continue
                
            except Exception as e:
                logger.error(f"Fatal error: {e}")
            finally:
                time.sleep(2)
                browser.close()
        
        logger.info(f"\n{'='*70}")
        logger.info(f"✅ Scraping complete! Total jobs: {len(self.jobs)}")
        logger.info(f"{'='*70}")
        return self.jobs
    
    def _extract_from_quick_view(self, page):
        """Extract job details from Quick View modal/popup"""
        job = {
            'title': '',
            'company': '',
            'location': '',
            'description': '',
            'salary': '',
            'posting_date': '',
            'url': ''
        }
        
        try:
            # Look for modal/popup container
            modal_selectors = [
                '[class*="modal"]',
                '[class*="popup"]',
                '[class*="quick-view"]',
                '[role="dialog"]',
                '.overlay-content'
            ]
            
            modal = None
            for selector in modal_selectors:
                if page.locator(selector).count() > 0:
                    modal = page.locator(selector).first
                    break
            
            # If no specific modal found, use the whole page
            if not modal:
                modal = page.locator('body')
            
            # Extract title
            title_selectors = ['h1', 'h2', '.job-title', '[class*="title"]']
            for sel in title_selectors:
                try:
                    elem = modal.locator(sel).first
                    if elem.count() > 0:
                        text = elem.inner_text().strip()
                        if text and len(text) > 3:
                            job['title'] = text
                            break
                except:
                    pass
            
            # Extract company
            company_selectors = ['.company', '.company-name', '[class*="empresa"]', '[class*="company"]']
            for sel in company_selectors:
                try:
                    elem = modal.locator(sel).first
                    if elem.count() > 0:
                        text = elem.inner_text().strip()
                        if text and len(text) > 1:
                            job['company'] = text
                            break
                except:
                    pass
            
            # Extract location
            location_selectors = ['.location', '[class*="ubicacion"]', '[class*="location"]']
            for sel in location_selectors:
                try:
                    elem = modal.locator(sel).first
                    if elem.count() > 0:
                        text = elem.inner_text().strip()
                        if text:
                            job['location'] = text
                            break
                except:
                    pass
            
            # Extract description
            desc_selectors = ['.description', '.job-description', '[class*="descripcion"]', 'article', '.content']
            for sel in desc_selectors:
                try:
                    elem = modal.locator(sel).first
                    if elem.count() > 0:
                        text = elem.inner_text().strip()
                        if len(text) > 100:
                            job['description'] = text
                            break
                except:
                    pass
            
            # Extract salary
            salary_selectors = ['.salary', '[class*="salario"]', '[class*="sueldo"]']
            for sel in salary_selectors:
                try:
                    elem = modal.locator(sel).first
                    if elem.count() > 0:
                        text = elem.inner_text().strip()
                        if text and ('₡' in text or '$' in text or 'confidencial' in text.lower()):
                            job['salary'] = text
                            break
                except:
                    pass
            
            # Extract posting date
            date_selectors = ['.date', '.posted-date', 'time', '[class*="fecha"]', '[class*="publicado"]']
            for sel in date_selectors:
                try:
                    elem = modal.locator(sel).first
                    if elem.count() > 0:
                        text = elem.inner_text().strip()
                        if text and ('2025' in text or '2024' in text or 'Oct' in text or 'hace' in text.lower()):
                            job['posting_date'] = text
                            break
                except:
                    pass
            
            # Extract URL
            try:
                link = modal.locator('a[href*="/empleo/"], a[href*="/oferta/"]').first
                if link.count() > 0:
                    href = link.get_attribute('href')
                    if href:
                        job['url'] = href if href.startswith('http') else f"https://www.elempleo.com{href}"
            except:
                pass
            
            # If still missing data, try parsing all text
            if not job['company'] or not job['location']:
                try:
                    modal_text = modal.inner_text()
                    lines = [l.strip() for l in modal_text.split('\n') if l.strip()]
                    
                    # Company is often near the top
                    if not job['company'] and len(lines) > 1:
                        for line in lines[1:5]:
                            # Skip if it's the title or other common words
                            if line != job['title'] and len(line) > 3 and len(line) < 100:
                                if not any(word in line.lower() for word in ['publicado', 'vista', 'aplicar']):
                                    job['company'] = line
                                    break
                    
                    # Location usually has city names
                    if not job['location']:
                        for line in lines:
                            if any(city in line for city in ['San José', 'Heredia', 'Cartago', 'Alajuela', 'Limón', 'Guanacaste', 'Puntarenas']):
                                job['location'] = line
                                break
                    
                    # Salary has money symbols or "confidencial"
                    if not job['salary']:
                        for line in lines:
                            if '₡' in line or '$' in line or 'confidencial' in line.lower():
                                if any(c.isdigit() for c in line) or 'confidencial' in line.lower():
                                    job['salary'] = line
                                    break
                    
                    # Date has "Publicado" or dates
                    if not job['posting_date']:
                        for line in lines:
                            if 'publicado' in line.lower() or re.search(r'\d{1,2}\s+(Oct|Nov|Dic|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep)', line):
                                job['posting_date'] = line
                                break
                    
                except:
                    pass
            
        except Exception as e:
            logger.error(f"Error extracting from Quick View: {e}")
        
        return job
    
    def _close_modal(self, page):
        """Close the Quick View modal"""
        close_selectors = [
            'button[aria-label="Close"]',
            'button[class*="close"]',
            '[class*="close-button"]',
            '.modal-close',
            'button:has-text("×")',
            'button:has-text("Cerrar")'
        ]
        
        for selector in close_selectors:
            try:
                close_btn = page.locator(selector).first
                if close_btn.count() > 0 and close_btn.is_visible():
                    close_btn.click()
                    time.sleep(0.5)
                    return
            except:
                continue
        
        # If no close button found, try pressing Escape
        try:
            page.keyboard.press('Escape')
            time.sleep(0.5)
        except:
            pass
    
    def save_to_csv(self, filename='elempleo_jobs.csv'):
        """Save jobs to CSV"""
        if not self.jobs:
            logger.warning("⚠️  No jobs to save")
            return None
        
        fieldnames = ['title', 'company', 'location', 'description', 'salary', 'posting_date', 'url']
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.jobs)
            
            logger.info(f"\n✅ Saved {len(self.jobs)} jobs to {filename}")
            return filename
        except Exception as e:
            logger.error(f"❌ Error saving CSV: {e}")
            return None
    
    def print_summary(self):
        """Print field coverage summary"""
        if not self.jobs:
            return
        
        print("\n" + "="*70)
        print("📊 FIELD COVERAGE")
        print("="*70)
        
        fields = ['title', 'company', 'location', 'description', 'salary', 'posting_date', 'url']
        
        for field in fields:
            count = sum(1 for job in self.jobs if job.get(field) and str(job[field]).strip())
            pct = (count / len(self.jobs)) * 100
            bar = '█' * int(pct / 2)
            print(f"  {field:15s} : {count:3d}/{len(self.jobs)} ({pct:5.1f}%) {bar}")
        
        print("="*70)


def main():
    scraper = ElempleoQuickViewScraper()
    
    print("\n🚀 Starting Elempleo Quick View Scraper...")
    print("💡 This will click each 'Vista rápida' button to get full details")
    print("👀 Watch the browser - you'll see each Quick View popup open\n")
    
    # Scrape jobs (start with 20 for testing)
    jobs = scraper.scrape(max_jobs=20)
    
    if jobs:
        # Save to CSV
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'elempleo_jobs_{timestamp}.csv'
        scraper.save_to_csv(filename)
        
        # Show summary
        scraper.print_summary()
        
        print(f"\n✅ Complete! Output: {filename}")
        print(f"📸 Quick View screenshots saved as: quick_view_1.png, quick_view_2.png, etc.\n")
    else:
        print("\n⚠️  No jobs scraped. Check elempleo_listing.png to see the page\n")


if __name__ == "__main__":
    main()