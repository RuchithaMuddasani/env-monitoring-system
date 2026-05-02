import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    OPENWEATHER_API = os.getenv("OPENWEATHER_API")
    AQI_API = os.getenv("AQI_API")