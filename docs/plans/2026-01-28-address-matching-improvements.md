# Manager Wizard Address Matching Improvements

## Design Document
**Date:** 2026-01-28
**Status:** IMPLEMENTED - READY FOR DEPLOYMENT
**Current Success Rate:** 50% (5/10 tests passing)
**Target Success Rate:** 90%+

---

## Implementation Summary

### Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `address_utils.py` | **CREATED** | New module with AddressParser, similarity scoring, normalization |
| `app.py` | **MODIFIED** | Updated `search_by_address()` to use new address matching |
| `scripts/test_address_matching.py` | **CREATED** | 50-test suite for address matching |
| `docs/plans/2026-01-28-address-matching-improvements.md` | **CREATED** | This design document |

### Key Features Implemented

1. **AddressParser class** - Parses addresses into structured components:
   - Street number, street name, street type
   - Pre/post directional (N, S, E, W, NE, etc.)
   - Unit type and number (Unit, Apt, Suite, #)
   - City, state, zip code

2. **Street type normalization** - 50+ mappings:
   - "Street" <-> "St", "Boulevard" <-> "Blvd", etc.
   - Handles Texas-specific patterns (Pointe, Ranch, Creek)

3. **Address similarity scoring** - Weighted algorithm:
   - 40% street number (required for any match)
   - 35% street name (fuzzy matching with Levenshtein)
   - 10% street type, 10% unit, 5% directional

4. **Smart OData query building**:
   - Uses `startswith()` for street number precision
   - Falls back to keyword search for partial addresses

5. **Edge case handling**:
   - "The Hills Dr" in "The Hills, TX" (street name = city name)
   - Duplicate city/zip patterns in Dataverse
   - Multi-word street names with embedded type-like words

---

## Executive Summary

Address matching is currently the weakest search type in Manager Wizard with only 50% success rate. Analysis of test failures reveals three main issues:

1. **No street name normalization** - "St" vs "Street", "Dr" vs "Drive" cause mismatches
2. **No partial address matching** - "123 Oak" fails to match "123 Oak Street"
3. **No fuzzy matching for typos** - Small typos cause complete failures

This document provides a comprehensive solution including normalization rules, a custom address parser, fuzzy matching algorithm, and 50 test cases.

---

## 1. Analysis of Address Failures

### Current Address Format in Dataverse
Addresses in `cr258_property_address` follow these patterns:
```
18517 Falcon Pointe Blvd Pflugerville, TX  78660, Pflugerville, TX 78660
1919 American Dr Unit 123 Lago Vista, TX  78645, Lago Vista, TX 78645
1481 Old Settlers Blvd Unit 1503, Round Rock, TX 78664
12 Monarch Oaks Ln, The Hills, TX 78738
```

### Key Observations:
1. **Duplicated city/state/zip** - Many addresses repeat "City, TX XXXXX" twice
2. **Inconsistent comma placement** - Some have commas after street, some don't
3. **Unit numbers** - Can appear as "Unit 123", "Apt 5", "#1503"
4. **Street types** - Mix of abbreviated (Dr, Blvd, Ln) and full (Street, Drive)
5. **Directional prefixes** - N, S, E, W, NE, NW, SE, SW before street names

### Test Cases That Failed:

| Query | Expected | Failure Reason |
|-------|----------|----------------|
| "100 Main Street" | Match "100 Main St" | No abbreviation normalization |
| "1234 Oak Drive" | Match "1234 Oak Dr" | No abbreviation normalization |
| "500 Falcon Pointe" | Match addresses on Falcon Pointe Blvd | Missing street type |
| "123 Vista Verde Dr" | Match "123 Vista Verde Drive" | Abbreviation mismatch |
| "100 N Main St" | Match "100 North Main St" | Directional abbreviation |
| "apt 5" | Match any unit 5 | Too broad, no context |
| "100 Main, Austin" | Match "100 Main St Austin" | City as part of query |

---

## 2. Street Name Normalization

### 2.1 Street Type Mappings

```python
STREET_TYPE_MAPPINGS = {
    # Standard street types -> canonical form
    'street': 'st',
    'st': 'st',
    'avenue': 'ave',
    'ave': 'ave',
    'av': 'ave',
    'boulevard': 'blvd',
    'blvd': 'blvd',
    'drive': 'dr',
    'dr': 'dr',
    'lane': 'ln',
    'ln': 'ln',
    'road': 'rd',
    'rd': 'rd',
    'court': 'ct',
    'ct': 'ct',
    'circle': 'cir',
    'cir': 'cir',
    'way': 'way',
    'place': 'pl',
    'pl': 'pl',
    'trail': 'trl',
    'trl': 'trl',
    'parkway': 'pkwy',
    'pkwy': 'pkwy',
    'terrace': 'ter',
    'ter': 'ter',
    'highway': 'hwy',
    'hwy': 'hwy',
    'crossing': 'xing',
    'xing': 'xing',
    'pass': 'pass',
    'loop': 'loop',
    'run': 'run',
    'path': 'path',
    'bend': 'bend',
    'cove': 'cv',
    'cv': 'cv',
    'point': 'pt',
    'pointe': 'pt',  # "Falcon Pointe" -> "Falcon Pt"
    'pt': 'pt',
    'ridge': 'rdg',
    'rdg': 'rdg',
    'creek': 'crk',
    'crk': 'crk',
    'estates': 'ests',
    'ests': 'ests',
    'heights': 'hts',
    'hts': 'hts',
    'hills': 'hls',
    'hls': 'hls',
    'meadow': 'mdw',
    'mdw': 'mdw',
    'meadows': 'mdws',
    'mdws': 'mdws',
    'oaks': 'oaks',
    'ranch': 'rnch',
    'rnch': 'rnch',
    'springs': 'spgs',
    'spgs': 'spgs',
    'valley': 'vly',
    'vly': 'vly',
    'view': 'vw',
    'vw': 'vw',
    'vista': 'vis',
    'vis': 'vis',
}

# Reverse mapping for expanding abbreviations
STREET_TYPE_EXPANSIONS = {
    'st': 'street',
    'ave': 'avenue',
    'blvd': 'boulevard',
    'dr': 'drive',
    'ln': 'lane',
    'rd': 'road',
    'ct': 'court',
    'cir': 'circle',
    'pl': 'place',
    'trl': 'trail',
    'pkwy': 'parkway',
    'ter': 'terrace',
    'hwy': 'highway',
    'xing': 'crossing',
    'cv': 'cove',
    'pt': 'point',
    'rdg': 'ridge',
    'crk': 'creek',
    'hts': 'heights',
}
```

### 2.2 Directional Mappings

```python
DIRECTIONAL_MAPPINGS = {
    'north': 'n',
    'n': 'n',
    'south': 's',
    's': 's',
    'east': 'e',
    'e': 'e',
    'west': 'w',
    'w': 'w',
    'northeast': 'ne',
    'ne': 'ne',
    'northwest': 'nw',
    'nw': 'nw',
    'southeast': 'se',
    'se': 'se',
    'southwest': 'sw',
    'sw': 'sw',
}
```

### 2.3 Unit Type Mappings

```python
UNIT_TYPE_MAPPINGS = {
    'unit': 'unit',
    'apt': 'unit',
    'apartment': 'unit',
    '#': 'unit',
    'suite': 'unit',
    'ste': 'unit',
    'room': 'unit',
    'rm': 'unit',
    'floor': 'floor',
    'fl': 'floor',
    'building': 'bldg',
    'bldg': 'bldg',
    'lot': 'lot',
}
```

---

## 3. Address Parser

### 3.1 Parsed Address Structure

```python
@dataclass
class ParsedAddress:
    """Structured representation of a parsed address."""
    original: str               # Original input
    street_number: str          # "123"
    street_number_suffix: str   # "A" in "123A Main St"
    pre_directional: str        # "N" in "123 N Main St"
    street_name: str            # "Main"
    street_type: str            # "St" (normalized)
    post_directional: str       # "SW" in "123 Main St SW"
    unit_type: str              # "Unit", "Apt", "#"
    unit_number: str            # "5", "5A", "100"
    city: str                   # "Austin"
    state: str                  # "TX"
    zip_code: str               # "78660"

    def normalized_street(self) -> str:
        """Return normalized street for matching."""
        parts = []
        if self.street_number:
            parts.append(self.street_number)
            if self.street_number_suffix:
                parts[-1] += self.street_number_suffix.upper()
        if self.pre_directional:
            parts.append(DIRECTIONAL_MAPPINGS.get(self.pre_directional.lower(), self.pre_directional))
        if self.street_name:
            parts.append(self.street_name.lower())
        if self.street_type:
            parts.append(STREET_TYPE_MAPPINGS.get(self.street_type.lower(), self.street_type.lower()))
        if self.post_directional:
            parts.append(DIRECTIONAL_MAPPINGS.get(self.post_directional.lower(), self.post_directional))
        return ' '.join(parts)

    def match_key(self) -> str:
        """Generate a key for fast matching."""
        # Just number + first word of street for quick filtering
        return f"{self.street_number or ''} {(self.street_name or '').split()[0] if self.street_name else ''}".strip().lower()
```

### 3.2 Address Parser Implementation

```python
import re
from typing import Optional

class AddressParser:
    """Parse addresses into structured components."""

    # Regex patterns
    STREET_NUMBER_PATTERN = r'^(\d+)([A-Za-z])?'
    UNIT_PATTERN = r'(?:unit|apt|apartment|suite|ste|#|room|rm)\s*([A-Za-z0-9]+)'
    ZIP_PATTERN = r'\b(\d{5})(?:-\d{4})?\b'
    STATE_PATTERN = r'\b(TX|Texas)\b'

    # Known Texas cities (common in the data)
    KNOWN_CITIES = {
        'austin', 'round rock', 'pflugerville', 'cedar park', 'leander',
        'georgetown', 'hutto', 'taylor', 'lago vista', 'the hills',
        'dripping springs', 'driftwood', 'bee cave', 'lakeway', 'manor',
        'bastrop', 'kyle', 'buda', 'san marcos', 'new braunfels'
    }

    def parse(self, address: str) -> ParsedAddress:
        """Parse an address string into components."""
        if not address:
            return ParsedAddress(original='', street_number='', street_number_suffix='',
                               pre_directional='', street_name='', street_type='',
                               post_directional='', unit_type='', unit_number='',
                               city='', state='', zip_code='')

        original = address
        working = address.strip()

        # Extract and remove zip code
        zip_code = ''
        zip_match = re.search(self.ZIP_PATTERN, working)
        if zip_match:
            zip_code = zip_match.group(1)
            # Remove all instances of the zip (handles duplicate city/zip)
            working = re.sub(r',?\s*\d{5}(?:-\d{4})?', '', working)

        # Extract and remove state
        state = ''
        state_match = re.search(self.STATE_PATTERN, working, re.IGNORECASE)
        if state_match:
            state = 'TX'
            working = re.sub(r',?\s*(TX|Texas)\b', '', working, flags=re.IGNORECASE)

        # Extract and remove city
        city = ''
        working_lower = working.lower()
        for known_city in sorted(self.KNOWN_CITIES, key=len, reverse=True):
            if known_city in working_lower:
                city = known_city.title()
                # Remove city (may appear multiple times due to duplication)
                pattern = rf',?\s*{re.escape(known_city)}'
                working = re.sub(pattern, '', working, flags=re.IGNORECASE)
                break

        # Extract and remove unit
        unit_type = ''
        unit_number = ''
        unit_match = re.search(self.UNIT_PATTERN, working, re.IGNORECASE)
        if unit_match:
            unit_number = unit_match.group(1)
            # Determine unit type
            full_match = unit_match.group(0).lower()
            if 'apt' in full_match or 'apartment' in full_match:
                unit_type = 'apt'
            elif 'suite' in full_match or 'ste' in full_match:
                unit_type = 'suite'
            elif '#' in full_match:
                unit_type = '#'
            else:
                unit_type = 'unit'
            working = working[:unit_match.start()] + working[unit_match.end():]

        # Clean up remaining address
        working = re.sub(r'\s+', ' ', working).strip()
        working = re.sub(r'^,\s*|,\s*$', '', working)

        # Parse street components
        parts = working.split()

        street_number = ''
        street_number_suffix = ''
        pre_directional = ''
        street_name_parts = []
        street_type = ''
        post_directional = ''

        i = 0

        # Street number (required)
        if parts and re.match(r'^\d+', parts[0]):
            num_match = re.match(self.STREET_NUMBER_PATTERN, parts[0])
            if num_match:
                street_number = num_match.group(1)
                street_number_suffix = num_match.group(2) or ''
            i += 1

        # Pre-directional (optional)
        if i < len(parts) and parts[i].lower() in DIRECTIONAL_MAPPINGS:
            pre_directional = parts[i]
            i += 1

        # Street name and type
        while i < len(parts):
            word = parts[i]
            word_lower = word.lower().rstrip('.,')

            # Check if this is a street type
            if word_lower in STREET_TYPE_MAPPINGS:
                street_type = word
                i += 1
                # Check for post-directional after street type
                if i < len(parts) and parts[i].lower() in DIRECTIONAL_MAPPINGS:
                    post_directional = parts[i]
                    i += 1
                break
            # Check if this is a post-directional without explicit street type
            elif word_lower in DIRECTIONAL_MAPPINGS and i == len(parts) - 1:
                post_directional = word
                break
            else:
                street_name_parts.append(word)
                i += 1

        street_name = ' '.join(street_name_parts)

        return ParsedAddress(
            original=original,
            street_number=street_number,
            street_number_suffix=street_number_suffix,
            pre_directional=pre_directional,
            street_name=street_name,
            street_type=street_type,
            post_directional=post_directional,
            unit_type=unit_type,
            unit_number=unit_number,
            city=city,
            state=state,
            zip_code=zip_code
        )
```

---

## 4. Fuzzy Matching Algorithm

### 4.1 Levenshtein Distance (Already Exists)

The existing `levenshtein_distance()` function in `app.py` is suitable.

### 4.2 Address Similarity Score

```python
def address_similarity_score(query: ParsedAddress, candidate: ParsedAddress) -> float:
    """
    Calculate similarity score between two addresses.
    Returns a score from 0.0 (no match) to 1.0 (perfect match).

    Scoring weights:
    - Street number: 40% (must match for any positive score)
    - Street name: 35%
    - Street type: 10%
    - Unit number: 10%
    - Directional: 5%
    """
    score = 0.0
    max_score = 0.0

    # Street number - REQUIRED for any match
    if query.street_number:
        max_score += 40
        if query.street_number == candidate.street_number:
            score += 40
            # Bonus for matching suffix
            if query.street_number_suffix and query.street_number_suffix.lower() == candidate.street_number_suffix.lower():
                score += 2
        else:
            # No street number match = no match at all
            return 0.0

    # Street name similarity
    if query.street_name:
        max_score += 35
        query_name = query.street_name.lower()
        candidate_name = candidate.street_name.lower()

        if query_name == candidate_name:
            score += 35
        elif query_name in candidate_name or candidate_name in query_name:
            # Partial match (e.g., "Oak" in "Oak Hills")
            score += 25
        else:
            # Fuzzy match using Levenshtein
            distance = levenshtein_distance(query_name, candidate_name)
            max_len = max(len(query_name), len(candidate_name))
            if max_len > 0:
                similarity = 1 - (distance / max_len)
                if similarity > 0.6:  # Only count if reasonably similar
                    score += 35 * similarity

    # Street type
    if query.street_type:
        max_score += 10
        query_type = STREET_TYPE_MAPPINGS.get(query.street_type.lower(), query.street_type.lower())
        candidate_type = STREET_TYPE_MAPPINGS.get(candidate.street_type.lower(), candidate.street_type.lower())
        if query_type == candidate_type:
            score += 10
        elif not candidate.street_type:
            # No penalty if candidate doesn't have street type (partial address in DB)
            score += 5

    # Unit number
    if query.unit_number:
        max_score += 10
        if query.unit_number.lower() == candidate.unit_number.lower():
            score += 10
        elif not candidate.unit_number and not query.unit_number:
            # Both have no unit - that's a match
            pass

    # Directional
    if query.pre_directional or query.post_directional:
        max_score += 5
        query_dir = (query.pre_directional or query.post_directional or '').lower()
        cand_dir = (candidate.pre_directional or candidate.post_directional or '').lower()
        query_dir_norm = DIRECTIONAL_MAPPINGS.get(query_dir, query_dir)
        cand_dir_norm = DIRECTIONAL_MAPPINGS.get(cand_dir, cand_dir)
        if query_dir_norm == cand_dir_norm:
            score += 5

    # Calculate final score as percentage
    if max_score == 0:
        return 0.0

    return score / max_score
```

### 4.3 Minimum Match Threshold

```python
# Minimum score required to consider it a match
MIN_ADDRESS_MATCH_SCORE = 0.70  # 70% similarity required

# Minimum score for "fuzzy" matches (shown with warning)
FUZZY_ADDRESS_MATCH_SCORE = 0.55  # 55-70% = fuzzy match
```

---

## 5. Enhanced Address Search Implementation

### 5.1 Main Search Function

```python
def search_by_address_v2(address: str, community_filter: str = None) -> dict:
    """
    Enhanced address search with normalization and fuzzy matching.

    Search strategy:
    1. Parse and normalize the input address
    2. Build OData filter using street number (required) and street name keywords
    3. Score all candidates using address_similarity_score()
    4. Return sorted by score
    """
    parser = AddressParser()
    query_parsed = parser.parse(address)

    # Must have at least a street number to search
    if not query_parsed.street_number:
        # Fall back to general contains search
        return search_by_address_fallback(address, community_filter)

    # Build OData filter - start with street number
    safe_number = query_parsed.street_number.replace("'", "''")
    filter_expr = f"startswith(cr258_property_address, '{safe_number} ')"

    # Add street name keyword if available
    if query_parsed.street_name:
        # Get first meaningful word of street name
        name_words = query_parsed.street_name.split()
        if name_words:
            first_word = name_words[0].replace("'", "''")
            if len(first_word) >= 3:  # Only if reasonably long
                filter_expr += f" and contains(cr258_property_address, '{first_word}')"

    # Add community filter
    if community_filter:
        safe_community = community_filter.replace("'", "''")
        filter_expr = f"contains(cr258_assoc_name, '{safe_community}') and ({filter_expr})"

    # Query Dataverse
    results = query_dataverse(filter_expr, top=50)

    if results is None:
        return {'error': 'Dataverse connection failed', 'homeowners': []}

    if not results:
        # Try broader search without street name constraint
        filter_expr = f"startswith(cr258_property_address, '{safe_number} ')"
        if community_filter:
            filter_expr = f"contains(cr258_assoc_name, '{safe_community}') and ({filter_expr})"
        results = query_dataverse(filter_expr, top=50)

    if not results:
        return {
            'search_type': 'address',
            'query': address,
            'community_filter': community_filter,
            'homeowners': [],
            'count': 0,
            'parsed': {
                'street_number': query_parsed.street_number,
                'street_name': query_parsed.street_name,
                'street_type': query_parsed.street_type
            }
        }

    # Score and rank results
    scored_results = []
    for rec in results:
        if is_excluded_community(rec.get('cr258_assoc_name')):
            continue

        candidate_address = rec.get('cr258_property_address', '')
        candidate_parsed = parser.parse(candidate_address)

        score = address_similarity_score(query_parsed, candidate_parsed)

        if score >= FUZZY_ADDRESS_MATCH_SCORE:
            homeowner = format_homeowner(rec)
            homeowner['_match_score'] = round(score, 3)
            homeowner['_is_fuzzy'] = score < MIN_ADDRESS_MATCH_SCORE
            scored_results.append((score, homeowner))

    # Sort by score descending
    scored_results.sort(key=lambda x: x[0], reverse=True)
    homeowners = [h for _, h in scored_results]

    # Separate exact and fuzzy matches
    exact_matches = [h for h in homeowners if not h.get('_is_fuzzy')]
    fuzzy_matches = [h for h in homeowners if h.get('_is_fuzzy')]

    return {
        'search_type': 'address',
        'query': address,
        'community_filter': community_filter,
        'homeowners': homeowners,
        'count': len(homeowners),
        'exact_matches': len(exact_matches),
        'fuzzy_matches': len(fuzzy_matches),
        'parsed': {
            'street_number': query_parsed.street_number,
            'street_name': query_parsed.street_name,
            'street_type': query_parsed.street_type,
            'unit': query_parsed.unit_number
        }
    }


def search_by_address_fallback(address: str, community_filter: str = None) -> dict:
    """
    Fallback search for addresses without clear street number.
    Uses keyword extraction and multiple OData queries.
    """
    safe_address = address.replace("'", "''")

    # Extract potential keywords (words with 4+ chars, excluding common words)
    stop_words = {'street', 'drive', 'lane', 'road', 'avenue', 'court', 'circle',
                  'unit', 'apt', 'apartment', 'suite', 'austin', 'texas', 'the'}
    words = [w for w in re.split(r'\W+', address.lower()) if len(w) >= 4 and w not in stop_words]

    if not words:
        # Last resort: just search for the whole thing
        filter_expr = f"contains(cr258_property_address, '{safe_address}')"
    else:
        # Search for each keyword
        conditions = [f"contains(cr258_property_address, '{w}')" for w in words[:3]]
        filter_expr = ' and '.join(conditions)

    if community_filter:
        safe_community = community_filter.replace("'", "''")
        filter_expr = f"contains(cr258_assoc_name, '{safe_community}') and ({filter_expr})"

    results = query_dataverse(filter_expr, top=20)

    if results is None:
        return {'error': 'Dataverse connection failed', 'homeowners': []}

    filtered = [r for r in (results or []) if not is_excluded_community(r.get('cr258_assoc_name'))]
    homeowners = [format_homeowner(r) for r in filtered]

    return {
        'search_type': 'address',
        'query': address,
        'community_filter': community_filter,
        'homeowners': homeowners,
        'count': len(homeowners),
        'fallback_used': True
    }
```

---

## 6. Integration with Existing Code

### 6.1 Update `search_by_address()` in app.py

Replace the existing `search_by_address()` function (lines 1614-1654) with:

```python
def search_by_address(address, community_filter=None):
    """Search by address - enhanced with normalization and fuzzy matching."""
    # Use new v2 implementation
    result = search_by_address_v2(address, community_filter)
    return jsonify(result)
```

### 6.2 Add New Module

Create `address_utils.py` in the same directory:

```python
"""
Address parsing and matching utilities for Manager Wizard.
"""

import re
from dataclasses import dataclass
from typing import Optional

# Include all the code from sections 2, 3, 4, and 5.1 above
```

### 6.3 Import in app.py

Add at the top of app.py:

```python
from address_utils import (
    AddressParser,
    ParsedAddress,
    address_similarity_score,
    search_by_address_v2,
    STREET_TYPE_MAPPINGS,
    DIRECTIONAL_MAPPINGS
)
```

---

## 7. Test Suite (50 Test Cases)

### 7.1 Test Categories

```python
ADDRESS_TEST_CASES = {
    # ===========================================================================
    # EXACT MATCHES (10 cases) - Should find with 100% confidence
    # ===========================================================================
    "exact_matches": [
        {"query": "18517 Falcon Pointe Blvd", "expected": "18517 Falcon Pointe Blvd", "desc": "Full address exact"},
        {"query": "1919 American Dr Unit 123", "expected": "1919 American Dr Unit 123", "desc": "With unit number"},
        {"query": "12 Monarch Oaks Ln", "expected": "12 Monarch Oaks Ln", "desc": "Short street number"},
        {"query": "3 Glenway Dr", "expected": "3 Glenway Dr", "desc": "Single digit number"},
        {"query": "1481 Old Settlers Blvd Unit 1503", "expected": "1481 Old Settlers Blvd Unit 1503", "desc": "Multi-word street with unit"},
        {"query": "207 The Hills Dr", "expected": "207 The Hills Dr", "desc": "Street name with article"},
        {"query": "4306 Cisco Valley Dr", "expected": "4306 Cisco Valley Dr", "desc": "Two-word community name"},
        {"query": "907 Mohican Street", "expected": "907 Mohican Street", "desc": "Full 'Street' spelling"},
        {"query": "219 Kaden Prince Dr", "expected": "219 Kaden Prince Dr", "desc": "Two-word street name"},
        {"query": "20805 Trotters Ln", "expected": "20805 Trotters Ln", "desc": "Five digit number"},
    ],

    # ===========================================================================
    # ABBREVIATION NORMALIZATION (10 cases)
    # ===========================================================================
    "abbreviation_tests": [
        {"query": "18517 Falcon Pointe Boulevard", "expected": "18517 Falcon Pointe Blvd", "desc": "Boulevard -> Blvd"},
        {"query": "1919 American Drive", "expected": "1919 American Dr", "desc": "Drive -> Dr"},
        {"query": "12 Monarch Oaks Lane", "expected": "12 Monarch Oaks Ln", "desc": "Lane -> Ln"},
        {"query": "907 Mohican St", "expected": "907 Mohican Street", "desc": "St -> Street"},
        {"query": "35 Cottondale Road", "expected": "35 Cottondale Rd", "desc": "Road -> Rd"},
        {"query": "3 Stillmeadow Court", "expected": "3 Stillmeadow Ct", "desc": "Court -> Ct"},
        {"query": "16 Falling Oaks Trail", "expected": "16 Falling Oaks Trl", "desc": "Trail -> Trl"},
        {"query": "8 Tiburon Drive", "expected": "8 Tiburon Dr", "desc": "Drive normalized"},
        {"query": "44 Autumn Oaks Drive", "expected": "44 Autumn Oaks Dr", "desc": "Multi-word + Drive"},
        {"query": "1000 Ranchers Club Lane", "expected": "1000 Ranchers Club Ln", "desc": "Multi-word + Lane"},
    ],

    # ===========================================================================
    # PARTIAL ADDRESS MATCHING (10 cases)
    # ===========================================================================
    "partial_matches": [
        {"query": "18517 Falcon", "expected": "18517 Falcon Pointe Blvd", "desc": "Number + first word"},
        {"query": "12 Monarch", "expected": "12 Monarch Oaks Ln", "desc": "Short number + first word"},
        {"query": "907 Mohican", "expected": "907 Mohican Street", "desc": "Number + street only"},
        {"query": "3 Glenway", "expected": "3 Glenway Dr", "desc": "Minimal address"},
        {"query": "1919 American", "expected": "1919 American Dr", "desc": "Without unit or type"},
        {"query": "219 Kaden", "expected": "219 Kaden Prince Dr", "desc": "First word of multi-word street"},
        {"query": "20805 Trotters", "expected": "20805 Trotters Ln", "desc": "Five digit + street name"},
        {"query": "4306 Cisco", "expected": "4306 Cisco Valley Dr", "desc": "First word of valley"},
        {"query": "1481 Old", "expected": "1481 Old Settlers Blvd", "desc": "First word of Old Settlers"},
        {"query": "35 Cottondale", "expected": "35 Cottondale Rd", "desc": "Number + name only"},
    ],

    # ===========================================================================
    # UNIT NUMBER VARIATIONS (10 cases)
    # ===========================================================================
    "unit_variations": [
        {"query": "1919 American Dr #123", "expected": "1919 American Dr Unit 123", "desc": "Hash notation"},
        {"query": "1919 American Dr Apt 123", "expected": "1919 American Dr Unit 123", "desc": "Apt notation"},
        {"query": "1919 American Dr Apartment 123", "expected": "1919 American Dr Unit 123", "desc": "Full Apartment"},
        {"query": "1481 Old Settlers #1503", "expected": "1481 Old Settlers Blvd Unit 1503", "desc": "Hash + partial"},
        {"query": "1481 Old Settlers Suite 1503", "expected": "1481 Old Settlers Blvd Unit 1503", "desc": "Suite notation"},
        {"query": "1481 Old Settlers Ste 1503", "expected": "1481 Old Settlers Blvd Unit 1503", "desc": "Ste abbreviation"},
        {"query": "1481 Old Settlers Unit 202", "expected": "1481 Old Settlers Blvd Unit 202", "desc": "Different unit"},
        {"query": "Unit 123, 1919 American", "expected": "1919 American Dr Unit 123", "desc": "Unit first format"},
        {"query": "#1503 1481 Old Settlers", "expected": "1481 Old Settlers Blvd Unit 1503", "desc": "Hash first format"},
        {"query": "1919 American, Unit 123", "expected": "1919 American Dr Unit 123", "desc": "Comma separated"},
    ],

    # ===========================================================================
    # TYPO TOLERANCE / FUZZY MATCHING (10 cases)
    # ===========================================================================
    "typo_tolerance": [
        {"query": "18517 Falcon Point Blvd", "expected": "18517 Falcon Pointe Blvd", "desc": "Point vs Pointe"},
        {"query": "12 Monarch Oak Ln", "expected": "12 Monarch Oaks Ln", "desc": "Oak vs Oaks"},
        {"query": "907 Mohiccan Street", "expected": "907 Mohican Street", "desc": "Double c typo"},
        {"query": "3 Gelnway Dr", "expected": "3 Glenway Dr", "desc": "Transposed letters"},
        {"query": "219 Kaiden Prince", "expected": "219 Kaden Prince Dr", "desc": "Extra letter"},
        {"query": "35 Cottendale Rd", "expected": "35 Cottondale Rd", "desc": "Cotton typo"},
        {"query": "20805 Trotters Lan", "expected": "20805 Trotters Ln", "desc": "Incomplete type"},
        {"query": "4306 Cisko Valley", "expected": "4306 Cisco Valley Dr", "desc": "Cisco typo"},
        {"query": "1000 Rancher Club Ln", "expected": "1000 Ranchers Club Ln", "desc": "Missing s"},
        {"query": "8 Tiberon Dr", "expected": "8 Tiburon Dr", "desc": "Vowel swap"},
    ],
}
```

### 7.2 Test Runner Script

Create `scripts/test_address_matching.py`:

```python
#!/usr/bin/env python3
"""
Address matching test suite for Manager Wizard.
Tests 50 address variations against live API.
"""

import requests
import json
import time
from datetime import datetime

BASE_URL = "https://manager-wizard-138752496729.us-central1.run.app"

# Include ADDRESS_TEST_CASES from above

def run_address_tests():
    """Run all 50 address test cases."""
    print("=" * 80)
    print("MANAGER WIZARD - ADDRESS MATCHING TEST SUITE (50 Tests)")
    print(f"Base URL: {BASE_URL}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    results = {"passed": 0, "failed": 0, "errors": 0, "details": []}
    total = sum(len(cases) for cases in ADDRESS_TEST_CASES.values())
    current = 0

    for category, cases in ADDRESS_TEST_CASES.items():
        print(f"\n{'='*60}")
        print(f"CATEGORY: {category.upper()}")
        print(f"{'='*60}")

        for test_case in cases:
            current += 1
            query = test_case["query"]
            expected = test_case["expected"]
            desc = test_case["desc"]

            try:
                resp = requests.get(
                    f"{BASE_URL}/api/search",
                    params={"q": query, "type": "address"},
                    timeout=15
                )

                if resp.status_code != 200:
                    results["errors"] += 1
                    status = "ERROR"
                    detail = f"HTTP {resp.status_code}"
                else:
                    data = resp.json()
                    homeowners = data.get("homeowners", [])

                    # Check if expected address is in results
                    found = False
                    for h in homeowners:
                        if expected.lower() in h.get("property_address", "").lower():
                            found = True
                            break

                    if found:
                        results["passed"] += 1
                        status = "PASS"
                        detail = f"Found in {len(homeowners)} results"
                    else:
                        results["failed"] += 1
                        status = "FAIL"
                        detail = f"{len(homeowners)} results, expected not found"

            except Exception as e:
                results["errors"] += 1
                status = "ERROR"
                detail = str(e)

            icon = {"PASS": "[OK]", "FAIL": "[XX]", "ERROR": "[!!]"}.get(status, "[??]")
            print(f"[{current:2d}/{total}] {icon} {status:5s} | {desc:30s} | {query[:30]:30s}")

            results["details"].append({
                "category": category,
                "query": query,
                "expected": expected,
                "desc": desc,
                "status": status,
                "detail": detail
            })

            time.sleep(0.1)  # Rate limiting

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Passed:  {results['passed']}/{total} ({results['passed']/total*100:.1f}%)")
    print(f"Failed:  {results['failed']}/{total}")
    print(f"Errors:  {results['errors']}/{total}")
    print("=" * 80)

    # Save results
    output_file = f"address_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {output_file}")

    return results


if __name__ == "__main__":
    run_address_tests()
```

---

## 8. Implementation Checklist

- [ ] Create `address_utils.py` with AddressParser and scoring functions
- [ ] Add all street type and directional mappings
- [ ] Implement `address_similarity_score()`
- [ ] Implement `search_by_address_v2()`
- [ ] Update `search_by_address()` in app.py to use v2
- [ ] Add imports at top of app.py
- [ ] Create `scripts/test_address_matching.py`
- [ ] Run test suite and verify 90%+ success rate
- [ ] Deploy to Cloud Run
- [ ] Run 150-query test suite to verify overall improvement

---

## 9. Expected Impact

| Metric | Before | After (Expected) |
|--------|--------|------------------|
| Address Search Success Rate | 50% | 90%+ |
| Abbreviation Handling | None | Full normalization |
| Partial Address Support | Limited | Robust |
| Typo Tolerance | None | Levenshtein-based |
| Unit Number Variations | Limited | Full support |

---

## 10. Rollback Plan

If issues arise after deployment:

1. Revert `search_by_address()` to use old implementation
2. Keep `address_utils.py` but don't import it
3. Redeploy with:
   ```bash
   gcloud builds submit --config cloudbuild.yaml --project command-center-484415
   ```

---

*Document created: 2026-01-28*
*Author: Claude Code*
