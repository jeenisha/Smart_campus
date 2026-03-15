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
        location TEXT,
        message TEXT
    )
    """)
    # locations table
    c.execute("""
    CREATE TABLE IF NOT EXISTS locations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        building TEXT,
        floor TEXT,
        room_number TEXT
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
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE teacher_status ADD COLUMN message TEXT")
    print("Message column added successfully")
except:
    print("Message column already exists")

conn.commit()
conn.close()
# ---------- Routes ----------

@app.route("/")
def home():
    return render_template("index.html")
@app.route("/chat", methods=["GET", "POST"])
def chat():

    # Initialize chat history if not exists
    if "chat_history" not in session:
        session["chat_history"] = []

    if request.method == "POST":
        user_msg = request.json["message"]
        msg_lower = user_msg.lower()

        # Save user message
        session["chat_history"].append({
            "role": "user",
            "text": user_msg
        })

        conn = get_db_connection()

        # ------------------ TEACHER CHECK ------------------
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
                # MESSAGE / NOTE / UPDATE / ANNOUNCEMENT
                if any(word in msg_lower for word in ["message", "note", "update", "announcement"]):
                    if status_row["message"]:
                        bot_reply = f"{found_teacher['name']}'s message: {status_row['message']}"
                    else:
                        bot_reply = f"{found_teacher['name']} has not left any message."

                elif "where" in msg_lower:
                    message = status_row["message"]
                    if message:
                        bot_reply = f"{found_teacher['name']} is {status_row['status']} and is in {status_row['location']}. Message: {message}"
                    else:
                        #bot_reply = f"{found_teacher['name']} is {status_row['status']} and is in {status_row['location']}."
                        bot_reply = f"{found_teacher['name']} is currently in {status_row['location']}."
                elif "available" in msg_lower or "free" in msg_lower:
                    bot_reply = f"{found_teacher['name']} is currently {status_row['status']}."
                else:
                    bot_reply = f"{found_teacher['name']} is {status_row['status']} and is in {status_row['location']}."
        else:
            # ------------------ LOCATION CHECK ------------------
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

        # Save bot reply
        session["chat_history"].append({
            "role": "bot",
            "text": bot_reply
        })

        session.modified = True  # IMPORTANT

        return jsonify({"response": bot_reply})

    # On GET request, return page
    return render_template("chat.html")

@app.route("/clear_chat")
def clear_chat():
    session.pop("chat_history", None)
    return redirect("/chat")

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
    
    conn = get_db_connection()

    teachers = conn.execute(
        "SELECT * FROM users WHERE role='teacher'"
    ).fetchall()

    locations = conn.execute(
        "SELECT * FROM locations"
    ).fetchall()

    conn.close()

    return render_template(
        "admin_dashboard.html",
        teachers=teachers,
        locations=locations)


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

@app.route("/delete_teacher/<int:id>")
def delete_teacher(id):

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_db_connection()

    conn.execute(
        "DELETE FROM users WHERE id=?",
        (id,)
    )

    conn.commit()
    conn.close()

    return redirect("/admin")

@app.route("/edit_teacher/<int:id>", methods=["GET", "POST"])
def edit_teacher(id):

    if "role" not in session or session["role"] != "admin":
        return redirect("/login")

    conn = get_db_connection()

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]

        conn.execute(
            "UPDATE users SET name=?, email=?, password=? WHERE id=?",
            (name, email, password, id)
        )

        conn.commit()
        conn.close()

        return redirect("/admin")

    teacher = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (id,)
    ).fetchone()

    conn.close()

    return render_template("edit_teacher.html", teacher=teacher)


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
    message = request.form["message"]

    conn = get_db_connection()

    # Check if already exists
    existing = conn.execute(
        "SELECT * FROM teacher_status WHERE user_id=?",
        (user_id,)
    ).fetchone()

    if existing:
        conn.execute(
            "UPDATE teacher_status SET status=?, location=?, message=? WHERE user_id=?",
            (status, location, message, user_id)
        )
    else:
        conn.execute(
            "INSERT INTO teacher_status (user_id, status, location, message) VALUES (?, ?, ?,?)",
            (user_id, status, location,message)
        )

    conn.commit()
    conn.close()

    return redirect("/teacher")

@app.route("/delete_message", methods=["POST"])
def delete_message():

    if "role" not in session or session["role"] != "teacher":
        return redirect("/login")

    user_id = session["user_id"]

    conn = get_db_connection()

    conn.execute(
        "UPDATE teacher_status SET message='' WHERE user_id=?",
        (user_id,)
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
    #x = request.form["x"]
   # y = request.form["y"]

    conn = get_db_connection()
    conn.execute(
        "INSERT INTO locations (name, building, floor, room_number) VALUES (?, ?, ?, ?)",
        (name, building, floor, room_number)
    )
    conn.commit()
    conn.close()

    return redirect("/admin")


if __name__ == "__main__":
    app.run(debug=True)
