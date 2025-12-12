"""
Crawl Top 5 Australian Universities
====================================
Focused crawl of:
1. University of Melbourne
2. University of Sydney
3. Australian National University (ANU)
4. University of New South Wales (UNSW)
5. University of Queensland
"""

from crawler import WebCrawler
import json
import os

# Top 5 Australian Universities
TOP_5_UNIVERSITIES = [
    {
        'name': 'The University of Melbourne',
        'city': 'Melbourne',
        'state': 'Victoria',
        'website': 'https://www.unimelb.edu.au/',
        'courses_url': 'https://study.unimelb.edu.au/find/'
    },
    {
        'name': 'The University of Sydney',
        'city': 'Sydney',
        'state': 'New South Wales',
        'website': 'https://www.sydney.edu.au/',
        'courses_url': 'https://www.sydney.edu.au/courses/'
    },
    {
        'name': 'Australian National University',
        'city': 'Canberra',
        'state': 'Australian Capital Territory',
        'website': 'https://www.anu.edu.au/',
        'courses_url': 'https://programsandcourses.anu.edu.au/'
    },
    {
        'name': 'University of New South Wales',
        'city': 'Sydney',
        'state': 'New South Wales',
        'website': 'https://www.unsw.edu.au/',
        'courses_url': 'https://www.unsw.edu.au/study'
    },
    {
        'name': 'The University of Queensland',
        'city': 'Brisbane',
        'state': 'Queensland',
        'website': 'https://www.uq.edu.au/',
        'courses_url': 'https://study.uq.edu.au/study-options/programs'
    }
]


def crawl_top5():
    """Crawl the top 5 Australian universities."""
    crawler = WebCrawler(output_dir="output")

    print("=" * 70)
    print("TOP 5 AUSTRALIAN UNIVERSITIES CRAWLER")
    print("=" * 70)
    print("\nUniversities to crawl:")
    for i, uni in enumerate(TOP_5_UNIVERSITIES, 1):
        print(f"  {i}. {uni['name']} ({uni['city']})")
    print("\n" + "=" * 70)

    # Clear previous text file
    text_file = os.path.join("output", "text", "all_courses.txt")
    if os.path.exists(text_file):
        os.remove(text_file)

    results = []

    for i, uni in enumerate(TOP_5_UNIVERSITIES):
        print(f"\n[{i+1}/5] Crawling {uni['name']}...")
        print("-" * 50)

        result = {
            'university': uni['name'],
            'city': uni['city'],
            'state': uni['state'],
            'website': uni['website'],
            'courses': []
        }

        # First, try the dedicated courses URL
        courses_url = uni.get('courses_url', uni['website'])
        print(f"  Fetching courses page: {courses_url}")

        html = crawler.fetch_page(courses_url)
        if html:
            crawler.save_html(courses_url, html)

            # Discover course links
            course_links = crawler.discover_course_links(courses_url, html)
            print(f"  Found {len(course_links)} course-related links")

            # Crawl up to 15 course pages
            for j, course_url in enumerate(course_links[:15]):
                print(f"    [{j+1}/{min(15, len(course_links))}] {course_url[:60]}...")

                import time
                time.sleep(1)  # Be respectful

                course_html = crawler.fetch_page(course_url)
                if course_html:
                    crawler.save_html(course_url, course_html)
                    course_data = crawler.extract_course_info(course_html, course_url)

                    # Only add if we got meaningful data
                    if course_data.get('name') and len(course_data['name']) > 5:
                        result['courses'].append(course_data)
                        crawler.save_text(f"{uni['name']}: {course_data['name']}")

        results.append(result)

        # Save intermediate results
        with open(os.path.join("output", "json", "top5_universities.json"), 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

    # Print summary
    print("\n" + "=" * 70)
    print("CRAWL COMPLETE - SUMMARY")
    print("=" * 70)

    total_courses = 0
    for r in results:
        course_count = len(r.get('courses', []))
        total_courses += course_count
        print(f"\n{r['university']}:")
        print(f"  Location: {r['city']}, {r['state']}")
        print(f"  Courses found: {course_count}")

        if r['courses']:
            print("  Sample courses:")
            for course in r['courses'][:5]:
                name = course.get('name', 'N/A')[:50]
                duration = course.get('duration', 'N/A')
                fees = course.get('fees', 'N/A')
                print(f"    - {name}")
                if duration:
                    print(f"      Duration: {duration}")
                if fees:
                    print(f"      Fees: {fees}")

    print(f"\n{'=' * 70}")
    print(f"Total courses extracted: {total_courses}")
    print(f"\nOutput saved to:")
    print(f"  - JSON: output/json/top5_universities.json")
    print(f"  - HTML: output/html/")
    print(f"  - Text: output/text/all_courses.txt")
    print("=" * 70)

    return results


if __name__ == "__main__":
    crawl_top5()
