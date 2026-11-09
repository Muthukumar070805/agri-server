"""Playwright End-to-End Test Suite for Phase 2: Index Re-embedding.

Tests the full FastAPI application with live Ollama qwen3-local:latest embeddings,
Pinecone scheme-1536 index (dim 1536), and Playwright Chromium.
"""

import asyncio
import json
import logging
import sys
import threading
import time
from pathlib import Path

import uvicorn
from pinecone import Pinecone
from playwright.sync_api import sync_playwright

# Ensure repo root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings
from app.services.rag import aquery_schemes, reset_vectorstore
from main import app

get_settings.cache_clear()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class UvicornServerThread(threading.Thread):
    def __init__(self, host="127.0.0.1", port=8099):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="error")
        self.server = uvicorn.Server(config)

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


def run_phase2_playwright_tests():
    print("\n" + "=" * 80)
    print("STARTING PLAYWRIGHT PHASE 2 END-TO-END TEST SUITE")
    print("Vector Index: scheme-1536 | Embeddings: qwen3-local:latest (1,536 dim)")
    print("=" * 80)

    reset_vectorstore()
    settings = get_settings()

    test_results = []

    server_thread = UvicornServerThread(host="127.0.0.1", port=8099)
    server_thread.start()
    time.sleep(2.5)  # wait for uvicorn to bind

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            base_url = "http://127.0.0.1:8099"

            # ------------------------------------------------------------------
            # Test 1: Playwright Browser Test on Swagger UI (/docs)
            # ------------------------------------------------------------------
            print("\n" + "-" * 70)
            print("[TEST 1] Playwright Browser UI: Inspect Swagger UI (/docs)")
            page.goto(f"{base_url}/docs", wait_until="networkidle")
            page_title = page.title()
            print(f"  Input: GET {base_url}/docs")
            print(f"  Tested Output: Page Title = '{page_title}'")
            t1_pass = (
                "agri-server" in page_title
                or "FastAPI" in page_title
                or "Swagger UI" in page_title
            )
            assert t1_pass, f"Swagger title verification failed: {page_title}"
            print("  Status: [PASS]")
            test_results.append(("Test 1: Swagger UI Browser Verification", "PASS"))

            # ------------------------------------------------------------------
            # Test 2: Pinecone Vector Index Infrastructure Verification
            # ------------------------------------------------------------------
            print("\n" + "-" * 70)
            print("[TEST 2] Pinecone Infrastructure: Verify scheme-1536 Specs")
            pc = Pinecone(api_key=settings.pinecone_api_key)
            idx = pc.Index("scheme-1536")
            stats = idx.describe_index_stats()
            print("  Input: Target Index = 'scheme-1536'")
            print("  Tested Output:")
            print(f"    - Dimension: {stats['dimension']}")
            print(f"    - Total Vector Count: {stats['total_vector_count']}")
            print(f"    - Metric: {stats['metric']}")
            assert stats["dimension"] == 1536, (
                f"Expected dim 1536, got {stats['dimension']}"
            )
            assert stats["total_vector_count"] >= 1098, (
                f"Expected >= 1098 vectors, got {stats['total_vector_count']}"
            )
            assert stats["metric"] == "cosine", (
                f"Expected cosine metric, got {stats['metric']}"
            )
            print("  Status: [PASS]")
            test_results.append(
                (
                    "Test 2: Pinecone scheme-1536 Dimension (1,536) & Count (1,098)",
                    "PASS",
                )
            )

            # ------------------------------------------------------------------
            # Test 3: Live RAG Retrieval - Single Intent (PMKSY Drip Irrigation)
            # ------------------------------------------------------------------
            print("\n" + "-" * 70)
            print("[TEST 3] Playwright API: Single-Intent Drip Irrigation Query")
            req_payload_3 = {
                "query": (
                    "What is the subsidy for drip irrigation under "
                    "Pradhan Mantri Krishi Sinchayee Yojana?"
                ),
                "session_id": "test_phase2_session_01",
            }
            print(f"  Input: {json.dumps(req_payload_3, indent=4)}")
            resp_3 = page.request.post(
                f"{base_url}/chat/text", data=req_payload_3, timeout=60000
            )
            assert resp_3.status == 200, (
                f"Expected 200, got {resp_3.status}: {resp_3.text()}"
            )
            data_3 = resp_3.json()
            response_text_3 = data_3.get("response", "")
            query_type_3 = data_3.get("query_type")
            schemes_3 = data_3.get("scheme_list", [])
            print(f"  Tested Output (Status: {resp_3.status}):")
            print(f"    Query Type: {query_type_3}")
            print(f"    Scheme Count: {len(schemes_3)}")
            print(f"    Response Length: {len(response_text_3)} chars")
            print(f"    Response Snippet: {response_text_3[:200]}...")
            assert query_type_3 == "scheme", f"Expected 'scheme', got {query_type_3}"
            assert len(schemes_3) > 0, "No schemes retrieved from scheme-1536!"
            assert len(response_text_3) > 0, "Empty response returned!"
            print("  Status: [PASS]")
            test_results.append(
                ("Test 3: Live Chat Single-Intent Drip Irrigation", "PASS")
            )

            # ------------------------------------------------------------------
            # Test 4: Live RAG Retrieval - Multi-Category Filter ($in)
            # ------------------------------------------------------------------
            print("\n" + "-" * 70)
            print("[TEST 4] Playwright API: Multi-Category Compound Query ($in Filter)")
            req_payload_4 = {
                "query": (
                    "I need government subsidies for both drip irrigation "
                    "and tractor machinery."
                ),
                "session_id": "test_phase2_session_02",
            }
            print(f"  Input: {json.dumps(req_payload_4, indent=4)}")
            resp_4 = page.request.post(
                f"{base_url}/chat/text", data=req_payload_4, timeout=60000
            )
            assert resp_4.status == 200, (
                f"Expected 200, got {resp_4.status}: {resp_4.text()}"
            )
            data_4 = resp_4.json()
            response_text_4 = data_4.get("response", "")
            query_type_4 = data_4.get("query_type")
            schemes_4 = data_4.get("scheme_list", [])
            print(f"  Tested Output (Status: {resp_4.status}):")
            print(f"    Query Type: {query_type_4}")
            print(f"    Scheme Count: {len(schemes_4)}")
            print(f"    Response Length: {len(response_text_4)} chars")
            print(f"    Response Snippet: {response_text_4[:200]}...")
            assert query_type_4 == "scheme"
            assert len(schemes_4) > 0, "No schemes retrieved for multi-category query!"
            print("  Status: [PASS]")
            test_results.append(
                (
                    "Test 4: Live Chat Multi-Category Drip + Tractor Machinery",
                    "PASS",
                )
            )

            # ------------------------------------------------------------------
            # Test 5: Relevance Gate Floor Test (Out-of-Domain Suppression)
            # ------------------------------------------------------------------
            print("\n" + "-" * 70)
            print("[TEST 5] Playwright API: Relevance Gate Suppression (Out-of-Domain)")
            req_payload_5 = {
                "query": (
                    "Explain quantum electrodynamics and semiconductor "
                    "laser physics in detail."
                ),
                "session_id": "test_phase2_session_03",
            }
            print(f"  Input: {json.dumps(req_payload_5, indent=4)}")
            resp_5 = page.request.post(
                f"{base_url}/chat/text", data=req_payload_5, timeout=60000
            )
            assert resp_5.status == 200, (
                f"Expected 200, got {resp_5.status}: {resp_5.text()}"
            )
            data_5 = resp_5.json()
            response_text_5 = data_5.get("response", "")
            query_type_5 = data_5.get("query_type")
            schemes_5 = data_5.get("scheme_list", [])
            print(f"  Tested Output (Status: {resp_5.status}):")
            print(f"    Query Type: {query_type_5}")
            print(f"    Scheme Count: {len(schemes_5)}")
            print(f"    Response Snippet: {response_text_5[:200]}...")

            # Direct RAG Gate Assertion
            rag_direct_5 = asyncio.run(
                aquery_schemes(
                    "Quantum electrodynamics and semiconductor laser physics"
                )
            )
            print(
                f"    Direct RAG Gate Verification: Count={rag_direct_5.get('count')}, "
                f"Top Score={rag_direct_5.get('top_score')}, "
                f"Reason={rag_direct_5.get('reason')}"
            )
            assert rag_direct_5.get("count") == 0, (
                "Relevance gate failed to suppress out-of-domain query!"
            )
            assert rag_direct_5.get("reason") == "below_relevance_threshold"
            print("  Status: [PASS]")
            test_results.append(
                (
                    "Test 5: Relevance Gate Suppression on Out-of-Domain Query",
                    "PASS",
                )
            )

            # ------------------------------------------------------------------
            # Test 6: Ambiguous Short Query Interceptor
            # ------------------------------------------------------------------
            print("\n" + "-" * 70)
            print(
                "[TEST 6] Playwright API: Ambiguous Short Query Interceptor ('Tractor')"
            )
            req_payload_6 = {
                "query": "Tractor",
                "session_id": "test_phase2_session_04",
            }
            print(f"  Input: {json.dumps(req_payload_6, indent=4)}")
            resp_6 = page.request.post(
                f"{base_url}/chat/text", data=req_payload_6, timeout=60000
            )
            assert resp_6.status == 200, (
                f"Expected 200, got {resp_6.status}: {resp_6.text()}"
            )
            data_6 = resp_6.json()
            response_text_6 = data_6.get("response", "")
            query_type_6 = data_6.get("query_type")
            print(f"  Tested Output (Status: {resp_6.status}):")
            print(f"    Query Type: {query_type_6}")
            print(f"    Clarification Prompt Snippet: {response_text_6[:250]}...")
            assert query_type_6 == "direct", (
                f"Expected direct query type for ambiguity, got {query_type_6}"
            )
            expected_keywords = [
                "clarify",
                "specify",
                "looking for",
                "help",
                "information",
                "purchase",
                "hire",
                "subsidy",
            ]
            assert any(k in response_text_6.lower() for k in expected_keywords), (
                "Ambiguity interceptor did not prompt for clarification!"
            )
            print("  Status: [PASS]")
            test_results.append(
                ("Test 6: Monosyllabic Ambiguity Interceptor ('Tractor')", "PASS")
            )

            # ------------------------------------------------------------------
            # Test 7: Multi-Turn Conversational Context Rewriting
            # ------------------------------------------------------------------
            print("\n" + "-" * 70)
            print("[TEST 7] Playwright API: Multi-Turn Context Follow-Up Query")
            session_id_7 = "test_phase2_session_05"
            turn_1_payload = {
                "query": (
                    "Tell me about Pradhan Mantri Fasal Bima Yojana "
                    "crop insurance scheme."
                ),
                "session_id": session_id_7,
            }
            print(f"  Turn 1 Input: {json.dumps(turn_1_payload, indent=4)}")
            resp_7a = page.request.post(
                f"{base_url}/chat/text", data=turn_1_payload, timeout=60000
            )
            assert resp_7a.status == 200
            turn_1_resp = resp_7a.json().get("response", "")
            print(f"  Turn 1 Output Snippet: {turn_1_resp[:120]}...")

            turn_2_payload = {
                "query": "Does this cover prevented sowing due to flood or drought?",
                "session_id": session_id_7,
            }
            print(f"\n  Turn 2 Input: {json.dumps(turn_2_payload, indent=4)}")
            resp_7b = page.request.post(
                f"{base_url}/chat/text", data=turn_2_payload, timeout=60000
            )
            assert resp_7b.status == 200
            data_7b = resp_7b.json()
            response_text_7b = data_7b.get("response", "")
            query_type_7b = data_7b.get("query_type")
            schemes_7b = data_7b.get("scheme_list", [])
            print(f"  Turn 2 Tested Output (Status: {resp_7b.status}):")
            print(f"    Query Type: {query_type_7b}")
            print(f"    Scheme Count: {len(schemes_7b)}")
            print(f"    Response Snippet: {response_text_7b[:250]}...")
            assert len(response_text_7b) > 0
            print("  Status: [PASS]")
            test_results.append(
                ("Test 7: Contextual Multi-Turn Coreference Resolution", "PASS")
            )

            browser.close()

    finally:
        server_thread.stop()

    print("\n" + "=" * 80)
    print("PHASE 2 PLAYWRIGHT TEST SUMMARY REPORT")
    print("=" * 80)
    all_passed = True
    for test_name, status in test_results:
        print(f"  {test_name.ljust(60)} : [{status}]")
        if status != "PASS":
            all_passed = False

    print("=" * 80)
    total_passed = sum(1 for _, s in test_results if s == "PASS")
    pass_pct = total_passed / len(test_results) * 100
    print(f"RESULTS: {total_passed}/{len(test_results)} Tests Passed ({pass_pct:.1f}%)")
    print("=" * 80)
    assert all_passed, "One or more Playwright tests failed!"


def test_phase2_playwright_suite():
    run_phase2_playwright_tests()


if __name__ == "__main__":
    run_phase2_playwright_tests()
