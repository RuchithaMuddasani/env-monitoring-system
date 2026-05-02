import requests
from config import Config


# 🌤 WEATHER FUNCTION (ADVANCED)
def get_weather(city="hyderabad"):
    try:
        if not Config.OPENWEATHER_API:
            return {"error": "Missing OpenWeather API key"}

        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={Config.OPENWEATHER_API}"
        response = requests.get(url, timeout=5)
        data = response.json()

        if response.status_code != 200:
            return {"error": data.get("message", "Weather API failed")}

        return {
            "city": data.get("name"),

            # 🌡 Core Weather
            "temperature": round(data["main"]["temp"] - 273.15, 2),
            "humidity": data["main"]["humidity"],
            "pressure": data["main"]["pressure"],
            "condition": data["weather"][0]["description"],

            # 🌬 Extra Sensors
            "wind_speed": data.get("wind", {}).get("speed"),
            "visibility": data.get("visibility"),

            # 🗺 VERY IMPORTANT (FOR MAP)
            "lat": data["coord"]["lat"],
            "lon": data["coord"]["lon"]
        }

    except Exception as e:
        return {"error": str(e)}


# 🌫 AQI FUNCTION (ADVANCED GLOBAL SUPPORT 🔥)
def get_aqi(city="hyderabad"):
    try:
        if not Config.AQI_API:
            return {"status": "unavailable"}

        # ✅ Normalize city name
        city = city.lower().replace(" ", "%20")

        url = f"https://api.waqi.info/feed/{city}/?token={Config.AQI_API}"
        response = requests.get(url, timeout=5)
        data = response.json()

        if data.get("status") != "ok":
            return {
                "aqi": None,
                "status": "error",
                "note": data.get("data", "No AQI data available")
            }

        aqi_data = data.get("data", {})
        iaqi = aqi_data.get("iaqi", {})

        return {
            "aqi": aqi_data.get("aqi"),

            # 🌫 Pollutants
            "pm25": iaqi.get("pm25", {}).get("v"),
            "pm10": iaqi.get("pm10", {}).get("v"),
            "co": iaqi.get("co", {}).get("v"),
            "no2": iaqi.get("no2", {}).get("v"),
            "o3": iaqi.get("o3", {}).get("v"),

            # 🌡 Additional
            "temperature": iaqi.get("t", {}).get("v"),
            "humidity": iaqi.get("h", {}).get("v"),
            "wind": iaqi.get("w", {}).get("v"),

            "status": "available"
        }

    except Exception as e:
        return {
            "aqi": None,
            "status": "error",
            "note": str(e)
        }