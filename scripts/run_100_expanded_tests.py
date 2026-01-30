#!/usr/bin/env python3
"""
Manager Wizard - 100 Expanded Document Query Test Suite
Realistic question types including maintenance, trash, CC&Rs, bylaws, etc.
Includes condo-specific maintenance responsibility questions.
"""

import requests
import json
import time
import sys
from datetime import datetime
from collections import defaultdict

# Configuration
BASE_URL = "https://manager-wizard-138752496729.us-central1.run.app"

# 10 communities x 10 question types = 100 queries
# Mix of single-family HOAs and condos for maintenance responsibility questions
COMMUNITIES = [
    # Single-family HOAs
    "Falcon Pointe",
    "Chandler Creek",
    "Highpointe",
    "Avalon",
    "Hills of Lakeway",
    # Condos / Townhomes
    "Canopy",
    "Willow Branch",
    "Crossing",
    # More HOAs with newly indexed docs
    "Brushy Creek",
    "La Ventana",
]

QUESTION_TYPES = [
    # Original types
    {"template": "fence rules {community}", "category": "fence", "desc": "Fence rules"},
    {"template": "pool rules {community}", "category": "pool", "desc": "Pool rules"},
    # Expanded realistic questions
    {"template": "trash pickup schedule {community}", "category": "trash", "desc": "Trash schedule"},
    {"template": "who is responsible for roof maintenance {community}", "category": "maintenance", "desc": "Roof maintenance responsibility"},
    {"template": "CC&Rs {community}", "category": "ccrs", "desc": "CC&Rs document"},
    {"template": "bylaws {community}", "category": "bylaws", "desc": "Bylaws document"},
    {"template": "rental restrictions {community}", "category": "rental", "desc": "Rental restrictions"},
    {"template": "is the owner responsible for plumbing repairs {community}", "category": "maintenance", "desc": "Plumbing maintenance responsibility"},
    {"template": "landscaping maintenance responsibility {community}", "category": "maintenance", "desc": "Landscaping responsibility"},
    {"template": "insurance requirements {community}", "category": "insurance", "desc": "Insurance requirements"},
]

# Build 100 queries
TEST_QUERIES = []
for community in COMMUNITIES:
    for qt in QUESTION_TYPES:
        TEST_QUERIES.append({
            "q": qt["template"].format(community=community),
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
        return "ERROR", f"HTTP {result['status_code']}", False, False, 0

    resp = result["response"]
    if not resp:
        return "ERROR", "No response body", False, False, 0

    ai_answer = resp.get("ai_answer", {})
    docs = resp.get("documents", [])
    semantic = resp.get("semantic_answers", [])

    # Check for contamination
    queried = query_info["community"].lower()
    contaminated = False
    if docs:
        for doc in docs:
            doc_community = (doc.get("community") or "").lower()
            if doc_community and queried.split()[0] not in doc_community and queried not in doc_community:
                contaminated = True
                break

    # Check if documents have URLs now
    docs_with_urls = sum(1 for d in docs if d.get("url"))

    has_ai = ai_answer and ai_answer.get("extracted") and ai_answer["extracted"].get("answer")
    has_docs = len(docs) > 0

    # Check if AI answer is actually useful (not "not found" type)
    ai_useful = False
    if has_ai:
        answer_lower = ai_answer["extracted"]["answer"].lower()
        negative_phrases = ['not found', 'no specific', 'could not find', 'not available',
                           'unable to find', 'unable to determine', 'cannot determine',
                           'no information', 'no mention', 'does not mention', 'does not address',
                           'does not contain', 'additional documents', 'more specific search']
        ai_useful = not any(phrase in answer_lower for phrase in negative_phrases)

    if ai_useful:
        detail = ai_answer["extracted"]["answer"][:80]
        return "AI_ANSWER", detail, contaminated, docs_with_urls > 0, docs_with_urls
    elif has_docs:
        return "DOCS_ONLY", f"{len(docs)} doc(s), {docs_with_urls} with URLs", contaminated, docs_with_urls > 0, docs_with_urls
    else:
        return "NOT_FOUND", "No results", False, False, 0


def run_tests():
    print("=" * 100)
    print(f"MANAGER WIZARD - 100 EXPANDED DOCUMENT QUERY TEST SUITE")
    print(f"Base URL: {BASE_URL}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Communities: {len(COMMUNITIES)} | Question Types: {len(QUESTION_TYPES)} | Total: {len(TEST_QUERIES)}")
    print("=" * 100)

    # Connectivity check
    print("\nChecking service connectivity...")
    health = test_endpoint("/api/search", {"q": "test"})
    if health["status_code"] not in [200, 400]:
        print(f"[X] Service unreachable: {health['error']}")
        return
    print(f"[OK] Service responding - {health['elapsed_ms']}ms\n")

    all_results = []
    community_stats = defaultdict(lambda: {"total": 0, "found": 0, "ai_answers": 0, "not_found": 0, "error": 0, "contaminated": 0, "has_urls": 0})
    category_stats = defaultdict(lambda: {"total": 0, "found": 0, "ai_answers": 0, "not_found": 0, "error": 0, "contaminated": 0, "has_urls": 0})
    total_contaminated = 0
    total_with_urls = 0
    total_url_count = 0

    for i, query_info in enumerate(TEST_QUERIES, 1):
        q = query_info["q"]
        community = query_info["community"]
        category = query_info["category"]

        result = test_endpoint("/api/unified-search", {"q": q, "mode": "document"})
        status, details, contaminated, has_url, url_count = evaluate_result(result, query_info)

        for stats_dict in [community_stats[community], category_stats[category]]:
            stats_dict["total"] += 1
            if status in ["AI_ANSWER", "DOCS_ONLY"]:
                stats_dict["found"] += 1
            elif status == "NOT_FOUND":
                stats_dict["not_found"] += 1
            else:
                stats_dict["error"] += 1
            if status == "AI_ANSWER":
                stats_dict["ai_answers"] += 1
            if contaminated:
                stats_dict["contaminated"] += 1
            if has_url:
                stats_dict["has_urls"] += 1

        if contaminated:
            total_contaminated += 1
        if has_url:
            total_with_urls += 1
        total_url_count += url_count

        icon = "[OK]" if status == "AI_ANSWER" else "[ok]" if status == "DOCS_ONLY" else "[--]" if status == "NOT_FOUND" else "[XX]"
        url_flag = f" [URLs:{url_count}]" if url_count > 0 else " [NO URLs]" if status in ["AI_ANSWER", "DOCS_ONLY"] else ""
        contam_flag = " CONTAM!" if contaminated else ""

        all_results.append({
            "query": q, "community": community, "category": category,
            "status": status, "details": details, "contaminated": contaminated,
            "has_urls": has_url, "url_count": url_count,
            "elapsed_ms": result["elapsed_ms"], "response": result["response"],
        })

        print(f"[{i:3d}/100] {icon} {status:12s} | {result['elapsed_ms']:4d}ms | {q[:55]:<55s} | {details[:35]}{url_flag}{contam_flag}")
        time.sleep(0.15)

    # Summary by Community
    print("\n" + "=" * 100)
    print("RESULTS BY COMMUNITY")
    print("=" * 100)

    sorted_communities = sorted(community_stats.items(), key=lambda x: x[1]["found"], reverse=True)
    for community, stats in sorted_communities:
        pct = (stats["found"] / stats["total"] * 100) if stats["total"] > 0 else 0
        ai_pct = (stats["ai_answers"] / stats["total"] * 100) if stats["total"] > 0 else 0
        bar = "#" * int(pct / 10) + "-" * (10 - int(pct / 10))
        url_str = f" | {stats['has_urls']}/{stats['found']} with URLs" if stats["found"] > 0 else ""
        print(f"  {community:<30s} [{bar}] {stats['found']}/{stats['total']} ({pct:5.1f}%) | AI: {stats['ai_answers']} ({ai_pct:.0f}%){url_str}")

    # Summary by Question Type
    print("\n" + "=" * 100)
    print("RESULTS BY QUESTION TYPE")
    print("=" * 100)

    for category, stats in sorted(category_stats.items(), key=lambda x: x[1]["found"], reverse=True):
        pct = (stats["found"] / stats["total"] * 100) if stats["total"] > 0 else 0
        ai_pct = (stats["ai_answers"] / stats["total"] * 100) if stats["total"] > 0 else 0
        url_str = f" | {stats['has_urls']}/{stats['found']} with URLs" if stats["found"] > 0 else ""
        print(f"  {category:<15s} {stats['found']}/{stats['total']} ({pct:5.1f}%) | AI answers: {stats['ai_answers']} ({ai_pct:.0f}%){url_str}")

    total_found = sum(s["found"] for s in community_stats.values())
    total_ai = sum(s["ai_answers"] for s in community_stats.values())
    total = len(TEST_QUERIES)
    total_not_found = sum(s["not_found"] for s in community_stats.values())
    total_error = sum(s["error"] for s in community_stats.values())
    overall_pct = (total_found / total * 100) if total > 0 else 0
    ai_pct = (total_ai / total * 100) if total > 0 else 0
    url_pct = (total_with_urls / total_found * 100) if total_found > 0 else 0
    avg_ms = sum(r["elapsed_ms"] for r in all_results) / len(all_results)

    print("\n" + "=" * 100)
    print(f"OVERALL: {total_found}/{total} ({overall_pct:.1f}%) returned results")
    print(f"AI Answers: {total_ai}/{total} ({ai_pct:.1f}%)")
    print(f"Document URLs: {total_with_urls}/{total_found} ({url_pct:.1f}%) queries with clickable links")
    print(f"Contaminated: {total_contaminated} | Errors: {total_error}")
    print(f"Avg Response Time: {avg_ms:.0f}ms")
    print("=" * 100)

    # Save results
    output_file = f"expanded_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path = f"C:\\Users\\ricky\\OneDrive - PS Prop Mgmt\\Documents\\GitHub\\manager-wizard\\scripts\\{output_file}"
    with open(output_path, "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "base_url": BASE_URL,
            "total_queries": total,
            "total_found": total_found,
            "total_ai_answers": total_ai,
            "total_not_found": total_not_found,
            "total_error": total_error,
            "total_contaminated": total_contaminated,
            "total_with_urls": total_with_urls,
            "success_rate": overall_pct,
            "ai_answer_rate": ai_pct,
            "url_rate": url_pct,
            "avg_response_ms": avg_ms,
            "community_stats": {k: dict(v) for k, v in community_stats.items()},
            "category_stats": {k: dict(v) for k, v in category_stats.items()},
            "results": all_results,
        }, f, indent=2, default=str)

    print(f"\nResults saved to: {output_file}")


if __name__ == "__main__":
    run_tests()
