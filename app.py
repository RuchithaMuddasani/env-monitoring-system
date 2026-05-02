from flask import Flask, jsonify, request, render_template
from utils.data_fetch import get_weather, get_aqi
from utils.preprocess import process_environmental_data
from datetime import datetime
from pymongo import MongoClient
import boto3
from datetime import timedelta
cloudwatch = boto3.client("cloudwatch", region_name="ap-southeast-2")
ec2 = boto3.client("ec2", region_name="ap-southeast-2")


# ✅ MongoDB
client = MongoClient("mongodb://localhost:27017/")
db = client["env_monitoring"]
collection = db["data"]

app = Flask(__name__)


# ✅ Save Data (safe)
def save_data(record):
    try:
        collection.insert_one(record)
    except Exception as e:
        print("⚠️ DB Error:", e)


# ✅ Get History (case-insensitive + safe)
def get_history(city):
    try:
        data = collection.find(
            {"city": {"$regex": f"^{city}$", "$options": "i"}}
        ).sort("timestamp", -1).limit(10)
        return list(data)
    except Exception as e:
        print("History Error:", e)
        return []


# 🤖 AI Prediction (safe)
def predict_aqi(history):
    try:
        values = [
            d["processed_data"].get("aqi")
            for d in history
            if d.get("processed_data") and d["processed_data"].get("aqi")
        ]

        if len(values) < 3:
            return None

        return round(sum(values[-3:]) / 3 + 5, 2)

    except Exception as e:
        print("Prediction Error:", e)
        return None


@app.route("/")
def home():
    return render_template("dashboard.html")


# ✅ Main API (GLOBAL 🌍)
@app.route("/api/live-data", methods=["GET"])
def live_data():
    city = request.args.get("city", "Hyderabad")

    sync_ec2_jobs()

    weather = get_weather(city)
    aqi = get_aqi(city)

    if "error" in weather:
        return jsonify({
            "status": "error",
            "message": weather["error"]
        }), 500

    processed = process_environmental_data(weather, aqi)

    # Save
    record = {
        "city": city.lower(),
        "timestamp": datetime.utcnow(),
        "processed_data": processed,
        "lat": weather.get("lat"),
        "lon": weather.get("lon")
    }
    save_data(record)

    return jsonify({
        "status": "success",
        "data": {
            "city": city,
            "timestamp": datetime.utcnow().isoformat(),
            "raw_data": {
                "weather": weather,
                "air_quality": aqi
            },
            "processed_data": processed
        }
    })

def get_cpu(instance_id):
    try:
        metrics = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            StartTime=datetime.utcnow() - timedelta(minutes=10),
            EndTime=datetime.utcnow(),
            Period=300,
            Statistics=['Average']
        )

        datapoints = metrics.get("Datapoints", [])

        if datapoints:
            return round(datapoints[-1]["Average"], 2)

        return 0

    except Exception as e:
        print("CPU Error:", e)
        return 0
    
@app.route("/api/aws/ec2")
def aws_ec2():

    response = ec2.describe_instances()

    total = 0
    running = 0
    stopped = 0

    for r in response["Reservations"]:
        for i in r["Instances"]:
            total += 1
            state = i["State"]["Name"]

            if state == "running":
                running += 1
            elif state == "stopped":
                stopped += 1

    return jsonify({
        "total": total,
        "running": running,
        "stopped": stopped
    })

# ✅ History API
@app.route("/api/history/<city>")
def history(city):
    data = get_history(city)

    result = []
    for d in data:
        pd = d.get("processed_data", {})
        result.append({
            "temp": pd.get("temperature"),
            "aqi": pd.get("aqi"),
            "time": str(d.get("timestamp"))
        })

    return jsonify(result)


# 🤖 Prediction API
@app.route("/api/predict/<city>")
def predict(city):
    history = get_history(city)
    prediction = predict_aqi(history)

    return jsonify({"predicted_aqi": prediction})


# =========================
# 🔥 UI ROUTES (IMPORTANT)
# =========================

@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


@app.route("/data-sources")
def data_sources():
    return render_template("data_sources.html")


@app.route("/processing")
def processing():
    return render_template("processing.html")


@app.route("/analytics")
def analytics():
    return render_template("analytics.html")


@app.route("/map")
def map_view():
    return render_template("map.html")


@app.route("/alerts")
def alerts():
    return render_template("alerts.html")


# =========================

# ✅ Health
@app.route("/api/health")
def health():
    return jsonify({
        "status": "healthy",
        "time": datetime.utcnow().isoformat()
    })

from bson import ObjectId

# COLLECTION
jobs_collection = db["jobs"]


# ✅ CREATE JOB
@app.route("/api/jobs", methods=["POST"])
def create_job():
    data = request.json

    job = {
        "name": data.get("name"),
        "infra": data.get("infra"),
        "type": data.get("type"),
        "status": "queued",
        "created_at": datetime.utcnow()
    }

    result = jobs_collection.insert_one(job)

    return jsonify({"status": "success", "id": str(result.inserted_id)})


# ✅ GET JOBS
@app.route("/api/jobs", methods=["GET"])
def get_jobs():
    
    sync_ec2_jobs()

    jobs = list(jobs_collection.find().sort("created_at", -1))

    result = []
    for j in jobs:
        result.append({
            "id": str(j["_id"]),
            "name": j["name"],
            "infra": j["infra"],
            "type": j.get("type"),
            "status": j["status"],
            "cpu": j.get("cpu", 0),
            "instance_id": j.get("instance_id"),
            "created_at": j.get("created_at")
                    })

    return jsonify(result)


@app.route("/api/dashboard-stats")
def dashboard_stats():

    total_sources = collection.count_documents({})
    total_readings = collection.count_documents({})
    alerts = collection.count_documents({"processed_data.aqi": {"$gt": 150}})

    # REAL JOB COUNTS
    total_jobs = jobs_collection.count_documents({})
    running_jobs = jobs_collection.count_documents({"status": "running"})
    completed_jobs = jobs_collection.count_documents({"status": "completed"})

    return jsonify({
        "data_sources": total_sources,
        "running_jobs": running_jobs,
        "completed_jobs": completed_jobs,
        "readings": total_readings,
        "alerts": alerts
    })

def sync_ec2_jobs():

    response = ec2.describe_instances()

    for r in response["Reservations"]:
        for i in r["Instances"]:

            instance_id = i["InstanceId"]
            state = i["State"]["Name"]

            # STATUS MAP
            if state == "running":
                status = "running"
            elif state == "stopped":
                status = "completed"
            else:
                status = "failed"

            # 🔥 GET CPU (IMPORTANT)
            cpu = get_cpu(instance_id)

            existing = jobs_collection.find_one({"instance_id": instance_id})

            if existing:
                jobs_collection.update_one(
                    {"instance_id": instance_id},
                    {"$set": {
                        "status": status,
                        "cpu": cpu
                    }}
                )
            else:
                jobs_collection.insert_one({
                    "name": f"EC2-{instance_id}",
                    "infra": "AWS",
                    "type": i.get("InstanceType", "EC2"),
                    "status": status,
                    "instance_id": instance_id,
                    "cpu": cpu,
                    "created_at": datetime.utcnow()
                })

@app.route("/api/cloud-usage")
def cloud_usage():

    jobs = list(jobs_collection.find())

    if len(jobs) == 0:
        return jsonify({
            "aws": 0,
            "azure": 0,
            "gcp": 0,
            "edge": 0
        })

    total = len(jobs)

    aws = sum(1 for j in jobs if j["infra"] == "AWS")
    azure = sum(1 for j in jobs if j["infra"] == "Azure")
    gcp = sum(1 for j in jobs if j["infra"] == "GCP")
    edge = sum(1 for j in jobs if j["infra"] == "Edge")

    return jsonify({
        "aws": round((aws / total) * 100),
        "azure": round((azure / total) * 100),
        "gcp": round((gcp / total) * 100),
        "edge": round((edge / total) * 100)
    })


# ✅ Multi-city API
@app.route("/api/multi-city", methods=["POST"])
def multi_city():
    cities = request.json.get("cities", [])
    results = []

    for city in cities:
        weather = get_weather(city)
        aqi = get_aqi(city)
        processed = process_environmental_data(weather, aqi)

        results.append({
            "city": city,
            "processed_data": processed,
            "lat": weather.get("lat"),
            "lon": weather.get("lon")
        })

    return jsonify({
        "status": "success",
        "data": results
    })


if __name__ == "__main__":
    app.run(debug=True)