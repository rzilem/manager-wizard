#!/usr/bin/env python3
"""
Manager Wizard - 100 Document Query Test Suite
Tests document search across many communities to measure indexer coverage.
"""

import requests
import json
import time
import sys
from datetime import datetime
from collections import defaultdict

# Configuration
BASE_URL = "https://manager-wizard-138752496729.us-central1.run.app"

# 20 communities x 5 question types = 100 queries
COMMUNITIES = [
    # Previously indexed (12 from last test)
    "Falcon Pointe",
    "Avalon",
    "Chandler Creek",
    "Highpointe",
    "McKinney Park East",
    "Central Park",
    "Parkside at Slaughter Creek",
    "Cooper",
    "Spicewood",
    "Enclave at Forest Creek",
    "Willow Branch",
    "Villages of Hidden Lake",
    # Previously NOT indexed (8 - should have docs now)
    "Brushy Creek",
    "Heritage Park",
    "Hills of Lakeway",
    "La Ventana",
    "Mountain Creek",
    "Scofield Farms",
    "Switch Willo",
    "Vista Vera",
]

QUESTION_TYPES = [
    {"suffix": "fence rules", "category": "fence", "desc": "Fence rules/restrictions"},
    {"suffix": "pool rules", "category": "pool", "desc": "Pool rules/hours"},
    {"suffix": "pet policy", "category": "pet", "desc": "Pet policy/restrictions"},
    {"suffix": "parking rules", "category": "parking", "desc": "Parking rules"},
    {"suffix": "architectural guidelines", "category": "arc", "desc": "ARC/architectural guidelines"},
]

# Build 100 queries
TEST_QUERIES = []
for community in COMMUNITIES:
    for qt in QUESTION_TYPES:
        TEST_QUERIES.append({
            "q": f"{qt['suffix']} {community}",
            "community": community,
            "category": qt["category"],
            "desc": f"{qt['desc']} - {community}",
        })


def test_endpoint(endpoint, params, timeout=30):
    url = f"{BASE_URL}{endpoint}"
    start = time.time()
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        elapsed = time.time() - start
        return {
            "status_code": resp.status_code,
            "elapsed_ms": int(elapsed * 1000),
            "response": resp.json() if resp.status_code == 200 else None,
            "error": resp.text if resp.status_code != 200 else None,
        }
    except requests.Timeout:
        return {"status_code": 408, "elapsed_ms": int((time.time() - start) * 1000), "response": None, "error": "Timeout"}
    except Exception as e:
        return {"status_code": 500, "elapsed_ms": int((time.time() - start) * 1000), "response": None, "error": str(e)}


def evaluate_result(result, query_info):
    if result["status_code"] != 200:
        return "ERROR", f"HTTP {result['status_code']}", False

    resp = result["response"]
    if not resp:
        return "ERROR", "No response body", False

    ai_answer = resp.get("ai_answer", {})
    docs = resp.get("documents", [])
    semantic = resp.get("semantic_answers", [])

    # Check for contamination - docs should match queried community
    queried = query_info["community"].lower()
    contaminated = False
    contam_names = []
    if docs:
        for doc in docs:
            doc_community = (doc.get("community_name") or "").lower()
            doc_path = (doc.get("file_path") or "").lower()
            if doc_community and queried.split()[0] not in doc_community and queried not in doc_path:
                contaminated = True
                contam_names.append(doc.get("community_name", "unknown"))

    has_ai = ai_answer and ai_answer.get("found")
    has_docs = len(docs) > 0
    has_semantic = len(semantic) > 0

    if has_ai:
        detail = ai_answer.get("answer", "")[:80]
        return "AI_ANSWER", detail, contaminated
    elif has_semantic:
        return "SEMANTIC", semantic[0].get("text", "")[:80], contaminated
    elif has_docs:
        return "DOCS_ONLY", f"{len(docs)} doc(s)", contaminated
    else:
        return "NOT_FOUND", "No results", False


def run_tests():
    print("=" * 90)
    print(f"MANAGER WIZARD - 100 DOCUMENT QUERY TEST SUITE")
    print(f"Base URL: {BASE_URL}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Communities: {len(COMMUNITIES)} | Question Types: {len(QUESTION_TYPES)} | Total: {len(TEST_QUERIES)}")
    print("=" * 90)

    # Connectivity check
    print("\nChecking service connectivity...")
    health = test_endpoint("/api/search", {"q": "test"})
    if health["status_code"] not in [200, 400]:
        print(f"[X] Service unreachable: {health['error']}")
        return
    print(f"[OK] Service responding - {health['elapsed_ms']}ms\n")

    all_results = []
    community_stats = defaultdict(lambda: {"total": 0, "found": 0, "not_found": 0, "error": 0, "contaminated": 0})
    category_stats = defaultdict(lambda: {"total": 0, "found": 0, "not_found": 0, "error": 0, "contaminated": 0})
    total_contaminated = 0

    for i, query_info in enumerate(TEST_QUERIES, 1):
        q = query_info["q"]
        community = query_info["community"]
        category = query_info["category"]

        result = test_endpoint("/api/unified-search", {"q": q, "mode": "document"})
        status, details, contaminated = evaluate_result(result, query_info)

        # Stats
        for stats_dict in [community_stats[community], category_stats[category]]:
            stats_dict["total"] += 1
            if status in ["AI_ANSWER", "SEMANTIC", "DOCS_ONLY"]:
                stats_dict["found"] += 1
            elif status == "NOT_FOUND":
                stats_dict["not_found"] += 1
            else:
                stats_dict["error"] += 1
            if contaminated:
                stats_dict["contaminated"] += 1

        if contaminated:
            total_contaminated += 1

        icon = "[OK]" if status in ["AI_ANSWER", "SEMANTIC", "DOCS_ONLY"] else "[--]" if status == "NOT_FOUND" else "[XX]"
        contam_flag = " CONTAM!" if contaminated else ""

        all_results.append({
            "query": q, "community": community, "category": category,
            "status": status, "details": details, "contaminated": contaminated,
            "elapsed_ms": result["elapsed_ms"], "response": result["response"],
        })

        print(f"[{i:3d}/100] {icon} {status:12s} | {result['elapsed_ms']:4d}ms | {q[:50]:<50s} | {details[:40]}{contam_flag}")
        time.sleep(0.15)

    # Summary
    print("\n" + "=" * 90)
    print("RESULTS BY COMMUNITY")
    print("=" * 90)

    sorted_communities = sorted(community_stats.items(), key=lambda x: x[1]["found"], reverse=True)
    for community, stats in sorted_communities:
        pct = (stats["found"] / stats["total"] * 100) if stats["total"] > 0 else 0
        bar = "#" * int(pct / 10) + "-" * (10 - int(pct / 10))
        contam_str = f" | {stats['contaminated']} contam" if stats["contaminated"] > 0 else ""
        prev_tag = " (NEW)" if community in COMMUNITIES[12:] else ""
        print(f"  {community:<30s} [{bar}] {stats['found']}/{stats['total']} ({pct:5.1f}%){contam_str}{prev_tag}")

    print("\n" + "=" * 90)
    print("RESULTS BY QUESTION TYPE")
    print("=" * 90)

    for category, stats in sorted(category_stats.items()):
        pct = (stats["found"] / stats["total"] * 100) if stats["total"] > 0 else 0
        contam_str = f" | {stats['contaminated']} contam" if stats["contaminated"] > 0 else ""
        print(f"  {category:<15s} {stats['found']}/{stats['total']} ({pct:5.1f}%){contam_str}")

    total_found = sum(s["found"] for s in community_stats.values())
    total = len(TEST_QUERIES)
    total_not_found = sum(s["not_found"] for s in community_stats.values())
    total_error = sum(s["error"] for s in community_stats.values())
    overall_pct = (total_found / total * 100) if total > 0 else 0
    avg_ms = sum(r["elapsed_ms"] for r in all_results) / len(all_results)

    print("\n" + "=" * 90)
    print(f"OVERALL: {total_found}/{total} ({overall_pct:.1f}%) returned results")
    print(f"Not Found: {total_not_found} | Errors: {total_error} | Contaminated: {total_contaminated}")
    print(f"Avg Response Time: {avg_ms:.0f}ms")
    print("=" * 90)

    # Communities with indexed docs
    indexed = [c for c, s in sorted_communities if s["found"] > 0]
    not_indexed = [c for c, s in sorted_communities if s["found"] == 0]
    print(f"\nCommunities WITH docs ({len(indexed)}): {', '.join(indexed)}")
    print(f"Communities WITHOUT docs ({len(not_indexed)}): {', '.join(not_indexed)}")

    # Save results
    output_file = f"doc_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path = f"C:\\Users\\ricky\\OneDrive - PS Prop Mgmt\\Documents\\GitHub\\manager-wizard\\scripts\\{output_file}"
    with open(output_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "total_queries": total,
            "total_found": total_found,
            "total_not_found": total_not_found,
            "total_error": total_error,
            "total_contaminated": total_contaminated,
            "success_rate": overall_pct,
            "avg_response_ms": avg_ms,
            "community_stats": {k: dict(v) for k, v in community_stats.items()},
            "category_stats": {k: dict(v) for k, v in category_stats.items()},
            "results": all_results,
        }, f, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    run_tests()
