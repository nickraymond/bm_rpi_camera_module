# filename: app.py
# description: runs flask server to show Bristlemouth Camera Explorer UI for parsing + showing images

from flask import Flask, request, render_template, send_from_directory
from sofar_api_image_pull import main as pull_images
import os
from datetime import datetime
import pytz
import glob
from pillow_heif import register_heif_opener
from PIL import Image
import csv

app = Flask(__name__)
register_heif_opener()  # Enables HEIC loading

IMAGE_DIR = os.path.join("static", "images")


def to_utc_iso(local_str, timezone_str="America/Los_Angeles"):
    local_dt = datetime.strptime(local_str, "%Y-%m-%dT%H:%M")
    local_tz = pytz.timezone(timezone_str)
    local_dt = local_tz.localize(local_dt)
    utc_dt = local_dt.astimezone(pytz.utc)
    utc_str = utc_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"[Time Conversion] Local Time ({timezone_str}): {local_dt.isoformat()}")
    print(f"[Time Conversion] UTC Time: {utc_str}")

    return utc_str


def find_heic_images(spotter_id):
    search_path = os.path.join("parsed_images", spotter_id, "*", "*.heic")
    found = glob.glob(search_path)
    print(f"[Image Scan] Found {len(found)} HEIC images for {spotter_id}")
    return found


def convert_heic_to_jpg(heic_paths):
    jpg_paths = []

    for heic_path in heic_paths:
        jpg_path = heic_path.replace(".heic", ".jpg")

        if not os.path.exists(jpg_path):
            try:
                with Image.open(heic_path) as img:
                    img.save(jpg_path, "JPEG")
                    print(f"[Conversion] Converted {heic_path} → {jpg_path}")
            except Exception as e:
                print(f"[Conversion] Failed to convert {heic_path}: {e}")
                continue

        jpg_paths.append(jpg_path)

    return jpg_paths


def find_heic_images_grouped():
    image_root = "parsed_images"
    csv_path = os.path.join(image_root, "spotter_image_log.csv")
    result = {}

    gps_lookup = {}
    if os.path.exists(csv_path):
        with open(csv_path, newline='') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if "Filename" not in row or "Node ID" not in row:
                    print(f"[WARN] Skipping malformed row: {row}")
                    continue
                filename = row["Filename"].replace(".heic", ".jpg")
                node_id = row["Node ID"]
                key = (node_id, filename)
                gps_lookup[key] = {
                    "lat": row.get("Latitude"),
                    "lon": row.get("Longitude"),
                    "timestamp": row.get("Timestamp")
                }

    for spotter_id in os.listdir(image_root):
        spot_path = os.path.join(image_root, spotter_id)
        if not os.path.isdir(spot_path):
            continue

        result[spotter_id] = {}

        for node_id in os.listdir(spot_path):
            node_path = os.path.join(spot_path, node_id)
            if not os.path.isdir(node_path):
                continue

            image_files = sorted(glob.glob(os.path.join(node_path, "*.jpg")))
            result[spotter_id][node_id] = []

            for fpath in image_files:
                fname = os.path.basename(fpath)
                key = (node_id, fname)
                meta = gps_lookup.get(key)

                if meta:
                    print(f"[GPS Match] Found GPS for {key}: lat={meta['lat']}, lon={meta['lon']}")
                else:
                    print(f"[GPS Miss] No GPS data for {key}")

                result[spotter_id][node_id].append({
                    "path": os.path.join(spotter_id, node_id, fname),
                    "lat": meta.get("lat") if meta else None,
                    "lon": meta.get("lon") if meta else None,
                    "timestamp": meta.get("timestamp") if meta else None
                })

    return result


@app.route("/", methods=["GET", "POST"])
def index():
    images_grouped = {}

    if request.method == "POST":
        spot_id = request.form["spotter"]
        token = request.form["token"]
        start_local = request.form["start"]
        end_local = request.form["end"]

        start = to_utc_iso(start_local)
        end = to_utc_iso(end_local)

        os.makedirs(IMAGE_DIR, exist_ok=True)

        result = pull_images([spot_id], start, end, token)

        heic_images = find_heic_images(spot_id)
        convert_heic_to_jpg(heic_images)

        images_grouped = find_heic_images_grouped()

    return render_template("index.html", images_grouped=images_grouped)


@app.route('/parsed_images/<path:filename>')
def serve_image(filename):
    return send_from_directory('parsed_images', filename)


if __name__ == "__main__":
    import webbrowser
    import threading

    port = 5000
    url = f"http://127.0.0.1:{port}/"

    def open_browser():
        webbrowser.open(url)

    threading.Timer(1.0, open_browser).start()
    app.run(debug=True, port=port, use_reloader=False)
