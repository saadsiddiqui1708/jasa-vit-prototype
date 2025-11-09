from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from collections import defaultdict
from datetime import datetime, timedelta


app = Flask(__name__)

app.secret_key = "dev-secret"  # for session cookies only (prototype)

# -------------------------
# Hardcoded users / roles
# -------------------------
ROLES = {
    "JASA01": "JASA_USER",
    "VIT01": "VIT_ADMIN",
    "SPORIC01": "SPORIC",
}
PASSWORD = "123"

# -------------------------
# Enums (strings for demo)
# -------------------------
POSTING_INTERNSHIP = "INTERNSHIP"
POSTING_VACANCY = "VACANCY"
POSTING_RESEARCH = "RESEARCH"
JAP_SCALE = ["NONE", "N5", "N4", "N3", "N2", "N1"]
PROF_WEIGHT = {"BEGINNER": 1, "INTERMEDIATE": 2, "ADVANCED": 3}

# -------------------------
# Demo student database
# -------------------------
students = [
    {
        "id": "stu1",
        "regNo": "VIT2023CSE001",
        "name": "Aarya Iyer",
        "degreeLevel": "Undergrad",
        "branch": "CSE (AI & Robotics)",
        "tenthScore": 92,
        "twelfthScore": 90,
        "skills": {
            "python": "INTERMEDIATE",
            "c++": "INTERMEDIATE",
            "java": "BEGINNER",
            "sql": "BEGINNER",
        },
        "softwares": {
            "excel": "ADVANCED",
            "git": "INTERMEDIATE",
        },
        "japanese": "N5",
    },
    {
        "id": "stu2",
        "regNo": "VIT2022EEE045",
        "name": "Rohan Mehta",
        "degreeLevel": "Undergrad",
        "branch": "EEE",
        "tenthScore": 88,
        "twelfthScore": 85,
        "skills": {
            "embedded c": "INTERMEDIATE",
            "python": "BEGINNER",
            "matlab": "ADVANCED",
        },
        "softwares": {
            "simulink": "ADVANCED",
            "autocad": "INTERMEDIATE",
        },
        "japanese": "N4",
    },
    {
        "id": "stu3",
        "regNo": "VIT2021ME120",
        "name": "Sneha Narayanan",
        "degreeLevel": "Undergrad",
        "branch": "Mechanical",
        "tenthScore": 95,
        "twelfthScore": 93,
        "skills": {
            "python": "BEGINNER",
        },
        "softwares": {
            "solidworks": "ADVANCED",
            "ansys": "INTERMEDIATE",
        },
        "japanese": "N3",
    },
]

# -------------------------
# Demo postings + IDs
# -------------------------
postings = []
_id_counter = {"posting": 1, "interview": 1}

def next_id(kind):
    _id_counter[kind] += 1
    return str(_id_counter[kind])

# notifications: list of dicts {toRole, title, body, link, read}
notifications = []

# interview requests
interview_requests = []  # {id, postingId, studentId, status, scheduledAt, notes, requestedBy}

# -------------------------
# Utility: matching
# -------------------------
def jap_index(level):
    try:
        return JAP_SCALE.index(level)
    except ValueError:
        return 0

def compute_match_score(post):
    required = [s.strip().lower() for s in (post.get("requiredSkills") or [])]
    req_jap = post.get("requiredJapanese") or "NONE"

    matches = []
    for s in students:
        # skill score
        total = 0
        for rs in required:
            prof = None
            if rs in s["skills"]:
                prof = s["skills"][rs]
            elif rs in s["softwares"]:
                prof = s["softwares"][rs]
            if prof:
                total += PROF_WEIGHT.get(prof, 1) / 3.0
        skill_score = (total / max(len(required), 1)) if required else 0

        # japanese score
        js = 1.0 if jap_index(s["japanese"]) >= jap_index(req_jap) and req_jap != "NONE" else 0.0
        if req_jap == "NONE" and jap_index(s["japanese"]) >= jap_index("N4"):
            js = 0.2

        final = 0.8 * skill_score + 0.2 * js
        if final >= 0.5:
            matches.append({"student": s, "score": round(final, 2)})
    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches

# -------------------------
# Auth helpers
# -------------------------
def current_user():
    user = session.get("user")
    if user and user in ROLES:
        return {"username": user, "role": ROLES[user]}
    return None

def require_role(*allowed):
    user = current_user()
    return user and user["role"] in allowed

# -------------------------
# Seed demo postings on first request
# -------------------------
seeded = {"done": False}

def seed_demo():
    if seeded["done"]:
        return
    demo = [
        {
            "type": POSTING_INTERNSHIP,
            "title": "Data Analyst Intern (JASA)",
            "description": "Python + SQL + Excel for dashboards.",
            "location": "Chennai",
            "duration": "3 months",
            "stipend": 15000,
            "eligibility": "Undergrad (CSE/IT/DS)",
            "experience": "0–1 yrs",
            "requiredSkills": ["python", "sql", "excel"],
            "requiredJapanese": "N5",
        },
        {
            "type": POSTING_INTERNSHIP,
            "title": "Embedded Systems Intern",
            "description": "Work with Embedded C, MATLAB/Simulink.",
            "location": "Chennai",
            "duration": "2 months",
            "stipend": 12000,
            "eligibility": "EEE/ECE Undergrad",
            "experience": "0–1 yrs",
            "requiredSkills": ["embedded c", "matlab", "simulink"],
            "requiredJapanese": "N5",
        },
        {
            "type": POSTING_VACANCY,
            "title": "Junior Mechanical Design Engineer",
            "description": "CAD modeling and FEA support.",
            "location": "Chennai",
            "compensation": "₹5–6 LPA",
            "eligibility": "B.Tech Mechanical",
            "experience": "1–2 yrs",
            "requiredSkills": ["solidworks", "ansys"],
            "requiredJapanese": "N5",
        },
        {
            "type": POSTING_RESEARCH,
            "title": "AI for Predictive Maintenance in Manufacturing",
            "description": "Python/Pandas/Scikit for failure prediction.",
            "researchArea": "AI/ML",
            "requiredSkills": ["python", "pandas", "scikit-learn"],
            "requiredJapanese": "N4",
        },
        {
            "type": POSTING_RESEARCH,
            "title": "Renewable Energy Microgrids Control",
            "description": "Control strategies in microgrids.",
            "researchArea": "Power Systems",
            "requiredSkills": ["matlab", "simulink", "control systems"],
            "requiredJapanese": "NONE",
        },
        {
            "type": POSTING_RESEARCH,
            "title": "Lightweight Composite Brackets",
            "description": "Topology optimization and FEA.",
            "researchArea": "Mechanical Design",
            "requiredSkills": ["solidworks", "ansys"],
            "requiredJapanese": "NONE",
        },
    ]
    for p in demo:
        p["id"] = next_id("posting")
        p["createdBy"] = "JASA01"
        p["createdAt"] = datetime.now()
        p["matches"] = compute_match_score(p) if p["type"] != POSTING_RESEARCH else []
        postings.append(p)
        # Notifications
        notifications.append({
            "toRole": "VIT_ADMIN",
            "title": f"New {p['type'].title()} posted",
            "body": p["title"],
            "link": f"/postings/{p['id']}",
            "read": False
        })
        if p["type"] == POSTING_RESEARCH:
            notifications.append({
                "toRole": "SPORIC",
                "title": "New Research posted",
                "body": p["title"],
                "link": f"/postings/{p['id']}",
                "read": False
            })
    # --- Demo: create a couple of scheduled interview requests so Admin sees them ---
    for post in postings:
        # Only for INTERNSHIP/VACANCY that have matches
        if post["type"] in (POSTING_INTERNSHIP, POSTING_VACANCY) and post.get("matches"):
            top = post["matches"][0]["student"]["id"]  # pick top student
            interview_requests.append({
                "id": next_id("interview"),
                "postingId": post["id"],
                "studentId": top,
                "status": "SCHEDULED",
                "scheduledAt": (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
                "notes": "Initial HR + tech round",
                "requestedBy": "JASA01",
                "createdAt": datetime.now()
            })

    # Notify Admin that interviews got scheduled (so it’s visible on dashboard)
    notifications.append({
        "toRole": "VIT_ADMIN",
        "title": "Interviews Scheduled",
        "body": "Demo: a couple of interviews were scheduled automatically.",
        "link": "/interview_requests",
        "read": False
    })
    seeded["done"] = True

# -------------------------
# Routes
# -------------------------
@app.before_request
def ensure_seed():
    seed_demo()

@app.route("/")
def home():
    if current_user():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password")
        if username in ROLES and password == PASSWORD:
            session["user"] = username
            session["role"] = ROLES[username]
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials.", "error")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for("login"))

@app.route("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    role = user["role"]

    # role-specific data
    if role == "JASA_USER":
        my_posts = [p for p in postings if p["createdBy"] == user["username"]]
        # collect top matches per post (up to 3)
        matches_rollup = []
        for p in my_posts:
            if p["type"] in (POSTING_INTERNSHIP, POSTING_VACANCY) and p.get("matches"):
                top = p["matches"][:3]
                matches_rollup.append({"post": p, "top": top})
        return render_template("dashboard.html",
                           role=role,
                           postings=my_posts,
                           matches_rollup=matches_rollup)

    if role == "VIT_ADMIN":
        unread = [n for n in notifications if n["toRole"] == "VIT_ADMIN" and not n["read"]]
        # build upcoming scheduled list
        upcoming = []
        for r in interview_requests:
            if r["status"] == "SCHEDULED":
                post = next((p for p in postings if p["id"] == r["postingId"]), None)
                stu = next((s for s in students if s["id"] == r["studentId"]), None)
                upcoming.append({"r": r, "posting": post, "student": stu})
        # sort by soonest
        upcoming.sort(key=lambda x: x["r"]["scheduledAt"] or "")
        return render_template("dashboard.html",
                           role=role,
                           postings=postings,
                           unread_count=len(unread),
                           upcoming=upcoming)

    if role == "SPORIC":
        research = [p for p in postings if p["type"] == POSTING_RESEARCH]
        return render_template("dashboard.html",
                               role=role,
                               research=research)
    return redirect(url_for("login"))

@app.route("/postings/new", methods=["GET", "POST"])
def new_posting():
    user = current_user()
    if not user or user["role"] != "JASA_USER":
        flash("Only JASA can create postings.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        ptype = request.form.get("type")
        title = request.form.get("title")
        description = request.form.get("description")
        location = request.form.get("location")
        duration = request.form.get("duration")
        stipend = request.form.get("stipend")
        compensation = request.form.get("compensation")
        eligibility = request.form.get("eligibility")
        experience = request.form.get("experience")
        researchArea = request.form.get("researchArea")
        reqSkills = [s.strip().lower() for s in (request.form.get("requiredSkills") or "").split(",") if s.strip()]
        reqJap = request.form.get("requiredJapanese") or "NONE"

        post = {
            "id": next_id("posting"),
            "type": ptype,
            "title": title,
            "description": description,
            "location": location,
            "duration": duration if ptype == POSTING_INTERNSHIP else None,
            "stipend": int(stipend) if stipend else None,
            "compensation": compensation if ptype == POSTING_VACANCY else None,
            "eligibility": eligibility,
            "experience": experience,
            "researchArea": researchArea if ptype == POSTING_RESEARCH else None,
            "requiredSkills": reqSkills,
            "requiredJapanese": reqJap,
            "createdAt": datetime.now(),
            "createdBy": user["username"],
            "matches": [],
        }
        if ptype in (POSTING_INTERNSHIP, POSTING_VACANCY):
            post["matches"] = compute_match_score(post)

        postings.append(post)

        # Notifications
        notifications.append({
            "toRole": "VIT_ADMIN",
            "title": f"New {ptype.title()} posted",
            "body": post["title"],
            "link": f"/postings/{post['id']}",
            "read": False
        })
        if ptype == POSTING_RESEARCH:
            notifications.append({
                "toRole": "SPORIC",
                "title": "New Research posted",
                "body": post["title"],
                "link": f"/postings/{post['id']}",
                "read": False
            })

        flash("Posting created.", "success")
        return redirect(url_for("posting_detail", posting_id=post["id"]))

    return render_template("posting_form.html")

@app.route("/postings/<posting_id>")
def posting_detail(posting_id):
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    post = next((p for p in postings if p["id"] == posting_id), None)
    if not post:
        flash("Posting not found.", "error")
        return redirect(url_for("dashboard"))
    return render_template("posting_detail.html", post=post, role=user["role"])

@app.route("/postings/<posting_id>/request_interviews", methods=["POST"])
def request_interviews(posting_id):
    user = current_user()
    if not user or user["role"] != "JASA_USER":
        flash("Only JASA can request interviews.", "error")
        return redirect(url_for("dashboard"))
    post = next((p for p in postings if p["id"] == posting_id), None)
    if not post:
        flash("Posting not found.", "error")
        return redirect(url_for("dashboard"))

    selected = request.form.getlist("student_id")
    for sid in selected:
        interview_requests.append({
            "id": next_id("interview"),
            "postingId": posting_id,
            "studentId": sid,
            "status": "PENDING",
            "scheduledAt": None,
            "notes": "",
            "requestedBy": user["username"],
            "createdAt": datetime.now()
        })
    if selected:
        notifications.append({
            "toRole": "VIT_ADMIN",
            "title": "Interview Requests",
            "body": f"{len(selected)} request(s) for '{post['title']}'",
            "link": "/interview_requests",
            "read": False
        })
        flash("Interview request(s) sent to VIT Admin.", "success")
    else:
        flash("No students selected.", "error")
    return redirect(url_for("posting_detail", posting_id=posting_id))

@app.route("/interview_requests", methods=["GET", "POST"])
def manage_interviews():
    user = current_user()
    if not user or user["role"] != "VIT_ADMIN":
        flash("Only VIT Admin can manage interviews.", "error")
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        iid = request.form.get("id")
        action = request.form.get("action")
        dt = request.form.get("scheduledAt")
        note = request.form.get("notes", "")
        req = next((r for r in interview_requests if r["id"] == iid), None)
        if req:
            if action == "approve":
                req["status"] = "APPROVED"
            elif action == "decline":
                req["status"] = "DECLINED"
            elif action == "schedule":
                req["status"] = "SCHEDULED"
                req["scheduledAt"] = dt or None
            req["notes"] = note
            flash("Updated request.", "success")
    # Build display rows
    rows = []
    for r in interview_requests:
        post = next((p for p in postings if p["id"] == r["postingId"]), None)
        stu = next((s for s in students if s["id"] == r["studentId"]), None)
        rows.append({"r": r, "posting": post, "student": stu})
    return render_template("interview_requests.html", rows=rows)

@app.route("/students")
def list_students():
    user = current_user()
    if not user or user["role"] != "VIT_ADMIN":
        flash("Only VIT Admin can view the student database.", "error")
        return redirect(url_for("dashboard"))
    return render_template("students.html", students=students)

@app.route("/notifications/mark_all_read")
def mark_all_read():
    user = current_user()
    if not user:
        return redirect(url_for("login"))
    for n in notifications:
        if n["toRole"] == ROLES[user["username"]]:
            n["read"] = True
    return redirect(url_for("dashboard"))

# SPORIC "Interested" on research post
@app.route("/research_interest/<posting_id>", methods=["POST"])
def research_interest(posting_id):
    user = current_user()
    if not user or user["role"] != "SPORIC":
        flash("Only SPORIC can mark interest.", "error")
        return redirect(url_for("dashboard"))
    post = next((p for p in postings if p["id"] == posting_id and p["type"] == POSTING_RESEARCH), None)
    if not post:
        flash("Research post not found.", "error")
        return redirect(url_for("dashboard"))
    notifications.append({
        "toRole": "VIT_ADMIN",
        "title": "SPORIC interested",
        "body": post["title"],
        "link": f"/postings/{post['id']}",
        "read": False
    })
    notifications.append({
        "toRole": "JASA_USER",
        "title": "SPORIC interested",
        "body": post["title"],
        "link": f"/postings/{post['id']}",
        "read": False
    })
    flash("Interest noted. Admin & JASA notified.", "success")
    return redirect(url_for("dashboard"))

if __name__ == "__main__":
    app.run(debug=True)
