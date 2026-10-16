"""Live Open-Meteo adapters with a real Redis cache and bounded stale fallback."""
import json
import os
from datetime import datetime, timezone
import httpx
import redis
from fastapi import Depends, FastAPI, HTTPException, Query
from common import setup, user

app = FastAPI(title="Run Conditions Service", version="1.0.0")
setup(app)
cache = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

@app.get("/api/v1/conditions")
def conditions(latitude: float = Query(ge=-90, le=90), longitude: float = Query(ge=-180, le=180),
               at: datetime = Query(), claims=Depends(user)):
    if at.tzinfo is None:
        raise HTTPException(422, "Forecast time needs a timezone")
    at = at.astimezone(timezone.utc)
    if at < datetime.now(timezone.utc):
        raise HTTPException(422, "Forecast must be for a future time")
    key=f"forecast:{latitude:.2f}:{longitude:.2f}:{at:%Y-%m-%dT%H}"
    cached=cache.get(key)
    if cached:
        return {**json.loads(cached), "cacheHit": True, "cacheKey": key}
    try:
        params={"latitude":latitude,"longitude":longitude,"timezone":"UTC","forecast_days":7}
        with httpx.Client(timeout=8) as client:
            weather=client.get("https://api.open-meteo.com/v1/forecast",params={**params,"hourly":"temperature_2m,relative_humidity_2m,precipitation_probability"})
            weather.raise_for_status()
            air=client.get("https://air-quality-api.open-meteo.com/v1/air-quality",params={**params,"hourly":"pm2_5"})
            air.raise_for_status()
        w,a=weather.json()["hourly"],air.json()["hourly"]
        stamp=at.strftime("%Y-%m-%dT%H:00")
        i,j=w["time"].index(stamp),a["time"].index(stamp)
        temp,humidity,rain,pm=w["temperature_2m"][i],w["relative_humidity_2m"][i],w["precipitation_probability"][i],a["pm2_5"][j]
        if any(value is None for value in (temp,humidity,rain,pm)):
            raise ValueError("Provider has no readings for this slot")
        level="poor" if rain>=70 or pm>=50 or temp>=36 else "fair" if rain>=40 or pm>=25 or temp>=32 or humidity>=85 else "great"
        result={"temperature":temp,"humidity":humidity,"rainChance":rain,"pm25":pm,"level":level,
                "label":{"great":"Great to run","fair":"Use caution","poor":"Consider another time"}[level],
                "updatedAt":datetime.now(timezone.utc).isoformat(),"stale":False,"provider":"Open-Meteo / CAMS"}
        cache.setex(key,900,json.dumps(result))
        cache.setex(f"stale:{key}",21600,json.dumps(result))
        return {**result,"cacheHit":False,"cacheKey":key}
    except (httpx.HTTPError,ValueError,KeyError,IndexError):
        stale=cache.get(f"stale:{key}")
        if stale:
            return {**json.loads(stale),"stale":True,"cacheHit":True,"cacheKey":key}
        raise HTTPException(503,"Weather provider unavailable or forecast time outside available range; no cached forecast exists")

@app.get("/ready")
def ready():
    return {"redis":cache.ping()}
