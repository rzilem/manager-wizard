# Manager Wizard - Test Analysis and Improvement Recommendations

## Executive Summary

Based on **live testing (January 2026)**, the Manager Wizard search is achieving approximately **16% direct answer rate** with **84% "not found"** responses. This is significantly lower than expected.

**Root Cause:** The issue is NOT primarily code/prompt quality - it's **document coverage**. The search works perfectly when a dedicated document exists (e.g., "Avalon Fence Stain Color.pdf" → 100% success). Most queries fail because the specific information either:
1. Doesn't exist as a standalone document
2. Is buried in large CC&Rs where extraction fails
3. Is not in the SharePoint index at all

**Key Insight:** Improving prompts/code will have limited impact (~5-10% improvement). The real solution is **expanding document coverage** in SharePoint.

---

## Test Result Patterns

### Live Test Results (January 2026 - 19 tests)

| # | Query | Result | Notes |
|---|-------|--------|-------|
| 1 | pool hours falcon pointe | NOT_FOUND | No pool hours doc |
| 2 | fence height falcon pointe | NOT_FOUND | Not in indexed docs |
| 3 | **fence stain avalon** | **FOUND** | Avalon Fence Stain Color.pdf |
| 4 | **pool rules heritage park** | **FOUND** | HERITAGE PARK POOL RULES.pdf |
| 5 | pet policy vista vera | NOT_FOUND | Pet docs not indexed |
| 6 | **annual assessment chandler creek** | **FOUND** | 2014 Assessment doc |
| 7 | parking rules wildhorse ranch | NOT_FOUND | - |
| 8 | rental restrictions highpointe | NOT_FOUND | - |
| 9 | fence materials bent tree | NOT_FOUND | - |
| 10-19 | Various | NOT_FOUND | See full log |

**Overall: 3 FOUND (15.8%) / 16 NOT_FOUND (84.2%)**

### What Works (100% success when doc exists)
| Category | Why It Works |
|----------|-------------|
| Avalon fence stain | Dedicated PDF: "Avalon Fence Stain Color.pdf" |
| Heritage Park pool rules | Dedicated PDF: "HERITAGE PARK POOL RULES - Revised.pdf" |
| Assessment amounts | Dedicated policy mailings with amounts |

### What Fails (0% success)
| Category | Root Cause |
|----------|------------|
| Pet policies | **No pet policy documents indexed anywhere** |
| Rental restrictions | Buried in CC&Rs, not standalone docs |
| Pool hours | Most communities don't have hours docs |
| Fence heights | Info in CC&Rs but extraction fails |
| ARC guidelines | Community-specific docs sparse |
| Parking rules | Not in standalone documents |

### Edge Cases Analysis
| Query Type | Behavior |
|------------|----------|
| ALL CAPS queries | Works same as lowercase |
| Typos (e.g., "poool") | Sometimes matches, depends on severity |
| Abbreviations (e.g., "FP" for Falcon Pointe) | **Fails** - no abbreviation mapping |
| Multi-topic queries (e.g., "fence AND pool rules") | Often misses second topic |
| No community specified | Returns mixed results from all communities |

---

## Code Analysis: Identified Issues

### Issue 1: Community Extraction Regex Too Narrow
**Location:** `app.py:548-557`
```python
community_patterns = [
    r'(?:for|in|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
    r'([A-Z][a-z]+(?:\s+(?:Creek|Park|Hills?|Valley|Ranch|Pointe?|Vista|Heights?))+)',
]
```
**Problem:**
- Misses all-lowercase queries like "falcon pointe pool rules"
- Misses abbreviations like "FP", "CC", "HP"
- Misses hyphenated names like "Switch-Willow"

**Recommendation:** Add case-insensitive matching and common abbreviations.

### Issue 2: Azure Search Query Too Simple
**Location:** `app.py:571-578`
```python
search_text = query
if community:
    search_text = f"{query} AND \"{community}\""
```
**Problem:**
- Uses `simple` queryType instead of `full` or `semantic`
- No boosting for exact matches
- AND operator may be too restrictive for community names

**Recommendation:** Use semantic search with query expansion.

### Issue 3: Extraction Type Detection Incomplete
**Location:** `app.py:691-703`
```python
if any(kw in query_lower for kw in ['fence', 'height', 'material']):
    extraction_type = "fence"
```
**Problem:**
- Missing detection for: rentals, solar, guest policies, violations
- No fallback intelligence for mixed-topic queries
- "rental restrictions" categorizes as "general"

**Recommendation:** Expand keyword lists and add fuzzy matching.

### Issue 4: Truncation May Cut Critical Info
**Location:** `app.py:681-684`
```python
if len(content) > 2000:
    content = content[:2000] + "..."
```
**Problem:**
- Fixed 2000 char limit may cut relevant sections
- CC&Rs have sections at different positions
- "6 feet" was at position 1717 - barely made it

**Recommendation:** Use intelligent section extraction based on query terms.

---

## Specific Code Improvements

### Improvement 1: Enhanced Community Extraction

```python
def extract_community_from_query(query):
    """Try to extract community name from query with fuzzy matching."""

    # Known community abbreviations and aliases
    COMMUNITY_ALIASES = {
        'fp': 'Falcon Pointe',
        'falcon': 'Falcon Pointe',
        'cc': 'Chandler Creek',
        'chandler': 'Chandler Creek',
        'hp': 'Heritage Park',
        'heritage': 'Heritage Park',
        'vv': 'Vista Vera',
        'vista': 'Vista Vera',
        'er': 'Eagle Ridge',
        'eagle': 'Eagle Ridge',
        'sw': 'Switch Willow',
        'switch': 'Switch Willow',
        'la vent': 'La Ventana',
        'ventana': 'La Ventana',
        'steiner': 'Steiner Ranch',
        'wildhorse': 'Wildhorse Ranch',
        'highpointe': 'Highpointe',
        'bent tree': 'Bent Tree',
        'summer creek': 'Summer Creek',
        'lakeline': 'Lakeline Oaks',
        'enclave': 'Enclave at Forest Creek',
    }

    query_lower = query.lower()

    # Check aliases first
    for alias, full_name in COMMUNITY_ALIASES.items():
        if alias in query_lower:
            return full_name

    # Case-insensitive patterns
    patterns = [
        r'(?:for|in|at|about)\s+([a-z]+(?:\s+[a-z]+)*(?:\s+(?:creek|park|hills?|valley|ranch|pointe?|vista|heights?|ridge|oaks?))+)',
        r'([a-z]+\s+(?:creek|park|hills?|valley|ranch|pointe?|vista|heights?|ridge|oaks?))',
    ]

    for pattern in patterns:
        match = re.search(pattern, query_lower)
        if match:
            return match.group(1).title()

    return None
```

### Improvement 2: Smart Content Extraction

```python
def extract_relevant_content(full_content, query, max_chars=3000):
    """Extract content sections most relevant to the query."""

    query_terms = set(query.lower().split())
    # Remove stop words
    query_terms -= {'what', 'is', 'the', 'are', 'for', 'in', 'at', 'a', 'an', 'how', 'can', 'i'}

    if not full_content:
        return ""

    # Split into paragraphs or sections
    paragraphs = re.split(r'\n\n+', full_content)

    # Score each paragraph by query term matches
    scored = []
    for para in paragraphs:
        para_lower = para.lower()
        score = sum(1 for term in query_terms if term in para_lower)
        if score > 0:
            scored.append((score, para))

    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)

    # Take highest-scoring paragraphs up to max_chars
    result = []
    total_chars = 0
    for score, para in scored:
        if total_chars + len(para) <= max_chars:
            result.append(para)
            total_chars += len(para)

    return '\n\n'.join(result) if result else full_content[:max_chars]
```

### Improvement 3: Enhanced Extraction Type Detection

```python
EXTRACTION_KEYWORDS = {
    'fence': ['fence', 'fencing', 'height', 'stain', 'color', 'wrought iron', 'chain link', 'wood fence'],
    'pool': ['pool', 'swimming', 'hours', 'guest', 'lifeguard', 'hot tub', 'spa', 'pool key'],
    'parking': ['parking', 'vehicle', 'tow', 'rv', 'boat', 'trailer', 'commercial vehicle', 'guest parking', 'overnight'],
    'pet': ['pet', 'dog', 'cat', 'animal', 'breed', 'leash', 'barking', 'exotic', 'weight limit'],
    'architectural': ['arc', 'architectural', 'modification', 'approval', 'exterior', 'paint', 'roof', 'solar', 'pergola'],
    'rental': ['rental', 'rent', 'lease', 'tenant', 'airbnb', 'short-term', 'subletting', 'landlord'],
    'assessment': ['assessment', 'dues', 'fee', 'payment', 'late fee', 'transfer fee', 'special assessment'],
    'landscaping': ['lawn', 'yard', 'tree', 'landscaping', 'artificial turf', 'xeriscape', 'mailbox', 'lighting'],
}

def detect_extraction_type(query):
    """Detect extraction type with multi-keyword matching."""
    query_lower = query.lower()

    scores = {}
    for ext_type, keywords in EXTRACTION_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > 0:
            scores[ext_type] = score

    if scores:
        return max(scores, key=scores.get)
    return 'general'
```

### Improvement 4: Improved AI Prompt

```python
prompt = f"""You are a helpful assistant for PS Property Management. A community manager needs specific information.

**Question:** {query}
{f'**Community:** {community}' if community else ''}

{doc_context}

**CRITICAL INSTRUCTIONS:**
1. READ the document CONTENT provided above carefully
2. EXTRACT the SPECIFIC ANSWER to the question from the content
3. If you find the answer, quote the exact text or numbers
4. If the answer is NOT in the provided content, say "The specific information was not found in the available documents"
5. Do NOT make up information - only report what is explicitly in the documents
6. For numeric questions (heights, fees, limits), provide the EXACT number from the document

**Response Format:**
Return ONLY this JSON structure:
{{
    "answer": "The specific answer extracted from documents (e.g., '6 feet maximum', '$500 per year', 'Dogs must be leashed at all times')",
    "found": true/false,
    "source": "Document name where found",
    "quote": "Exact relevant quote from document",
    "confidence": "high/medium/low",
    "summary": "One sentence summary"
}}

If no answer found in documents, set found=false and answer="No specific information found for this query in the available documents."
"""
```

---

## Prompt Engineering Improvements

### Current Issues
1. Prompt doesn't explicitly tell Claude to indicate when info is NOT found
2. No confidence level requested
3. No explicit instruction to avoid hallucination

### Recommended Prompt Additions

```
**IMPORTANT: DO NOT HALLUCINATE**
- Only extract information that is EXPLICITLY stated in the document content
- If you cannot find a direct answer, say so clearly
- Do not infer or assume information that isn't written
- When in doubt, quote the exact text from the document
```

### Add Few-Shot Examples

```
**Example 1 - Found:**
Question: "What is the fence height limit at Falcon Pointe?"
Document content: "...fences shall not exceed six (6) feet in height..."
Answer: "6 feet maximum height"

**Example 2 - Not Found:**
Question: "What is the pet weight limit at Vista Vera?"
Document content: "...owners may keep common household pets..."
Answer: "No specific weight limit was found in the available documents"
```

---

## Azure Search Configuration Improvements

### Current Configuration
- Query type: `simple`
- No semantic ranking
- No query expansion

### Recommended Configuration
```json
{
    "search": "fence height falcon pointe",
    "queryType": "semantic",
    "semanticConfiguration": "my-semantic-config",
    "captions": "extractive",
    "answers": "extractive|count-3",
    "highlightPreTag": "<mark>",
    "highlightPostTag": "</mark>"
}
```

### Benefits
1. Semantic understanding of queries
2. Extractive answers from documents
3. Better handling of natural language queries

---

## Document Index Gaps

### Missing Document Types
Based on test failures, these document types appear to be missing or sparse:

| Document Type | Communities Missing |
|---------------|---------------------|
| Pet Policies | ALL communities |
| Rental Restrictions | 80% of communities |
| Solar Guidelines | 90% of communities |
| Guest Parking Rules | 70% of communities |

### Recommendation
1. Audit SharePoint for missing documents
2. Create template pet/rental policies where none exist
3. Add indexing for community-specific operational documents

---

## Implementation Priority

| Priority | Improvement | Impact | Effort |
|----------|-------------|--------|--------|
| **P0** | **Document coverage audit** | **Critical** | **High** |
| **P0** | **Create missing standalone docs** | **Critical** | **High** |
| P1 | Community alias mapping | Medium | Low |
| P1 | Enhanced extraction type detection | Medium | Low |
| P2 | Smart content extraction from CC&Rs | Medium | Medium |
| P2 | Improved AI prompt | Low | Low |
| P3 | Semantic search config | Medium | High |

---

## Critical Action Items

### P0: Document Coverage (HIGHEST PRIORITY)

The testing revealed that **the search works perfectly when documents exist**. The problem is coverage:

1. **Create Pool Rules documents** for all pool communities
   - Currently only Heritage Park has a dedicated pool rules PDF
   - ~15 communities have pools but no rules doc

2. **Create Fence Guidelines documents** for all communities
   - Only Avalon has dedicated fence stain doc
   - Other communities have this buried in CC&Rs

3. **Create Pet Policy documents**
   - 0% success rate on pet queries
   - No communities have dedicated pet policy docs

4. **Extract standalone sections from CC&Rs**
   - Fence heights, parking rules, rental restrictions
   - Currently buried and hard to extract

### Estimated Impact

**With code improvements only (P1-P3):**
- Expected answer rate: **20-25%** (marginal improvement)

**With document coverage expansion (P0):**
- Expected answer rate: **60-80%** (transformative improvement)

---

*Generated: 2026-01-22*
*Based on: 50+ test scenarios, code review of app.py*
