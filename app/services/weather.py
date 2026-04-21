from app.core.logger import get_logger
from app.services.redis_cache import redis_cache

logger = get_logger(__name__)

WEATHER_CODES = {
    "113": "Clear/Sunny",
    "116": "Partly Cloudy",
    "119": "Cloudy",
    "122": "Overcast",
    "176": "Light Rain",
    "179": "Light Sleet",
    "182": "Light Sleet",
    "185": "Patchy Sleet",
    "200": "Thunderstorm",
    "227": "Snow",
    "230": "Heavy Snow",
    "248": "Fog",
    "260": "Freezing Fog",
}


def get_weather() -> str:
    import asyncio

    try:
        data = asyncio.run(redis_cache.get(f"weather:{farm_id}"))

        if not data:
            return "Weather data not available"

        temp = data.get("temp_C", "N/A")
        humidity = data.get("humidity", "N/A")
        pressure = data.get("pressure", "N/A")
        visibility = data.get("visibility", "N/A")
        weather_code = data.get("weatherCode", "0")
        condition = WEATHER_CODES.get(str(weather_code), "Unknown")

        return (
            f"Current Weather:\n"
            f"- Temperature: {temp}°C\n"
            f"- Condition: {condition}\n"
            f"- Humidity: {humidity}%\n"
            f"- Pressure: {pressure} mb\n"
            f"- Visibility: {visibility} km"
        )
    except Exception as e:
        logger.error(f"Weather read error: {e}")
        return "Weather data not available"
