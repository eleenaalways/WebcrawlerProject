# WebcrawlerProject - Extraction Improvement Plan

## Overview
This plan outlines improvements to enhance course data extraction accuracy for the university web crawler.

---

## Current State Analysis

### Existing Extraction Methods
- Basic CSS selector matching for course fields
- Regex patterns for duration, fees, ATAR
- Generic fallback patterns

### Identified Limitations
1. No structured data (JSON-LD/Schema.org) extraction
2. Missing table-based key-value extraction
3. No university-specific selectors
4. Limited fee pattern coverage
5. No credit points extraction
6. No course code extraction

---

## Proposed Improvements

### 1. JSON-LD/Schema.org Structured Data Extraction
**Priority: HIGH**

**Description:**
Extract course data from `<script type="application/ld+json">` tags. Many universities embed structured data following Schema.org standards (Course, EducationalOccupationalProgram schemas).

**Implementation:**
- Parse all JSON-LD scripts on the page
- Look for @type: Course, EducationalOccupationalProgram, Program
- Extract: name, description, duration, offers/price, provider, educationalCredentialAwarded

**File:** `deep_crawl.py`
**Method:** `_extract_json_ld(soup) -> Dict`

---

### 2. University-Specific CSS Selectors
**Priority: HIGH**

**Description:**
Add custom selectors for major Australian universities based on their actual HTML structure.

**Target Universities:**
| University | Domain | Custom Selectors Needed |
|------------|--------|------------------------|
| UNSW | unsw.edu.au | .degree-title, .key-info__item--duration |
| UQ | uq.edu.au | .program-title, .program-duration |
| ANU | anu.edu.au | .introduction__title, .degree-requirements |
| Sydney | sydney.edu.au | .b-course-header__title, .b-key-information |
| Melbourne | unimelb.edu.au | .course-title, .course-duration |

**Implementation:**
- Create `UNIVERSITY_SELECTORS` dictionary mapping domains to selectors
- Add `_get_university_selectors(url)` method
- Prioritize university-specific selectors before generic ones

**File:** `deep_crawl.py`

---

### 3. Table-Based Key-Value Extraction
**Priority: HIGH**

**Description:**
Many university pages display course info in tables, definition lists (dl/dt/dd), or structured div containers.

**Target Structures:**
- HTML tables with th/td pairs
- Definition lists (dl > dt + dd)
- Div containers with label/value patterns

**Key Mappings:**
```python
{
    'duration': ['duration', 'length', 'time to complete'],
    'fees': ['fees', 'tuition', 'cost', 'annual fee'],
    'fees_domestic': ['domestic fee', 'csp', 'commonwealth supported'],
    'fees_international': ['international fee', 'overseas fee'],
    'atar': ['atar', 'selection rank', 'guaranteed atar'],
    'credit_points': ['credit points', 'units', 'credits'],
    'course_code': ['course code', 'program code', 'cricos'],
    'intake': ['intake', 'start date', 'commencement'],
    'campus': ['campus', 'location'],
    'study_mode': ['study mode', 'delivery mode', 'attendance'],
}
```

**File:** `deep_crawl.py`
**Method:** `_extract_from_tables(soup) -> Dict`

---

### 4. Enhanced Fee Extraction
**Priority: MEDIUM**

**Description:**
Improve fee detection with better AUD-specific patterns and separate domestic/international fees.

**New Patterns:**
```python
# Domestic patterns
r'(?:domestic|australian|local)[\s\w]*(?:fee|cost|tuition)[s]?[:\s]*\$?([\d,]+)'
r'(?:CSP|commonwealth[\s]*supported)[:\s]*\$?([\d,]+)'
r'(?:annual[\s]*)?(?:fee|tuition)[:\s]*\$?([\d,]+)[\s]*(?:per[\s]*year|p\.?a\.?)'

# International patterns
r'(?:international|overseas)[\s\w]*(?:fee|cost|tuition)[s]?[:\s]*\$?([\d,]+)'
r'(?:international)[\s\w]*\$?([\d,]+)[\s]*(?:per[\s]*year|p\.?a\.?)'
```

**Validation:**
- Domestic fees: $5,000 - $50,000 range
- International fees: $15,000 - $80,000 range

**File:** `deep_crawl.py`
**Method:** `_smart_extract_fees(soup, text, fee_type)`

---

### 5. Credit Points Extraction
**Priority: MEDIUM**

**Description:**
Add new field to extract total credit points/units for courses.

**Patterns:**
```python
r'(\d+)\s*(?:credit\s*points?|CP|units?|credits?)'
r'(?:credit\s*points?|units?)[:\s]+(\d+)'
r'(?:total|required)[:\s]+(\d+)\s*(?:credit\s*points?|units?)'
```

**Validation:** 24-600 credit points (typical Australian degree range)

**File:** `deep_crawl.py`
**Method:** `_extract_credit_points(text) -> str`

---

### 6. Improved Duration Extraction
**Priority: MEDIUM**

**Description:**
Support duration ranges and multiple study modes.

**New Patterns:**
```python
# Range support
r'(\d+(?:\.\d+)?[\s-]*(?:to[\s-]*\d+(?:\.\d+)?)?[\s]*years?)'

# Full-time/Part-time specific
r'(?:full[- ]?time)[:\s]+(\d+(?:\.\d+)?[\s]*(?:years?|months?))'
r'(?:part[- ]?time)[:\s]+(\d+(?:\.\d+)?[\s]*(?:years?|months?))'
```

**Output Format:** "3 years full-time / 6 years part-time"

**File:** `deep_crawl.py`
**Method:** `_smart_extract_duration(soup, text)`

---

### 7. Course Code Extraction
**Priority: LOW**

**Description:**
Extract course/program codes and CRICOS codes.

**Patterns:**
```python
r'(?:course|program|degree)\s*code[:\s]+([A-Z]{2,5}\d{3,5})'
r'(?:CRICOS)[:\s]+(\d{5,7}[A-Z]?)'
r'\b([A-Z]{2,4}\d{4})\b'  # Common format like BENG1234
```

**File:** `deep_crawl.py`
**Method:** `_extract_course_code(soup, text) -> str`

---

## Implementation Order

### Phase 1: Core Improvements
1. Add `UNIVERSITY_SELECTORS` dictionary
2. Implement `_extract_json_ld()` method
3. Implement `_extract_from_tables()` method
4. Update `extract_course_details()` to use priority chain

### Phase 2: Field Enhancements
5. Add `_extract_credit_points()` method
6. Add `_extract_course_code()` method
7. Enhance `_smart_extract_fees()` with new patterns
8. Enhance `_smart_extract_duration()` with range support

### Phase 3: Integration
9. Update course data structure to include new fields
10. Update `_print_summary()` to display new fields
11. Test with all 5 target universities

---

## New Course Data Structure

```python
course = {
    'url': str,
    'name': str,
    'description': str,
    'duration': str,
    'fees_domestic': str,
    'fees_international': str,
    'entry_requirements': str,
    'atar': str,
    'study_mode': str,
    'intake': str,
    'campus': str,
    'career_outcomes': List[str],
    # NEW FIELDS
    'credit_points': str,
    'course_code': str,
}
```

---

## Extraction Priority Chain

For each field, data sources are tried in this order:

1. **JSON-LD structured data** (highest reliability)
2. **University-specific selectors** (customized for site)
3. **Table-based extraction** (key-value pairs)
4. **Generic CSS selectors** (common patterns)
5. **Regex patterns on page text** (fallback)

---

## Testing Plan

1. Run crawler on each target university
2. Verify extraction accuracy for each field
3. Compare before/after extraction rates
4. Document any university-specific issues

---

## Files to Modify

| File | Changes |
|------|---------|
| `deep_crawl.py` | Add new methods, update extraction logic |
| `crawler/crawler.py` | Optionally apply same improvements |

---

## Estimated Changes

- ~150 lines of new code for extraction methods
- ~50 lines for university selectors
- ~30 lines for updated data structure
- Total: ~230 lines of additions/modifications
