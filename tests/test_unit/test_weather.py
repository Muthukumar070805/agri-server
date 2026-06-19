import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock


class TestWeatherService:
    @pytest.mark.asyncio
    async def test_build_url_uses_location(self, monkeypatch):
        monkeypatch.setenv("WEATHER_LOCATION", "Mumbai")
        from app.core.config import get_settings

        get_settings.cache_clear()
        from app.services.weather import _build_url

        url = await _build_url()
        assert "Mumbai" in url
        assert "wttr.in" in url
        get_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_fetch_weather_cached(self):
        from app.services.weather import fetch_weather

        with patch("app.services.weather.redis_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value='{"temp_C": "25"}')
            result = await fetch_weather("test-farm")
            assert result == '{"temp_C": "25"}'
            mock_cache.get.assert_called_once_with("weather:test-farm")

    @pytest.mark.asyncio
    async def test_fetch_weather_success(self):
        from app.services.weather import fetch_weather

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "current_condition": [
                {
                    "temp_C": "32",
                    "humidity": "60",
                    "pressure": "1013",
                    "visibility": "10",
                    "weatherCode": "113",
                    "FeelsLikeC": "35",
                    "windspeedKmph": "12",
                    "winddir16Point": "SE",
                    "cloudcover": "25",
                    "uvIndex": "7",
                    "weatherDesc": [{"value": "Sunny"}],
                    "precipMM": "0.0",
                }
            ]
        }
        with patch("app.services.weather.redis_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=True)
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )
                result = await fetch_weather("default")
                data = json.loads(result)
                assert data["temp_C"] == "32"
                assert data["condition"] == "Sunny"
                assert data["humidity"] == "60"

    @pytest.mark.asyncio
    async def test_fetch_weather_http_error(self):
        from app.services.weather import fetch_weather

        with patch("app.services.weather.redis_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    side_effect=Exception("HTTP 500")
                )
                result = await fetch_weather("default")
                data = json.loads(result)
                assert "error" in data

    @pytest.mark.asyncio
    async def test_fetch_weather_cache_on_success(self):
        from app.services.weather import fetch_weather

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "current_condition": [
                {
                    "temp_C": "28",
                    "humidity": "55",
                    "pressure": "1010",
                    "visibility": "8",
                    "weatherCode": "116",
                    "FeelsLikeC": "30",
                    "windspeedKmph": "10",
                    "winddir16Point": "W",
                    "cloudcover": "50",
                    "uvIndex": "5",
                    "weatherDesc": [{"value": "Cloudy"}],
                    "precipMM": "0.5",
                }
            ]
        }
        with patch("app.services.weather.redis_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=True)
            with patch("httpx.AsyncClient") as mock_client:
                mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                    return_value=mock_response
                )
                await fetch_weather("default")
                mock_cache.set.assert_called_once()
