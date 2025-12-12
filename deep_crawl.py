"""
Deep Course Crawler - Intelligent Extraction
=============================================
Goes deeper into individual course pages to extract:
- Course Name
- Description
- Duration
- Fees (domestic/international)
- Entry Requirements
- Study Mode
- Career Outcomes
- Credit Points
- Course Code

Enhanced with:
- JSON-LD/Schema.org structured data extraction
- Table-based key-value pair extraction
- University-specific selectors
- Improved pattern matching
"""

import requests
from bs4 import BeautifulSoup
import json
import os
import re
import time
from urllib.parse import urlparse, urljoin
from typing import Dict, List, Optional, Any


class DeepCourseCrawler:
    """Intelligent crawler for extracting detailed course information."""

    # University-specific CSS selectors for better extraction accuracy
    UNIVERSITY_SELECTORS = {
        'unsw.edu.au': {
            'name': ['.degree-title', 'h1.banner__title', '.course-header h1'],
            'description': ['.degree-overview', '.intro-text', '.course-description'],
            'duration': ['.key-info__item--duration', '[data-cy="duration"]', '.degree-duration'],
            'fees': ['.key-info__item--fees', '[data-cy="fees"]', '.degree-fees'],
            'requirements': ['.entry-requirements', '.admission-requirements'],
            'atar': ['.atar-score', '.selection-rank'],
        },
        'uq.edu.au': {
            'name': ['h1.program-title', '.program-header h1', 'h1[class*="title"]'],
            'description': ['.program-overview', '.program-intro', '.summary'],
            'duration': ['.program-duration', '.duration-value', '[class*="duration"]'],
            'fees': ['.program-fees', '.fee-information', '.tuition-fees'],
            'requirements': ['.entry-requirements', '.prerequisites', '.admission'],
        },
        'anu.edu.au': {
            'name': ['h1.introduction__title', '.degree-title', 'h1'],
            'description': ['.introduction__text', '.degree-overview', '.program-description'],
            'duration': ['.degree-requirements__item--duration', '[class*="duration"]'],
            'fees': ['.fees-section', '.fee-details'],
            'requirements': ['.admission-requirements', '.entry-requirements'],
        },
        'sydney.edu.au': {
            'name': ['h1.course-title', '.b-course-header__title', 'h1'],
            'description': ['.course-overview', '.b-course-overview', '.introduction'],
            'duration': ['.b-key-information__item--duration', '[data-field="duration"]'],
            'fees': ['.b-key-information__item--fees', '.fee-calculator'],
            'requirements': ['.b-admission-requirements', '.entry-requirements'],
        },
        'unimelb.edu.au': {
            'name': ['h1.course-title', '.page-header-title', 'h1'],
            'description': ['.course-overview', '.overview', '.course-intro'],
            'duration': ['.course-duration', '.key-details [class*="duration"]'],
            'fees': ['.course-fees', '.fee-information'],
            'requirements': ['.entry-requirements', '.prerequisites'],
        },
    }

    # Direct course catalog URLs for each university
    UNIVERSITY_COURSE_URLS = {
        'unsw': [
            'https://www.unsw.edu.au/study/find-a-degree-or-course/undergraduate-degrees',
            'https://www.unsw.edu.au/study/find-a-degree-or-course/postgraduate-degrees',
        ],
        'uq': [
            'https://study.uq.edu.au/study-options/programs?level=undergraduate',
            'https://study.uq.edu.au/study-options/programs?level=postgraduate-coursework',
        ],
        'anu': [
            'https://programsandcourses.anu.edu.au/catalogue?keywords=&career=Undergraduate&career=Postgraduate',
        ],
        'sydney': [
            'https://www.sydney.edu.au/courses/search.html?search-type=course&page=1',
        ],
        'melbourne': [
            'https://study.unimelb.edu.au/find/?collection=study-search',
        ]
    }

    # Known course listing page patterns
    COURSE_LIST_PATTERNS = [
        r'/programs?/', r'/courses?/', r'/degrees?/',
        r'/undergraduate', r'/postgraduate', r'/bachelor',
        r'/master', r'/diploma', r'/certificate'
    ]

    # Individual course page patterns
    COURSE_PAGE_PATTERNS = [
        r'/program/[a-z0-9-]+', r'/course/[a-z0-9-]+',
        r'/degree/[a-z0-9-]+', r'/study/[a-z0-9-]+/[a-z0-9-]+',
        r'/bachelor-of-', r'/master-of-', r'/graduate-'
    ]

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        self.json_dir = os.path.join(output_dir, "json")
        self.html_dir = os.path.join(output_dir, "html")
        os.makedirs(self.json_dir, exist_ok=True)
        os.makedirs(self.html_dir, exist_ok=True)

        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        })

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch page with error handling."""
        try:
            response = self.session.get(url, timeout=30, allow_redirects=True)
            response.raise_for_status()
            return response.text
        except Exception as e:
            print(f"    Error fetching {url}: {e}")
            return None

    def _get_university_selectors(self, url: str) -> Dict[str, List[str]]:
        """Get university-specific selectors based on URL domain."""
        domain = urlparse(url).netloc.lower()
        for uni_domain, selectors in self.UNIVERSITY_SELECTORS.items():
            if uni_domain in domain:
                return selectors
        return {}

    def _extract_json_ld(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """
        Extract structured data from JSON-LD scripts (Schema.org).
        This is the most reliable source when available.
        """
        json_ld_data = {}

        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)

                # Handle array of schemas
                if isinstance(data, list):
                    for item in data:
                        json_ld_data.update(self._parse_schema_item(item))
                else:
                    json_ld_data.update(self._parse_schema_item(data))
            except (json.JSONDecodeError, TypeError):
                continue

        return json_ld_data

    def _parse_schema_item(self, item: Dict) -> Dict[str, Any]:
        """Parse a Schema.org item for course-related data."""
        result = {}

        if not isinstance(item, dict):
            return result

        schema_type = item.get('@type', '')

        # Course, EducationalOccupationalProgram, or Program schemas
        if schema_type in ['Course', 'EducationalOccupationalProgram', 'Program',
                          'CollegeOrUniversity', 'Organization']:

            if 'name' in item:
                result['name'] = item['name']

            if 'description' in item:
                result['description'] = item['description']

            # Duration can be in various formats
            if 'timeToComplete' in item:
                result['duration'] = item['timeToComplete']
            elif 'duration' in item:
                result['duration'] = item['duration']

            # Fees/offers
            if 'offers' in item:
                offers = item['offers']
                if isinstance(offers, dict):
                    if 'price' in offers:
                        result['fees'] = f"${offers['price']}"
                elif isinstance(offers, list) and offers:
                    result['fees'] = f"${offers[0].get('price', '')}"

            # Provider info
            if 'provider' in item:
                provider = item['provider']
                if isinstance(provider, dict):
                    result['university'] = provider.get('name', '')

            # Educational requirements
            if 'educationalCredentialAwarded' in item:
                result['credential'] = item['educationalCredentialAwarded']

            # Occupational outcomes
            if 'occupationalCategory' in item:
                result['careers'] = item['occupationalCategory']

        return result

    def _extract_from_tables(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Extract key-value pairs from HTML tables.
        Many university sites use tables for course details.
        """
        table_data = {}

        # Key mappings for common labels
        key_mappings = {
            'duration': ['duration', 'length', 'time to complete', 'study period', 'course length'],
            'fees': ['fees', 'tuition', 'cost', 'price', 'annual fee', 'course fee'],
            'fees_domestic': ['domestic fee', 'csp', 'commonwealth supported', 'australian fee'],
            'fees_international': ['international fee', 'overseas fee', 'international tuition'],
            'atar': ['atar', 'selection rank', 'guaranteed atar', 'minimum atar'],
            'credit_points': ['credit points', 'units', 'credits', 'credit hours', 'total units'],
            'course_code': ['course code', 'program code', 'code', 'cricos'],
            'intake': ['intake', 'start date', 'commencement', 'start'],
            'campus': ['campus', 'location', 'study location'],
            'study_mode': ['study mode', 'mode of delivery', 'delivery mode', 'attendance'],
        }

        # Process definition lists (dl/dt/dd)
        for dl in soup.find_all('dl'):
            dts = dl.find_all('dt')
            dds = dl.find_all('dd')
            for dt, dd in zip(dts, dds):
                label = dt.get_text(strip=True).lower()
                value = dd.get_text(strip=True)
                self._map_table_value(table_data, label, value, key_mappings)

        # Process tables with th/td pairs
        for table in soup.find_all('table'):
            for row in table.find_all('tr'):
                cells = row.find_all(['th', 'td'])
                if len(cells) >= 2:
                    label = cells[0].get_text(strip=True).lower()
                    value = cells[1].get_text(strip=True)
                    self._map_table_value(table_data, label, value, key_mappings)

        # Process div-based key-value pairs (common pattern)
        for container in soup.find_all(['div', 'li'], class_=re.compile(r'key-info|detail|fact|stat', re.I)):
            label_elem = container.find(['span', 'strong', 'h3', 'h4', 'dt'], class_=re.compile(r'label|title|key', re.I))
            value_elem = container.find(['span', 'p', 'dd'], class_=re.compile(r'value|content|data', re.I))

            if label_elem and value_elem:
                label = label_elem.get_text(strip=True).lower()
                value = value_elem.get_text(strip=True)
                self._map_table_value(table_data, label, value, key_mappings)

        return table_data

    def _map_table_value(self, table_data: Dict, label: str, value: str,
                         key_mappings: Dict[str, List[str]]) -> None:
        """Map extracted label-value pair to standardized keys."""
        if not value or len(value) < 2:
            return

        for key, patterns in key_mappings.items():
            if any(pattern in label for pattern in patterns):
                # Don't overwrite if already found
                if key not in table_data or len(value) > len(table_data[key]):
                    table_data[key] = value
                break

    def extract_course_details(self, html: str, url: str) -> Dict:
        """
        Intelligently extract course details from a page.
        Uses multiple strategies to find information.
        """
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)

        course = {
            'url': url,
            'name': self._smart_extract_name(soup, url),
            'description': self._smart_extract_description(soup),
            'duration': self._smart_extract_duration(soup, text),
            'fees_domestic': self._smart_extract_fees(soup, text, 'domestic'),
            'fees_international': self._smart_extract_fees(soup, text, 'international'),
            'entry_requirements': self._smart_extract_requirements(soup, text),
            'atar': self._extract_atar(text),
            'study_mode': self._smart_extract_study_mode(soup, text),
            'intake': self._extract_intake(text),
            'campus': self._extract_campus(soup, text),
            'career_outcomes': self._smart_extract_careers(soup),
        }

        return course

    def _smart_extract_name(self, soup: BeautifulSoup, url: str) -> str:
        """Intelligently extract course name."""
        # Priority 1: Specific course title selectors
        selectors = [
            'h1.course-title', 'h1.program-title', '.course-header h1',
            '.program-header h1', '[class*="course-name"]', '[class*="degree-title"]',
            '.hero-content h1', '.banner-content h1', 'article h1',
            '.page-header h1', 'main h1', 'h1'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                name = elem.get_text(strip=True)
                # Filter out generic names
                if name and len(name) > 5 and len(name) < 200:
                    if not any(x in name.lower() for x in ['menu', 'navigation', 'search', 'login', 'home']):
                        return name

        # Priority 2: Try og:title meta
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            return og_title['content']

        # Priority 3: Extract from URL
        path = urlparse(url).path
        parts = [p for p in path.split('/') if p and len(p) > 3]
        if parts:
            return parts[-1].replace('-', ' ').title()

        return ""

    def _smart_extract_description(self, soup: BeautifulSoup) -> str:
        """Extract course description intelligently."""
        # Try meta description first
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta and meta.get('content') and len(meta['content']) > 50:
            return meta['content'][:500]

        # Try common description containers
        selectors = [
            '.course-description', '.program-description', '.overview',
            '[class*="overview"]', '[class*="summary"]', '[class*="intro"]',
            '.lead', '.excerpt', 'article > p', '.content > p'
        ]

        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(strip=True)
                if len(text) > 100:
                    return text[:500]

        # Try first substantial paragraph
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if len(text) > 100 and not any(x in text.lower() for x in ['cookie', 'privacy', 'javascript']):
                return text[:500]

        return ""

    def _smart_extract_duration(self, soup: BeautifulSoup, text: str) -> str:
        """Extract duration with multiple patterns."""
        # Pattern 1: Duration label followed by value
        patterns = [
            r'(?:duration|length|time)[:\s]+(\d+(?:\.\d+)?[\s-]*(?:to[\s-]*\d+(?:\.\d+)?)?[\s]*(?:years?|months?|semesters?|weeks?)(?:[\s]*(?:full[- ]?time|part[- ]?time|FT|PT))?)',
            r'(\d+(?:\.\d+)?[\s-]*(?:to[\s-]*\d+(?:\.\d+)?)?[\s]*years?[\s]*(?:full[- ]?time|part[- ]?time)?)',
            r'(?:full[- ]?time)[:\s]+(\d+(?:\.\d+)?[\s]*(?:years?|months?|semesters?))',
            r'(?:part[- ]?time)[:\s]+(\d+(?:\.\d+)?[\s]*(?:years?|months?|semesters?))',
            r'(\d+[\s-]*(?:year|yr)s?[\s]+(?:full[- ]?time|FT))',
            r'(\d+[\s-]*(?:year|yr)s?[\s]+(?:part[- ]?time|PT))',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                duration = match.group(1).strip()
                if duration:
                    return duration

        # Try selectors
        selectors = ['.duration', '[class*="duration"]', '[data-duration]']
        for selector in selectors:
            try:
                elem = soup.select_one(selector)
                if elem:
                    text = elem.get_text(strip=True)
                    if any(x in text.lower() for x in ['year', 'month', 'semester']):
                        return text
            except:
                pass

        return ""

    def _smart_extract_fees(self, soup: BeautifulSoup, text: str, fee_type: str) -> str:
        """Extract fees - domestic or international."""
        # Australian fee patterns
        if fee_type == 'domestic':
            patterns = [
                r'(?:domestic|australian|local)[\s\w]*(?:fee|cost|tuition)[s]?[:\s]*\$?([\d,]+(?:\.\d{2})?)',
                r'(?:CSP|commonwealth[\s]*supported)[:\s]*\$?([\d,]+)',
                r'(?:annual[\s]*)?(?:fee|tuition)[:\s]*\$?([\d,]+)[\s]*(?:per[\s]*year|p\.?a\.?|annually)',
            ]
        else:
            patterns = [
                r'(?:international|overseas)[\s\w]*(?:fee|cost|tuition)[s]?[:\s]*\$?([\d,]+(?:\.\d{2})?)',
                r'(?:international)[\s\w]*\$?([\d,]+)[\s]*(?:per[\s]*year|p\.?a\.?)',
            ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                fee = match.group(1).replace(',', '')
                try:
                    fee_num = float(fee)
                    if 1000 < fee_num < 200000:
                        return f"${fee_num:,.0f}"
                except:
                    pass

        # Generic fee pattern as fallback
        if fee_type == 'domestic':
            # Look for any fee that seems reasonable for domestic
            pattern = r'\$([\d,]+)[\s]*(?:per[\s]*year|annually|p\.?a\.?)'
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    fee_num = float(match.replace(',', ''))
                    if 5000 < fee_num < 50000:  # Typical domestic range
                        return f"${fee_num:,.0f}"
                except:
                    pass

        return ""

    def _smart_extract_requirements(self, soup: BeautifulSoup, text: str) -> str:
        """Extract entry requirements."""
        requirements = []

        # Look for requirement sections
        selectors = [
            '[class*="requirement"]', '[class*="eligibility"]',
            '[class*="entry"]', '[class*="admission"]',
            '[class*="prerequisite"]'
        ]

        for selector in selectors:
            elems = soup.select(selector)
            for elem in elems[:2]:
                req_text = elem.get_text(strip=True)
                if len(req_text) > 20 and len(req_text) < 500:
                    requirements.append(req_text[:200])

        # Look for specific patterns in text
        patterns = [
            r'(?:entry requirements?|admission requirements?|prerequisites?)[:\s]+([^.]+\.)',
            r'(?:you(?:\'ll)?[\s]+need|applicants?[\s]+must[\s]+have)[:\s]+([^.]+\.)',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                requirements.append(match.group(1).strip()[:200])

        return ' | '.join(requirements[:2]) if requirements else ""

    def _extract_atar(self, text: str) -> str:
        """Extract ATAR score if present."""
        patterns = [
            r'ATAR[:\s]+(\d{2}(?:\.\d{1,2})?)',
            r'(?:selection[\s]+rank|minimum[\s]+ATAR)[:\s]+(\d{2}(?:\.\d{1,2})?)',
            r'(\d{2}(?:\.\d{1,2})?)[\s]*ATAR',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                atar = match.group(1)
                try:
                    atar_num = float(atar)
                    if 50 <= atar_num <= 99.95:
                        return str(atar_num)
                except:
                    pass
        return ""

    def _smart_extract_study_mode(self, soup: BeautifulSoup, text: str) -> str:
        """Extract study mode."""
        modes = []
        text_lower = text.lower()

        mode_keywords = {
            'On-campus': ['on-campus', 'on campus', 'face-to-face', 'in person'],
            'Online': ['online', 'distance', 'remote'],
            'Flexible': ['flexible', 'blended', 'hybrid'],
            'Part-time': ['part-time', 'part time'],
            'Full-time': ['full-time', 'full time'],
        }

        for mode, keywords in mode_keywords.items():
            if any(kw in text_lower for kw in keywords):
                modes.append(mode)

        return ', '.join(modes) if modes else ""

    def _extract_intake(self, text: str) -> str:
        """Extract intake/start dates."""
        patterns = [
            r'(?:intake|start|commence)[s]?[:\s]+(?:in[\s]+)?([A-Za-z]+[\s]+\d{4})',
            r'(?:semester[\s]+[12]|term[\s]+[1-4])[,\s]+(\d{4})',
            r'(?:february|march|july|august)[\s]+(?:and[\s]+)?(?:february|march|july|august)?[\s]*(?:intake)?',
        ]

        intakes = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            intakes.extend(matches[:3])

        return ', '.join(set(intakes)) if intakes else ""

    def _extract_campus(self, soup: BeautifulSoup, text: str) -> str:
        """Extract campus location."""
        # Common Australian university campuses
        campuses = ['Sydney', 'Melbourne', 'Brisbane', 'Perth', 'Canberra',
                    'Adelaide', 'Gold Coast', 'Parramatta', 'Kensington',
                    'St Lucia', 'Gatton', 'Clayton', 'Parkville']

        found = []
        for campus in campuses:
            if campus.lower() in text.lower():
                found.append(campus)

        return ', '.join(found[:3]) if found else ""

    def _smart_extract_careers(self, soup: BeautifulSoup) -> List[str]:
        """Extract career outcomes."""
        careers = []

        selectors = [
            '[class*="career"] li', '[class*="outcome"] li',
            '[class*="employment"] li', '[class*="graduate"] li',
            '.careers li', '.opportunities li'
        ]

        for selector in selectors:
            elems = soup.select(selector)
            for elem in elems[:10]:
                text = elem.get_text(strip=True)
                if 5 < len(text) < 100:
                    careers.append(text)
            if careers:
                break

        return careers

    def find_course_links(self, html: str, base_url: str) -> List[str]:
        """Find links to individual course pages."""
        soup = BeautifulSoup(html, 'html.parser')
        course_links = []
        seen = set()

        for link in soup.find_all('a', href=True):
            href = link['href']
            full_url = urljoin(base_url, href)

            # Skip if already seen or external
            if full_url in seen:
                continue
            if not full_url.startswith(('http://', 'https://')):
                continue

            href_lower = href.lower()
            link_text = link.get_text(strip=True).lower()

            # Check if it looks like a course page
            is_course = False

            # Check URL patterns
            for pattern in self.COURSE_PAGE_PATTERNS:
                if re.search(pattern, href_lower):
                    is_course = True
                    break

            # Check link text for course indicators
            course_keywords = ['bachelor', 'master', 'graduate', 'diploma',
                             'certificate', 'degree', 'program']
            if any(kw in link_text for kw in course_keywords):
                is_course = True

            if is_course:
                seen.add(full_url)
                course_links.append(full_url)

        return course_links[:30]  # Limit per page

    def crawl_university(self, name: str, base_url: str, course_urls: List[str],
                        max_courses: int = 20, delay: float = 1.0) -> Dict:
        """Crawl a university for detailed course information."""
        print(f"\n{'='*70}")
        print(f"CRAWLING: {name}")
        print(f"{'='*70}")

        result = {
            'university': name,
            'website': base_url,
            'courses': []
        }

        all_course_links = []

        # Step 1: Gather course links from catalog pages
        for catalog_url in course_urls:
            print(f"\n  Fetching catalog: {catalog_url[:60]}...")
            html = self.fetch_page(catalog_url)
            if html:
                links = self.find_course_links(html, catalog_url)
                print(f"    Found {len(links)} course links")
                all_course_links.extend(links)
            time.sleep(delay)

        # Remove duplicates
        all_course_links = list(dict.fromkeys(all_course_links))
        print(f"\n  Total unique course links: {len(all_course_links)}")

        # Step 2: Crawl individual course pages
        for i, course_url in enumerate(all_course_links[:max_courses]):
            print(f"\n  [{i+1}/{min(len(all_course_links), max_courses)}] Crawling course...")
            print(f"    URL: {course_url[:70]}...")

            html = self.fetch_page(course_url)
            if html:
                # Save HTML
                safe_name = re.sub(r'[^\w\-_.]', '_', urlparse(course_url).path)[:80]
                html_path = os.path.join(self.html_dir, f"{safe_name}.html")
                with open(html_path, 'w', encoding='utf-8') as f:
                    f.write(html)

                # Extract details
                course = self.extract_course_details(html, course_url)

                if course['name'] and len(course['name']) > 5:
                    result['courses'].append(course)
                    print(f"    Name: {course['name'][:50]}")
                    if course['duration']:
                        print(f"    Duration: {course['duration']}")
                    if course['fees_domestic']:
                        print(f"    Fees (Domestic): {course['fees_domestic']}")
                    if course['fees_international']:
                        print(f"    Fees (International): {course['fees_international']}")

            time.sleep(delay)

        print(f"\n  Extracted {len(result['courses'])} courses with details")
        return result

    def run(self):
        """Run the deep crawler for all universities."""
        universities = [
            {
                'name': 'University of New South Wales',
                'base_url': 'https://www.unsw.edu.au/',
                'course_urls': [
                    'https://www.unsw.edu.au/study/find-a-degree-or-course',
                    'https://www.unsw.edu.au/study/undergraduate',
                    'https://www.unsw.edu.au/study/postgraduate',
                ]
            },
            {
                'name': 'University of Queensland',
                'base_url': 'https://www.uq.edu.au/',
                'course_urls': [
                    'https://study.uq.edu.au/study-options/programs',
                    'https://study.uq.edu.au/study-options/browse-study-areas',
                ]
            },
            {
                'name': 'Australian National University',
                'base_url': 'https://www.anu.edu.au/',
                'course_urls': [
                    'https://programsandcourses.anu.edu.au/',
                    'https://programsandcourses.anu.edu.au/catalogue',
                ]
            },
        ]

        print("=" * 70)
        print("DEEP COURSE CRAWLER - Extracting Detailed Information")
        print("=" * 70)
        print("\nExtracting: Name, Description, Duration, Fees, Requirements")
        print("=" * 70)

        all_results = []

        for uni in universities:
            result = self.crawl_university(
                uni['name'],
                uni['base_url'],
                uni['course_urls'],
                max_courses=15,
                delay=1.0
            )
            all_results.append(result)

            # Save intermediate results
            output_path = os.path.join(self.json_dir, 'detailed_courses.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(all_results, f, indent=2, ensure_ascii=False)

        # Print summary
        self._print_summary(all_results)

        return all_results

    def _print_summary(self, results: List[Dict]):
        """Print a formatted summary of results."""
        print("\n" + "=" * 70)
        print("CRAWL COMPLETE - DETAILED SUMMARY")
        print("=" * 70)

        for uni in results:
            print(f"\n{uni['university']}")
            print("-" * 50)
            print(f"Total courses: {len(uni['courses'])}")

            if uni['courses']:
                print("\nSample courses with details:")
                for course in uni['courses'][:5]:
                    print(f"\n  {course['name'][:60]}")
                    if course['description']:
                        print(f"    Description: {course['description'][:80]}...")
                    if course['duration']:
                        print(f"    Duration: {course['duration']}")
                    if course['fees_domestic']:
                        print(f"    Fees (Domestic): {course['fees_domestic']}")
                    if course['fees_international']:
                        print(f"    Fees (Intl): {course['fees_international']}")
                    if course['atar']:
                        print(f"    ATAR: {course['atar']}")
                    if course['study_mode']:
                        print(f"    Study Mode: {course['study_mode']}")
                    if course['entry_requirements']:
                        print(f"    Requirements: {course['entry_requirements'][:60]}...")

        total = sum(len(u['courses']) for u in results)
        print(f"\n{'='*70}")
        print(f"TOTAL COURSES EXTRACTED: {total}")
        print(f"Output saved to: output/json/detailed_courses.json")
        print("=" * 70)


if __name__ == "__main__":
    crawler = DeepCourseCrawler()
    crawler.run()
