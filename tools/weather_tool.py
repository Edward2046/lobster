# weather_tool.py — 天气查询工具
# 使用 Open-Meteo API，完全免费，无需 API key。

import requests
from smolagents import tool


@tool
def get_weather(city: str) -> str:
    """Get current weather for a city using the Open-Meteo API (no API key needed).

    Args:
        city: City name, e.g. 'Beijing', 'Tokyo', 'London'.
    """
    # ── 第一步：地理编码（城市名 → 经纬度）────────────────────────────────────
    # Open-Meteo 的天气 API 只接受经纬度，不接受城市名，
    # 所以先用它配套的 geocoding API 做一次转换。
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    try:
        geo_resp = requests.get(
            geo_url,
            params={"name": city, "count": 1},  # count=1 只取最匹配的一个结果
            timeout=10,
        )
        geo_resp.raise_for_status()  # 非 2xx 状态码抛出异常
        results = geo_resp.json().get("results")
        if not results:
            return f"City '{city}' not found."
        loc = results[0]
        lat, lon, name = loc["latitude"], loc["longitude"], loc["name"]
    except Exception as e:
        return f"Geocoding failed: {e}"

    # ── 第二步：获取天气数据 ───────────────────────────────────────────────────
    # current_weather=True 返回当前时刻的简要天气（温度、风速、天气代码）
    # 天气代码（weathercode）含义参见 WMO 标准：
    #   0=晴，1-3=多云，45/48=雾，51-67=雨，71-77=雪，80-82=阵雨，95+=雷暴
    weather_url = "https://api.open-meteo.com/v1/forecast"
    try:
        w_resp = requests.get(
            weather_url,
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": True,
            },
            timeout=10,
        )
        w_resp.raise_for_status()
        cw = w_resp.json().get("current_weather", {})
        return (
            f"Weather in {name}: "
            f"temperature {cw.get('temperature')}°C, "
            f"wind speed {cw.get('windspeed')} km/h, "
            f"weather code {cw.get('weathercode')}."
        )
    except Exception as e:
        return f"Weather fetch failed: {e}"
