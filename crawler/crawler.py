import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
from urllib.parse import urlparse, urljoin
from typing import Dict, List, Optional
import pandas as pd


class WebCrawler:
    """Web crawler for extracting university course information."""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        self.html_dir = os.path.join(output_dir, "html")
        self.json_dir = os.path.join(output_dir, "json")
        self.text_dir = os.path.join(output_dir, "text")
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self._ensure_directories()

    def _ensure_directories(self):
        """Create output directories if they don't exist."""
        for directory in [self.html_dir, self.json_dir, self.text_dir]:
            os.makedirs(directory, exist_ok=True)

    def _get_safe_filename(self, url: str) -> str:
        """Generate a safe filename from URL."""
        parsed = urlparse(url)
        name = parsed.netloc + parsed.path
        name = re.sub(r'[^\w\-_.]', '_', name)
        name = re.sub(r'_+', '_', name).strip('_')
        return name[:100] if len(name) > 100 else name

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch HTML content from a URL."""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None

    def save_html(self, url: str, html: str) -> str:
        """Save raw HTML to file."""
        filename = self._get_safe_filename(url) + ".html"
        filepath = os.path.join(self.html_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        return filepath

    def extract_course_info(self, html: str, url: str) -> Dict:
        """
        Extract course information from HTML.

        This method uses common patterns to find course data.
        You may need to customize the selectors for specific university websites.
        """
        soup = BeautifulSoup(html, 'html.parser')

        course_data = {
            'url': url,
            'name': self._extract_course_name(soup),
            'description': self._extract_description(soup),
            'duration': self._extract_duration(soup),
            'fees': self._extract_fees(soup),
            'eligibility': self._extract_eligibility(soup),
            'syllabus': self._extract_syllabus(soup),
            'intake_dates': self._extract_intake_dates(soup),
            'study_mode': self._extract_study_mode(soup),
            'career_outcomes': self._extract_career_outcomes(soup),
        }

        return course_data

    def _extract_course_name(self, soup: BeautifulSoup) -> str:
        """Extract course name from page."""
        # Try common selectors for course titles
        selectors = [
            'h1.course-title', 'h1.program-title', '.course-name h1',
            'h1[class*="course"]', 'h1[class*="program"]',
            '.hero-title h1', '.page-title h1',
            '[class*="degree-title"]', '[class*="program-name"]',
            '.banner h1', '.header h1', 'h1'
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                # Filter out generic titles
                if text and len(text) > 3 and text.lower() not in ['home', 'menu', 'search', 'login']:
                    return text
        return ""

    def _extract_description(self, soup: BeautifulSoup) -> str:
        """Extract course description."""
        selectors = [
            '.course-description', '.program-description', '.overview',
            '[class*="description"]', '[class*="overview"]',
            '[class*="intro"]', '[class*="summary"]',
            '.course-content p', '.program-content p',
            '.lead', '.excerpt', 'article p'
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text and len(text) > 50:
                    return text[:1000]

        # Try meta description
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta and meta.get('content'):
            return meta['content'][:1000]
        return ""

    def _extract_duration(self, soup: BeautifulSoup) -> str:
        """Extract course duration."""
        # More specific duration patterns
        patterns = [
            r'(?:duration|length)[:\s]+(\d+(?:\.\d+)?\s*(?:year|month|semester|week)s?(?:\s*(?:full[- ]?time|part[- ]?time))?)',
            r'(\d+(?:\.\d+)?\s*(?:year|month|semester|week)s?\s*(?:full[- ]?time|part[- ]?time))',
            r'(\d+(?:\.\d+)?\s*(?:year|month)s?)',
            r'(?:full[- ]?time|part[- ]?time)[:\s]+(\d+(?:\.\d+)?\s*(?:year|month|semester)s?)',
        ]

        text = soup.get_text()
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                result = match.group(1) if match.lastindex else match.group(0)
                return result.strip()

        # Try specific selectors
        selectors = [
            '.duration', '[class*="duration"]',
            '[data-duration]', '.course-length',
            'dt:contains("Duration") + dd', 'th:contains("Duration") + td'
        ]
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    if text and any(word in text.lower() for word in ['year', 'month', 'week', 'semester']):
                        return text
            except:
                continue
        return ""

    def _extract_fees(self, soup: BeautifulSoup) -> str:
        """Extract course fees."""
        # Australian dollar patterns
        patterns = [
            r'(?:annual\s+)?(?:fee|tuition|cost)s?[:\s]*\$?\s*([\d,]+(?:\.\d{2})?)\s*(?:AUD)?(?:\s*(?:per|/|a)\s*(?:year|annum|semester))?',
            r'\$([\d,]+(?:\.\d{2})?)\s*(?:AUD)?\s*(?:per|/|a)?\s*(?:year|annum|semester|credit)',
            r'(?:CSP|Commonwealth\s+Supported)[:\s]*\$?([\d,]+)',
            r'(?:international|domestic)\s+(?:fee|student)s?[:\s]*\$?([\d,]+)',
        ]

        text = soup.get_text()
        fees_found = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                fee = match if isinstance(match, str) else match[0] if match else ''
                if fee:
                    # Clean up and validate
                    fee_num = fee.replace(',', '').replace('$', '')
                    try:
                        if 1000 < float(fee_num) < 200000:  # Reasonable fee range
                            fees_found.append(f"${fee}")
                    except:
                        pass

        return ', '.join(fees_found[:3]) if fees_found else ""

    def _extract_eligibility(self, soup: BeautifulSoup) -> str:
        """Extract eligibility requirements."""
        selectors = [
            '.eligibility', '.requirements', '.admission-requirements',
            '[class*="eligibility"]', '[class*="requirement"]',
            '.entry-requirements', '[class*="entry"]',
            '[class*="prerequisite"]', '.admission', '[class*="atar"]'
        ]

        requirements = []
        for selector in selectors:
            elements = soup.select(selector)
            for element in elements[:3]:
                text = element.get_text(strip=True)
                if text and len(text) > 20:
                    requirements.append(text[:300])

        # Look for ATAR scores (Australian Tertiary Admission Rank)
        atar_pattern = r'ATAR[:\s]+(\d+(?:\.\d+)?)'
        text = soup.get_text()
        atar_match = re.search(atar_pattern, text, re.IGNORECASE)
        if atar_match:
            requirements.insert(0, f"ATAR: {atar_match.group(1)}")

        return ' | '.join(requirements[:3]) if requirements else ""

    def _extract_syllabus(self, soup: BeautifulSoup) -> List[str]:
        """Extract syllabus/curriculum topics."""
        selectors = [
            '.syllabus li', '.curriculum li', '.modules li',
            '[class*="syllabus"] li', '[class*="curriculum"] li',
            '.course-modules li', '.subjects li', '.units li',
            '[class*="course-structure"] li', '[class*="major"] li',
            '.study-areas li', '[class*="specialisation"] li'
        ]
        topics = []
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for el in elements[:20]:
                    text = el.get_text(strip=True)
                    if text and len(text) > 3 and len(text) < 200:
                        topics.append(text)
                if topics:
                    break
        return topics

    def _extract_intake_dates(self, soup: BeautifulSoup) -> List[str]:
        """Extract intake/admission dates."""
        patterns = [
            r'(?:intake|admission|start|commence)s?[:\s]+(?:in\s+)?(?:january|february|march|april|may|june|july|august|september|october|november|december)\s*\d{4}',
            r'(?:semester\s*[12]|term\s*[1-4])[:\s]+\d{4}',
            r'(?:spring|fall|summer|winter|mid[- ]?year)\s*(?:semester\s*)?\d{4}',
            r'(?:february|july|march|august)\s+(?:intake|entry)',
        ]

        dates = []
        text = soup.get_text()
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            dates.extend(matches[:5])
        return list(set(dates))

    def _extract_study_mode(self, soup: BeautifulSoup) -> str:
        """Extract study mode (online, on-campus, etc.)."""
        modes = []
        text = soup.get_text().lower()

        if 'online' in text or 'distance' in text:
            modes.append('Online')
        if 'on-campus' in text or 'on campus' in text or 'face-to-face' in text:
            modes.append('On-campus')
        if 'flexible' in text or 'blended' in text:
            modes.append('Flexible')
        if 'part-time' in text or 'part time' in text:
            modes.append('Part-time available')

        return ', '.join(modes) if modes else ""

    def _extract_career_outcomes(self, soup: BeautifulSoup) -> List[str]:
        """Extract career outcomes/job prospects."""
        selectors = [
            '[class*="career"] li', '[class*="outcome"] li',
            '[class*="employment"] li', '[class*="job"] li',
            '.careers li', '.opportunities li'
        ]

        careers = []
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for el in elements[:10]:
                    text = el.get_text(strip=True)
                    if text and len(text) > 3 and len(text) < 100:
                        careers.append(text)
                if careers:
                    break
        return careers

    def save_json(self, data: Dict, url: str) -> str:
        """Save extracted data as JSON."""
        filename = self._get_safe_filename(url) + ".json"
        filepath = os.path.join(self.json_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return filepath

    def save_text(self, course_name: str, filename: str = "all_courses.txt"):
        """Append course name to text file."""
        filepath = os.path.join(self.text_dir, filename)
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(course_name + '\n')
        return filepath

    def crawl_url(self, url: str) -> Optional[Dict]:
        """Crawl a single URL and extract course information."""
        print(f"Crawling: {url}")

        html = self.fetch_page(url)
        if not html:
            return None

        # Save raw HTML
        self.save_html(url, html)

        # Extract course info
        course_data = self.extract_course_info(html, url)

        # Save as JSON
        self.save_json(course_data, url)

        # Save course name to text file
        if course_data.get('name'):
            self.save_text(course_data['name'])

        return course_data

    def crawl_urls(self, urls: List[str], delay: float = 1.0) -> List[Dict]:
        """
        Crawl multiple URLs with a delay between requests.

        Args:
            urls: List of URLs to crawl
            delay: Delay in seconds between requests (be respectful to servers)

        Returns:
            List of extracted course data dictionaries
        """
        results = []

        # Clear previous course list
        text_file = os.path.join(self.text_dir, "all_courses.txt")
        if os.path.exists(text_file):
            os.remove(text_file)

        for i, url in enumerate(urls):
            print(f"\n[{i+1}/{len(urls)}] Processing...")

            result = self.crawl_url(url)
            if result:
                results.append(result)

            # Delay between requests
            if i < len(urls) - 1:
                time.sleep(delay)

        # Save combined results
        self._save_combined_results(results)

        return results

    def _save_combined_results(self, results: List[Dict]):
        """Save all results to a combined JSON file."""
        filepath = os.path.join(self.json_dir, "all_courses.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\nCombined results saved to: {filepath}")

    def load_urls_from_file(self, filepath: str) -> List[str]:
        """Load URLs from a text file (one URL per line)."""
        urls = []
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                url = line.strip()
                if url and not url.startswith('#'):
                    urls.append(url)
        return urls

    def load_urls_from_excel(self, filepath: str, url_column: str = "Website") -> List[Dict]:
        """
        Load university data from Excel file.

        Args:
            filepath: Path to Excel file
            url_column: Name of column containing URLs

        Returns:
            List of dictionaries with university info
        """
        df = pd.read_excel(filepath)
        universities = []
        for _, row in df.iterrows():
            uni_data = {
                'name': row.get('CollegeName', ''),
                'city': row.get('City', ''),
                'state': row.get('State', ''),
                'website': row.get(url_column, '')
            }
            if uni_data['website']:
                universities.append(uni_data)
        return universities

    def discover_course_links(self, base_url: str, html: str) -> List[str]:
        """
        Discover course/program links from a university homepage.

        Args:
            base_url: The base URL of the university
            html: HTML content of the page

        Returns:
            List of course page URLs
        """
        soup = BeautifulSoup(html, 'html.parser')
        course_links = []

        # Common patterns for course/program links
        patterns = [
            r'/course', r'/program', r'/study', r'/degree',
            r'/undergraduate', r'/postgraduate', r'/masters',
            r'/bachelor', r'/diploma', r'/certificate'
        ]

        for link in soup.find_all('a', href=True):
            href = link['href'].lower()
            text = link.get_text(strip=True).lower()

            # Check if link matches course patterns
            for pattern in patterns:
                if pattern in href or pattern.replace('/', ' ').strip() in text:
                    full_url = urljoin(base_url, link['href'])
                    if full_url not in course_links:
                        course_links.append(full_url)
                    break

        return course_links[:50]  # Limit to 50 links per university

    def crawl_university(self, uni_data: Dict, discover_courses: bool = True,
                         max_courses: int = 10, delay: float = 1.0) -> Dict:
        """
        Crawl a single university and optionally discover course pages.

        Args:
            uni_data: Dictionary with university info (name, website, etc.)
            discover_courses: Whether to discover and crawl course pages
            max_courses: Maximum number of course pages to crawl per university
            delay: Delay between requests

        Returns:
            Dictionary with university data and extracted courses
        """
        base_url = uni_data['website']
        print(f"\n{'='*60}")
        print(f"Crawling: {uni_data['name']}")
        print(f"URL: {base_url}")
        print('='*60)

        result = {
            'university': uni_data['name'],
            'city': uni_data.get('city', ''),
            'state': uni_data.get('state', ''),
            'website': base_url,
            'courses': []
        }

        # Fetch university homepage
        html = self.fetch_page(base_url)
        if not html:
            print(f"Failed to fetch {base_url}")
            return result

        # Save homepage HTML
        self.save_html(base_url, html)

        if discover_courses:
            # Find course links
            print("Discovering course links...")
            course_links = self.discover_course_links(base_url, html)
            print(f"Found {len(course_links)} potential course links")

            # Crawl course pages
            for i, course_url in enumerate(course_links[:max_courses]):
                print(f"  [{i+1}/{min(len(course_links), max_courses)}] {course_url[:80]}...")
                time.sleep(delay)

                course_html = self.fetch_page(course_url)
                if course_html:
                    self.save_html(course_url, course_html)
                    course_data = self.extract_course_info(course_html, course_url)
                    if course_data.get('name'):
                        result['courses'].append(course_data)
                        self.save_text(f"{uni_data['name']}: {course_data['name']}")

        return result

    def crawl_universities_from_excel(self, excel_path: str, discover_courses: bool = True,
                                       max_courses_per_uni: int = 10, delay: float = 1.5) -> List[Dict]:
        """
        Crawl all universities from an Excel file.

        Args:
            excel_path: Path to Excel file with university data
            discover_courses: Whether to discover and crawl course pages
            max_courses_per_uni: Maximum courses to crawl per university
            delay: Delay between requests

        Returns:
            List of university data with extracted courses
        """
        print(f"Loading universities from: {excel_path}")
        universities = self.load_urls_from_excel(excel_path)
        print(f"Found {len(universities)} universities")

        # Clear previous course list
        text_file = os.path.join(self.text_dir, "all_courses.txt")
        if os.path.exists(text_file):
            os.remove(text_file)

        results = []
        for i, uni_data in enumerate(universities):
            print(f"\n[{i+1}/{len(universities)}] Processing {uni_data['name']}...")

            result = self.crawl_university(
                uni_data,
                discover_courses=discover_courses,
                max_courses=max_courses_per_uni,
                delay=delay
            )
            results.append(result)

            # Save intermediate results
            self._save_university_results(results)

            # Delay between universities
            if i < len(universities) - 1:
                time.sleep(delay)

        return results

    def _save_university_results(self, results: List[Dict]):
        """Save university results to JSON file."""
        filepath = os.path.join(self.json_dir, "all_universities.json")
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Results saved to: {filepath}")
