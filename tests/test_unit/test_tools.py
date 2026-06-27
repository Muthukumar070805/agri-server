import pytest
import json
from unittest.mock import patch


@pytest.mark.asyncio
async def test_get_farm_data_handles_partial_failure():
    from app.agent.tools import get_farm_data

    async def fail_weather(_):
        return None

    async def ok_soil(_):
        return '{"moisture": 45}'

    async def fail_sat(_):
        return "bad json"

    with patch("app.agent.tools.fetch_weather", fail_weather), \
         patch("app.agent.tools.fetch_soil", ok_soil), \
         patch("app.agent.tools.fetch_satellite", fail_sat):
        result = await get_farm_data("test")

    data = json.loads(result)
    assert "error" in data["weather"]
    assert data["iot"]["moisture"] == 45
    assert "error" in data["gee"]
