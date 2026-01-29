#!/usr/bin/env python3
"""
Address matching test suite for Manager Wizard.
Tests 50 address variations against live API.

Run: python scripts/test_address_matching.py
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

# =============================================================================
# TEST CASES (50 total)
# =============================================================================

ADDRESS_TEST_CASES = {
    # ===========================================================================
    # EXACT MATCHES (10 cases) - Should find with 100% confidence
    # Real addresses from Dataverse
    # ===========================================================================
    "exact_matches": [
        {"query": "18517 Falcon Pointe Blvd", "contains": "18517 Falcon", "desc": "Full address exact"},
        {"query": "1919 American Dr", "contains": "1919 American", "desc": "With Drive abbreviated"},
        {"query": "12 Monarch Oaks Ln", "contains": "12 Monarch Oaks", "desc": "Short street number"},
        {"query": "3 Glenway Dr", "contains": "3 Glenway", "desc": "Single digit number"},
        {"query": "1481 Old Settlers Blvd", "contains": "1481 Old Settlers", "desc": "Multi-word street"},
        {"query": "207 The Hills Dr", "contains": "207 The Hills", "desc": "Street name with article"},
        {"query": "4306 Cisco Valley Dr", "contains": "4306 Cisco Valley", "desc": "Two-word community name"},
        {"query": "907 Mohican Street", "contains": "907 Mohican", "desc": "Full 'Street' spelling"},
        {"query": "219 Kaden Prince Dr", "contains": "219 Kaden Prince", "desc": "Two-word street name"},
        {"query": "20805 Trotters Ln", "contains": "20805 Trotters", "desc": "Five digit number"},
    ],

    # ===========================================================================
    # ABBREVIATION NORMALIZATION (10 cases)
    # Query uses different abbreviation than DB
    # ===========================================================================
    "abbreviation_tests": [
        {"query": "18517 Falcon Pointe Boulevard", "contains": "18517 Falcon", "desc": "Boulevard -> Blvd"},
        {"query": "1919 American Drive", "contains": "1919 American", "desc": "Drive -> Dr"},
        {"query": "12 Monarch Oaks Lane", "contains": "12 Monarch Oaks", "desc": "Lane -> Ln"},
        {"query": "907 Mohican St", "contains": "907 Mohican", "desc": "St -> Street"},
        {"query": "35 Cottondale Road", "contains": "35 Cottondale", "desc": "Road -> Rd"},
        {"query": "3 Stillmeadow Court", "contains": "3 Stillmeadow", "desc": "Court -> Ct"},
        {"query": "16 Falling Oaks Trail", "contains": "16 Falling Oaks", "desc": "Trail -> Trl"},
        {"query": "8 Tiburon Drive", "contains": "8 Tiburon", "desc": "Drive normalized"},
        {"query": "44 Autumn Oaks Drive", "contains": "44 Autumn Oaks", "desc": "Multi-word + Drive"},
        {"query": "1000 Ranchers Club Lane", "contains": "1000 Ranchers Club", "desc": "Multi-word + Lane"},
    ],

    # ===========================================================================
    # PARTIAL ADDRESS MATCHING (10 cases)
    # Query is incomplete but should still match
    # ===========================================================================
    "partial_matches": [
        {"query": "18517 Falcon", "contains": "18517 Falcon", "desc": "Number + first word"},
        {"query": "12 Monarch", "contains": "12 Monarch", "desc": "Short number + first word"},
        {"query": "907 Mohican", "contains": "907 Mohican", "desc": "Number + street only"},
        {"query": "3 Glenway", "contains": "3 Glenway", "desc": "Minimal address"},
        {"query": "1919 American", "contains": "1919 American", "desc": "Without unit or type"},
        {"query": "219 Kaden", "contains": "219 Kaden", "desc": "First word of multi-word street"},
        {"query": "20805 Trotters", "contains": "20805 Trotters", "desc": "Five digit + street name"},
        {"query": "4306 Cisco", "contains": "4306 Cisco", "desc": "First word of valley"},
        {"query": "1481 Old", "contains": "1481 Old Settlers", "desc": "First word of Old Settlers"},
        {"query": "35 Cottondale", "contains": "35 Cottondale", "desc": "Number + name only"},
    ],

    # ===========================================================================
    # UNIT NUMBER VARIATIONS (10 cases)
    # Different ways to specify unit numbers
    # ===========================================================================
    "unit_variations": [
        {"query": "1919 American Dr #123", "contains": "1919 American", "desc": "Hash notation"},
        {"query": "1919 American Dr Apt 123", "contains": "1919 American", "desc": "Apt notation"},
        {"query": "1919 American Dr Apartment 123", "contains": "1919 American", "desc": "Full Apartment"},
        {"query": "1481 Old Settlers #1503", "contains": "1481 Old Settlers", "desc": "Hash + partial"},
        {"query": "1481 Old Settlers Suite 1503", "contains": "1481 Old Settlers", "desc": "Suite notation"},
        {"query": "1481 Old Settlers Ste 1503", "contains": "1481 Old Settlers", "desc": "Ste abbreviation"},
        {"query": "1481 Old Settlers Unit 202", "contains": "1481 Old Settlers", "desc": "Different unit"},
        {"query": "1481 Old Settlers Blvd Unit 1503", "contains": "1481 Old Settlers", "desc": "Full address with unit"},
        {"query": "Unit 1503 1481 Old Settlers", "contains": "1481 Old Settlers", "desc": "Unit first format"},
        {"query": "1919 American, Unit 123", "contains": "1919 American", "desc": "Comma separated"},
    ],

    # ===========================================================================
    # TYPO TOLERANCE / FUZZY MATCHING (10 cases)
    # Common typos that should still match
    # ===========================================================================
    "typo_tolerance": [
        {"query": "18517 Falcon Point Blvd", "contains": "18517 Falcon", "desc": "Point vs Pointe"},
        {"query": "12 Monarch Oak Ln", "contains": "12 Monarch Oaks", "desc": "Oak vs Oaks"},
        {"query": "907 Mohiccan Street", "contains": "907 Mohican", "desc": "Double c typo"},
        {"query": "3 Gelnway Dr", "contains": "3 Glenway", "desc": "Transposed letters"},
        {"query": "219 Kaiden Prince", "contains": "219 Kaden", "desc": "Extra letter"},
        {"query": "35 Cottendale Rd", "contains": "35 Cottondale", "desc": "Cotton typo"},
        {"query": "20805 Trotters Lan", "contains": "20805 Trotters", "desc": "Incomplete type"},
        {"query": "4306 Cisko Valley", "contains": "4306 Cisco", "desc": "Cisco typo"},
        {"query": "1000 Rancher Club Ln", "contains": "1000 Ranchers", "desc": "Missing s"},
        {"query": "8 Tiberon Dr", "contains": "8 Tiburon", "desc": "Vowel swap"},
    ],
}


def test_address_search(query: str, expected_contains: str, desc: str, timeout: int = 15) -> dict:
    """Test a single address search and return result."""
    url = f"{BASE_URL}/api/search"
    params = {"q": query, "type": "address"}

    start = time.time()
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        elapsed = time.time() - start

        if resp.status_code != 200:
            return {
                "status": "ERROR",
                "detail": f"HTTP {resp.status_code}",
                "elapsed_ms": int(elapsed * 1000),
                "count": 0
            }

        data = resp.json()
        homeowners = data.get("homeowners", [])
        count = len(homeowners)

        # Check if expected address pattern is in any result
        found = False
        matched_address = None
        for h in homeowners:
            addr = h.get("property_address", "")
            if expected_contains.lower() in addr.lower():
                found = True
                matched_address = addr
                break

        if found:
            return {
                "status": "PASS",
                "detail": f"Found: {matched_address[:50]}..." if matched_address else "Match found",
                "elapsed_ms": int(elapsed * 1000),
                "count": count
            }
        else:
            return {
                "status": "FAIL",
                "detail": f"{count} results, expected '{expected_contains}' not found",
                "elapsed_ms": int(elapsed * 1000),
                "count": count,
                "first_result": homeowners[0].get("property_address", "N/A")[:50] if homeowners else "No results"
            }

    except requests.Timeout:
        return {
            "status": "ERROR",
            "detail": "Request timed out",
            "elapsed_ms": int((time.time() - start) * 1000),
            "count": 0
        }
    except Exception as e:
        return {
            "status": "ERROR",
            "detail": str(e),
            "elapsed_ms": int((time.time() - start) * 1000),
            "count": 0
        }


def run_address_tests():
    """Run all 50 address test cases."""
    print("=" * 80)
    print("MANAGER WIZARD - ADDRESS MATCHING TEST SUITE (50 Tests)")
    print(f"Base URL: {BASE_URL}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Check connectivity first
    print("\nChecking service connectivity...")
    try:
        resp = requests.get(f"{BASE_URL}/api/status", timeout=10)
        if resp.status_code == 200:
            print(f"[OK] Service responding")
        else:
            print(f"[WARN] Status endpoint returned {resp.status_code}")
    except Exception as e:
        print(f"[ERROR] Cannot reach service: {e}")
        print("Make sure the service is running and accessible.")
        sys.exit(1)

    results = {
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "details": [],
        "category_stats": defaultdict(lambda: {"total": 0, "passed": 0, "failed": 0, "errors": 0})
    }

    total = sum(len(cases) for cases in ADDRESS_TEST_CASES.values())
    current = 0

    for category, cases in ADDRESS_TEST_CASES.items():
        print(f"\n{'='*60}")
        print(f"CATEGORY: {category.upper().replace('_', ' ')}")
        print(f"{'='*60}")

        for test_case in cases:
            current += 1
            query = test_case["query"]
            expected = test_case["contains"]
            desc = test_case["desc"]

            result = test_address_search(query, expected, desc)

            # Update stats
            results["category_stats"][category]["total"] += 1
            if result["status"] == "PASS":
                results["passed"] += 1
                results["category_stats"][category]["passed"] += 1
                icon = "[OK]"
            elif result["status"] == "FAIL":
                results["failed"] += 1
                results["category_stats"][category]["failed"] += 1
                icon = "[XX]"
            else:
                results["errors"] += 1
                results["category_stats"][category]["errors"] += 1
                icon = "[!!]"

            # Store detailed result
            results["details"].append({
                "category": category,
                "query": query,
                "expected_contains": expected,
                "desc": desc,
                "status": result["status"],
                "detail": result["detail"],
                "elapsed_ms": result["elapsed_ms"],
                "count": result["count"]
            })

            # Print progress
            detail_str = result["detail"][:45] if len(result["detail"]) > 45 else result["detail"]
            print(f"[{current:2d}/{total}] {icon} {result['status']:5s} | {desc:30s} | {detail_str}")

            time.sleep(0.1)  # Rate limiting

    # Summary
    print("\n" + "=" * 80)
    print("CATEGORY BREAKDOWN")
    print("=" * 80)

    for category, stats in results["category_stats"].items():
        pct = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"  {category.replace('_', ' ').title():25s}: {stats['passed']}/{stats['total']} ({pct:.0f}%)")

    print("\n" + "=" * 80)
    print("OVERALL SUMMARY")
    print("=" * 80)
    print(f"  Passed:  {results['passed']}/{total} ({results['passed']/total*100:.1f}%)")
    print(f"  Failed:  {results['failed']}/{total}")
    print(f"  Errors:  {results['errors']}/{total}")
    print("=" * 80)

    # Determine target achievement
    target = 90
    current_pct = results['passed'] / total * 100
    if current_pct >= target:
        print(f"\n[SUCCESS] Target of {target}% achieved! ({current_pct:.1f}%)")
    else:
        print(f"\n[NEEDS WORK] Current: {current_pct:.1f}%, Target: {target}%")
        print(f"Need to fix {int((target - current_pct) / 100 * total) + 1} more tests to reach target.")

    # Save results
    output_file = f"address_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "total": total,
            "passed": results["passed"],
            "failed": results["failed"],
            "errors": results["errors"],
            "success_rate": results['passed'] / total * 100,
            "category_stats": dict(results["category_stats"]),
            "details": results["details"]
        }, f, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")

    # List failed tests for quick reference
    failed_tests = [d for d in results["details"] if d["status"] == "FAIL"]
    if failed_tests:
        print(f"\n{'='*60}")
        print("FAILED TESTS:")
        print("="*60)
        for t in failed_tests:
            print(f"  - [{t['category']}] {t['query']}")
            print(f"    Expected: '{t['expected_contains']}'")
            print(f"    Detail: {t['detail']}")
            print()

    return results


if __name__ == "__main__":
    run_address_tests()
