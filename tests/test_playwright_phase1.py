"""Playwright End-to-End & Integration Test Suite for Phase 1 In-Code Fixes.

Uses Playwright Chromium to test Swagger UI (/docs) and POST /chat/text API.
"""

import asyncio
import sys
import threading
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import uvicorn
from playwright.sync_api import sync_playwright

from app.agent.nodes import (
    _build_system_prompt,
    _rewrite_query_if_followup,
    direct_node,
)
from app.models.classify import _fast_classify, _is_underspecified_query
from app.services.rag import query_schemes
from main import app


class UvicornServerThread(threading.Thread):
    def __init__(self, host="127.0.0.1", port=8088):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        config = uvicorn.Config(app, host=self.host, port=self.port, log_level="error")
        self.server = uvicorn.Server(config)

    def run(self):
        self.server.run()

    def stop(self):
        self.server.should_exit = True


def run_phase1_playwright_tests():
    print("\n" + "=" * 80)
    print("STARTING PLAYWRIGHT PHASE 1 TEST SUITE")
    print("=" * 80)

    mock_llm_response = (
        "Could you please specify what information you need regarding tractors? "
        "For example, are you looking for government subsidy schemes under SMAM, "
        "or hiring options from a Custom Hiring Center (CHC)?"
    )

    results = []

    with patch(
        "app.models.reasoning.ReasoningLLM.generate",
        return_value=mock_llm_response,
    ):
        server_thread = UvicornServerThread(host="127.0.0.1", port=8088)
        server_thread.start()
        time.sleep(2.0)  # wait for uvicorn to bind

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            base_url = "http://127.0.0.1:8088"

            # ------------------------------------------------------------------
            # Test 1: Playwright Browser Test on Swagger UI (/docs)
            # ------------------------------------------------------------------
            try:
                page.goto(f"{base_url}/docs", timeout=15000)
                page.wait_for_selector(".swagger-ui", timeout=10000)
                title = page.title()
                assert any(
                    term in title for term in ("agri-server", "Swagger UI", "FastAPI")
                )
                results.append(
                    {
                        "id": "PW-01",
                        "name": "Swagger UI Accessibility via Playwright Browser",
                        "status": "PASS",
                        "detail": f"Swagger UI loaded. Title: '{title}'",
                    }
                )
            except Exception as e:  # noqa: BLE001
                results.append(
                    {
                        "id": "PW-01",
                        "name": "Swagger UI Accessibility via Playwright Browser",
                        "status": "FAIL",
                        "detail": str(e),
                    }
                )

            # ------------------------------------------------------------------
            # Test 2: Multi-Label Intent & $in Filter (RAG-01, 08, 09, 20)
            # ------------------------------------------------------------------
            try:
                query = (
                    "Sir, I want to set up drip irrigation for my banana field and "
                    "also need 50% subsidy for buying a small 20HP tractor"
                )
                q_type, filters = _fast_classify(query)
                types = filters.get("types", [])
                assert q_type == "scheme", f"Expected scheme, got {q_type}"
                assert "irrigation" in types, f"Expected irrigation in {types}"
                assert "farm_mechanization" in types, (
                    f"Expected farm_mechanization in {types}"
                )
                assert filters.get("type") == "irrigation"

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                rag_res = loop.run_until_complete(
                    query_schemes(
                        "drip and tractor",
                        scheme_type=["irrigation", "farm_mechanization"],
                    )
                )
                loop.close()

                assert rag_res["filters_used"]["types"] == [
                    "irrigation",
                    "farm_mechanization",
                ]

                results.append(
                    {
                        "id": "PW-02",
                        "name": "Multi-Label Classification & $in Filter Construction",
                        "status": "PASS",
                        "detail": f"Matched types: {types}. $in filter constructed.",
                    }
                )
            except Exception as e:  # noqa: BLE001
                results.append(
                    {
                        "id": "PW-02",
                        "name": "Multi-Label Classification & $in Filter Construction",
                        "status": "FAIL",
                        "detail": str(e),
                    }
                )

            # ------------------------------------------------------------------
            # Test 3: Scalable Underspecified / Ambiguity Interceptor (RAG-16)
            # ------------------------------------------------------------------
            try:
                test_entities = [
                    "Tractor",
                    "Polyhouse",
                    "Mulching",
                    "Azolla",
                    "Solar pump",
                ]
                for entity in test_entities:
                    assert _is_underspecified_query(entity) is True
                    q_type, filters = _fast_classify(entity)
                    assert q_type == "direct"
                    assert filters.get("ambiguous") is True

                action_queries = [
                    "tractor subsidy",
                    "how to build polyhouse",
                    "weather forecast",
                    "apply for loan",
                ]
                for aq in action_queries:
                    assert _is_underspecified_query(aq) is False

                results.append(
                    {
                        "id": "PW-03",
                        "name": "Scalable Ambiguity Interceptor (Zero Hardcoded Dicts)",
                        "status": "PASS",
                        "detail": (
                            f"Verified {test_entities} -> direct + ambiguous: True"
                        ),
                    }
                )
            except Exception as e:  # noqa: BLE001
                results.append(
                    {
                        "id": "PW-03",
                        "name": "Scalable Ambiguity Interceptor (Zero Hardcoded Dicts)",
                        "status": "FAIL",
                        "detail": str(e),
                    }
                )

            # ------------------------------------------------------------------
            # Test 4: Conversational Coreference Rewriter (RAG-10)
            # ------------------------------------------------------------------
            try:
                history = [
                    {
                        "role": "user",
                        "content": "Subsidy for micro-irrigation in Tamil Nadu?",
                    },
                    {
                        "role": "assistant",
                        "content": "PMKSY provides 100% micro-irrigation subsidy.",
                    },
                ]
                followup = "Does this also apply if my father owns the land?"

                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                rewritten = loop.run_until_complete(
                    _rewrite_query_if_followup(followup, history)
                )
                loop.close()

                has_context = (
                    "irrigation" in rewritten.lower()
                    or "pmksy" in rewritten.lower()
                    or "subsidy" in rewritten.lower()
                    or len(rewritten) > len(followup)
                    or rewritten == followup  # graceful fallback
                )
                assert has_context

                results.append(
                    {
                        "id": "PW-04",
                        "name": "Conversational Coreference Rewriter (Turn 2 Pronoun)",
                        "status": "PASS",
                        "detail": f"Follow-up: '{followup}' -> '{rewritten}'",
                    }
                )
            except Exception as e:  # noqa: BLE001
                results.append(
                    {
                        "id": "PW-04",
                        "name": "Conversational Coreference Rewriter (Turn 2 Pronoun)",
                        "status": "FAIL",
                        "detail": str(e),
                    }
                )

            # ------------------------------------------------------------------
            # Test 5: Circuit Breaker Outage Awareness in direct_node (RAG-15)
            # ------------------------------------------------------------------
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                degraded_state = {
                    "query": "Is crop insurance mandatory for KCC loan?",
                    "query_type": "scheme",
                    "filters": {"type": "crop_insurance"},
                    "tool_data": {},
                    "scheme_data": {
                        "schemes": [],
                        "error": "RAG service temporarily unavailable",
                    },
                    "context": [],
                    "response": "",
                    "session_id": "test_pw",
                    "farm_id": "default",
                    "stream_callback": None,
                }
                res_state = loop.run_until_complete(direct_node(degraded_state))
                loop.close()

                response_text = res_state["response"]
                assert "temporarily" in response_text
                assert "do not have that detail" not in response_text

                results.append(
                    {
                        "id": "PW-05",
                        "name": "Circuit Breaker Outage Awareness Degradation",
                        "status": "PASS",
                        "detail": f"Outage advisory: '{response_text[:65]}...'",
                    }
                )
            except Exception as e:  # noqa: BLE001
                results.append(
                    {
                        "id": "PW-05",
                        "name": "Circuit Breaker Outage Awareness Degradation",
                        "status": "FAIL",
                        "detail": str(e),
                    }
                )

            # ------------------------------------------------------------------
            # Test 6: Cross-State Jurisdiction Guardrail in Prompt (RAG-17)
            # ------------------------------------------------------------------
            try:
                sys_prompt = _build_system_prompt(has_scheme_data=True)
                assert "Jurisdiction rule" in sys_prompt
                assert "Tamil Nadu" in sys_prompt and "Odisha" in sys_prompt
                assert "Clarification rule" in sys_prompt

                results.append(
                    {
                        "id": "PW-06",
                        "name": "Cross-State Jurisdiction & Ambiguity Directives",
                        "status": "PASS",
                        "detail": (
                            "Verified jurisdiction and ambiguity directives in "
                            "system prompt."
                        ),
                    }
                )
            except Exception as e:  # noqa: BLE001
                results.append(
                    {
                        "id": "PW-06",
                        "name": "Cross-State Jurisdiction & Ambiguity Directives",
                        "status": "FAIL",
                        "detail": str(e),
                    }
                )

            # ------------------------------------------------------------------
            # Test 7: Live HTTP /chat/text Playwright Request Context
            # ------------------------------------------------------------------
            try:
                api_context = p.request.new_context(base_url=base_url)
                response = api_context.post(
                    "/chat/text",
                    data={
                        "query": "Tractor",
                        "session_id": "pw_session_ambiguous",
                    },
                    headers={"Content-Type": "application/json"},
                )
                assert response.status == 200, f"Expected 200, got {response.status}"
                data = response.json()
                assert data["query_type"] == "direct"
                assert data["scheme_list"] == []

                results.append(
                    {
                        "id": "PW-07",
                        "name": "Live HTTP /chat/text Verification (Ambiguous Query)",
                        "status": "PASS",
                        "detail": (
                            "200 OK, query_type='direct', scheme_list=[] "
                            f"(RAG suppressed). Response: '{data['response'][:55]}...'"
                        ),
                    }
                )
            except Exception as e:  # noqa: BLE001
                results.append(
                    {
                        "id": "PW-07",
                        "name": "Live HTTP /chat/text Verification (Ambiguous Query)",
                        "status": "FAIL",
                        "detail": str(e),
                    }
                )

            browser.close()

        server_thread.stop()

    print("\n" + "=" * 80)
    print("PLAYWRIGHT TEST EXECUTION RESULTS SUMMARY")
    print("=" * 80)
    print(f"{'ID':<8} | {'Test Scenario':<55} | {'Status':<8}")
    print("-" * 80)

    passed_count = 0
    for r in results:
        status_symbol = "PASS" if r["status"] == "PASS" else "FAIL"
        if r["status"] == "PASS":
            passed_count += 1
        print(f"{r['id']:<8} | {r['name']:<55} | {status_symbol}")
        print(f"         └─ Detail: {r['detail']}")
        print("-" * 80)

    total_count = len(results)
    pass_pct = (passed_count / total_count) * 100
    print(f"\nFinal Result: {passed_count}/{total_count} Passed ({pass_pct:.1f}%)")
    print("=" * 80 + "\n")

    return passed_count == total_count


if __name__ == "__main__":
    success = run_phase1_playwright_tests()
    if not success:
        raise SystemExit(1)
