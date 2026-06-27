import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock

MOCK_GEE_RESPONSE = json.dumps({
    "wind": {"speed_m_s": 3.2, "direction_deg": 180.0},
    "rain": {"precipitation_mm_hr": 0.5},
    "ndvi": {"value": 0.72, "source": "Sentinel-2"},
    "sar": {"vv_db": -12.5, "vh_db": -18.3},
    "temperature": {"temp_2m_c": 32.1},
})


class TestFarmData:
    @pytest.mark.asyncio
    async def test_fetch_soil_cached(self):
        from app.services.farm_data import fetch_soil

        with patch("app.services.farm_data.redis_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value='{"moisture": 50}')
            result = await fetch_soil("test-farm")
            assert result == '{"moisture": 50}'
            mock_cache.get.assert_called_once_with("soil:test-farm")

    @pytest.mark.asyncio
    async def test_fetch_soil_fresh(self):
        from app.services.farm_data import fetch_soil

        with patch("app.services.farm_data.redis_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=True)
            result = await fetch_soil("new-farm")
            data = json.loads(result)
            assert "moisture" in data
            assert "pH" in data
            assert data["nitrogen"] == 28
            mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_satellite_cached(self):
        from app.services.farm_data import fetch_satellite

        with patch("app.services.farm_data.redis_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=MOCK_GEE_RESPONSE)
            result = await fetch_satellite("farm-1")
            data = json.loads(result)
            assert data["wind"]["speed_m_s"] == 3.2
            assert data["ndvi"]["source"] == "Sentinel-2"

    @pytest.mark.asyncio
    async def test_fetch_satellite_fresh_calls_gee(self):
        from app.services.farm_data import fetch_satellite

        _mock_gee = MagicMock()
        _mock_gee.fetch_satellite = AsyncMock(return_value=MOCK_GEE_RESPONSE)
        with patch.dict("sys.modules", {"app.services.gee": _mock_gee}):
            with patch("app.services.farm_data.redis_cache") as mock_cache:
                mock_cache.get = AsyncMock(return_value=None)
                mock_cache.set = AsyncMock(return_value=True)
                result = await fetch_satellite("farm-2")
                data = json.loads(result)
                assert data["wind"]["speed_m_s"] == 3.2
                assert data["temperature"]["temp_2m_c"] == 32.1
                _mock_gee.fetch_satellite.assert_awaited_once_with("farm-2")

    @pytest.mark.asyncio
    async def test_fetch_satellite_fallback_on_gee_failure(self):
        from app.services.farm_data import fetch_satellite

        _mock_gee = MagicMock()
        _mock_gee.fetch_satellite = AsyncMock(side_effect=Exception("EE down"))
        with patch.dict("sys.modules", {"app.services.gee": _mock_gee}):
            with patch("app.services.farm_data.redis_cache") as mock_cache:
                mock_cache.get = AsyncMock(return_value=None)
                mock_cache.set = AsyncMock(return_value=True)
                result = await fetch_satellite("farm-3")
                result = await fetch_satellite("farm-3")
                data = json.loads(result)
                assert data["ndvi"]["value"] is None
                assert data["wind"]["speed_m_s"] is None

    @pytest.mark.asyncio
    async def test_get_farm_data_aggregates(self):
        from app.agent.tools import get_farm_data

        with patch("app.agent.tools.fetch_weather") as mock_weather:
            mock_weather.return_value = '{"temp_C": "30"}'
            with patch("app.agent.tools.fetch_soil") as mock_soil:
                mock_soil.return_value = '{"moisture": 45}'
                with patch("app.agent.tools.fetch_satellite") as mock_sat:
                    mock_sat.return_value = MOCK_GEE_RESPONSE
                    result = await get_farm_data("test-farm-id")
                    data = json.loads(result)
                    assert data["weather"]["temp_C"] == "30"
                    assert data["iot"]["moisture"] == 45
                    assert data["gee"]["wind"]["speed_m_s"] == 3.2
