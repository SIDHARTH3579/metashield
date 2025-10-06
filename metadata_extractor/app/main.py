from flask import Flask, request, render_template, jsonify, send_file
from io import BytesIO
import os
from .extractor import (
    extract_metadata,
    strip_image_metadata,
    sniff_mime,
)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10MB limit
app = Flask(__name__, static_url_path='/static', static_folder='static', template_folder='templates')



@app.route("/")
def home():
    return render_template("index.html")


@app.route("/api/extract", methods=["POST"])
def extract_route():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["file"]
    data = f.read()
    result = extract_metadata(data)
    return jsonify(result)


@app.route("/api/clean", methods=["POST"])
def clean_file():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    f = request.files["file"]
    original_bytes = f.read()
    mime = sniff_mime(original_bytes) or ""
    if not mime.startswith("image/"):
        return jsonify({"error": "Only image cleaning supported"}), 400

    try:
        cleaned_bytes = strip_image_metadata(original_bytes)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    name, ext = os.path.splitext(f.filename or "cleaned.jpg")
    if not ext:
        ext = ".jpg" if mime == "image/jpeg" else ".png"
    cleaned_name = f"{name}_cleaned{ext}"

    return send_file(
        BytesIO(cleaned_bytes),
        mimetype=mime,
        as_attachment=True,
        download_name=cleaned_name,
    )


if __name__ == "__main__":
    app.run(debug=True)
