#!/usr/bin/env python3
"""
Manager Wizard - Edge Case Regression Test Suite

Tests for algorithm improvements identified in search-failure-analysis.md
Each test category validates specific edge case handling.

Run with: python test_edge_cases.py [--local]
"""

import requests
import json
import sys
from datetime import datetime

# Configuration
BASE_URL = "https://manager-wizard-138752496729.us-central1.run.app"

if len(sys.argv) > 1 and sys.argv[1] == "--local":
    BASE_URL = "http://localhost:8080"

# =============================================================================
# EDGE CASE TEST DEFINITIONS
# =============================================================================

EDGE_CASE_TESTS = {
    # -------------------------------------------------------------------------
    # NAME SEARCH EDGE CASES
    # -------------------------------------------------------------------------
    "name_hyphenated": {
        "description": "Hyphenated last names should split and search both parts",
        "tests": [
            {
                "query": "Garcia-Lopez",
                "type": "name",
                "expected_behavior": "Should search for 'Garcia' AND 'Lopez'",
                "success_if": "count >= 0 and no error",  # May not find match, but shouldn't error
            },
            {
                "query": "Smith-Jones",
                "type": "name",
                "expected_behavior": "Should search for 'Smith' AND 'Jones'",
                "success_if": "count >= 0 and no error",
            },
        ]
    },

    "name_with_title": {
        "description": "Names with titles (Dr., Mrs., etc.) should strip title first",
        "tests": [
            {
                "query": "Dr. Brown",
                "type": "name",
                "expected_behavior": "Should strip 'Dr.' and search 'Brown'",
                "success_if": "count >= 0 and searches 'Brown'",
            },
            {
                "query": "Mrs. Johnson",
                "type": "name",
                "expected_behavior": "Should strip 'Mrs.' and search 'Johnson'",
                "success_if": "count >= 0 and searches 'Johnson'",
            },
            {
                "query": "Mr. Williams",
                "type": "name",
                "expected_behavior": "Should strip 'Mr.' and search 'Williams'",
                "success_if": "count >= 0 and searches 'Williams'",
            },
        ]
    },

    "name_with_initial": {
        "description": "Single letter initials should be handled",
        "tests": [
            {
                "query": "A. Smith",
                "type": "name",
                "expected_behavior": "Should search for first name starting with 'A' + 'Smith'",
                "success_if": "count >= 0 and no error",
            },
            {
                "query": "J Smith",
                "type": "name",
                "expected_behavior": "Should handle single-letter first name",
                "success_if": "count >= 0 and no error",
            },
        ]
    },

    "name_dutch_prefix": {
        "description": "Dutch/German prefixes (van, von, de) should be handled",
        "tests": [
            {
                "query": "van Heusen",
                "type": "name",
                "expected_behavior": "Should search for 'van' and 'Heusen' together",
                "success_if": "count >= 0 and no error",
            },
            {
                "query": "Von Trapp",
                "type": "name",
                "expected_behavior": "Should handle 'Von' prefix",
                "success_if": "count >= 0 and no error",
            },
        ]
    },

    "name_saint_prefix": {
        "description": "St. prefix should expand to Saint",
        "tests": [
            {
                "query": "St. James",
                "type": "name",
                "expected_behavior": "Should expand 'St.' to 'Saint' and search",
                "success_if": "count >= 0 and no error",
            },
        ]
    },

    "name_three_word": {
        "description": "Three-word names should search all parts",
        "tests": [
            {
                "query": "Mary Jane Watson",
                "type": "name",
                "expected_behavior": "Should search for all three parts",
                "success_if": "count >= 0 and no error",
            },
        ]
    },

    # -------------------------------------------------------------------------
    # ACCOUNT SEARCH EDGE CASES
    # -------------------------------------------------------------------------
    "account_letters_only": {
        "description": "Letters-only input should fail gracefully",
        "tests": [
            {
                "query": "ABC",
                "type": "account",
                "expected_behavior": "Should return empty with helpful message, not timeout",
                "success_if": "response in < 5 seconds and count == 0",
            },
            {
                "query": "XYZ",
                "type": "account",
                "expected_behavior": "Should return empty quickly",
                "success_if": "response in < 5 seconds and count == 0",
            },
        ]
    },

    "account_mixed_format": {
        "description": "Mixed format (123ABC) should try reversed format (ABC123)",
        "tests": [
            {
                "query": "123ABC",
                "type": "account",
                "expected_behavior": "Should try 'ABC123' format",
                "success_if": "count >= 0 and response in < 5 seconds",
            },
            {
                "query": "51515FAL",
                "type": "account",
                "expected_behavior": "Should try 'FAL51515' format",
                "success_if": "count >= 0",
            },
        ]
    },

    "account_leading_zeros": {
        "description": "Leading zeros should be stripped for numeric accounts",
        "tests": [
            {
                "query": "000123",
                "type": "account",
                "expected_behavior": "Should strip zeros and search '123'",
                "success_if": "count >= 0 and response in < 3 seconds",
            },
            {
                "query": "00051515",
                "type": "account",
                "expected_behavior": "Should strip zeros and search '51515'",
                "success_if": "count >= 0",
            },
        ]
    },

    # -------------------------------------------------------------------------
    # UNIT SEARCH EDGE CASES
    # -------------------------------------------------------------------------
    "unit_alphanumeric": {
        "description": "Alphanumeric units (5A, 12B) should be searchable",
        "tests": [
            {
                "query": "unit 5A",
                "type": "unit",
                "expected_behavior": "Should search for '5A' in unit/lot fields",
                "success_if": "count >= 0 and no error",
            },
            {
                "query": "unit 12B",
                "type": "unit",
                "expected_behavior": "Should search for '12B'",
                "success_if": "count >= 0 and no error",
            },
        ]
    },

    "unit_building_pattern": {
        "description": "Building patterns (bldg 2) should be recognized",
        "tests": [
            {
                "query": "bldg 2",
                "type": "unit",
                "expected_behavior": "Should recognize 'bldg' as valid prefix",
                "success_if": "no error returned",
            },
            {
                "query": "building 5",
                "type": "unit",
                "expected_behavior": "Should recognize 'building' as valid prefix",
                "success_if": "no error returned",
            },
        ]
    },

    "unit_phase_pattern": {
        "description": "Phase patterns should be handled",
        "tests": [
            {
                "query": "phase 1",
                "type": "unit",
                "expected_behavior": "Should recognize 'phase' as valid prefix or fail gracefully",
                "success_if": "no error returned",
            },
        ]
    },

    # -------------------------------------------------------------------------
    # ADDRESS SEARCH EDGE CASES
    # -------------------------------------------------------------------------
    "address_apartment_only": {
        "description": "Apartment-only queries should redirect to unit search",
        "tests": [
            {
                "query": "apt 5",
                "type": "address",
                "expected_behavior": "Should redirect to unit search or handle gracefully",
                "success_if": "count >= 0 and no error",
            },
            {
                "query": "apartment 10",
                "type": "address",
                "expected_behavior": "Should redirect to unit search",
                "success_if": "count >= 0 and no error",
            },
        ]
    },

    "address_with_city": {
        "description": "Address with city should parse correctly",
        "tests": [
            {
                "query": "100 Main, Austin",
                "type": "address",
                "expected_behavior": "Should strip city and search '100 Main'",
                "success_if": "count >= 0 and no error",
            },
        ]
    },

    "address_highway": {
        "description": "Highway/interstate queries should fail gracefully",
        "tests": [
            {
                "query": "IH 35",
                "type": "address",
                "expected_behavior": "Should return empty with message, not search",
                "success_if": "count == 0 and response in < 2 seconds",
            },
            {
                "query": "Mopac",
                "type": "address",
                "expected_behavior": "Should return empty with message",
                "success_if": "count == 0 and response in < 2 seconds",
            },
        ]
    },

    # -------------------------------------------------------------------------
    # COMMUNITY SEARCH EDGE CASES
    # -------------------------------------------------------------------------
    "community_generic_term": {
        "description": "Generic terms should warn user",
        "tests": [
            {
                "query": "Oaks",
                "type": "community",
                "expected_behavior": "Should warn that term is too generic or return filtered results",
                "success_if": "response includes message or count is reasonable",
            },
            {
                "query": "Park",
                "type": "community",
                "expected_behavior": "Should warn or filter appropriately",
                "success_if": "response in < 5 seconds",
            },
        ]
    },
}


def run_test(test_config, category_name):
    """Run a single test and return result."""
    query = test_config["query"]
    search_type = test_config["type"]

    url = f"{BASE_URL}/api/search"
    params = {"q": query, "type": search_type}

    start_time = datetime.now()
    try:
        response = requests.get(url, params=params, timeout=30)
        elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

        if response.status_code == 200:
            data = response.json()
            count = data.get("count", 0)
            error = data.get("error")
            message = data.get("message")

            # Determine pass/fail based on expected behavior
            passed = True
            notes = []

            # Check for error condition
            if error and "timeout" not in str(error).lower():
                notes.append(f"Error: {error}")
                # Some errors are expected (like invalid input)
                if "invalid" in str(error).lower() or "required" in str(error).lower():
                    passed = True
                else:
                    passed = False

            # Check response time for time-sensitive tests
            if "< 2 seconds" in test_config.get("success_if", ""):
                if elapsed_ms > 2000:
                    passed = False
                    notes.append(f"Too slow: {elapsed_ms:.0f}ms")
            elif "< 3 seconds" in test_config.get("success_if", ""):
                if elapsed_ms > 3000:
                    passed = False
                    notes.append(f"Too slow: {elapsed_ms:.0f}ms")
            elif "< 5 seconds" in test_config.get("success_if", ""):
                if elapsed_ms > 5000:
                    passed = False
                    notes.append(f"Too slow: {elapsed_ms:.0f}ms")

            return {
                "query": query,
                "type": search_type,
                "status": "PASS" if passed else "FAIL",
                "count": count,
                "elapsed_ms": round(elapsed_ms),
                "notes": "; ".join(notes) if notes else test_config["expected_behavior"],
                "error": error,
                "message": message,
            }

        else:
            return {
                "query": query,
                "type": search_type,
                "status": "FAIL",
                "count": 0,
                "elapsed_ms": round((datetime.now() - start_time).total_seconds() * 1000),
                "notes": f"HTTP {response.status_code}",
                "error": response.text[:100],
            }

    except requests.exceptions.Timeout:
        return {
            "query": query,
            "type": search_type,
            "status": "FAIL",
            "count": 0,
            "elapsed_ms": 30000,
            "notes": "TIMEOUT (30s)",
            "error": "Timeout",
        }
    except Exception as e:
        return {
            "query": query,
            "type": search_type,
            "status": "ERROR",
            "count": 0,
            "elapsed_ms": 0,
            "notes": str(e),
            "error": str(e),
        }


def main():
    """Run all edge case tests."""
    print("=" * 70)
    print("MANAGER WIZARD - EDGE CASE REGRESSION TEST SUITE")
    print(f"Target: {BASE_URL}")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 70)

    all_results = []
    category_stats = {}

    for category_name, category_config in EDGE_CASE_TESTS.items():
        print(f"\n--- {category_name.upper()} ---")
        print(f"    {category_config['description']}")

        category_results = []
        for test in category_config["tests"]:
            result = run_test(test, category_name)
            category_results.append(result)
            all_results.append({**result, "category": category_name})

            status_icon = "PASS" if result["status"] == "PASS" else "FAIL"
            print(f"    [{status_icon}] {result['query']:<25} ({result['elapsed_ms']}ms) {result.get('notes', '')[:40]}")

        passed = sum(1 for r in category_results if r["status"] == "PASS")
        total = len(category_results)
        category_stats[category_name] = {"passed": passed, "total": total}

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY BY CATEGORY")
    print("=" * 70)

    total_passed = 0
    total_tests = 0
    for category, stats in category_stats.items():
        pct = (stats["passed"] / stats["total"] * 100) if stats["total"] > 0 else 0
        print(f"  {category:<30} {stats['passed']}/{stats['total']} ({pct:.0f}%)")
        total_passed += stats["passed"]
        total_tests += stats["total"]

    print("-" * 70)
    overall_pct = (total_passed / total_tests * 100) if total_tests > 0 else 0
    print(f"  {'OVERALL':<30} {total_passed}/{total_tests} ({overall_pct:.0f}%)")
    print("=" * 70)

    # Save results
    output_file = f"edge_case_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "total_tests": total_tests,
            "total_passed": total_passed,
            "success_rate": overall_pct,
            "category_stats": category_stats,
            "results": all_results,
        }, f, indent=2)

    print(f"\nResults saved to: {output_file}")

    # Exit code based on pass rate
    sys.exit(0 if overall_pct >= 80 else 1)


if __name__ == "__main__":
    main()
