"""
University Course Web Crawler
=============================
Crawls university websites to extract course information and saves data
in multiple formats (HTML, JSON, Text).

Usage:
    python main.py                    # Use default Excel file
    python main.py path/to/file.xlsx  # Use custom Excel file
"""

from crawler import WebCrawler
import os
import sys


def main():
    # Initialize crawler
    crawler = WebCrawler(output_dir="output")

    # Default Excel file path (Australian universities)
    default_excel = r"C:\Users\sushr\Desktop\task-webcraler\australia-website-data.xlsx"

    # Allow custom Excel file via command line
    if len(sys.argv) > 1:
        excel_path = sys.argv[1]
    else:
        excel_path = default_excel

    if not os.path.exists(excel_path):
        print(f"Excel file not found: {excel_path}")
        print("\nUsage: python main.py [path/to/excel_file.xlsx]")
        return

    print("=" * 60)
    print("UNIVERSITY COURSE WEB CRAWLER")
    print("=" * 60)
    print(f"\nSource file: {excel_path}")
    print("\nThis crawler will:")
    print("  1. Visit each university website")
    print("  2. Discover course/program pages")
    print("  3. Extract course details (name, duration, fees, etc.)")
    print("  4. Save data in HTML, JSON, and Text formats")
    print("\n" + "=" * 60)

    # Crawl universities from Excel file
    results = crawler.crawl_universities_from_excel(
        excel_path=excel_path,
        discover_courses=True,
        max_courses_per_uni=10,  # Limit courses per university
        delay=1.5  # Be respectful to servers
    )

    # Print summary
    print("\n" + "=" * 60)
    print("CRAWL SUMMARY")
    print("=" * 60)

    total_courses = sum(len(r.get('courses', [])) for r in results)
    successful_unis = sum(1 for r in results if r.get('courses'))

    print(f"Universities processed: {len(results)}")
    print(f"Universities with courses found: {successful_unis}")
    print(f"Total courses extracted: {total_courses}")
    print(f"\nOutput saved to:")
    print(f"  - HTML files: output/html/")
    print(f"  - JSON data: output/json/all_universities.json")
    print(f"  - Course list: output/text/all_courses.txt")

    # Display summary per university
    if results:
        print("\n" + "-" * 40)
        print("Courses per University:")
        print("-" * 40)
        for r in results:
            course_count = len(r.get('courses', []))
            print(f"  {r['university']}: {course_count} courses")


if __name__ == "__main__":
    main()
