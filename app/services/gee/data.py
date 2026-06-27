import json
from datetime import datetime, timedelta, timezone
from typing import Optional

try:
    import ee
    _ee_available = True
except ImportError:
    _ee_available = False

from app.core.config import get_settings
from app.core.logger import get_logger
from app.services.gee.utils import get_or_cache

logger = get_logger(__name__)

CACHE_TTL = 1800

_initialized = False

_EE_UNAVAILABLE_MSG = json.dumps({"error": "Google Earth Engine not available"})


def _ensure_ee():
    global _initialized
    if not _ee_available:
        raise RuntimeError("ee module not available")
    if _initialized:
        return
    settings = get_settings()
    ee.Initialize(project=settings.gee_project)
    _initialized = True


def _point(lat: float, lon: float):
    return ee.Geometry.Point([lon, lat])


def _date_range(days_back: int = 7) -> tuple[str, str]:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def _reduce_median(collection, band: str) -> Optional[float]:
    count = collection.size().getInfo()
    if count == 0:
        return None
    return collection.select(band).median().reduceRegion(
        reducer=ee.Reducer.mean(), geometry=collection.geometry(), scale=1000
    ).get(band).getInfo()


# ---- Sync fetchers (run in executor) ----


def _fetch_wind(lat: float, lon: float) -> str:
    if not _ee_available:
        return _EE_UNAVAILABLE_MSG
    _ensure_ee()
    start, end = _date_range(1)
    col = ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY").filterDate(start, end).filterBounds(
        _point(lat, lon)
    )
    speed = _reduce_median(col, "wind_speed_10m")
    direction = _reduce_median(col, "wind_direction_10m")
    return json.dumps({"speed_m_s": round(speed, 2) if speed else None, "direction_deg": round(direction, 1) if direction else None})


def _fetch_rain(lat: float, lon: float) -> str:
    if not _ee_available:
        return _EE_UNAVAILABLE_MSG
    _ensure_ee()
    start, end = _date_range(1)
    col = ee.ImageCollection("NASA/GPM_L3/IMERG_V06").filterDate(start, end).filterBounds(
        _point(lat, lon)
    )
    precip = _reduce_median(col, "precipitationCal")
    return json.dumps({"precipitation_mm_hr": round(precip, 3) if precip else None})


def _fetch_ndvi(lat: float, lon: float) -> str:
    if not _ee_available:
        return _EE_UNAVAILABLE_MSG
    _ensure_ee()
    start, end = _date_range(30)
    col = ee.ImageCollection("COPERNICUS/S2_SR").filterDate(start, end).filterBounds(
        _point(lat, lon)
    ).filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 30))
    count = col.size().getInfo()
    if count == 0:
        return json.dumps({"value": None, "source": "Sentinel-2", "note": "no clear scenes in window"})
    composite = col.median()
    ndvi = composite.normalizedDifference(["B8", "B4"]).reduceRegion(
        reducer=ee.Reducer.mean(), geometry=_point(lat, lon), scale=10
    ).get("nd").getInfo()
    return json.dumps({"value": round(ndvi, 4) if ndvi else None, "source": "Sentinel-2"})


def _fetch_sar(lat: float, lon: float) -> str:
    if not _ee_available:
        return _EE_UNAVAILABLE_MSG
    _ensure_ee()
    start, end = _date_range(30)
    col = ee.ImageCollection("COPERNICUS/S1_GRD").filterDate(start, end).filterBounds(
        _point(lat, lon)
    ).filter(ee.Filter.eq("instrumentMode", "IW"))
    count = col.size().getInfo()
    if count == 0:
        return json.dumps({"vv_db": None, "vh_db": None, "note": "no scenes in window"})
    median = col.median().reduceRegion(
        reducer=ee.Reducer.mean(), geometry=_point(lat, lon), scale=10
    )
    vv = median.get("VV").getInfo()
    vh = median.get("VH").getInfo()
    return json.dumps({"vv_db": round(vv, 2) if vv else None, "vh_db": round(vh, 2) if vh else None})


def _fetch_temp(lat: float, lon: float) -> str:
    if not _ee_available:
        return _EE_UNAVAILABLE_MSG
    _ensure_ee()
    start, end = _date_range(1)
    col = ee.ImageCollection("ECMWF/ERA5_LAND/HOURLY").filterDate(start, end).filterBounds(
        _point(lat, lon)
    )
    temp = _reduce_median(col, "temperature_2m")
    if temp is not None:
        temp_c = round(temp - 273.15, 1)
    else:
        temp_c = None
    return json.dumps({"temp_2m_c": temp_c})


# ---- Public async API ----


async def fetch_satellite(farm_id: str = "default", lat: Optional[float] = None, lon: Optional[float] = None) -> str:
    settings = get_settings()
    lat = lat or settings.gee_latitude
    lon = lon or settings.gee_longitude

    from asyncio import gather

    wind_json, rain_json, ndvi_json, sar_json, temp_json = await gather(
        get_or_cache(f"gee:{farm_id}:wind", lambda: _fetch_wind(lat, lon), CACHE_TTL),
        get_or_cache(f"gee:{farm_id}:rain", lambda: _fetch_rain(lat, lon), CACHE_TTL),
        get_or_cache(f"gee:{farm_id}:ndvi", lambda: _fetch_ndvi(lat, lon), CACHE_TTL),
        get_or_cache(f"gee:{farm_id}:sar", lambda: _fetch_sar(lat, lon), CACHE_TTL),
        get_or_cache(f"gee:{farm_id}:temp", lambda: _fetch_temp(lat, lon), CACHE_TTL),
    )

    return json.dumps({
        "wind": json.loads(wind_json),
        "rain": json.loads(rain_json),
        "ndvi": json.loads(ndvi_json),
        "sar": json.loads(sar_json),
        "temperature": json.loads(temp_json),
    })
