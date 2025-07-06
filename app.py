from flask import Flask, request, render_template
import mysql.connector
import datetime
import json

app = Flask(__name__)

# --- Load MySQL credentials ---
try:
    with open("credentials.json") as f:
        db_config = json.load(f)
        DB_HOST = db_config["host"]
        DB_PORT = db_config["port"]
        DB_USER = db_config["user"]
        DB_PASSWORD = db_config["password"]
        DB_NAME = db_config["database"]
except Exception as e:
    print("⚠️ Failed to load credentials.json:", e)
    raise SystemExit("❌ Could not load database credentials.")


@app.route("/")
def home():
    return "Hello, Flask is working!"


@app.route('/plot')
def plot():
    import random

    print("🔵 /plot called")

    # Read DB credentials from JSON
    with open("credentials.json") as f:
        creds = json.load(f)

    conn = mysql.connector.connect(
        host=creds["host"],
        port=creds["port"],
        user=creds["user"],
        password=creds["password"],
        database=creds["database"]
    )
    cursor = conn.cursor()

    # Fetch timestamp, voltage, and channel for last 1000 samples
    cursor.execute(
        "SELECT timestamp, voltage, channel FROM samples WHERE channel IS NOT NULL ORDER BY timestamp DESC LIMIT 1000"
    )
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    print(f"✅ Fetched {len(rows)} rows from DB")

    channel_data = {}  # { channel: [(timestamp, voltage), ...] }
    for ts, voltage, channel in rows:
        if channel not in channel_data:
            channel_data[channel] = []
        channel_data[channel].append((
            ts.strftime("%Y-%m-%dT%H:%M:%S") if isinstance(ts, datetime.datetime) else str(ts),
            voltage
        ))

    print(f"✅ Found channels: {list(channel_data.keys())}")

    datasets = []
    for ch in sorted(channel_data.keys()):
        if not channel_data[ch]:
            continue
        color = f"hsl({ch * 18}, 70%, 50%)"
        try:
            timestamps, voltages = zip(*channel_data[ch])
        except ValueError:
            print(f"⚠️ Channel {ch} has no data, skipping")
            continue
        datasets.append({
            "label": "Total battery voltage",
            "data": [{"x": t, "y": v} for t, v in zip(timestamps, voltages)],
            "borderColor": color,
            "fill": False,
            "tension": 0.1,
            "pointRadius": 1
        })

    print(f"✅ Prepared {len(datasets)} datasets")

    return render_template(
        'plot.html',
        datasets=json.dumps(datasets)
    )


@app.route('/api/store', methods=['POST'])
def store():
    data = request.get_json()
    voltage = data.get("voltage")
    timestamp = data.get("timestamp") or datetime.datetime.now().isoformat()
    device_id = data.get("device_id")
    channel = data.get("channel")

    conn = mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO samples (timestamp, voltage, device_id, channel) VALUES (%s, %s, %s, %s)",
        (timestamp, voltage, device_id, channel)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return {"status": "stored"}, 200


if __name__ == "__main__":
    try:
        print("Starting Flask app...")
        app.run(host="0.0.0.0", port=1111, debug=True)
    except Exception as e:
        print("Error starting app:", e)
