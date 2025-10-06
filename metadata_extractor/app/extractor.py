import io
import exifread
from PIL import Image
from PyPDF2 import PdfReader
from docx import Document
from mutagen import File as MutagenFile
import magic
import tempfile


def sniff_mime(file_bytes: bytes) -> str:
    """Detect file type from magic bytes."""
    ms = magic.Magic(mime=True)
    return ms.from_buffer(file_bytes[:65536])


def _convert_to_degrees(value):
    """Convert GPS coordinates from EXIF rationals to decimal degrees."""
    try:
        d, m, s = [x.num / x.den for x in value]
        return d + (m / 60.0) + (s / 3600.0)
    except Exception:
        return None


def extract_image_metadata(file_bytes: bytes) -> dict:
    """Extract EXIF, GPS, and camera info from an image."""
    info = {}
    try:
        img = Image.open(io.BytesIO(file_bytes))
        info["format"] = img.format
        info["size"] = img.size
        info["mode"] = img.mode
    except Exception as e:
        info["image_error"] = str(e)

    presence = {"gps_data": False, "camera_info": False, "timestamp": False}

    try:
        tags = exifread.process_file(io.BytesIO(file_bytes), details=True)
        exif = {str(k): str(v) for k, v in tags.items()}
        info["raw_exif"] = exif

        make = exif.get("Image Make")
        model = exif.get("Image Model")
        date_taken = exif.get("EXIF DateTimeOriginal")

        info["camera_make"] = make or "Unknown"
        info["camera_model"] = model or "Unknown"
        info["datetime_original"] = date_taken or "Unknown"
        info["software"] = exif.get("Image Software", "Unknown")

        if make or model:
            presence["camera_info"] = True
        if date_taken:
            presence["timestamp"] = True

        gps_lat = tags.get("GPS GPSLatitude")
        gps_lat_ref = tags.get("GPS GPSLatitudeRef")
        gps_lon = tags.get("GPS GPSLongitude")
        gps_lon_ref = tags.get("GPS GPSLongitudeRef")

        if gps_lat and gps_lat_ref and gps_lon and gps_lon_ref:
            lat = _convert_to_degrees(gps_lat.values)
            lon = _convert_to_degrees(gps_lon.values)
            if gps_lat_ref.values != "N":
                lat = -lat
            if gps_lon_ref.values != "E":
                lon = -lon
            info["gps"] = {"latitude": lat, "longitude": lon}
            presence["gps_data"] = True
        else:
            info["gps"] = "No GPS data found"

    except Exception as e:
        info["exif_error"] = str(e)

    info["presence_report"] = presence
    return info


def extract_pdf_metadata(file_bytes: bytes) -> dict:
    info = {}
    try:
        reader = PdfReader(io.BytesIO(file_bytes))
        info["num_pages"] = len(reader.pages)
        info["document_info"] = dict(reader.metadata or {})
    except Exception as e:
        info["pdf_error"] = str(e)
    return info


def extract_docx_metadata(file_bytes: bytes) -> dict:
    info = {}
    try:
        doc = Document(io.BytesIO(file_bytes))
        core = doc.core_properties
        info["author"] = core.author
        info["title"] = core.title
        info["created"] = str(core.created)
        info["modified"] = str(core.modified)
    except Exception as e:
        info["docx_error"] = str(e)
    return info


def extract_audio_metadata(file_bytes: bytes) -> dict:
    info = {}
    try:
        with tempfile.NamedTemporaryFile(delete=True) as t:
            t.write(file_bytes)
            t.flush()
            audio = MutagenFile(t.name)
            if audio:
                info["tags"] = dict(audio.tags or {})
                info["length"] = getattr(audio.info, "length", None)
    except Exception as e:
        info["audio_error"] = str(e)
    return info


def extract_metadata(file_bytes: bytes) -> dict:
    mime = sniff_mime(file_bytes)
    result = {"mime": mime}

    if mime.startswith("image/"):
        img_meta = extract_image_metadata(file_bytes)
        result["image"] = img_meta
        result["summary"] = {
            "Camera": f"{img_meta.get('camera_make')} {img_meta.get('camera_model')}",
            "Taken On": img_meta.get("datetime_original"),
            "Software": img_meta.get("software"),
            "GPS": img_meta.get("gps"),
        }

    elif mime == "application/pdf":
        result["pdf"] = extract_pdf_metadata(file_bytes)

    elif "wordprocessingml" in mime:
        result["docx"] = extract_docx_metadata(file_bytes)

    elif mime.startswith("audio/"):
        result["audio"] = extract_audio_metadata(file_bytes)

    else:
        result["note"] = "File type not supported"

    return result


def strip_image_metadata(file_bytes: bytes) -> bytes:
    """Remove EXIF and other metadata from an image and return cleaned bytes."""
    buf = io.BytesIO()
    try:
        img = Image.open(io.BytesIO(file_bytes))
        fmt = (img.format or "JPEG").upper()
        cleaned = img.copy()
        cleaned.info = {}

        if fmt == "JPEG":
            if cleaned.mode in ("RGBA", "LA", "P"):
                cleaned = cleaned.convert("RGB")
            cleaned.save(buf, format="JPEG", quality=95, optimize=True)
        elif fmt == "PNG":
            cleaned.save(buf, format="PNG", optimize=True)
        else:
            if cleaned.mode in ("RGBA", "LA", "P"):
                cleaned = cleaned.convert("RGB")
            cleaned.save(buf, format="JPEG", quality=95, optimize=True)

        return buf.getvalue()
    except Exception as e:
        raise RuntimeError(f"Failed to strip metadata: {e}")
