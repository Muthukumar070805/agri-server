from hypothesis import given, strategies as st, settings
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

MAX_EXAMPLES = 5
PROP_SETTINGS = settings(max_examples=MAX_EXAMPLES, deadline=None)


class TestHypothesisStringFuzz:
    @PROP_SETTINGS
    @given(
        query=st.text(
            min_size=0,
            max_size=5000,
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "S", "Zs"),
                blacklist_characters=("\x00",),
            ),
        ),
        session_id=st.text(max_size=100),
    )
    def test_chat_text_random_inputs(self, query, session_id):
        payload = {"query": query[:4096], "session_id": session_id}
        resp = client.post("/chat/text", json=payload)
        assert resp.status_code in (200, 400, 413, 422, 429, 500)

    @PROP_SETTINGS
    @given(
        query=st.text(
            min_size=1,
            max_size=100,
            alphabet=st.characters(
                whitelist_categories=("So",), blacklist_characters=("\x00",)
            ),
        )
    )
    def test_chat_text_unicode_symbols(self, query):
        payload = {"query": query}
        resp = client.post("/chat/text", json=payload)
        assert resp.status_code in (200, 400, 422, 429, 500)

    @PROP_SETTINGS
    @given(
        query=st.text(
            min_size=1,
            max_size=100,
            alphabet=st.characters(
                whitelist_categories=("Nd",), blacklist_characters=("\x00",)
            ),
        )
    )
    def test_chat_text_numeric_only(self, query):
        payload = {"query": query}
        resp = client.post("/chat/text", json=payload)
        assert resp.status_code in (200, 400, 422, 429, 500)


class TestHypothesisNumericBoundary:
    @PROP_SETTINGS
    @given(extra_chars=st.integers(min_value=0, max_value=100))
    def test_chat_text_query_boundary(self, extra_chars):
        length = 4096 + extra_chars
        query = "x" * length
        payload = {"query": query}
        resp = client.post("/chat/text", json=payload)
        if length <= 4096:
            assert resp.status_code in (200, 429, 500)
        else:
            assert resp.status_code in (422, 413, 500)


class TestHypothesisPayloadStructure:
    @PROP_SETTINGS
    @given(
        st.dictionaries(
            keys=st.text(max_size=10),
            values=st.one_of(
                st.none(),
                st.booleans(),
                st.integers(),
                st.floats(allow_nan=False, allow_infinity=False),
                st.text(max_size=100),
                st.lists(st.text(max_size=20), max_size=5),
            ),
            max_size=10,
        )
    )
    def test_chat_text_malformed_payloads(self, payload):
        resp = client.post("/chat/text", json=payload)
        assert resp.status_code in (200, 400, 413, 422, 429, 500)
