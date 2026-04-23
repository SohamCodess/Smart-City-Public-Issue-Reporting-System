from flask import Flask, render_template, jsonify, request, redirect, session
from pymongo import MongoClient
import os
from werkzeug.utils import secure_filename
from bson import ObjectId
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
import datetime

# ================= ENV =================
load_dotenv()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")

# ================= APP =================
app = Flask(__name__)
app.secret_key = "secret123"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# ================= DB =================
client = MongoClient("mongodb://localhost:27017/")
db = client["civiccare"]
users_col = db["users"]
issues_col = db["issues"]
ward_info_col=db["ward_info"]

# ================= EMAIL =================
def send_email(to_email, subject, body):
    if not EMAIL_USER or not EMAIL_PASS or not to_email:
        print("❌ Email skipped (missing credentials or recipient)")
        return

    msg = EmailMessage()
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)

    print("✅ Email sent to", to_email)

# ================= ROUTES =================
@app.route("/")
def home():
    return render_template("home.html", username=session.get("user"))

@app.route("/register", methods=["POST"])
def register():
    email = request.form.get("email")
    username = request.form.get("username")
    password = request.form.get("password")

    if users_col.find_one({"$or": [{"email": email}, {"username": username}]}):
        return render_template("login.html", err="Email or Username already exists")

    users_col.insert_one({
        "email": email,
        "username": username,
        "password": password
    })
    return render_template("login.html", msg="Registration successful! Please login.")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        user = users_col.find_one({"username": username})
        if user and password == user["password"]:
            session["user"] = username
            return redirect("/")

        return render_template("login.html", err="Invalid username or password")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect("/login")

@app.route("/ward")
def ward():
    return render_template("ward.html", username=session.get("user"))

@app.route("/ward-data/<letter>/<int:ward_no>")
def ward_data(letter, ward_no):
    data = ward_info_col.find_one(
        {"ward_letter": letter, "ward_no": ward_no},
        {"_id": 0}
    )
    return jsonify(data or {})


# ================= REPORT ISSUE =================
@app.route("/report-issue", methods=["GET", "POST"])
def report_issue():
    if "user" not in session:
        return redirect("/login")

    if request.method == "POST":
        filename = None
        image = request.files.get("image")

        # IMAGE SAVE
        if image and image.filename:
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        # USER EMAIL FETCH
        user = users_col.find_one({"username": session["user"]})
        email = user.get("email") if user else None

        # INSERT ISSUE

     
        issues_col.insert_one({
    "username": session["user"],
    "email": request.form.get("email"),
    "name": request.form.get("name"),
    "mobile": request.form.get("mobile"),
    "issues": request.form.get("issues"),
    "date":request.form.get("date"),
    "ward": request.form.get("ward"),
    "ward_no": request.form.get("ward_no"),

    # ✅ IMPORTANT FIX
    "address": request.form.get("address"),
    "Landmark":request.form.get("Landmark"),
    "pincode": request.form.get("pincode"),
    "description": request.form.get("description"),

    "status": "Pending",
    "stage": 1,
    "image": filename
})

        


        # EMAIL SEND (SAFE)
        if email:
            try:
                send_email(
                    email,
                    "Complaint Registered – CityFix",
                    "Your complaint has been registered successfully.\n\n"
                    "We will update you once it is assigned and resolved.\n\n"
                    "– CityFix Team"
                )
                print("✅ Registration email sent to:", email)
            except Exception as e:
                print("❌ Email sending failed:", e)
        else:
            print("⚠️ No email found for user")

        return redirect("/")

    return render_template("report.html", username=session.get("user"))

# ================= MY COMPLAINTS =================
@app.route("/my-complaints")
def my_complaints():
    if "user" not in session:
        return redirect("/login")

    complaints = list(issues_col.find({"username": session["user"]}).sort("_id", -1))

    stats = {
        "total": len(complaints),
        "pending": sum(1 for c in complaints if c["status"] == "Pending"),
        "assigned": sum(1 for c in complaints if c["status"] == "Assigned"),
        "resolved": sum(1 for c in complaints if c["status"] in ["Solved", "Resolved"])
    }

    return render_template(
        "my_complaints.html",
        complaints=complaints,
        stats=stats,
        username=session.get("user")
    )

@app.route("/live-stats")
def live_stats():
    total_users = users_col.count_documents({})
    total_issues = issues_col.count_documents({})
    solved_issues = issues_col.count_documents({"status": "Solved"})

    print("STATS:", total_users, total_issues, solved_issues)  # DEBUG

    return jsonify({
    "citizens": total_users,
    "issues": total_issues,
    "solved": solved_issues
})

# ================= ADMIN =================
@app.route("/admin")
def admin_dashboard():
    if not session.get("admin_logged_in"):
        return redirect("/admin-login")

    return render_template(
        "admin.html",
        total_citizens=users_col.count_documents({}),
        total_issues=issues_col.count_documents({}),
        pending_issues=issues_col.count_documents({"status": "Pending"}),
        solved_issues=issues_col.count_documents({"status": {"$in": ["Solved", "Resolved"]}}),
        citizens=list(users_col.find()),
        issues=list(issues_col.find().sort("_id", -1))
    )

@app.route("/admin/assign/<issue_id>", methods=["POST"])
def admin_assign(issue_id):
    issue = issues_col.find_one({"_id": ObjectId(issue_id)})

    issues_col.update_one(
        {"_id": ObjectId(issue_id)},
        {"$set": {"status": "Assigned", "stage": 2}}
    )

    send_email(
        issue.get("email"),
        "Complaint Assigned – CityFix",
        "Your complaint has been assigned to the concerned department.\n\n– CityFix Team"
    )

    return redirect("/admin")

@app.route("/admin/solve/<issue_id>", methods=["POST"])
def admin_solve_issue(issue_id):
    issue = issues_col.find_one({"_id": ObjectId(issue_id)})

    issues_col.update_one(
        {"_id": ObjectId(issue_id)},
        {"$set": {"status": "Solved", "stage": 3}}
    )

    send_email(
        issue.get("email"),
        "Complaint Resolved – CityFix",
        "Your complaint has been resolved successfully.\n\nThank you for using CityFix."
    )

    return redirect("/admin")

@app.route("/admin-login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_logged_in"):
        return redirect("/admin")

    if request.method == "POST":
        if request.form.get("username") == "admin" and request.form.get("password") == "admin123":
            session["admin_logged_in"] = True
            return redirect("/admin")

        return render_template("adminlogin.html", error="Invalid credentials")

    return render_template("adminlogin.html")

@app.route("/admin-logout")
def admin_logout():
    session.clear()
    return redirect("/admin-login")


@app.route("/admin/ward-extra", methods=["POST"])
def save_ward_extra():
    if not session.get("admin_logged_in"):
        return redirect("/admin-login")

    ward_info_col.update_one(
        {
            "ward_letter": request.form.get("ward_letter"),
            "ward_no": int(request.form.get("ward_no"))
        },
        {
            "$set": {
                "mp": request.form.get("mp"),
                "mla": request.form.get("mla"),
                "corporator": request.form.get("corporator"),
                "bmc_office": request.form.get("bmc_office")
            }
        },
        upsert=True   # 🔥 insert OR update
    )

    return redirect("/admin")
@app.route("/admin/ward-info", methods=["POST"])
def save_ward_info():
    if not session.get("admin_logged_in"):
        return redirect("/admin-login")

    ward_letter = request.form.get("ward_letter")
    ward_no = int(request.form.get("ward_no"))
    mp = request.form.get("mp")
    mla = request.form.get("mla")
    corporator = request.form.get("corporator")
    bmc_office = request.form.get("bmc_office")

    ward_info_col.update_one(
        {
            "ward_letter": ward_letter,
            "ward_no": ward_no
        },
        {
            "$set": {
                "mp": mp,
                "mla": mla,
                "corporator": corporator,
                "bmc_office": bmc_office
            }
        },
        upsert=True
    )

    return redirect("/admin")


# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True)
