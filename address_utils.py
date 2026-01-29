"""
Address parsing and matching utilities for Manager Wizard.

Provides:
- Address parsing into structured components
- Street type and directional normalization
- Fuzzy matching with Levenshtein distance
- Address similarity scoring

Author: Claude Code
Date: 2026-01-28
"""

import re
from dataclasses import dataclass
from typing import Optional, Dict, List, Tuple, Any


# =============================================================================
# STREET TYPE MAPPINGS
# =============================================================================

STREET_TYPE_MAPPINGS: Dict[str, str] = {
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
    'pointe': 'pt',
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
STREET_TYPE_EXPANSIONS: Dict[str, str] = {
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


# =============================================================================
# DIRECTIONAL MAPPINGS
# =============================================================================

DIRECTIONAL_MAPPINGS: Dict[str, str] = {
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


# =============================================================================
# UNIT TYPE MAPPINGS
# =============================================================================

UNIT_TYPE_MAPPINGS: Dict[str, str] = {
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


# =============================================================================
# MATCH THRESHOLDS
# =============================================================================

MIN_ADDRESS_MATCH_SCORE = 0.70  # 70% similarity required for exact match
FUZZY_ADDRESS_MATCH_SCORE = 0.55  # 55-70% = fuzzy match (shown with warning)


# =============================================================================
# PARSED ADDRESS DATA CLASS
# =============================================================================

@dataclass
class ParsedAddress:
    """Structured representation of a parsed address."""
    original: str
    street_number: str
    street_number_suffix: str
    pre_directional: str
    street_name: str
    street_type: str
    post_directional: str
    unit_type: str
    unit_number: str
    city: str
    state: str
    zip_code: str

    def normalized_street(self) -> str:
        """Return normalized street for matching."""
        parts = []
        if self.street_number:
            num = self.street_number
            if self.street_number_suffix:
                num += self.street_number_suffix.upper()
            parts.append(num)
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
        """Generate a key for fast matching (number + first word of street)."""
        first_word = (self.street_name or '').split()[0] if self.street_name else ''
        return f"{self.street_number or ''} {first_word}".strip().lower()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'street_number': self.street_number,
            'street_number_suffix': self.street_number_suffix,
            'pre_directional': self.pre_directional,
            'street_name': self.street_name,
            'street_type': self.street_type,
            'post_directional': self.post_directional,
            'unit_type': self.unit_type,
            'unit_number': self.unit_number,
            'city': self.city,
            'state': self.state,
            'zip_code': self.zip_code,
            'normalized': self.normalized_street()
        }


# =============================================================================
# ADDRESS PARSER
# =============================================================================

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
        'bastrop', 'kyle', 'buda', 'san marcos', 'new braunfels',
        'san antonio', 'seguin', 'lockhart', 'del valle', 'elgin',
        'jarrell', 'liberty hill', 'marble falls', 'spicewood', 'wimberley'
    }

    def __init__(self):
        """Initialize parser with compiled regex patterns."""
        self._street_number_re = re.compile(self.STREET_NUMBER_PATTERN)
        self._unit_re = re.compile(self.UNIT_PATTERN, re.IGNORECASE)
        self._zip_re = re.compile(self.ZIP_PATTERN)
        self._state_re = re.compile(self.STATE_PATTERN, re.IGNORECASE)

    def parse(self, address: str) -> ParsedAddress:
        """Parse an address string into components."""
        if not address:
            return self._empty_address('')

        original = address
        working = address.strip()

        # Extract and remove zip code
        # Zip codes appear after city/state, not at the start
        # Pattern: comma or state abbreviation followed by whitespace and 5 digits
        zip_code = ''
        # Look for zip at end or after TX/state
        zip_pattern = r'(?:,\s*|\bTX\s*|\bTexas\s*)(\d{5})(?:-\d{4})?\b'
        zip_match = re.search(zip_pattern, working, re.IGNORECASE)
        if zip_match:
            zip_code = zip_match.group(1)
            # Remove zip code patterns (may appear multiple times in duplicated addresses)
            working = re.sub(r'(?:,\s*)?\d{5}(?:-\d{4})?\s*(?:,|$)', '', working)
            working = re.sub(r'\bTX\s+\d{5}(?:-\d{4})?\b', 'TX', working, flags=re.IGNORECASE)

        # Extract and remove state
        state = ''
        state_match = self._state_re.search(working)
        if state_match:
            state = 'TX'
            working = re.sub(r',?\s*(TX|Texas)\b', '', working, flags=re.IGNORECASE)

        # Extract and remove city
        # Only remove city when it appears after a comma or at the end
        # (to avoid removing "The Hills Dr" street name when city is also "The Hills")
        city = ''
        working_lower = working.lower()
        for known_city in sorted(self.KNOWN_CITIES, key=len, reverse=True):
            # Look for city after comma, or city + state/zip at end
            city_pattern = rf',\s*{re.escape(known_city)}\b'
            if re.search(city_pattern, working_lower):
                city = known_city.title()
                # Only remove city when it appears after a comma
                working = re.sub(city_pattern, '', working, flags=re.IGNORECASE)
                break

        # Extract and remove unit
        unit_type = ''
        unit_number = ''
        unit_match = self._unit_re.search(working)
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
        working = re.sub(r',+', ',', working)
        working = working.strip(' ,')

        # Parse street components
        parts = working.split()

        street_number = ''
        street_number_suffix = ''
        pre_directional = ''
        street_name_parts = []
        street_type = ''
        post_directional = ''

        i = 0

        # Street number (required for most addresses)
        if parts and re.match(r'^\d+', parts[0]):
            num_match = self._street_number_re.match(parts[0])
            if num_match:
                street_number = num_match.group(1)
                street_number_suffix = num_match.group(2) or ''
            i += 1

        # Pre-directional (optional)
        if i < len(parts) and parts[i].lower().rstrip('.') in DIRECTIONAL_MAPPINGS:
            pre_directional = parts[i].rstrip('.')
            i += 1

        # Primary street types that should END the street name
        # (these are unambiguous and shouldn't appear mid-name)
        PRIMARY_STREET_TYPES = {
            'st', 'street', 'ave', 'avenue', 'blvd', 'boulevard',
            'dr', 'drive', 'ln', 'lane', 'rd', 'road', 'ct', 'court',
            'cir', 'circle', 'way', 'pl', 'place', 'trl', 'trail',
            'pkwy', 'parkway', 'ter', 'terrace', 'hwy', 'highway',
            'xing', 'crossing', 'loop', 'run', 'path', 'bend', 'pass'
        }

        # Secondary types that could be part of street names
        # (e.g., "Falcon Pointe Blvd" - Pointe is part of name, Blvd is type)
        SECONDARY_STREET_WORDS = {
            'pointe', 'point', 'pt', 'creek', 'crk', 'ridge', 'rdg',
            'oaks', 'hills', 'hls', 'heights', 'hts', 'vista', 'vis',
            'valley', 'vly', 'view', 'vw', 'estates', 'ests', 'ranch',
            'rnch', 'springs', 'spgs', 'meadow', 'mdw', 'meadows', 'mdws',
            'cove', 'cv'
        }

        # Street name and type - scan forward looking for end of street
        while i < len(parts):
            word = parts[i]
            word_lower = word.lower().rstrip('.,')

            # Is this a primary street type? (definite end of street name)
            if word_lower in PRIMARY_STREET_TYPES:
                street_type = word.rstrip('.,')
                i += 1
                # Check for post-directional after street type
                if i < len(parts) and parts[i].lower().rstrip('.') in DIRECTIONAL_MAPPINGS:
                    post_directional = parts[i].rstrip('.')
                    i += 1
                break

            # Is this a secondary street word?
            # Only treat as street type if it's the LAST word (no more parts after)
            elif word_lower in SECONDARY_STREET_WORDS:
                if i == len(parts) - 1:
                    # Last word and it's a secondary type - treat as type
                    street_type = word.rstrip('.,')
                    i += 1
                    break
                else:
                    # Not last word - include in street name (e.g., "Falcon Pointe" in "Falcon Pointe Blvd")
                    street_name_parts.append(word.rstrip(','))
                    i += 1

            # Check if this is a post-directional without explicit street type
            elif word_lower.rstrip('.') in DIRECTIONAL_MAPPINGS and i == len(parts) - 1:
                post_directional = word.rstrip('.')
                break

            else:
                street_name_parts.append(word.rstrip(','))
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

    def _empty_address(self, original: str) -> ParsedAddress:
        """Return an empty ParsedAddress."""
        return ParsedAddress(
            original=original,
            street_number='',
            street_number_suffix='',
            pre_directional='',
            street_name='',
            street_type='',
            post_directional='',
            unit_type='',
            unit_number='',
            city='',
            state='',
            zip_code=''
        )


# =============================================================================
# LEVENSHTEIN DISTANCE
# =============================================================================

def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate Levenshtein distance between two strings.
    Returns the minimum number of single-character edits needed to change s1 into s2.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


# =============================================================================
# ADDRESS SIMILARITY SCORING
# =============================================================================

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
            # Score based on how much of the name matches
            shorter = min(len(query_name), len(candidate_name))
            longer = max(len(query_name), len(candidate_name))
            overlap_ratio = shorter / longer if longer > 0 else 0
            score += 25 + (10 * overlap_ratio)
        else:
            # Fuzzy match using Levenshtein
            distance = levenshtein_distance(query_name, candidate_name)
            max_len = max(len(query_name), len(candidate_name))
            if max_len > 0:
                similarity = 1 - (distance / max_len)
                if similarity > 0.5:  # Only count if reasonably similar
                    score += 35 * similarity

    # Street type
    if query.street_type:
        max_score += 10
        query_type = STREET_TYPE_MAPPINGS.get(query.street_type.lower(), query.street_type.lower())
        candidate_type = STREET_TYPE_MAPPINGS.get(candidate.street_type.lower(), candidate.street_type.lower()) if candidate.street_type else ''
        if query_type == candidate_type:
            score += 10
        elif not candidate.street_type:
            # No penalty if candidate doesn't have street type (partial address in DB)
            score += 5
    else:
        # Query didn't specify street type - give credit if candidate has one
        max_score += 10
        if candidate.street_type:
            score += 8  # Still good, query just didn't specify

    # Unit number
    if query.unit_number:
        max_score += 10
        if query.unit_number.lower() == (candidate.unit_number or '').lower():
            score += 10
        elif not candidate.unit_number:
            # Query has unit but candidate doesn't - partial penalty
            score += 0
    else:
        # Query didn't specify unit - give credit if match
        max_score += 10
        if not candidate.unit_number:
            score += 10  # Both have no unit - that's a match
        else:
            score += 5  # Candidate has unit, query doesn't care

    # Directional
    query_dir = (query.pre_directional or query.post_directional or '').lower()
    if query_dir:
        max_score += 5
        cand_dir = (candidate.pre_directional or candidate.post_directional or '').lower()
        query_dir_norm = DIRECTIONAL_MAPPINGS.get(query_dir, query_dir)
        cand_dir_norm = DIRECTIONAL_MAPPINGS.get(cand_dir, cand_dir) if cand_dir else ''
        if query_dir_norm == cand_dir_norm:
            score += 5
        elif not cand_dir:
            score += 2  # Candidate doesn't have directional, slight credit

    # Calculate final score as percentage
    if max_score == 0:
        return 0.0

    return min(score / max_score, 1.0)  # Cap at 1.0


def normalize_address_for_search(address: str) -> str:
    """
    Normalize an address string for searching.
    Converts abbreviations to canonical form and lowercases.
    """
    if not address:
        return ''

    result = address.lower().strip()

    # Expand common abbreviations for search
    for abbr, full in STREET_TYPE_EXPANSIONS.items():
        # Match word boundaries
        pattern = rf'\b{abbr}\b'
        result = re.sub(pattern, full, result, flags=re.IGNORECASE)

    # Normalize directionals
    for full, abbr in DIRECTIONAL_MAPPINGS.items():
        if len(full) > 2:  # Only expand full words like "north" -> "n"
            pattern = rf'\b{full}\b'
            result = re.sub(pattern, abbr, result, flags=re.IGNORECASE)

    # Remove extra whitespace
    result = re.sub(r'\s+', ' ', result).strip()

    return result


def extract_search_terms(address: str) -> List[str]:
    """
    Extract key search terms from an address for OData filter building.
    Returns list of terms suitable for contains() filters.
    """
    parser = AddressParser()
    parsed = parser.parse(address)

    terms = []

    # Street number is most important
    if parsed.street_number:
        terms.append(parsed.street_number)

    # Street name words (excluding common words)
    if parsed.street_name:
        stop_words = {'the', 'at', 'of', 'and', 'a', 'an'}
        name_words = [w for w in parsed.street_name.split() if w.lower() not in stop_words and len(w) >= 3]
        terms.extend(name_words[:2])  # First 2 significant words

    return terms


# =============================================================================
# SINGLETON PARSER INSTANCE
# =============================================================================

_parser_instance: Optional[AddressParser] = None


def get_address_parser() -> AddressParser:
    """Get singleton AddressParser instance."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = AddressParser()
    return _parser_instance


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def parse_address(address: str) -> ParsedAddress:
    """Parse an address string (convenience function)."""
    return get_address_parser().parse(address)


def compare_addresses(addr1: str, addr2: str) -> float:
    """
    Compare two address strings and return similarity score.
    Convenience function that parses both addresses and scores them.
    """
    parser = get_address_parser()
    parsed1 = parser.parse(addr1)
    parsed2 = parser.parse(addr2)
    return address_similarity_score(parsed1, parsed2)
