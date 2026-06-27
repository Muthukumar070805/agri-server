import pytest
import json
from unittest.mock import patch, AsyncMock, MagicMock

patch.dict("sys.modules", {"ee": MagicMock()}).start()


class TestGetOrCache:
    @pytest.mark.asyncio
    async def test_hit_returns_cached(self):
        from app.services.gee.utils import get_or_cache

        with patch("app.services.gee.utils.redis_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value='"cached_data"')
            result = await get_or_cache("gee:test:wind", lambda: "fresh")
            assert result == '"cached_data"'
            mock_cache.get.assert_called_once_with("gee:test:wind")

    @pytest.mark.asyncio
    async def test_miss_calls_fetcher_and_caches(self):
        from app.services.gee.utils import get_or_cache

        with patch("app.services.gee.utils.redis_cache") as mock_cache:
            mock_cache.get = AsyncMock(return_value=None)
            mock_cache.set = AsyncMock(return_value=True)
            result = await get_or_cache("gee:test:ndvi", lambda: '{"ndvi": 0.8}')
            assert json.loads(result)["ndvi"] == 0.8
            mock_cache.set.assert_called_once()


class TestGeeData:
    @pytest.mark.asyncio
    async def test_fetch_satellite_aggregates_all_products(self):
        from app.services.gee.data import fetch_satellite

        mock_payloads = {
            "gee:farm-x:wind": json.dumps({"speed_m_s": 3.2, "direction_deg": 180.0}),
            "gee:farm-x:rain": json.dumps({"precipitation_mm_hr": 0.5}),
            "gee:farm-x:ndvi": json.dumps({"value": 0.72, "source": "Sentinel-2"}),
            "gee:farm-x:sar": json.dumps({"vv_db": -12.5, "vh_db": -18.3}),
            "gee:farm-x:temp": json.dumps({"temp_2m_c": 32.1}),
        }

        with patch("app.services.gee.data.get_or_cache") as mock_cache:
            async def side_effect(key, fetcher, ttl=1800):
                return mock_payloads[key]

            mock_cache.side_effect = side_effect
            result = await fetch_satellite("farm-x", lat=13.0, lon=80.0)
            data = json.loads(result)
            assert data["wind"]["speed_m_s"] == 3.2
            assert data["rain"]["precipitation_mm_hr"] == 0.5
            assert data["ndvi"]["value"] == 0.72
            assert data["sar"]["vv_db"] == -12.5
            assert data["temperature"]["temp_2m_c"] == 32.1
            assert mock_cache.call_count == 5

    @pytest.mark.asyncio
    async def test_fetch_wind_returns_expected_structure(self):
        from app.services.gee.data import _fetch_wind

        with patch("app.services.gee.data.ee") as mock_ee:
            mock_col = MagicMock()
            mock_ee.ImageCollection.return_value.filterDate.return_value.filterBounds.return_value = mock_col
            mock_col.size.return_value.getInfo.return_value = 1
            mock_col.select.return_value.median.return_value.reduceRegion.return_value.get.return_value.getInfo.side_effect = [3.5, 180.0]

            result = _fetch_wind(13.0, 80.0)
            data = json.loads(result)
            assert data["speed_m_s"] == 3.5
            assert data["direction_deg"] == 180.0

    @pytest.mark.asyncio
    async def test_fetch_ndvi_no_scenes_returns_note(self):
        from app.services.gee.data import _fetch_ndvi

        with patch("app.services.gee.data.ee") as mock_ee:
            mock_col = MagicMock()
            mock_ee.ImageCollection.return_value.filterDate.return_value.filterBounds.return_value.filter.return_value = mock_col
            mock_col.size.return_value.getInfo.return_value = 0

            result = _fetch_ndvi(13.0, 80.0)
            data = json.loads(result)
            assert data["value"] is None
            assert "no clear scenes" in data["note"]

    @pytest.mark.asyncio
    async def test_fetch_sar_no_scenes_returns_note(self):
        from app.services.gee.data import _fetch_sar

        with patch("app.services.gee.data.ee") as mock_ee:
            mock_col = MagicMock()
            mock_ee.ImageCollection.return_value.filterDate.return_value.filterBounds.return_value.filter.return_value = mock_col
            mock_col.size.return_value.getInfo.return_value = 0

            result = _fetch_sar(13.0, 80.0)
            data = json.loads(result)
            assert data["vv_db"] is None
            assert "no scenes" in data["note"]

    @pytest.mark.asyncio
    async def test_fetch_temp_converts_kelvin_to_celsius(self):
        from app.services.gee.data import _fetch_temp

        with patch("app.services.gee.data.ee") as mock_ee:
            mock_col = MagicMock()
            mock_ee.ImageCollection.return_value.filterDate.return_value.filterBounds.return_value = mock_col
            mock_col.size.return_value.getInfo.return_value = 1
            mock_col.select.return_value.median.return_value.reduceRegion.return_value.get.return_value.getInfo.return_value = 305.0

            result = _fetch_temp(13.0, 80.0)
            data = json.loads(result)
            assert data["temp_2m_c"] == 31.9  # 305.0 - 273.15
