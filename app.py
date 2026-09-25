from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector

app = Flask(__name__)

app.secret_key = "certificate_verification_secret"


# =========================
# MySQL Connection
# =========================

def get_db_connection():
    connection = mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="Rudrayani@123",
        database="certificate_db"
    )

    return connection


# =========================
# Home
# =========================

@app.route("/")
def home():
    return render_template("index.html")


# =========================
# Register
# =========================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email = %s",
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            flash("Email already registered!", "error")

            cursor.close()
            connection.close()

            return redirect(url_for("register"))

        query = """
            INSERT INTO users (name, email, password, role)
            VALUES (%s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (name, email, password, role)
        )

        connection.commit()

        cursor.close()
        connection.close()

        flash("Registration successful! Please login.", "success")

        return redirect(url_for("login"))

    return render_template("register.html")


# =========================
# Login
# =========================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT * FROM users
            WHERE email = %s AND password = %s
        """

        cursor.execute(query, (email, password))

        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if user:

            # Save login information
            session["user_id"] = user["id"]
            session["role"] = user["role"]

            flash("Login successful!", "success")

            if user["role"] == "student":
                return redirect(url_for("student_dashboard"))

            elif user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))

        else:

            flash("Invalid email or password", "error")

    return render_template("login.html")


# =========================
# Student Dashboard
# =========================

@app.route("/student-dashboard")
def student_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "student":
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM certificates
        WHERE student_id = %s
        ORDER BY id DESC
        """,
        (session["user_id"],)
    )

    certificates = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
    "student/student_dashboard.html",
    certificates=certificates
    )

# =========================
# View Certificate
# =========================

@app.route("/view-certificate/<certificate_id>")
def view_certificate(certificate_id):

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "student":
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM certificates
        WHERE certificate_id = %s
        AND student_id = %s
        """,
        (certificate_id, session["user_id"])
    )

    certificate = cursor.fetchone()

    cursor.close()
    connection.close()

    if certificate is None:
        flash("Certificate not found.", "error")
        return redirect(url_for("student_dashboard"))

    return render_template(
        "certificate.html",
        certificate=certificate
    )

# =========================
# Logout
# =========================

@app.route("/logout")
def logout():

    session.clear()

    flash("You have been logged out successfully.", "success")

    return redirect(url_for("login"))


# =========================
# Admin Dashboard
# =========================

@app.route("/admin-dashboard")
def admin_dashboard():

    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return redirect(url_for("login"))

    return render_template("admin_dashboard.html")


# =========================
# Run Flask
# =========================

if __name__ == "__main__":
    app.run(debug=True)