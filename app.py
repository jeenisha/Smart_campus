from flask import Flask, render_template, request, redirect, session
import sqlite3
from flask import jsonify

app = Flask(__name__)
app.secret_key = "supersecretkey"

DB_NAME = "database.db"

def get_db_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ---------- Initialize Database ----------
def init_db():
    conn = get_db_connection()
    c = conn.cursor()

    # users table (admin + teacher)
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT UNIQUE,
        password TEXT,
        role TEXT
    )
    """)

    # teacher_status table
    c.execute("""
    CREATE TABLE IF NOT EXISTS teacher_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        status TEXT,
        location TEXT
    )
    """)
    # locations table
    c.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        building TEXT,
        floor TEXT,
        room_number TEXT,
        x INTEGER,
        y INTEGER
    )
    """)

    # Create default admin if not exists
    c.execute("SELECT * FROM users WHERE role='admin'")
    admin = c.fetchone()
    if not admin:
        c.execute("INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                  ("Admin", "admin@college.com", "admin123", "admin"))

    conn.commit()
    conn.close()

# Run DB init
init_db()

# ---------- Routes ----------

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/chat", methods=["GET", "POST"])
def chat():
    if request.method == "POST":
        user_msg = request.json["message"]
        msg_lower = user_msg.lower()

        conn = get_db_connection()

        # ------------------ 1. CHECK TEACHER QUERIES ------------------
        teachers = conn.execute(
            "SELECT * FROM users WHERE role='teacher'"
        ).fetchall()

        found_teacher = None
        for t in teachers:
            if t["name"].lower() in msg_lower:
                found_teacher = t
                break

        if found_teacher:
            status_row = conn.execute(
                "SELECT * FROM teacher_status WHERE user_id=?",
                (found_teacher["id"],)
            ).fetchone()

            if not status_row:
                bot_reply = f"{found_teacher['name']} has not updated their status yet."
            else:
                if "where" in msg_lower:
                    bot_reply = f"{found_teacher['name']} is currently in {status_row['location']}."
                elif "available" in msg_lower or "free" in msg_lower:
                    bot_reply = f"{found_teacher['name']} is currently {status_row['status']}."
                else:
                    bot_reply = f"{found_teacher['name']} is {status_row['status']} and is in {status_row['location']}."

        else:
            # ------------------ 2. CHECK LOCATION QUERIES ------------------
            locations = conn.execute(
                "SELECT * FROM locations"
            ).fetchall()

            found_location = None
            for loc in locations:
                if loc["name"].lower() in msg_lower:
                    found_location = loc
                    break

            if found_location:
                bot_reply = (
                    f"{found_location['name']} is in {found_location['building']}, "
                    f"Floor {found_location['floor']}, Room {found_location['room_number']}."
                )
            else:
                bot_reply = "Sorry, I could not understand your question. Please ask about a teacher or a room."

        conn.close()

        return jsonify({"response": bot_reply})

    return render_template("chat.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email=? AND password=?",
            (email, password)
        ).fetchone()
        conn.close()

        if user:
            session["user_id"] = user["id"]
            session["role"] = user["role"]

            if user["role"] == "admin":
                return redirect("/admin")
            else:
                return redirect("/teacher")
        else:
            return "Invalid login"

    return render_template("login.html")

@app.route("/admin")
def admin_dashboard():
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")
    return render_template("admin_dashboard.html")

@app.route("/teacher")
def teacher_dashboard():
    if "role" not in session or session["role"] != "teacher":
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db_connection()
    status_row = conn.execute(
        "SELECT * FROM teacher_status WHERE user_id=?",
        (user_id,)
    ).fetchone()
    conn.close()

    return render_template("teacher_dashboard.html", status_row=status_row)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/add_teacher", methods=["POST"])
def add_teacher():
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    name = request.form["name"]
    email = request.form["email"]
    password = request.form["password"]

    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
            (name, email, password, "teacher")
        )
        conn.commit()
    except:
        conn.close()
        return "Error: Teacher already exists or invalid data"

    conn.close()
    return redirect("/admin")

@app.route("/update_status", methods=["POST"])
def update_status():
    if "role" not in session or session["role"] != "teacher":
        return redirect("/login")

    status = request.form["status"]
    location = request.form["location"]
    user_id = session["user_id"]

    conn = get_db_connection()

    # Check if already exists
    existing = conn.execute(
        "SELECT * FROM teacher_status WHERE user_id=?",
        (user_id,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE teacher_status SET status=?, location=? WHERE user_id=?",
            (status, location, user_id)
        )
    else:
        conn.execute(
            "INSERT INTO teacher_status (user_id, status, location) VALUES (?, ?, ?)",
            (user_id, status, location)
        )

    conn.commit()
    conn.close()

    return redirect("/teacher")


@app.route("/add_location", methods=["POST"])
def add_location():
    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    name = request.form["name"]
    building = request.form["building"]
    floor = request.form["floor"]
    room_number = request.form["room_number"]
    x = request.form["x"]
    y = request.form["y"]

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO locations (name, building, floor, room_number, x, y) VALUES (?, ?, ?, ?, ?, ?)",
        (name, building, floor, room_number, x, y)
    )
    conn.commit()
    conn.close()

    return redirect("/admin")


if __name__ == "__main__":
    app.run(debug=True)
