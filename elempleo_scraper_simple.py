"""
Alternative simpler scraper using Requests + BeautifulSoup
Use this if the site doesn't heavily rely on JavaScript
"""

import csv
import time
import random
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SimpleElempleoScraper:
    def __init__(self):
        self.base_url = "https://www.elempleo.com/cr/ofertas-empleo/"
        self.jobs = []
        self.session = requests.Session()
        
        # Set realistic headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,es;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def scrape(self, max_pages=5):
        """
        Scrape job listings
        """
        logger.info("Starting simple scraper...")
        
        try:
            for page in range(1, max_pages + 1):
                # Construct URL for pagination
                if page == 1:
                    url = self.base_url
                else:
                    url = f"{self.base_url}?page={page}"
                
                logger.info(f"Scraping page {page}: {url}")
                
                # Add random delay to be polite
                if page > 1:
                    time.sleep(random.uniform(2, 5))
                
                # Fetch page
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                
                # Parse HTML
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Extract jobs from this page
                jobs_found = self._extract_jobs_from_soup(soup)
                
                if jobs_found == 0:
                    logger.info("No more jobs found. Stopping.")
                    break
                
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        
        logger.info(f"Total jobs scraped: {len(self.jobs)}")
        return self.jobs
    
    def _extract_jobs_from_soup(self, soup):
        """
        Extract job listings from BeautifulSoup object
        """
        # Try different common selectors
        job_cards = (
            soup.select('.card-offer') or
            soup.select('.job-item') or
            soup.select('article.job') or
            soup.select('[data-job-id]') or
            soup.select('.vacancy-card')
        )
        
        if not job_cards:
            logger.warning("No job cards found with known selectors")
            return 0
        
        logger.info(f"Found {len(job_cards)} job cards")
        
        for card in job_cards:
            try:
                job = self._parse_job_card(card)
                if job and job['title']:
                    self.jobs.append(job)
            except Exception as e:
                logger.error(f"Error parsing job card: {e}")
        
        return len(job_cards)
    
    def _parse_job_card(self, card):
        """
        Parse individual job card
        """
        job = {
            'title': '',
            'company': '',
            'location': '',
            'description': '',
            'salary': '',
            'posting_date': '',
            'url': ''
        }
        
        # Extract title
        title_elem = (
            card.select_one('h2 a') or
            card.select_one('h3 a') or
            card.select_one('.job-title a') or
            card.select_one('a.title')
        )
        if title_elem:
            job['title'] = title_elem.get_text(strip=True)
            href = title_elem.get('href', '')
            if href:
                job['url'] = href if href.startswith('http') else f"https://www.elempleo.com{href}"
        
        # Extract company
        company_elem = (
            card.select_one('.company') or
            card.select_one('.company-name') or
            card.select_one('.employer')
        )
        if company_elem:
            job['company'] = company_elem.get_text(strip=True)
        
        # Extract location
        location_elem = (
            card.select_one('.location') or
            card.select_one('.job-location') or
            card.select_one('.place')
        )
        if location_elem:
            job['location'] = location_elem.get_text(strip=True)
        
        # Extract salary
        salary_elem = (
            card.select_one('.salary') or
            card.select_one('.wage') or
            card.select_one('.compensation')
        )
        if salary_elem:
            job['salary'] = salary_elem.get_text(strip=True)
        
        # Extract date
        date_elem = (
            card.select_one('.date') or
            card.select_one('.posted-date') or
            card.select_one('time')
        )
        if date_elem:
            job['posting_date'] = date_elem.get_text(strip=True)
        
        # Extract description
        desc_elem = (
            card.select_one('.description') or
            card.select_one('.job-desc') or
            card.select_one('.summary')
        )
        if desc_elem:
            job['description'] = desc_elem.get_text(strip=True)[:500]
        
        return job
    
    def save_to_csv(self, filename='elempleo_jobs_simple.csv'):
        """
        Save to CSV
        """
        if not self.jobs:
            logger.warning("No jobs to save")
            return
        
        fieldnames = ['title', 'company', 'location', 'description', 'salary', 'posting_date', 'url']
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.jobs)
            
            logger.info(f"Saved {len(self.jobs)} jobs to {filename}")
        except Exception as e:
            logger.error(f"Error saving CSV: {e}")


def main():
    scraper = SimpleElempleoScraper()
    jobs = scraper.scrape(max_pages=3)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'elempleo_jobs_simple_{timestamp}.csv'
    scraper.save_to_csv(filename)
    
    print(f"\nScraping complete!")
    print(f"Jobs found: {len(jobs)}")
    print(f"Output: {filename}")


if __name__ == "__main__":
    main()