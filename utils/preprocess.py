def process_environmental_data(weather, aqi):
    processed = {}

    # Weather
    if "error" not in weather:
        processed["temperature"] = weather.get("temperature")
        processed["humidity"] = weather.get("humidity")
        processed["condition"] = weather.get("condition")

    # AQI
    aqi_value = aqi.get("aqi")
    processed["aqi"] = aqi_value

    # AQI Category
    if aqi_value is None:
        processed["aqi_category"] = "Unavailable"
    elif aqi_value <= 50:
        processed["aqi_category"] = "Good"
    elif aqi_value <= 100:
        processed["aqi_category"] = "Moderate"
    elif aqi_value <= 150:
        processed["aqi_category"] = "Unhealthy (Sensitive)"
    elif aqi_value <= 200:
        processed["aqi_category"] = "Unhealthy"
    else:
        processed["aqi_category"] = "Hazardous"

    return processed