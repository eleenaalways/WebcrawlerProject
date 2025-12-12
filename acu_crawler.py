"""
ACU (Australian Catholic University) Course Data Extractor
===========================================================
Extracts comprehensive course information including:
- Course name, description, fees
- Department/Faculty
- Study level (Undergraduate/Postgraduate)
- Course type (Degree, Diploma, Certificate, Short Course)
- Study mode (Full-time, Part-time, Online, On-campus)
- Campus locations (cities)
- Subject areas with grouping

Output: Clean JSON format grouped by study area
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from collections import defaultdict


@dataclass
class CourseData:
    """Data class for course information."""
    course_name: str
    department: str
    study_level: str
    course_type: str
    subject_area: str
    duration: str
    study_mode: Dict[str, bool]
    delivery_mode: Dict[str, bool]
    campuses: List[str]
    fees: Dict[str, str]
    description: str
    atar_requirement: str
    intake_periods: List[str]
    url: str


class ACUCourseCrawler:
    """
    Specialized crawler for Australian Catholic University (ACU) courses.
    Extracts detailed course information and groups by study area.
    """

    BASE_URL = "https://www.acu.edu.au"

    # ACU course URLs organized by subject area (verified working URLs)
    COURSE_URLS = {
        "Nursing & Midwifery": [
            "/course/bachelor-of-nursing",
            "/course/bachelor-of-midwifery",
        ],
        "Allied Health": [
            "/course/bachelor-of-physiotherapy",
            "/course/bachelor-of-speech-pathology",
            "/course/bachelor-of-occupational-therapy",
            "/course/bachelor-of-paramedicine",
        ],
        "Business & Commerce": [
            "/course/bachelor-of-commerce",
            "/course/bachelor-of-business",
            "/course/bachelor-of-accounting-and-finance",
            "/course/master-of-business-administration",
            "/course/graduate-certificate-in-business-administration",
        ],
        "Information Technology": [
            "/course/bachelor-of-information-technology",
            "/course/master-of-information-technology",
        ],
        "Education & Teaching": [
            "/course/bachelor-of-education-primary",
            "/course/bachelor-of-education-secondary",
            "/course/bachelor-of-early-childhood-education-birth-to-five-years",
            "/course/master-of-teaching-primary",
            "/course/master-of-teaching-secondary",
            "/course/master-of-education",
            "/course/graduate-certificate-in-education",
            "/course/graduate-certificate-in-religious-education",
        ],
        "Law & Criminology": [
            "/course/bachelor-of-laws",
            "/course/bachelor-of-criminology-and-criminal-justice",
        ],
        "Psychology": [
            "/course/bachelor-of-psychological-science",
            "/course/master-of-psychology-clinical",
            "/course/master-of-professional-psychology",
        ],
        "Social Work & Community Services": [
            "/course/bachelor-of-social-work",
            "/course/bachelor-of-youth-work",
        ],
        "Theology & Philosophy": [
            "/course/bachelor-of-theology",
        ],
        "Exercise & Sports Science": [
            "/course/bachelor-of-exercise-and-sports-science",
        ],
        "Nutrition & Biomedical Science": [
            "/course/bachelor-of-biomedical-science",
            "/course/bachelor-of-nutrition-science",
        ],
        "Creative Arts & Humanities": [
            "/course/bachelor-of-creative-arts",
            "/course/bachelor-of-visual-arts-and-design",
            "/course/bachelor-of-arts",
        ],
    }

    # Department mapping based on subject area
    DEPARTMENT_MAP = {
        "Nursing & Midwifery": "Faculty of Health Sciences",
        "Allied Health": "Faculty of Health Sciences",
        "Psychology": "Faculty of Health Sciences",
        "Exercise & Sports Science": "Faculty of Health Sciences",
        "Nutrition & Biomedical Science": "Faculty of Health Sciences",
        "Business & Commerce": "Faculty of Law and Business",
        "Information Technology": "Faculty of Law and Business",
        "Law & Criminology": "Faculty of Law and Business",
        "Education & Teaching": "Faculty of Education and Arts",
        "Social Work & Community Services": "Faculty of Education and Arts",
        "Creative Arts & Humanities": "Faculty of Education and Arts",
        "Theology & Philosophy": "Faculty of Theology and Philosophy",
    }

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-AU,en;q=0.9',
        })
        self.courses_data: List[CourseData] = []

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch HTML content from URL with retry logic."""
        full_url = url if url.startswith('http') else f"{self.BASE_URL}{url}"

        for attempt in range(3):
            try:
                response = self.session.get(full_url, timeout=30)
                response.raise_for_status()
                return response.text
            except requests.RequestException as e:
                print(f"  Attempt {attempt + 1} failed for {full_url}: {e}")
                if attempt < 2:
                    time.sleep(2)
        return None

    def extract_course_name(self, soup: BeautifulSoup) -> str:
        """Extract course name from page."""
        selectors = [
            'h1.cmp-title__text',
            'h1[class*="title"]',
            '.hero-banner h1',
            '.page-header h1',
            'h1',
        ]
        for selector in selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(strip=True)
                if text and len(text) > 5:
                    return text
        return "Not Found"

    def extract_study_level(self, course_name: str, url: str) -> str:
        """Determine study level from course name and URL."""
        name_lower = course_name.lower()
        url_lower = url.lower()

        if any(term in name_lower or term in url_lower for term in
               ['master', 'graduate certificate', 'graduate diploma', 'postgraduate',
                'doctorate', 'phd', 'juris doctor']):
            return "Postgraduate"
        elif any(term in name_lower or term in url_lower for term in
                 ['bachelor', 'undergraduate', 'diploma']):
            return "Undergraduate"
        elif 'short-course' in url_lower or 'certificate' in name_lower:
            return "Short Course"
        return "Not Found"

    def extract_course_type(self, course_name: str) -> str:
        """Determine course type from name."""
        name_lower = course_name.lower()

        if 'bachelor' in name_lower:
            return "Bachelor Degree"
        elif 'master' in name_lower:
            return "Master Degree"
        elif 'juris doctor' in name_lower:
            return "Professional Doctorate"
        elif 'graduate certificate' in name_lower:
            return "Graduate Certificate"
        elif 'graduate diploma' in name_lower:
            return "Graduate Diploma"
        elif 'diploma' in name_lower:
            return "Diploma"
        elif 'certificate' in name_lower:
            return "Certificate"
        elif 'phd' in name_lower or 'doctorate' in name_lower:
            return "Doctorate"
        return "Degree"

    def extract_duration(self, soup: BeautifulSoup) -> str:
        """Extract course duration."""
        text = soup.get_text()

        patterns = [
            r'(\d+(?:\.\d+)?)\s*years?\s*full[- ]?time',
            r'(\d+(?:\.\d+)?)\s*years?\s*(?:or\s+equivalent\s+)?part[- ]?time',
            r'duration[:\s]+(\d+(?:\.\d+)?)\s*years?',
            r'(\d+)\s*months?\s*full[- ]?time',
            r'(\d+)\s*semesters?',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                value = match.group(1)
                if 'month' in pattern:
                    return f"{value} months"
                elif 'semester' in pattern:
                    return f"{value} semesters"
                else:
                    return f"{value} years full-time or equivalent part-time"

        return "Not Found"

    def extract_study_mode(self, soup: BeautifulSoup) -> Dict[str, bool]:
        """Extract study mode (full-time/part-time)."""
        text = soup.get_text().lower()

        return {
            "full_time": bool(re.search(r'full[- ]?time', text)),
            "part_time": bool(re.search(r'part[- ]?time|equivalent part[- ]?time', text)),
        }

    def extract_delivery_mode(self, soup: BeautifulSoup) -> Dict[str, bool]:
        """Extract delivery mode (online/on-campus)."""
        text = soup.get_text().lower()

        return {
            "online": bool(re.search(r'\bonline\b|distance|remote', text)),
            "on_campus": bool(re.search(r'on[- ]?campus|face[- ]?to[- ]?face|in[- ]?person', text)),
            "blended": bool(re.search(r'blended|flexible|mixed mode', text)),
        }

    def extract_campuses(self, soup: BeautifulSoup) -> List[str]:
        """Extract campus locations (cities)."""
        text = soup.get_text()

        # ACU campus cities
        acu_campuses = [
            "Ballarat", "Blacktown", "Brisbane", "Canberra",
            "Melbourne", "North Sydney", "Strathfield", "Adelaide"
        ]

        found_campuses = []
        for campus in acu_campuses:
            if re.search(rf'\b{campus}\b', text, re.IGNORECASE):
                found_campuses.append(campus)

        # Check for online-only
        if not found_campuses and re.search(r'\bonline\s+only\b', text, re.IGNORECASE):
            found_campuses.append("Online")

        return found_campuses if found_campuses else ["Not Found"]

    def extract_fees(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract course fees."""
        text = soup.get_text()
        fees = {
            "domestic_csp": "Not Found",
            "domestic_fee_paying": "Not Found",
            "international": "Not Found",
        }

        # CSP (Commonwealth Supported Place) fees
        csp_pattern = r'\$?([\d,]+)\s*(?:CSP|Commonwealth\s+Supported)'
        csp_match = re.search(csp_pattern, text, re.IGNORECASE)
        if csp_match:
            fees["domestic_csp"] = f"${csp_match.group(1)} AUD/year (CSP)"

        # Alternative domestic fee pattern
        domestic_pattern = r'domestic[^$]*\$?([\d,]+)'
        domestic_match = re.search(domestic_pattern, text, re.IGNORECASE)
        if domestic_match and fees["domestic_csp"] == "Not Found":
            fees["domestic_csp"] = f"${domestic_match.group(1)} AUD/year"

        # Fee-paying pattern
        fee_paying_pattern = r'fee[- ]?paying[^$]*\$?([\d,]+)'
        fee_match = re.search(fee_paying_pattern, text, re.IGNORECASE)
        if fee_match:
            fees["domestic_fee_paying"] = f"${fee_match.group(1)} AUD/year"

        # International fees
        intl_pattern = r'international[^$]*\$?([\d,]+)'
        intl_match = re.search(intl_pattern, text, re.IGNORECASE)
        if intl_match:
            fees["international"] = f"${intl_match.group(1)} AUD/year"

        return fees

    def extract_description(self, soup: BeautifulSoup) -> str:
        """Extract course description."""
        selectors = [
            '.course-overview',
            '.course-description',
            '[class*="description"]',
            '[class*="overview"]',
            '.intro-text',
            'article p',
            '.content p',
        ]

        for selector in selectors:
            elements = soup.select(selector)
            for element in elements:
                text = element.get_text(strip=True)
                if text and len(text) > 100:
                    return text[:500] + "..." if len(text) > 500 else text

        # Try meta description
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta and meta.get('content'):
            return meta['content']

        return "Not Found"

    def extract_atar(self, soup: BeautifulSoup) -> str:
        """Extract ATAR requirement."""
        text = soup.get_text()

        patterns = [
            r'ATAR[:\s]+(\d+(?:\.\d+)?)',
            r'selection\s+rank[:\s]+(\d+(?:\.\d+)?)',
            r'minimum\s+ATAR[:\s]+(\d+(?:\.\d+)?)',
        ]

        atar_scores = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            atar_scores.extend(matches)

        if atar_scores:
            # Return range if multiple scores found
            scores = [float(s) for s in atar_scores]
            if len(set(scores)) > 1:
                return f"{min(scores):.2f} - {max(scores):.2f}"
            return f"{scores[0]:.2f}"

        return "Not Found"

    def extract_intake_periods(self, soup: BeautifulSoup) -> List[str]:
        """Extract intake/start periods."""
        text = soup.get_text()
        intakes = []

        if re.search(r'semester\s*1|february|feb\s+\d{4}', text, re.IGNORECASE):
            intakes.append("Semester 1 (February)")
        if re.search(r'semester\s*2|july|jul\s+\d{4}|mid[- ]?year', text, re.IGNORECASE):
            intakes.append("Semester 2 (July)")
        if re.search(r'trimester', text, re.IGNORECASE):
            intakes.append("Multiple trimesters")

        return intakes if intakes else ["Not Found"]

    def extract_course_data(self, url: str, subject_area: str) -> Optional[CourseData]:
        """Extract all course data from a single URL."""
        print(f"  Fetching: {url}")

        html = self.fetch_page(url)
        if not html:
            return None

        soup = BeautifulSoup(html, 'html.parser')

        course_name = self.extract_course_name(soup)
        if course_name == "Not Found":
            return None

        return CourseData(
            course_name=course_name,
            department=self.DEPARTMENT_MAP.get(subject_area, "Not Found"),
            study_level=self.extract_study_level(course_name, url),
            course_type=self.extract_course_type(course_name),
            subject_area=subject_area,
            duration=self.extract_duration(soup),
            study_mode=self.extract_study_mode(soup),
            delivery_mode=self.extract_delivery_mode(soup),
            campuses=self.extract_campuses(soup),
            fees=self.extract_fees(soup),
            description=self.extract_description(soup),
            atar_requirement=self.extract_atar(soup),
            intake_periods=self.extract_intake_periods(soup),
            url=f"{self.BASE_URL}{url}" if not url.startswith('http') else url,
        )

    def crawl_all_courses(self, delay: float = 1.5) -> List[CourseData]:
        """Crawl all courses from all subject areas."""
        print("=" * 70)
        print("ACU Course Data Extractor")
        print("=" * 70)
        print(f"Starting crawl at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        total_urls = sum(len(urls) for urls in self.COURSE_URLS.values())
        print(f"Total courses to crawl: {total_urls}")
        print()

        crawled = 0
        for subject_area, urls in self.COURSE_URLS.items():
            print(f"\n[{subject_area}] - {len(urls)} courses")
            print("-" * 50)

            for url in urls:
                crawled += 1
                print(f"  [{crawled}/{total_urls}] ", end="")

                course_data = self.extract_course_data(url, subject_area)
                if course_data:
                    self.courses_data.append(course_data)
                    print(f"[OK] {course_data.course_name}")
                else:
                    print(f"[FAIL] Failed to extract from {url}")

                time.sleep(delay)

        print(f"\n{'=' * 70}")
        print(f"Crawl completed! Successfully extracted {len(self.courses_data)} courses.")
        print("=" * 70)

        return self.courses_data

    def group_by_study_area(self) -> Dict[str, List[Dict]]:
        """Group courses by study area."""
        grouped = defaultdict(list)

        for course in self.courses_data:
            course_dict = asdict(course)
            grouped[course.subject_area].append(course_dict)

        return dict(grouped)

    def group_by_study_level(self) -> Dict[str, List[Dict]]:
        """Group courses by study level."""
        grouped = defaultdict(list)

        for course in self.courses_data:
            course_dict = asdict(course)
            grouped[course.study_level].append(course_dict)

        return dict(grouped)

    def generate_summary(self) -> Dict:
        """Generate summary statistics."""
        summary = {
            "total_courses": len(self.courses_data),
            "by_study_level": defaultdict(int),
            "by_course_type": defaultdict(int),
            "by_subject_area": defaultdict(int),
            "by_campus": defaultdict(int),
            "online_available": 0,
            "part_time_available": 0,
        }

        for course in self.courses_data:
            summary["by_study_level"][course.study_level] += 1
            summary["by_course_type"][course.course_type] += 1
            summary["by_subject_area"][course.subject_area] += 1

            for campus in course.campuses:
                summary["by_campus"][campus] += 1

            if course.delivery_mode.get("online"):
                summary["online_available"] += 1
            if course.study_mode.get("part_time"):
                summary["part_time_available"] += 1

        # Convert defaultdicts to regular dicts
        summary["by_study_level"] = dict(summary["by_study_level"])
        summary["by_course_type"] = dict(summary["by_course_type"])
        summary["by_subject_area"] = dict(summary["by_subject_area"])
        summary["by_campus"] = dict(summary["by_campus"])

        return summary

    def to_json(self, grouped_by: str = "study_area") -> Dict:
        """
        Convert courses to JSON format.

        Args:
            grouped_by: "study_area", "study_level", or "none"
        """
        output = {
            "university": "Australian Catholic University (ACU)",
            "website": self.BASE_URL,
            "extraction_date": datetime.now().strftime("%Y-%m-%d"),
            "extraction_time": datetime.now().strftime("%H:%M:%S"),
            "summary": self.generate_summary(),
        }

        if grouped_by == "study_area":
            output["courses_by_study_area"] = self.group_by_study_area()
        elif grouped_by == "study_level":
            output["courses_by_study_level"] = self.group_by_study_level()
        else:
            output["courses"] = [asdict(c) for c in self.courses_data]

        return output

    def save_json(self, filepath: str, grouped_by: str = "study_area"):
        """Save data to JSON file."""
        data = self.to_json(grouped_by)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"\nData saved to: {filepath}")

    def print_summary(self):
        """Print a formatted summary of extracted data."""
        summary = self.generate_summary()

        print("\n" + "=" * 70)
        print("EXTRACTION SUMMARY")
        print("=" * 70)

        print(f"\nTotal Courses Extracted: {summary['total_courses']}")

        print(f"\nBy Study Level:")
        for level, count in summary['by_study_level'].items():
            print(f"  - {level}: {count}")

        print(f"\nBy Course Type:")
        for ctype, count in summary['by_course_type'].items():
            print(f"  - {ctype}: {count}")

        print(f"\nBy Subject Area:")
        for area, count in sorted(summary['by_subject_area'].items()):
            print(f"  - {area}: {count}")

        print(f"\nBy Campus Location:")
        for campus, count in sorted(summary['by_campus'].items(), key=lambda x: -x[1]):
            print(f"  - {campus}: {count}")

        print(f"\nStudy Options:")
        print(f"  - Online courses available: {summary['online_available']}")
        print(f"  - Part-time study available: {summary['part_time_available']}")

        print("\n" + "=" * 70)


def main():
    """Main function to run the ACU course crawler."""
    import os

    # Create output directory (use absolute path)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output", "acu")
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Initialize crawler
    crawler = ACUCourseCrawler(output_dir=output_dir)

    # Crawl all courses
    crawler.crawl_all_courses(delay=1.5)

    # Print summary
    crawler.print_summary()

    # Save to JSON (grouped by study area)
    crawler.save_json(
        filepath=os.path.join(output_dir, "acu_courses_by_study_area.json"),
        grouped_by="study_area"
    )

    # Also save grouped by study level
    crawler.save_json(
        filepath=os.path.join(output_dir, "acu_courses_by_study_level.json"),
        grouped_by="study_level"
    )

    # Save flat list
    crawler.save_json(
        filepath=os.path.join(output_dir, "acu_courses_all.json"),
        grouped_by="none"
    )

    print("\nAll data files saved successfully!")

    return crawler.to_json()


if __name__ == "__main__":
    main()
