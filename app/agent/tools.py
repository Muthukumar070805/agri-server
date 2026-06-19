from app.services.weather import fetch_weather
from app.services.farm_data import fetch_soil, fetch_satellite
import json


async def get_farm_data(farm_id: str = "default") -> str:
    """Get all farm data: weather, soil/IoT, satellite."""
    weather = await fetch_weather(farm_id)
    soil = await fetch_soil(farm_id)
    satellite = await fetch_satellite(farm_id)

    return json.dumps(
        {
            "weather": json.loads(weather) if weather else {},
            "iot": json.loads(soil) if soil else {},
            "gee": json.loads(satellite) if satellite else {},
        }
    )
