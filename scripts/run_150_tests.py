#!/usr/bin/env python3
"""
Manager Wizard - Comprehensive 150-Query Test Suite
Tests homeowner searches, document searches, and unified searches
"""

import requests
import json
import time
import sys
from datetime import datetime
from collections import defaultdict

# Configuration
BASE_URL = "https://manager-wizard-138752496729.us-central1.run.app"
# BASE_URL = "http://localhost:8080"  # For local testing

# Test queries organized by category
TEST_QUERIES = {
    # ===========================================================================
    # HOMEOWNER SEARCHES (60 queries)
    # ===========================================================================

    "phone_searches": [
        # Standard phone formats
        {"q": "512-555-1234", "type": "phone", "desc": "Standard phone with dashes"},
        {"q": "5125551234", "type": "phone", "desc": "Phone without formatting"},
        {"q": "(512) 555-1234", "type": "phone", "desc": "Phone with parentheses"},
        {"q": "512.555.1234", "type": "phone", "desc": "Phone with dots"},
        {"q": "555-1234", "type": "phone", "desc": "7-digit phone"},
        {"q": "1234", "type": "phone", "desc": "4-digit (should fail)"},
        {"q": "+1 512 555 1234", "type": "phone", "desc": "International format"},
        {"q": "512 555 1234", "type": "phone", "desc": "Phone with spaces"},
        {"q": "5128896300", "type": "phone", "desc": "Real area code search"},
        {"q": "737-555-0100", "type": "phone", "desc": "Austin 737 area code"},
    ],

    "address_searches": [
        # Address patterns
        {"q": "100 Main Street", "type": "address", "desc": "Standard address"},
        {"q": "1234 Oak Drive", "type": "address", "desc": "Common street name"},
        {"q": "500 Falcon Pointe", "type": "address", "desc": "Address with community name"},
        {"q": "7016 Walkup", "type": "address", "desc": "Partial address"},
        {"q": "123 Vista Verde Dr", "type": "address", "desc": "Abbreviated street type"},
        {"q": "100 N Main St", "type": "address", "desc": "Directional address"},
        {"q": "1000 Ranch Road", "type": "address", "desc": "Ranch road address"},
        {"q": "apt 5", "type": "address", "desc": "Apartment only (edge case)"},
        {"q": "100 Main, Austin", "type": "address", "desc": "Address with city"},
        {"q": "Falcon", "type": "address", "desc": "Community name as address"},
    ],

    "name_searches": [
        # Name patterns
        {"q": "Smith", "type": "name", "desc": "Common last name"},
        {"q": "John Smith", "type": "name", "desc": "Full name"},
        {"q": "johnson", "type": "name", "desc": "Lowercase name"},
        {"q": "WILLIAMS", "type": "name", "desc": "Uppercase name"},
        {"q": "O'Brien", "type": "name", "desc": "Name with apostrophe"},
        {"q": "Garcia-Lopez", "type": "name", "desc": "Hyphenated name"},
        {"q": "Van Der Berg", "type": "name", "desc": "Multi-word last name"},
        {"q": "Jr.", "type": "name", "desc": "Suffix only (edge case)"},
        {"q": "Mary Jane Watson", "type": "name", "desc": "Three-word name"},
        {"q": "J Smith", "type": "name", "desc": "Initial + last name"},
    ],

    "account_searches": [
        # Account number patterns
        {"q": "FAL51515", "type": "account", "desc": "Standard account with prefix"},
        {"q": "AMC12345", "type": "account", "desc": "Avalon account"},
        {"q": "51515", "type": "account", "desc": "Account without prefix"},
        {"q": "12345", "type": "account", "desc": "Short account number"},
        {"q": "VIS99999", "type": "account", "desc": "Vista Vera account"},
        {"q": "fal51515", "type": "account", "desc": "Lowercase account"},
        {"q": "CCH0001", "type": "account", "desc": "Chandler Creek account"},
        {"q": "HER", "type": "account", "desc": "Prefix only"},
        {"q": "000123", "type": "account", "desc": "Account with leading zeros"},
        {"q": "SAGE1234", "type": "account", "desc": "Sage account"},
    ],

    "community_searches": [
        # Community name patterns
        {"q": "Falcon Pointe", "type": "community", "desc": "Full community name"},
        {"q": "falcon pointe", "type": "community", "desc": "Lowercase community"},
        {"q": "AVALON", "type": "community", "desc": "Uppercase community"},
        {"q": "Chandler Creek", "type": "community", "desc": "Two-word community"},
        {"q": "Heritage Park", "type": "community", "desc": "Common community"},
        {"q": "Vista Vera", "type": "community", "desc": "Vista community"},
        {"q": "La Ventana", "type": "community", "desc": "Spanish name"},
        {"q": "Switch Willow", "type": "community", "desc": "Less common community"},
        {"q": "Highpointe", "type": "community", "desc": "Single word community"},
        {"q": "Wildhorse Ranch", "type": "community", "desc": "Ranch community"},
    ],

    "unit_searches": [
        # Unit/lot patterns
        {"q": "unit 5", "type": "unit", "desc": "Unit search"},
        {"q": "Unit 100", "type": "unit", "desc": "Capitalized unit"},
        {"q": "lot 12", "type": "unit", "desc": "Lot search"},
        {"q": "#5", "type": "unit", "desc": "Hash unit notation"},
        {"q": "unit 5A", "type": "unit", "desc": "Alphanumeric unit"},
        {"q": "UNIT 200", "type": "unit", "desc": "Uppercase unit"},
        {"q": "lot A", "type": "unit", "desc": "Letter lot"},
        {"q": "apt 101", "type": "unit", "desc": "Apartment"},
        {"q": "suite 300", "type": "unit", "desc": "Suite"},
        {"q": "#1A", "type": "unit", "desc": "Hash alphanumeric"},
    ],

    # ===========================================================================
    # DOCUMENT SEARCHES (60 queries)
    # ===========================================================================

    "fence_queries": [
        {"q": "fence height falcon pointe", "type": "doc", "desc": "Fence height specific community"},
        {"q": "fence stain avalon", "type": "doc", "desc": "Fence stain (known good)"},
        {"q": "what color can I paint my fence", "type": "doc", "desc": "Natural language fence"},
        {"q": "fence materials", "type": "doc", "desc": "Fence materials general"},
        {"q": "wrought iron fence", "type": "doc", "desc": "Specific fence type"},
        {"q": "chain link fence allowed", "type": "doc", "desc": "Chain link question"},
        {"q": "fence setback requirements", "type": "doc", "desc": "Fence setback"},
        {"q": "max fence height", "type": "doc", "desc": "Maximum height"},
        {"q": "fence between neighbors", "type": "doc", "desc": "Neighbor fence"},
        {"q": "replacing fence", "type": "doc", "desc": "Fence replacement"},
    ],

    "pool_queries": [
        {"q": "pool hours falcon pointe", "type": "doc", "desc": "Pool hours specific"},
        {"q": "pool rules heritage park", "type": "doc", "desc": "Pool rules (known good)"},
        {"q": "can I bring guests to the pool", "type": "doc", "desc": "Pool guests question"},
        {"q": "pool key", "type": "doc", "desc": "Pool key info"},
        {"q": "swimming pool rules", "type": "doc", "desc": "General pool rules"},
        {"q": "hot tub hours", "type": "doc", "desc": "Hot tub/spa hours"},
        {"q": "pool closing time", "type": "doc", "desc": "Pool closing"},
        {"q": "pool party reservation", "type": "doc", "desc": "Pool party"},
        {"q": "children at the pool", "type": "doc", "desc": "Pool children rules"},
        {"q": "pool guest limit", "type": "doc", "desc": "Guest limits"},
    ],

    "pet_queries": [
        {"q": "pet policy falcon pointe", "type": "doc", "desc": "Pet policy specific"},
        {"q": "dog breed restrictions", "type": "doc", "desc": "Breed restrictions"},
        {"q": "how many pets can I have", "type": "doc", "desc": "Pet limit question"},
        {"q": "pet weight limit", "type": "doc", "desc": "Pet weight"},
        {"q": "leash rules", "type": "doc", "desc": "Leash requirements"},
        {"q": "barking dog", "type": "doc", "desc": "Barking complaints"},
        {"q": "exotic pets", "type": "doc", "desc": "Exotic animals"},
        {"q": "cat restrictions", "type": "doc", "desc": "Cat rules"},
        {"q": "pet registration", "type": "doc", "desc": "Pet registration"},
        {"q": "animals allowed", "type": "doc", "desc": "General animal rules"},
    ],

    "parking_queries": [
        {"q": "parking rules", "type": "doc", "desc": "General parking"},
        {"q": "guest parking", "type": "doc", "desc": "Guest parking"},
        {"q": "overnight parking", "type": "doc", "desc": "Overnight rules"},
        {"q": "rv parking", "type": "doc", "desc": "RV parking"},
        {"q": "boat storage", "type": "doc", "desc": "Boat/trailer parking"},
        {"q": "commercial vehicle", "type": "doc", "desc": "Commercial vehicles"},
        {"q": "towing policy", "type": "doc", "desc": "Towing"},
        {"q": "garage requirements", "type": "doc", "desc": "Garage parking"},
        {"q": "street parking restrictions", "type": "doc", "desc": "Street parking"},
        {"q": "visitor parking permit", "type": "doc", "desc": "Visitor permits"},
    ],

    "rental_queries": [
        {"q": "rental restrictions falcon pointe", "type": "doc", "desc": "Rental restrictions specific"},
        {"q": "can I rent my house", "type": "doc", "desc": "Rental question"},
        {"q": "airbnb allowed", "type": "doc", "desc": "Short-term rental"},
        {"q": "lease requirements", "type": "doc", "desc": "Lease requirements"},
        {"q": "tenant rules", "type": "doc", "desc": "Tenant rules"},
        {"q": "minimum lease term", "type": "doc", "desc": "Lease term"},
        {"q": "rental cap", "type": "doc", "desc": "Rental percentage cap"},
        {"q": "landlord responsibilities", "type": "doc", "desc": "Landlord duties"},
        {"q": "subletting", "type": "doc", "desc": "Subletting rules"},
        {"q": "short term rental ban", "type": "doc", "desc": "STR ban"},
    ],

    "arc_queries": [
        {"q": "arc application", "type": "doc", "desc": "ARC application"},
        {"q": "architectural guidelines", "type": "doc", "desc": "Guidelines"},
        {"q": "exterior modifications", "type": "doc", "desc": "Exterior mods"},
        {"q": "paint colors approved", "type": "doc", "desc": "Paint colors"},
        {"q": "solar panels", "type": "doc", "desc": "Solar panels"},
        {"q": "roof replacement approval", "type": "doc", "desc": "Roof replacement"},
        {"q": "patio cover", "type": "doc", "desc": "Patio cover"},
        {"q": "pergola requirements", "type": "doc", "desc": "Pergola"},
        {"q": "window replacement", "type": "doc", "desc": "Window replacement"},
        {"q": "landscaping approval", "type": "doc", "desc": "Landscaping"},
    ],

    # ===========================================================================
    # UNIFIED/MIXED SEARCHES (30 queries)
    # ===========================================================================

    "unified_searches": [
        {"q": "John Smith Falcon Pointe", "type": "unified", "desc": "Name + community"},
        {"q": "balance due Smith", "type": "unified", "desc": "Balance inquiry"},
        {"q": "what are my dues", "type": "unified", "desc": "Dues question"},
        {"q": "annual assessment amount", "type": "unified", "desc": "Assessment amount"},
        {"q": "HOA fees chandler creek", "type": "unified", "desc": "HOA fees"},
        {"q": "late fee policy", "type": "unified", "desc": "Late fees"},
        {"q": "transfer fee", "type": "unified", "desc": "Transfer fees"},
        {"q": "when are dues due", "type": "unified", "desc": "Due date"},
        {"q": "special assessment", "type": "unified", "desc": "Special assessment"},
        {"q": "budget falcon pointe", "type": "unified", "desc": "Budget document"},
        {"q": "board meeting", "type": "unified", "desc": "Board meeting info"},
        {"q": "contact property manager", "type": "unified", "desc": "Manager contact"},
        {"q": "CC&Rs falcon pointe", "type": "unified", "desc": "CC&Rs request"},
        {"q": "bylaws", "type": "unified", "desc": "Bylaws request"},
        {"q": "rules and regulations", "type": "unified", "desc": "Rules document"},
        {"q": "violation appeal", "type": "unified", "desc": "Violation appeal"},
        {"q": "fine schedule", "type": "unified", "desc": "Fine amounts"},
        {"q": "collections policy", "type": "unified", "desc": "Collections"},
        {"q": "insurance requirements", "type": "unified", "desc": "Insurance"},
        {"q": "tree removal", "type": "unified", "desc": "Tree removal"},
        {"q": "mailbox replacement", "type": "unified", "desc": "Mailbox"},
        {"q": "holiday decorations", "type": "unified", "desc": "Decorations"},
        {"q": "noise restrictions", "type": "unified", "desc": "Noise rules"},
        {"q": "trash pickup", "type": "unified", "desc": "Trash schedule"},
        {"q": "recycling", "type": "unified", "desc": "Recycling info"},
        {"q": "gate code", "type": "unified", "desc": "Gate code"},
        {"q": "amenity hours", "type": "unified", "desc": "Amenity hours"},
        {"q": "clubhouse reservation", "type": "unified", "desc": "Clubhouse"},
        {"q": "playground rules", "type": "unified", "desc": "Playground"},
        {"q": "speed limit", "type": "unified", "desc": "Speed limit"},
    ],
}


def test_endpoint(endpoint, params, timeout=30):
    """Test an API endpoint and return results."""
    url = f"{BASE_URL}{endpoint}"
    start = time.time()

    try:
        resp = requests.get(url, params=params, timeout=timeout)
        elapsed = time.time() - start

        return {
            "status_code": resp.status_code,
            "elapsed_ms": int(elapsed * 1000),
            "response": resp.json() if resp.status_code == 200 else None,
            "error": resp.text if resp.status_code != 200 else None
        }
    except requests.Timeout:
        return {
            "status_code": 408,
            "elapsed_ms": int((time.time() - start) * 1000),
            "response": None,
            "error": "Request timed out"
        }
    except Exception as e:
        return {
            "status_code": 500,
            "elapsed_ms": int((time.time() - start) * 1000),
            "response": None,
            "error": str(e)
        }


def evaluate_homeowner_result(result, query_info):
    """Evaluate if a homeowner search was successful."""
    if result["status_code"] != 200:
        return "ERROR", f"HTTP {result['status_code']}"

    resp = result["response"]
    if not resp:
        return "ERROR", "No response body"

    homeowners = resp.get("homeowners", [])
    count = len(homeowners)

    if count > 0:
        return "FOUND", f"{count} result(s)"
    else:
        return "NOT_FOUND", "No matches"


def evaluate_document_result(result, query_info):
    """Evaluate if a document search was successful."""
    if result["status_code"] != 200:
        return "ERROR", f"HTTP {result['status_code']}"

    resp = result["response"]
    if not resp:
        return "ERROR", "No response body"

    # Check for AI answer
    ai_answer = resp.get("ai_answer", {})
    if ai_answer and ai_answer.get("found"):
        return "AI_ANSWER", ai_answer.get("answer", "")[:100]

    # Check for semantic answers
    semantic = resp.get("semantic_answers", [])
    if semantic:
        return "SEMANTIC", semantic[0].get("text", "")[:100]

    # Check for documents
    docs = resp.get("documents", [])
    if docs:
        return "DOCS_ONLY", f"{len(docs)} document(s)"

    return "NOT_FOUND", "No results"


def evaluate_unified_result(result, query_info):
    """Evaluate unified search results."""
    if result["status_code"] != 200:
        return "ERROR", f"HTTP {result['status_code']}"

    resp = result["response"]
    if not resp:
        return "ERROR", "No response body"

    homeowners = resp.get("homeowners", [])
    docs = resp.get("documents", [])
    ai_answer = resp.get("ai_answer", {})

    results = []
    if homeowners:
        results.append(f"{len(homeowners)} homeowners")
    if docs:
        results.append(f"{len(docs)} docs")
    if ai_answer and ai_answer.get("found"):
        results.append("AI answer")

    if results:
        return "FOUND", ", ".join(results)
    return "NOT_FOUND", "No results"


def run_tests():
    """Run all 150 tests and report results."""
    print("=" * 80)
    print(f"MANAGER WIZARD - 150 QUERY TEST SUITE")
    print(f"Base URL: {BASE_URL}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # First check connectivity with a simple search
    print("\nChecking service connectivity...")
    health = test_endpoint("/api/search", {"q": "test"})
    if health["status_code"] not in [200, 400]:
        print(f"[X] Service unreachable: {health['error']}")
        return
    print(f"[OK] Service responding - {health['elapsed_ms']}ms")

    all_results = []
    category_stats = defaultdict(lambda: {"total": 0, "found": 0, "not_found": 0, "error": 0})

    total_queries = sum(len(queries) for queries in TEST_QUERIES.values())
    current = 0

    for category, queries in TEST_QUERIES.items():
        print(f"\n{'='*60}")
        print(f"CATEGORY: {category.upper()}")
        print(f"{'='*60}")

        for query_info in queries:
            current += 1
            q = query_info["q"]
            query_type = query_info["type"]
            desc = query_info["desc"]

            # Determine endpoint and evaluation function
            if query_type in ["phone", "address", "name", "account", "community", "unit"]:
                endpoint = "/api/search"
                params = {"q": q, "type": query_type if query_type != "general" else "auto"}
                evaluate = evaluate_homeowner_result
            elif query_type == "doc":
                endpoint = "/api/unified-search"
                params = {"q": q, "mode": "document"}
                evaluate = evaluate_document_result
            else:  # unified
                endpoint = "/api/unified-search"
                params = {"q": q, "mode": "auto"}
                evaluate = evaluate_unified_result

            # Run test
            result = test_endpoint(endpoint, params)
            status, details = evaluate(result, query_info)

            # Track stats
            category_stats[category]["total"] += 1
            if status in ["FOUND", "AI_ANSWER", "SEMANTIC", "DOCS_ONLY"]:
                category_stats[category]["found"] += 1
                icon = "[OK]"
            elif status == "NOT_FOUND":
                category_stats[category]["not_found"] += 1
                icon = "[--]"
            else:
                category_stats[category]["error"] += 1
                icon = "[XX]"

            # Store result
            all_results.append({
                "category": category,
                "query": q,
                "type": query_type,
                "desc": desc,
                "status": status,
                "details": details,
                "elapsed_ms": result["elapsed_ms"],
                "response": result["response"]
            })

            # Print progress
            print(f"[{current:3d}/{total_queries}] {icon} {status:12s} | {result['elapsed_ms']:4d}ms | {q[:40]:<40s} | {details[:50]}")

            # Small delay to avoid rate limiting
            time.sleep(0.1)

    # Print summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    total_found = 0
    total_not_found = 0
    total_error = 0

    for category, stats in category_stats.items():
        found_pct = (stats["found"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"\n{category}:")
        print(f"  Total: {stats['total']}, Found: {stats['found']} ({found_pct:.1f}%), Not Found: {stats['not_found']}, Errors: {stats['error']}")
        total_found += stats["found"]
        total_not_found += stats["not_found"]
        total_error += stats["error"]

    total = total_found + total_not_found + total_error
    overall_pct = (total_found / total * 100) if total > 0 else 0

    print("\n" + "=" * 80)
    print(f"OVERALL: {total_found}/{total} ({overall_pct:.1f}%) successful")
    print(f"Not Found: {total_not_found}, Errors: {total_error}")
    print("=" * 80)

    # Save detailed results
    output_file = f"test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "total_queries": total,
            "total_found": total_found,
            "total_not_found": total_not_found,
            "total_error": total_error,
            "success_rate": overall_pct,
            "category_stats": dict(category_stats),
            "results": all_results
        }, f, indent=2, default=str)

    print(f"\nDetailed results saved to: {output_file}")

    return all_results, category_stats


if __name__ == "__main__":
    run_tests()
