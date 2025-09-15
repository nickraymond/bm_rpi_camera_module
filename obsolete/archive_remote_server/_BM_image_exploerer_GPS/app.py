from flask import Flask, request, render_template, send_from_directory
from sofar_api_image_pull import main as pull_images
import os
from datetime import datetime
import pytz
import glob
from pillow_heif import register_heif_opener
from PIL import Image

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

def find_heic_images_grouped():
    image_root = "parsed_images"
    result = {}

    for spotter_id in os.listdir(image_root):
        spot_path = os.path.join(image_root, spotter_id)
        if not os.path.isdir(spot_path):
            continue

        result[spotter_id] = {}

        for node_id in os.listdir(spot_path):
            node_path = os.path.join(spot_path, node_id)
            if not os.path.isdir(node_path):
                continue

            image_files = [
                os.path.join("parsed_images", spotter_id, node_id, f)
                for f in os.listdir(node_path)
                if f.lower().endswith(".jpg")
            ]

            if image_files:
                result[spotter_id][node_id] = sorted(image_files)

    return result


def convert_heic_to_jpg(heic_paths):
    jpg_paths = []

    for heic_path in heic_paths:
        jpg_path = heic_path.replace(".heic", ".jpg")

        if not os.path.exists(jpg_path):  # Avoid re-converting
            try:
                with Image.open(heic_path) as img:
                    img.save(jpg_path, "JPEG")
                    print(f"[Conversion] Converted {heic_path} → {jpg_path}")
            except Exception as e:
                print(f"[Conversion] Failed to convert {heic_path}: {e}")
                continue

        jpg_paths.append(jpg_path)

    return jpg_paths

# @app.route("/", methods=["GET", "POST"])
# def index():
#     images = []
#
#     if request.method == "POST":
#         token = request.form["token"]
#         spot_id = request.form["spotter"]
#         start_local = request.form["start"]
#         end_local = request.form["end"]
#
#         start = to_utc_iso(start_local)
#         end = to_utc_iso(end_local)
#
#         os.makedirs(IMAGE_DIR, exist_ok=True)
#
#         result = pull_images([spot_id], start, end, token)
#
#         # Find all HEIC images for this SPOT ID
#         heic_images = find_heic_images(spot_id)
#
#         # Convert to JPEG and return .jpg paths
#         #images = convert_heic_to_jpg(heic_images)
#         find_heic_images(spot_id)  # optional: if you still want flat list
#         images_grouped = find_heic_images_grouped()
#
#     #return render_template("index.html", images=images)
#     return render_template("index.html", images_grouped=images_grouped)

# @app.route("/", methods=["GET", "POST"])
# def index():
#     images_grouped = {}  # ✅ Always initialize this so it's available on both GET and POST
#
#
#     if request.method == "POST":
#         spot_id = request.form["spotter"]
#         token = request.form["token"]
#         start_local = request.form["start"]
#         end_local = request.form["end"]
#
#         start = to_utc_iso(start_local)
#         end = to_utc_iso(end_local)
#
#         os.makedirs(IMAGE_DIR, exist_ok=True)
#
#         result = pull_images([spot_id], start, end, token)
#
#         # Convert HEIC to JPG and group
#         heic_images = find_heic_images(spot_id)
#         convert_heic_to_jpg(heic_images)
#
#         # Update structured grouped images
#         images_grouped = find_heic_images_grouped()
#
#     return render_template("index.html", images_grouped=images_grouped)
from flask import Flask, request, render_template
from sofar_api_image_pull import main as pull_images
import os

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    images_grouped = {}

    if request.method == "POST":
        if request.form.get("clear") == "true":
            return render_template("index.html", images_grouped={})

        spot_id = request.form["spotter"]
        token = request.form["token"]
        start = request.form["start"]
        end = request.form["end"]

        # Create necessary directories
        img_directory = os.path.join("parsed_images", spot_id)
        os.makedirs(img_directory, exist_ok=True)
        csv_path = os.path.join(img_directory, "all_data.csv")
        image_log_path = os.path.join(img_directory, "image_log.csv")

        result = pull_images([spot_id], start, end, token)

        if isinstance(result, dict):
            images_grouped[spot_id] = result.get(spot_id, {})

    return render_template("index.html", images_grouped=images_grouped)

if __name__ == "__main__":
    app.run(debug=True)


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
