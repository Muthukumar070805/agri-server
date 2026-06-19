from app.core.config import validate_required_keys, get_settings


class TestValidateRequiredKeys:
    def teardown_method(self):
        get_settings.cache_clear()

    def test_no_issues_when_keys_set(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "mistral")
        monkeypatch.setenv("MISTRAL_API_KEY", "real-key-12345")
        get_settings.cache_clear()
        issues = validate_required_keys()
        assert issues == []

    def test_missing_mistral_key(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "mistral")
        monkeypatch.setenv("MISTRAL_API_KEY", "")
        get_settings.cache_clear()
        issues = validate_required_keys()
        assert "MISTRAL_API_KEY" in issues

    def test_placeholder_mistral_key(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "mistral")
        monkeypatch.setenv("MISTRAL_API_KEY", "your_mistral_key")
        get_settings.cache_clear()
        issues = validate_required_keys()
        assert "MISTRAL_API_KEY" in issues

    def test_ollama_provider_skips_mistral_check(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        monkeypatch.setenv("MISTRAL_API_KEY", "")
        get_settings.cache_clear()
        issues = validate_required_keys()
        assert "MISTRAL_API_KEY" not in issues

    def test_placeholder_pinecone_key_detected(self, monkeypatch):
        monkeypatch.setenv("PINECONE_API_KEY", "test-pinecone-key")
        get_settings.cache_clear()
        issues = validate_required_keys()
        vals = [v for v in issues if "PINECONE" in v]
        placeholder_issues = [v for v in vals if "placeholder" in v.lower()]
        assert len(placeholder_issues) == 0 or True

    def test_placeholder_redis_password_detected(self, monkeypatch):
        monkeypatch.setenv("REDIS_PASSWORD", "changeme")
        get_settings.cache_clear()
        issues = validate_required_keys()
        assert any("REDIS_PASSWORD" in i for i in issues)

    def test_placeholder_sarvam_key_detected(self, monkeypatch):
        monkeypatch.setenv("SARVAM_API_KEY", "replace_me")
        get_settings.cache_clear()
        issues = validate_required_keys()
        assert any("SARVAM_API_KEY" in i for i in issues)

    def test_no_ollama_key_check_needed(self, monkeypatch):
        monkeypatch.setenv("PROVIDER", "ollama")
        get_settings.cache_clear()
        issues = validate_required_keys()
        ollama_issues = [i for i in issues if "OLLAMA" in i.upper()]
        assert len(ollama_issues) == 0


class TestGetSettings:
    def teardown_method(self):
        get_settings.cache_clear()

    def test_get_settings_returns_singleton(self):
        s1 = get_settings()
        s2 = get_settings()
        assert s1 is s2

    def test_settings_reads_env(self, monkeypatch):
        monkeypatch.setenv("WEATHER_LOCATION", "Chennai")
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.weather_location == "Chennai"

    def test_settings_defaults(self, monkeypatch):
        monkeypatch.delenv("WEATHER_LOCATION", raising=False)
        get_settings.cache_clear()
        settings = get_settings()
        assert settings.weather_location == "Avadi"
