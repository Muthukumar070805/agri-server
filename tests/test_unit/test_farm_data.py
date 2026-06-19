import pytest
import json
from unittest.mock import patch, AsyncMock


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
            mock_cache.get = AsyncMock(return_value='{"ndvi": 0.8}')
            result = await fetch_satellite("farm-1")
            assert json.loads(result)["ndvi"] == 0.8

    @pytest.mark.asyncio
    async def test_fetch_satellite_fresh(self):
        from app.services.farm_data import fetch_satellite

        with patch("app.services.farm_data.redis_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=True)
            result = await fetch_satellite("farm-2")
            data = json.loads(result)
            assert data["crop_health"] == "good"
            assert data["ndvi"] == 0.72
            mock_cache.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_farm_data_aggregates(self):
        from app.agent.tools import get_farm_data

        with patch("app.agent.tools.fetch_weather") as mock_weather:
            mock_weather.return_value = '{"temp_C": "30"}'
            with patch("app.agent.tools.fetch_soil") as mock_soil:
                mock_soil.return_value = '{"moisture": 45}'
                with patch("app.agent.tools.fetch_satellite") as mock_sat:
                    mock_sat.return_value = '{"ndvi": 0.7}'
                    result = await get_farm_data("test-farm-id")
                    data = json.loads(result)
                    assert data["weather"]["temp_C"] == "30"
                    assert data["iot"]["moisture"] == 45
                    assert data["gee"]["ndvi"] == 0.7
