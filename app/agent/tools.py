from langchain_core.tools import tool
from app.services.weather import get_weather as fetch_weather
from app.services.rag import query_schemes
from app.services.redis_cache import redis_cache
import json
import asyncio


def _run_async(coro):
    """Run async coroutine in new event loop (sync context)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run(coro)
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


@tool(
    name_or_callable="get_weather",
    description="Get current weather for the farm location (temperature, humidity, pressure, visibility and conditions)"
)
def get_weather(farm_id: str = "default") -> str:
    """Get current weather data for the farm."""
    return fetch_weather(farm_id)


@tool
def get_scheme_info(query: str) -> str:
    """Search government schemes, subsidies, loans, insurance info."""
    return query_schemes(query)


@tool
def get_soil_data(farm_id: str = "default") -> str:
    """Get IoT soil moisture data for a farm."""
    async def _get():
        return await redis_cache.get(f"soil:{farm_id}")

    data = _run_async(_get())
    return data or "No soil data available"


@tool
def get_satellite_data(farm_id: str = "default") -> str:
    """Get satellite imagery data for a farm."""
    async def _get():
        return await redis_cache.get(f"satellite:{farm_id}")

    data = _run_async(_get())
    return data or "No satellite data available"


@tool(name_or_callable="get_farm_data")
def get_farm_data(farm_id: str = "default") -> str:
    """Get all farm data: weather, soil/IoT, satellite."""
    async def fetch_all():
        weather = await redis_cache.get(f"weather:{farm_id}")
        soil = await redis_cache.get(f"soil:{farm_id}")
        satellite = await redis_cache.get(f"satellite:{farm_id}")
        return weather, soil, satellite

    weather, soil, satellite = _run_async(fetch_all())

    return json.dumps({
        "weather": weather or {},
        "iot": json.loads(soil) if soil else {},
        "gee": json.loads(satellite) if satellite else {}
    })