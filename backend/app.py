
from flask import Flask, render_template, request, redirect, url_for, flash
import hashlib
import requests
import cv2
import numpy as np
from urllib.parse import urlparse
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file
)

from math import asin, cos, radians, sin, sqrt
import json
import hashlib
import io
import qrcode
import requests
import os
from functools import wraps
from models import User, ScanLog, db
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from user_agents import parse
import requests
from models import ScanLog, User, db

PUBLIC_BASE_URL = os.environ.get(
    "PHARMACHAIN_PUBLIC_URL",
    "http://127.0.0.1:5000",
).rstrip("/")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "PHARMACHAIN_SECRET_KEY",
    "development-secret-change-before-deployment",
)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    "sqlite:///pharmachain_users.db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = (
    "Please log in to access this page."
)
login_manager.login_message_category = "warning"

@login_manager.user_loader
def load_user(user_id: str):
    try:
        return db.session.get(User, int(user_id))
    except (TypeError, ValueError):
        return None

def roles_required(*allowed_roles):
    def decorator(view_function):
        @wraps(view_function)
        @login_required
        def wrapped_view(*args, **kwargs):
            if current_user.role not in allowed_roles:
                flash(
                    "You are not authorized to perform this action.",
                    "danger",
                )
                return redirect(url_for("home"))

            return view_function(*args, **kwargs)

        return wrapped_view

    return decorator

def get_client_ip() -> tuple[str | None, str | None]:
    cloudflare_ip = request.headers.get(
        "CF-Connecting-IP",
        "",
    ).strip()

    cloudflare_ipv6 = request.headers.get(
        "CF-Connecting-IPv6",
        "",
    ).strip()

    forwarded_for = request.headers.get(
        "X-Forwarded-For",
        "",
    ).strip()

    client_ip = None

    if cloudflare_ipv6:
        client_ip = cloudflare_ipv6
    elif cloudflare_ip:
        client_ip = cloudflare_ip
    elif forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()

    return request.remote_addr, client_ip

def classify_device(user_agent: str) -> tuple[str, str, str]:
    value = (user_agent or "").lower()

    if "android" in value:
        operating_system = "Android"
    elif "iphone" in value or "ipad" in value:
        operating_system = "iOS"
    elif "windows" in value:
        operating_system = "Windows"
    elif "mac os" in value or "macintosh" in value:
        operating_system = "macOS"
    elif "linux" in value:
        operating_system = "Linux"
    else:
        operating_system = "Unknown"

    if "edg/" in value:
        browser = "Microsoft Edge"
    elif "chrome/" in value:
        browser = "Google Chrome"
    elif "firefox/" in value:
        browser = "Mozilla Firefox"
    elif "safari/" in value:
        browser = "Safari"
    else:
        browser = "Unknown"

    if "mobile" in value or "android" in value or "iphone" in value:
        device = "Mobile"
    elif "ipad" in value or "tablet" in value:
        device = "Tablet"
    else:
        device = "Desktop"

    return device, browser, operating_system

def get_location(ip_address):
    if not ip_address:
        return {}

    if ip_address in {"127.0.0.1", "::1"}:
        return {}

    try:
        response = requests.get(
            f"http://ip-api.com/json/{ip_address}",
            params={
                "fields": (
                    "status,message,country,regionName,"
                    "city,lat,lon,query"
                )
            },
            timeout=5,
        )

        response.raise_for_status()
        data = response.json()

        if data.get("status") == "success":
            return {
                "country": data.get("country"),
                "region": data.get("regionName"),
                "city": data.get("city"),
                "latitude": data.get("lat"),
                "longitude": data.get("lon"),
            }

        print(
            "GeoIP lookup failed:",
            data.get("message", "Unknown reason"),
        )

    except requests.RequestException as error:
        print("GeoIP request failed:", error)

    return {}

def calculate_distance_km(
    latitude_1,
    longitude_1,
    latitude_2,
    longitude_2,
):
    """Calculate distance between two geographic points."""

    earth_radius_km = 6371.0

    lat1 = radians(latitude_1)
    lon1 = radians(longitude_1)
    lat2 = radians(latitude_2)
    lon2 = radians(longitude_2)

    lat_difference = lat2 - lat1
    lon_difference = lon2 - lon1

    value = (
        sin(lat_difference / 2) ** 2
        + cos(lat1)
        * cos(lat2)
        * sin(lon_difference / 2) ** 2
    )

    return 2 * earth_radius_km * asin(sqrt(value))

def assess_scan_risk(
    drug_id,
    verification_result,
    location,
):
    risk_score = 0
    alerts = []

    status = str(
        verification_result.get("status", "UNKNOWN")
    ).strip().upper()

    current_time = datetime.utcnow()

    # -------------------------------------------------
    # Rule 1: Invalid QR or blockchain verification error
    # -------------------------------------------------
    critical_statuses = {
        "QR_MISMATCH",
        "NOT_FOUND",
        "VERIFICATION_FAILED",
        "INVALID_RESPONSE",
    }

    if status in critical_statuses:
        risk_score += 90
        alerts.append(
            "Blockchain verification failed or QR data is invalid."
        )

    elif status in {
        "GATEWAY_UNAVAILABLE",
        "GATEWAY_TIMEOUT",
        "VERIFICATION_ERROR",
        "UNKNOWN",
    }:
        risk_score += 50
        alerts.append(
            "Verification could not be completed due to a system error."
        )

    # -------------------------------------------------
    # Rule 2: Revoked product
    # -------------------------------------------------
    if status == "REVOKED":
        risk_score += 70
        alerts.append(
            "A revoked pharmaceutical product was scanned."
        )

    # -------------------------------------------------
    # Behavioural rules apply mainly to genuine scans
    # -------------------------------------------------
    if status == "GENUINE":

        # Repeated scans in one minute
        one_minute_ago = current_time - timedelta(minutes=1)

        recent_scan_count = (
            ScanLog.query
            .filter(
                ScanLog.drug_id == drug_id,
                ScanLog.scan_time >= one_minute_ago,
            )
            .count()
        )

        # Do not penalize one ordinary repeat or browser refresh.
        if recent_scan_count >= 3:
            risk_score += 10
            alerts.append(
                "The same QR code was scanned at least three times "
                "within one minute."
            )

        # Excessive scans within ten minutes
        ten_minutes_ago = current_time - timedelta(minutes=10)

        ten_minute_scan_count = (
            ScanLog.query
            .filter(
                ScanLog.drug_id == drug_id,
                ScanLog.scan_time >= ten_minutes_ago,
            )
            .count()
        )

        if ten_minute_scan_count >= 10:
            risk_score += 20
            alerts.append(
                "Excessive scan frequency was detected "
                "within ten minutes."
            )

        # -------------------------------------------------
        # Geographic anomaly rule
        # IP GeoIP is approximate, so use conservative limits.
        # -------------------------------------------------
        current_latitude = location.get("latitude")
        current_longitude = location.get("longitude")

        if (
            current_latitude is not None
            and current_longitude is not None
        ):
            previous_scan = (
                ScanLog.query
                .filter(
                    ScanLog.drug_id == drug_id,
                    ScanLog.latitude.isnot(None),
                    ScanLog.longitude.isnot(None),
                    ScanLog.forwarded_ip.isnot(None),
                )
                .order_by(ScanLog.scan_time.desc())
                .first()
            )

            if previous_scan:
                distance_km = calculate_distance_km(
                    previous_scan.latitude,
                    previous_scan.longitude,
                    current_latitude,
                    current_longitude,
                )

                previous_time = previous_scan.scan_time

                elapsed_seconds = (
                    current_time - previous_time
                ).total_seconds()

                if elapsed_seconds > 0:
                    elapsed_hours = elapsed_seconds / 3600
                    implied_speed = distance_km / elapsed_hours

                    # GeoIP gateway changes inside the same state/country
                    # should not be treated as counterfeit evidence.
                    different_country = (
                        previous_scan.country
                        and location.get("country")
                        and previous_scan.country
                        != location.get("country")
                    )

                    # Require a very large distance plus extreme speed.
                    if (
                        distance_km >= 1000
                        and implied_speed >= 900
                        and different_country
                    ):
                        risk_score += 40
                        alerts.append(
                            "A possible impossible-travel pattern was "
                            f"detected: {distance_km:.1f} km in "
                            f"{elapsed_hours:.2f} hours."
                        )

    risk_score = min(risk_score, 100)

    alert_text = (
        " | ".join(alerts)
        if alerts
        else None
    )

    return risk_score, alert_text

def generate_explanation(
    verification_result,
    risk_score,
    location,
):
    status = str(
        verification_result.get("status", "UNKNOWN")
    ).upper()

    reasons = []

    recommendation = ""

    # ----------------------------
    # Determine Risk Level
    # ----------------------------

    if risk_score >= 70:
        risk_level = "HIGH"

    elif risk_score >= 30:
        risk_level = "MEDIUM"

    else:
        risk_level = "LOW"

    # ----------------------------
    # Blockchain Status
    # ----------------------------

    if status == "GENUINE":

        reasons.append(
            "Blockchain verification successful."
        )

        reasons.append(
            "Drug status is ACTIVE."
        )

        recommendation = (
            "Safe to dispense."
        )

    elif status == "REVOKED":

        reasons.append(
            "Drug has been revoked by the manufacturer or regulator."
        )

        recommendation = (
            "Do NOT dispense. Quarantine the product immediately."
        )

    else:

        reasons.append(
            "Blockchain verification failed."
        )

        recommendation = (
            "Possible counterfeit product. Do not purchase or dispense."
        )

    # ----------------------------
    # Geo Information
    # ----------------------------

    if location.get("city"):

        reasons.append(
            f"Scan location: "
            f"{location['city']}, "
            f"{location['country']}."
        )

    # ----------------------------
    # Risk Reason
    # ----------------------------

    if risk_score >= 70:

        reasons.append(
            "High counterfeit risk detected."
        )

    elif risk_score >= 30:

        reasons.append(
            "Moderate suspicious behaviour detected."
        )

    else:

        reasons.append(
            "No suspicious activity detected."
        )

    explanation = "\n".join(reasons)

    return (
        risk_level,
        explanation,
        recommendation,
    )

def save_scan_log(
    drug_id: str,
    qr_hash: str,
    verification_result: dict,
) -> None:
    user_agent = request.headers.get("User-Agent", "")

    direct_ip, forwarded_ip = get_client_ip()
    client_ip = forwarded_ip or direct_ip

    print("Direct IP:", direct_ip)
    print("Forwarded IP:", forwarded_ip)
    print("GeoIP Client IP:", client_ip)

    location = get_location(client_ip)
    risk_score, alert = assess_scan_risk(
    drug_id=drug_id,
    verification_result=verification_result,
    location=location,
    )

    risk_level, explanation, recommendation = generate_explanation(
    verification_result,
    risk_score,
    location,
    )

    print("GeoIP result:", location)

    device, browser, operating_system = classify_device(
        user_agent
    )

    if not device or len(device.strip()) <= 1:
        device = (
            "Mobile"
            if operating_system == "Android"
            else "Unknown"
        )

    log = ScanLog(
        drug_id=drug_id,
        qr_hash=qr_hash,
        result=verification_result.get(
            "status",
            "UNKNOWN",
        ),
        message=verification_result.get("message"),
        ip_address=direct_ip,
        forwarded_ip=forwarded_ip,
        user_agent=user_agent,
        device=device,
        browser=browser,
        operating_system=operating_system,
        city=location.get("city"),
        region=location.get("region"),
        country=location.get("country"),
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
        risk_score=risk_score,
        alert=alert,
        risk_level=risk_level,

        explanation=explanation,

        recommendation=recommendation,
    )

    db.session.add(log)
    db.session.commit()

    print(
    "Scan saved:",
    log.id,
    log.drug_id,
    log.city,
    "Risk:",
    log.risk_score,
    "Alert:",
    log.alert,
    )
GATEWAY_URL = "http://localhost:3000"


@app.route("/")
@login_required
def home():
    return render_template("index.html")


@app.route("/drug/<drug_id>")
@login_required
def view_drug(drug_id):
    try:
        response = requests.get(
            f"{GATEWAY_URL}/drugs/{drug_id}",
            timeout=10
        )

        response.raise_for_status()

        drug = response.json()

        return render_template(
            "drug.html",
            drug=drug
        )

    except requests.RequestException as error:
        return (
            f"Unable to retrieve the blockchain record: {error}",
            503
        )

from flask import request, redirect, url_for, flash

@app.route("/register", methods=["GET","POST"])
@roles_required("ADMIN","MANUFACTURER")
def register():
    if request.method == "POST":
        drug_id = request.form.get("drugID", "").strip().upper()
        drug_name = request.form.get("drugName", "").strip()
        manufacturer = request.form.get("manufacturer", "").strip()
        batch_number = request.form.get("batchNumber", "").strip()
        manufacture_date = request.form.get("manufactureDate", "").strip()
        expiry_date = request.form.get("expiryDate", "").strip()

        if not all([
            drug_id,
            drug_name,
            manufacturer,
            batch_number,
            manufacture_date,
            expiry_date
        ]):
            flash("All fields are required.", "danger")
            return render_template("register.html")

        if expiry_date <= manufacture_date:
            flash(
                "Expiry date must be later than the manufacture date.",
                "danger"
            )
            return render_template("register.html")

        qr_source = (
            f"{drug_id}|{drug_name}|{manufacturer}|"
            f"{batch_number}|{manufacture_date}|{expiry_date}"
        )

        qr_hash = hashlib.sha256(
            qr_source.encode("utf-8")
        ).hexdigest()

        payload = {
            "drugID": drug_id,
            "drugName": drug_name,
            "manufacturer": manufacturer,
            "batchNumber": batch_number,
            "manufactureDate": manufacture_date,
            "expiryDate": expiry_date,
            "qrHash": qr_hash
        }

        try:
            response = requests.post(
                f"{GATEWAY_URL}/drugs",
                json=payload,
                timeout=30
            )

            result = response.json()

            if response.status_code == 201:
                flash(
                    f"Drug {drug_id} was registered successfully.",
                    "success"
                )
                return redirect(
                    url_for("view_drug", drug_id=drug_id)
                )

            flash(
                result.get(
                    "message",
                    "Blockchain registration failed."
                ),
                "danger"
            )

        except requests.ConnectionError:
            flash(
                "The Fabric Gateway is not running on port 3000.",
                "danger"
            )

        except requests.Timeout:
            flash(
                "The blockchain transaction timed out.",
                "danger"
            )

        except requests.RequestException as error:
            flash(
                f"Unable to register the drug: {error}",
                "danger"
            )

    return render_template("register.html")

@app.route("/qr/<drug_id>")
def generate_qr(drug_id):
    try:
        response = requests.get(
            f"{GATEWAY_URL}/drugs/{drug_id}",
            timeout=10
        )

        response.raise_for_status()
        drug = response.json()

        qr_hash = drug.get("qrHash")

        if not qr_hash:
            return "QR hash is missing from the blockchain record.", 404

        verification_path = url_for(
             "verify_qr",
              drug_id=drug_id,
             qr_hash=qr_hash,
                    )

        verification_url = (
             f"{PUBLIC_BASE_URL}{verification_path}"
        )

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4
        )

        qr.add_data(verification_url)
        qr.make(fit=True)

        image = qr.make_image(
            fill_color="black",
            back_color="white"
        )

        image_buffer = io.BytesIO()
        image.save(image_buffer, format="PNG")
        image_buffer.seek(0)

        return send_file(
            image_buffer,
            mimetype="image/png",
            download_name=f"{drug_id}_qr.png"
        )

    except requests.RequestException as error:
        return f"Unable to generate QR code: {error}", 503

@app.route("/verify-qr/<drug_id>/<qr_hash>")
def verify_qr(drug_id, qr_hash):

    payload = {
        "drugId": drug_id,
        "qrHash": qr_hash,
    }

    try:
        response = requests.post(
            f"{GATEWAY_URL}/verify",
            json=payload,
            timeout=20,
        )

        print("Gateway HTTP Status:", response.status_code)
        print("Gateway Raw Response:", response.text)

        try:
            gateway_result = response.json()
        except ValueError:
            gateway_result = {
                "isValid": False,
                "status": "INVALID_RESPONSE",
                "message": (
                    "The Gateway returned a non-JSON response."
                ),
            }

        print("Gateway JSON Response:", gateway_result)

        is_valid = gateway_result.get(
            "isValid",
            gateway_result.get(
                "valid",
                gateway_result.get("verified", False),
            ),
        )

        status = gateway_result.get("status")

        if not status:
            status = (
                "AUTHENTIC"
                if is_valid
                else "VERIFICATION_FAILED"
            )

        message = gateway_result.get("message")

        if not message:
            if is_valid:
                message = (
                    "The QR code matches an active "
                    "pharmaceutical record on the blockchain."
                )
            else:
                message = (
                    gateway_result.get("error")
                    or "The QR code could not be authenticated."
                )

        result = {
            "isValid": bool(is_valid),
            "status": status,
            "message": message,
            "drug": gateway_result.get("drug"),
        }

        location = get_location(
            request.headers.get("CF-Connecting-IP")
            or request.remote_addr
        )

        risk_score, alert = assess_scan_risk(
            drug_id=drug_id,
            verification_result=result,
            location=location,
        )

        risk_level, explanation, recommendation = generate_explanation(
            result,
            risk_score,
            location,
        )

        result["risk_score"] = risk_score
        result["risk_level"] = risk_level
        result["alert"] = alert
        result["explanation"] = explanation
        result["recommendation"] = recommendation


        try:
            print("Remote address:", request.remote_addr)
            print(
                "CF-Connecting-IP:",
                request.headers.get("CF-Connecting-IP"),
            )
            print(
                "CF-Connecting-IPv6:",
                request.headers.get("CF-Connecting-IPv6"),
            )
            print(
                "X-Forwarded-For:",
                request.headers.get("X-Forwarded-For"),
            )

            save_scan_log(
                drug_id=drug_id,
                qr_hash=qr_hash,
                verification_result=result,
            )

        except Exception as error:
            db.session.rollback()
            print("Scan logging failed:", error)

        return render_template(
            "verify_result.html",
            result=result,
            drug_id=drug_id,
        )

    except requests.ConnectionError:
        result = {
            "isValid": False,
            "status": "GATEWAY_UNAVAILABLE",
            "message": (
                "The Node.js Fabric Gateway is not running."
            ),
        }

    except requests.Timeout:
        result = {
            "isValid": False,
            "status": "GATEWAY_TIMEOUT",
            "message": "Blockchain verification timed out.",
        }

    except requests.RequestException as error:
        result = {
            "isValid": False,
            "status": "VERIFICATION_ERROR",
            "message": str(error),
        }

    return render_template(
        "verify_result.html",
        result=result,
        drug_id=drug_id,
    )

@app.route("/verify")
@login_required
def verify_page():
    return render_template("verify.html")

@app.route("/upload-qr", methods=["POST"])
def upload_qr():

    uploaded_file = request.files.get("qrimage")

    if not uploaded_file or uploaded_file.filename == "":
        flash("Please choose a QR image.", "danger")
        return redirect(url_for("verify_page"))

    image_bytes = np.frombuffer(
        uploaded_file.read(),
        np.uint8
    )

    image = cv2.imdecode(
        image_bytes,
        cv2.IMREAD_COLOR
    )

    if image is None:
        flash("The uploaded file is not a valid image.", "danger")
        return redirect(url_for("verify_page"))

    detector = cv2.QRCodeDetector()

    qr_text, points, _ = detector.detectAndDecode(image)

    if not qr_text:
        flash("QR code could not be decoded.", "danger")
        return redirect(url_for("verify_page"))

    parsed_url = urlparse(qr_text)

    expected_base = urlparse(PUBLIC_BASE_URL)

    valid_scheme = parsed_url.scheme in {"http", "https"}
    valid_host = parsed_url.netloc == expected_base.netloc
    valid_path = parsed_url.path.startswith("/verify-qr/")

    if valid_scheme and valid_host and valid_path:
      return redirect(qr_text)

    flash("Invalid pharmaceutical QR code.", "danger")
    return redirect(url_for("verify_page"))

    flash("Invalid pharmaceutical QR code.", "danger")
    return redirect(url_for("verify_page"))

def normalize_history_item(item):
    if not isinstance(item, dict):
        return {
            "txId": "Not available",
            "timestamp": "Not available",
            "isDelete": False,
            "record": {}
        }

    record = (
        item.get("record")
        or item.get("Record")
        or item.get("value")
        or item.get("Value")
        or {}
    )

    # Fabric may return the record as a JSON string
    if isinstance(record, str):
        try:
            record = json.loads(record)
        except json.JSONDecodeError:
            record = {}

    # Some responses contain another nested value
    if isinstance(record, dict):
        nested_value = record.get("value") or record.get("Value")

        if isinstance(nested_value, str):
            try:
                nested_value = json.loads(nested_value)
            except json.JSONDecodeError:
                nested_value = None

        if isinstance(nested_value, dict):
            record = nested_value

    return {
        "txId": (
            item.get("txId")
            or item.get("TxId")
            or item.get("txID")
            or item.get("TxID")
            or item.get("transactionId")
            or item.get("transactionID")
            or "Not available"
        ),
        "timestamp": (
            item.get("timestamp")
            or item.get("Timestamp")
            or "Not available"
        ),
        "isDelete": bool(
            item.get("isDelete", item.get("IsDelete", False))
        ),
        "record": record if isinstance(record, dict) else {}
    }

def extract_device_info():

    ua = parse(request.headers.get("User-Agent", ""))

    # Device
    if ua.is_mobile:
        device = "Mobile"
    elif ua.is_tablet:
        device = "Tablet"
    elif ua.is_pc:
        device = "Desktop"
    else:
        device = "Unknown"

    # Browser
    browser = ua.browser.family

    # Operating System
    operating_system = ua.os.family

    return {
        "device": device,
        "browser": browser,
        "os": operating_system
    }


@app.route("/history")
@login_required
def history_page():
    
    return render_template(
        "history.html",
        history=None,
        drug_id=None
    )

@app.route("/history/search", methods=["POST"])
def search_history():
    drug_id = request.form.get("drugID", "").strip()

    if not drug_id:
        flash("Please enter a Drug ID.", "danger")
        return redirect(url_for("history_page"))

    return redirect(
        url_for(
            "view_history",
            drug_id=drug_id
        )
    )

@app.route("/history/<drug_id>")
def view_history(drug_id):
    try:
        response = requests.get(
            f"{GATEWAY_URL}/drugs/{drug_id}/history",
            timeout=20
        )

        print("History HTTP Status:", response.status_code)
        print("History Response:", response.text)

        if response.status_code == 404:
            flash(
                f"No blockchain record was found for {drug_id}.",
                "danger"
            )

            return render_template(
                "history.html",
                history=None,
                drug_id=drug_id
            )

        response.raise_for_status()

        gateway_data = response.json()

        if isinstance(gateway_data, list):
            history = gateway_data

        elif isinstance(gateway_data, dict):
            history = gateway_data.get("history", [])

        else:
            history = []

        if not isinstance(history, list):
            history = []

        print("History passed to template:", history)

        return render_template(
            "history.html",
            history=history,
            drug_id=drug_id
        )

    except requests.ConnectionError:
        flash(
            "The Node.js Fabric Gateway is not running.",
            "danger"
        )

    except requests.Timeout:
        flash(
            "Blockchain history retrieval timed out.",
            "danger"
        )

    except requests.RequestException as error:
        flash(
            f"Unable to retrieve drug history: {error}",
            "danger"
        )

    return render_template(
        "history.html",
        history=None,
        drug_id=drug_id
    )

@app.route("/revoke")
@roles_required("ADMIN","MANUFACTURER","REGULATOR")
def revoke_page():
    drug_id = request.args.get("drug_id", "").strip().upper()

    return render_template(
        "revoke.html",
        drug_id=drug_id
    )


@app.route("/revoke", methods=["POST"])
@roles_required("ADMIN","MANUFACTURER","REGULATOR")
def revoke_drug():
    drug_id = request.form.get("drugID", "").strip().upper()
    reason = request.form.get("reason", "").strip()

    if not drug_id or not reason:
        flash(
            "Drug ID and revocation reason are required.",
            "danger"
        )

        return render_template(
            "revoke.html",
            drug_id=drug_id
        )

    try:
        response = requests.post(
            f"{GATEWAY_URL}/drugs/{drug_id}/revoke",
            json={"reason": reason},
            timeout=30
        )

        result = response.json()

        if response.status_code == 200:
            flash(
                f"Drug {drug_id} was revoked successfully.",
                "success"
            )

            return redirect(
                url_for("view_drug", drug_id=drug_id)
            )

        error_message = (
            result.get("error")
            or result.get("message")
            or "Drug revocation failed."
        )

        flash(error_message, "danger")

    except requests.ConnectionError:
        flash(
            "The Fabric Gateway is not running on port 3000.",
            "danger"
        )

    except requests.Timeout:
        flash(
            "The revocation transaction timed out.",
            "danger"
        )

    except requests.RequestException as error:
        flash(
            f"Unable to revoke the drug: {error}",
            "danger"
        )

    return render_template(
        "revoke.html",
        drug_id=drug_id
    )
@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":
        username = request.form.get(
            "username",
            "",
        ).strip()

        password = request.form.get(
            "password",
            "",
        )

        remember = request.form.get("remember") == "on"

        user = User.query.filter_by(
            username=username,
        ).first()

        if user is None or not user.check_password(password):
            flash(
                "Invalid username or password.",
                "danger",
            )
            return render_template("login.html")

        if not user.is_active_account:
            flash(
                "This account has been disabled.",
                "danger",
            )
            return render_template("login.html")

        login_user(user, remember=remember)

        flash(
            f"Welcome, {user.full_name}.",
            "success",
        )

        next_page = request.args.get("next")

        if next_page and next_page.startswith("/"):
            return redirect(next_page)

        return redirect(url_for("home"))

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()

    flash(
        "You have been logged out successfully.",
        "success",
    )

    return redirect(url_for("login"))

@app.route("/analytics")
@roles_required("ADMIN", "MANUFACTURER", "REGULATOR")
def analytics():
    total_scans = ScanLog.query.count()

    genuine_scans = ScanLog.query.filter_by(
        result="GENUINE"
    ).count()

    revoked_scans = ScanLog.query.filter_by(
        result="REVOKED"
    ).count()

    failed_scans = ScanLog.query.filter(
        ScanLog.result.notin_(["GENUINE", "REVOKED"])
    ).count()

    unique_drugs = (
        db.session.query(
            func.count(func.distinct(ScanLog.drug_id))
        ).scalar()
        or 0
    )

    today_utc = datetime.now(timezone.utc).date()

    today_scans = ScanLog.query.filter(
        func.date(ScanLog.scan_time) == today_utc.isoformat()
    ).count()

    device_rows = (
        db.session.query(
            ScanLog.device,
            func.count(ScanLog.id)
        )
        .group_by(ScanLog.device)
        .all()
    )

    result_rows = (
        db.session.query(
            ScanLog.result,
            func.count(ScanLog.id)
        )
        .group_by(ScanLog.result)
        .all()
    )

    recent_logs = (
    ScanLog.query
    .order_by(
        ScanLog.country.is_(None),
        ScanLog.scan_time.desc(),
    )
    .limit(20)
    .all()
    )
    map_logs = (
    ScanLog.query
    .filter(
        ScanLog.latitude.isnot(None),
        ScanLog.longitude.isnot(None),
    )
    .order_by(ScanLog.scan_time.desc())
    .limit(100)
    .all()
    )

    map_points = []

    for log in map_logs:
     map_points.append({
        "drug_id": log.drug_id,
        "result": log.result,
        "latitude": log.latitude,
        "longitude": log.longitude,
        "city": log.city or "Unknown",
        "region": log.region or "Unknown",
        "country": log.country or "Unknown",
        "risk_score": log.risk_score or 0,
        "alert": log.alert or "No suspicious activity",
        "scan_time": (
            log.scan_time.strftime("%Y-%m-%d %H:%M:%S")
            if log.scan_time
            else "Unknown"
        ),
    })

    return render_template(
            "analytics.html",
            total_scans=total_scans,
            today_scans=today_scans,
            unique_drugs=unique_drugs,
            genuine_scans=genuine_scans,
            revoked_scans=revoked_scans,
            failed_scans=failed_scans,
            device_labels=[
                row[0] or "Unknown"
                for row in device_rows
            ],
            device_values=[
                row[1]
                for row in device_rows
            ],
            result_labels=[
                row[0] or "UNKNOWN"
                for row in result_rows
            ],
            result_values=[
                row[1]
                for row in result_rows
            ],
            recent_logs=recent_logs,
            map_points=map_points,
        )


if __name__ == "__main__":
    app.run(debug=True)