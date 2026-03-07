from flask import Flask, render_template, request, redirect, session
import csv
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "123456"


# =========================
# KIỂM TRA ROLE
# =========================
def require_role(roles):

    def wrapper(func):

        def decorated(*args, **kwargs):

            if "username" not in session:
                return redirect("/login")

            if session.get("role") not in roles:
                return "❌ Bạn không có quyền truy cập"

            return func(*args, **kwargs)

        decorated.__name__ = func.__name__
        return decorated

    return wrapper


# =========================
# ĐỌC USER
# =========================
def load_users():

    users = {}

    if not os.path.exists("users.csv"):
        return users

    with open("users.csv", newline="", encoding="utf-8-sig") as f:

        reader = csv.DictReader(f)

        for row in reader:
            users[row["username"].strip()] = row

    return users


# =========================
# ĐỌC TÀI SẢN
# =========================
def load_assets():

    assets = {}

    if not os.path.exists("aims.csv"):
        return assets

    with open("aims.csv", newline="", encoding="utf-8") as f:

        reader = csv.DictReader(f)

        for row in reader:

            asset_id = row.get("ID_assets", "").strip()

            if asset_id:

                if "ATS" not in row or row["ATS"] == "":
                    row["ATS"] = "100"

                assets[asset_id] = row

    return assets


# =========================
# CẬP NHẬT ATS
# =========================
def update_ats(asset_id, minus):

    rows = []

    with open("aims.csv", newline="", encoding="utf-8-sig") as f:

        reader = csv.DictReader(f)

        for row in reader:

            if row.get("ID_assets", "").strip() == asset_id.strip():

                ats = int(row.get("ATS", 100))
                ats = max(0, ats - minus)

                row["ATS"] = str(ats)

            rows.append(row)

    with open("aims.csv", "w", newline="", encoding="utf-8") as f:

        fieldnames = rows[0].keys()

        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(rows)


# =========================
# GHI ALERT
# =========================
def save_alert(user, asset_id, expected_room, scanned_room, alert_type, description=""):

    file_exists = os.path.exists("alerts.csv")

    with open("alerts.csv", "a", newline="", encoding="utf-8") as f:

        writer = csv.writer(f)

        if not file_exists:
            writer.writerow([
                "user",
                "asset_id",
                "expected_room",
                "scanned_room",
                "type_alert",
                "description",
                "time"
            ])

        writer.writerow([
            user,
            asset_id,
            expected_room,
            scanned_room,
            alert_type,
            description,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ])


# =========================
# LOGIN
# =========================
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get("username")
        password = request.form.get("password")

        users = load_users()

        user = users.get(username)

        if user and user["password"] == password:

            session["username"] = username
            session["role"] = user.get("role")

            return redirect("/")

        return render_template("login.html", error="Sai tài khoản hoặc mật khẩu")

    return render_template("login.html")


# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# =========================
# TRANG CHỦ
# =========================
@app.route("/")
@require_role(["admin","manager","user"])
def home():

    return render_template("index.html")


# =========================
# SCAN QR
# =========================
@app.route("/scan")
@require_role(["admin","manager","user"])
def scan_qr():

    return render_template("scan.html")


# =========================
# DANH SÁCH TÀI SẢN
# =========================
@app.route("/assets")
@require_role(["admin","manager"])
def assets():

    assets = load_assets()

    room = request.args.get("room")
    asset_type = request.args.get("type")

    result = {}

    for id, asset in assets.items():

        if room and room.lower() not in asset.get("Room", "").lower():
            continue

        if asset_type and asset_type.lower() not in asset.get("Type_asset", "").lower():
            continue

        result[id] = asset

    return render_template("assets.html", assets=result)


# =========================
# CHI TIẾT TÀI SẢN
# =========================
@app.route("/asset/<asset_id>")
@require_role(["admin","manager","user"])
def asset_detail(asset_id):

    assets = load_assets()
    asset = assets.get(asset_id)

    if not asset:
        return "Không tìm thấy tài sản"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    room = asset.get("Room", "").strip()
    asset_type = asset.get("Type_asset", "").strip()

    file_exists = os.path.exists("scan_history.csv")

    with open("scan_history.csv", "a", newline="", encoding="utf-8") as f:

        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(["user", "asset_id", "room", "type", "time"])

        writer.writerow([
            session["username"],
            asset_id,
            room,
            asset_type,
            now
        ])

    scanned_room = request.args.get("scan_room")

    if scanned_room and scanned_room != room:

        save_alert(
            session["username"],
            asset_id,
            room,
            scanned_room,
            "wrong_room"
        )

        update_ats(asset_id, 15)

    return render_template("asset.html", asset=asset)


# =========================
# BÁO HỎNG
# =========================
@app.route("/report/<asset_id>", methods=["GET", "POST"])
@require_role(["admin","manager","user"])
def report(asset_id):

    assets = load_assets()
    asset = assets.get(asset_id)

    if not asset:
        return redirect("/scan")

    if request.method == "POST":

        description = request.form.get("description")

        save_alert(
            session["username"],
            asset_id,
            asset.get("Room"),
            asset.get("Room"),
            "damage",
            description
        )

        update_ats(asset_id, 25)

        return render_template("report_success.html", asset=asset)

    return render_template("report_form.html", asset=asset)


# =========================
# LỊCH SỬ QUÉT
# =========================
@app.route("/history")
@require_role(["admin","manager"])
def history():

    history = []

    if os.path.exists("scan_history.csv"):

        with open("scan_history.csv", newline="", encoding="utf-8") as f:

            reader = csv.DictReader(f)

            for row in reader:
                history.append(row)

    return render_template("history.html", history=history)


# =========================
# TÀI SẢN BẤT THƯỜNG
# =========================
@app.route("/abnormal")
@require_role(["admin"])
def abnormal():

    abnormal_assets = []

    if os.path.exists("alerts.csv"):

        with open("alerts.csv", newline="", encoding="utf-8") as f:

            reader = csv.DictReader(f)

            for row in reader:
                abnormal_assets.append(row)

    return render_template("abnormal.html", abnormal_assets=abnormal_assets)


# =========================
# XOÁ ALERT
# =========================
@app.route("/delete_abnormal", methods=["POST"])
@require_role(["admin"])
def delete_abnormal():

    asset_id = request.form.get("asset_id")

    update_ats(asset_id, -10)

    rows = []

    with open("alerts.csv", newline="", encoding="utf-8") as f:

        reader = csv.DictReader(f)

        for row in reader:
            if row["asset_id"] != asset_id:
                rows.append(row)

    with open("alerts.csv", "w", newline="", encoding="utf-8") as f:

        fieldnames = [
            "user",
            "asset_id",
            "expected_room",
            "scanned_room",
            "type_alert",
            "description",
            "time"
        ]

        writer = csv.DictWriter(f, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(rows)

    return redirect("/abnormal")


# =========================
# CHẠY SERVER
# =========================
if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))


    app.run(host="0.0.0.0", port=port, debug=True)
