import os
import io
import re
import json
import hashlib
import uuid
from datetime import datetime
from functools import wraps

from flask import Flask, request, render_template, redirect, url_for, flash, session
import mysql.connector
from mysql.connector import Error
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from web3 import Web3
from PyPDF2 import PdfReader

# Optional PDF QR scanning dependencies
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
try:
    import cv2
except ImportError:
    cv2 = None
try:
    import numpy as np
except ImportError:
    np = None

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-secret-key")

# Database settings: preferably set DB_PASSWORD as an environment variable.
DB_CONFIG = {
    "host": os.environ.get("DB_HOST", "127.0.0.1"),
    "user": os.environ.get("DB_USER", "root"),
    "password": os.environ.get("DB_PASSWORD", "Jadhav@1234"),
    "database": os.environ.get("DB_NAME", "blockchain_certificate"),
}


def get_db_connection():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except Error as exc:
        app.logger.exception("Database connection error: %s", exc)
        return None


# Ganache / contract configuration
GANACHE_URL = os.environ.get("GANACHE_URL", "http://127.0.0.1:7545")
CONTRACT_ADDRESS = os.environ.get(
    "CONTRACT_ADDRESS", "0x5f1E738Fb50E2A99D1805ED517c530d30F5Be676"
)
INSTITUTION_NAME = os.environ.get("INSTITUTION_NAME", "CertiChain Institution")
w3 = Web3(Web3.HTTPProvider(GANACHE_URL, request_kwargs={"timeout": 10}))

CONTRACT_ABI = [
    {"inputs":[{"internalType":"address","name":"issuer","type":"address"}],"name":"authorizeIssuer","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"address","name":"issuer","type":"address"}],"name":"removeIssuer","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"string","name":"certificateId","type":"string"},{"internalType":"string","name":"studentName","type":"string"},{"internalType":"string","name":"courseName","type":"string"},{"internalType":"string","name":"institutionName","type":"string"},{"internalType":"string","name":"certificateHash","type":"string"}],"name":"issueCertificate","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"string","name":"certificateId","type":"string"}],"name":"revokeCertificate","outputs":[],"stateMutability":"nonpayable","type":"function"},
    {"inputs":[{"internalType":"string","name":"certificateId","type":"string"}],"name":"certificateExists","outputs":[{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"string","name":"certificateId","type":"string"}],"name":"verifyCertificate","outputs":[{"internalType":"bool","name":"exists","type":"bool"},{"internalType":"bool","name":"valid","type":"bool"}],"stateMutability":"view","type":"function"},
    {"inputs":[{"internalType":"string","name":"certificateId","type":"string"}],"name":"getCertificate","outputs":[{"internalType":"string","name":"","type":"string"},{"internalType":"string","name":"","type":"string"},{"internalType":"string","name":"","type":"string"},{"internalType":"string","name":"","type":"string"},{"internalType":"string","name":"","type":"string"},{"internalType":"uint256","name":"","type":"uint256"},{"internalType":"address","name":"","type":"address"},{"internalType":"bool","name":"","type":"bool"}],"stateMutability":"view","type":"function"},
]

contract = None
try:
    if Web3.is_address(CONTRACT_ADDRESS):
        contract = w3.eth.contract(address=Web3.to_checksum_address(CONTRACT_ADDRESS), abi=CONTRACT_ABI)
except Exception as exc:
    app.logger.warning("Contract configuration error: %s", exc)


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("admin_login"))
        return func(*args, **kwargs)
    return wrapper


def student_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if "student_id" not in session:
            return redirect(url_for("student_login"))
        return func(*args, **kwargs)
    return wrapper


def db_error(message="Database connection failed."):
    flash(message, "danger")
    return None


def save_verification_log(certificate_id, result, blockchain_status):
    """Store a check only when the certificate exists in our SQL database."""
    connection = get_db_connection()
    if connection is None:
        return
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """INSERT INTO verification_logs
               (certificate_id, verifier_name, verifier_email, result, blockchain_status)
               VALUES (%s, %s, %s, %s, %s)""",
            (int(certificate_id), session.get("student_name") or session.get("admin_name") or "Public verifier",
             session.get("student_email") or session.get("admin_email"), result, blockchain_status),
        )
        connection.commit()
    except Error as exc:
        connection.rollback()
        app.logger.warning("Could not save verification log: %s", exc)
    finally:
        if cursor:
            cursor.close()
        connection.close()


def record_blockchain_result(certificate_id, certificate_hash, tx_hash=None, block_number=None, status="Failed"):
    connection = get_db_connection()
    if connection is None:
        return
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """INSERT INTO blockchain_records
               (certificate_id, certificate_hash, transaction_hash, block_number, network, status)
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (certificate_id, certificate_hash, tx_hash, block_number, "Ganache/Ethereum", status),
        )
        connection.commit()
    except Error as exc:
        connection.rollback()
        app.logger.warning("Could not save blockchain record: %s", exc)
    finally:
        if cursor:
            cursor.close()
        connection.close()


@app.route("/")
def home():
    return render_template("index.html")


# ------------------------------ STUDENT REGISTRATION ------------------------------
@app.route("/student/register", methods=["GET", "POST"])
def student_register():
    if request.method == "GET":
        return render_template("student/register.html")

    name = request.form.get("student_name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm = request.form.get("confirm_password", "")
    phone = request.form.get("phone", "").strip()
    department = request.form.get("department", "").strip()
    course = request.form.get("course", "").strip()
    enrollment = request.form.get("enrollment_no", "").strip()
    year_text = request.form.get("admission_year", "").strip()

    if not name or not email or not password:
        flash("Name, email and password are required.", "danger")
        return redirect(url_for("student_register"))
    if confirm and password != confirm:
        flash("Passwords do not match.", "danger")
        return redirect(url_for("student_register"))
    if len(password) < 6:
        flash("Password must contain at least 6 characters.", "danger")
        return redirect(url_for("student_register"))

    year_value = None
    if year_text:
        try:
            year_value = int(year_text)
            if year_value < 1901 or year_value > 2155:
                raise ValueError
        except ValueError:
            flash("Enter a valid admission year.", "danger")
            return redirect(url_for("student_register"))

    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed. Check MySQL settings.", "danger")
        return redirect(url_for("student_register"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT student_id FROM students WHERE LOWER(TRIM(email))=%s", (email,))
        if cursor.fetchone():
            flash("This email is already registered. Please log in.", "warning")
            return redirect(url_for("student_login"))
        if enrollment:
            cursor.execute("SELECT student_id FROM students WHERE enrollment_no=%s", (enrollment,))
            if cursor.fetchone():
                flash("This enrollment number is already registered.", "danger")
                return redirect(url_for("student_register"))

        # The students table MUST have a password column for login to work.
        cursor.execute(
            """INSERT INTO students
               (student_name, email, phone, department, course, enrollment_no,
                admission_year, status, password)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'Pending',%s)""",
            (name, email, phone or None, department or None, course or None,
             enrollment or None, year_value, generate_password_hash(password)),
        )
        connection.commit()
        flash("Registration successful. Please log in.", "success")
        return redirect(url_for("student_login"))
    except Error as exc:
        connection.rollback()
        app.logger.exception("Student registration failed: %s", exc)
        flash("Registration failed. Check the Flask terminal and students table columns.", "danger")
        return redirect(url_for("student_register"))
    finally:
        if cursor:
            cursor.close()
        connection.close()


# ------------------------------ STUDENT LOGIN ------------------------------
@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "GET":
        return render_template("student/login.html")
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return render_template("student/login.html")
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT student_id, student_name, email, password, status FROM students WHERE LOWER(TRIM(email))=%s",
            (email,),
        )
        student = cursor.fetchone()
        if not student:
            flash("Invalid email or password.", "danger")
            return render_template("student/login.html")
        stored = student.get("password") or ""
        # Support Werkzeug hashes; safely migrate legacy plaintext passwords on successful login.
        try:
            matched = check_password_hash(stored, password)
        except (ValueError, TypeError):
            matched = False
        if not matched and stored and stored == password:
            matched = True
            cursor.execute("UPDATE students SET password=%s WHERE student_id=%s",
                           (generate_password_hash(password), student["student_id"]))
            connection.commit()
        if not matched:
            flash("Invalid email or password.", "danger")
            return render_template("student/login.html")
        if student.get("status") == "Inactive":
            flash("Your account is inactive. Contact the administrator.", "warning")
            return render_template("student/login.html")
        session.clear()
        session["student_id"] = student["student_id"]
        session["student_name"] = student["student_name"]
        session["student_email"] = student["email"]
        return redirect(url_for("student_dashboard"))
    except Error as exc:
        app.logger.exception("Student login failed: %s", exc)
        flash("Login failed. Verify that students.password exists in MySQL.", "danger")
        return render_template("student/login.html")
    finally:
        if cursor:
            cursor.close()
        connection.close()


# ------------------------------ ADMIN REGISTRATION / LOGIN ------------------------------
@app.route("/admin/register", methods=["GET", "POST"])
def admin_register():
    # For a real deployment, protect admin registration or create admins manually in SQL.
    if request.method == "GET":
        return render_template("admin/register.html")
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "")
    if not name or not email or not password:
        flash("Name, email and password are required.", "danger")
        return render_template("admin/register.html")
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/register.html")
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("INSERT INTO admins (name,email,phone,password) VALUES (%s,%s,%s,%s)",
                       (name, email, phone or None, generate_password_hash(password)))
        connection.commit()
        flash("Admin account created. Please log in.", "success")
        return redirect(url_for("admin_login"))
    except Error as exc:
        connection.rollback()
        app.logger.warning("Admin registration failed: %s", exc)
        flash("Admin registration failed. The email may already exist.", "danger")
        return render_template("admin/register.html")
    finally:
        if cursor:
            cursor.close()
        connection.close()


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        return render_template("admin/login.html")
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return render_template("admin/login.html")
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT admin_id,name,email,password FROM admins WHERE LOWER(TRIM(email))=%s", (email,))
        admin = cursor.fetchone()
        if not admin or not check_password_hash(admin["password"], password):
            flash("Invalid email or password.", "danger")
            return render_template("admin/login.html")
        session.clear()
        session["admin_id"] = admin["admin_id"]
        session["admin_name"] = admin["name"]
        session["admin_email"] = admin["email"]
        return redirect(url_for("admin_dashboard"))
    except (Error, ValueError, TypeError) as exc:
        app.logger.exception("Admin login error: %s", exc)
        flash("Unable to log in. Check admin table and password hash.", "danger")
        return render_template("admin/login.html")
    finally:
        if cursor:
            cursor.close()
        connection.close()


# ------------------------------ STUDENT PAGES ------------------------------

@app.route("/student/dashboard")
def student_dashboard():
    # Check whether a student is logged in
    if "student_id" not in session:
        flash("Please log in as a student.", "warning")
        return redirect(url_for("student_login"))

    connection = get_db_connection()

    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("student_login"))

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        # Fetch only the currently logged-in student's information
        cursor.execute("""
            SELECT
                student_id,
                student_name,
                email,
                phone,
                department,
                course,
                enrollment_no,
                admission_year,
                status,
                created_at
            FROM students
            WHERE student_id = %s
        """, (session["student_id"],))

        student = cursor.fetchone()

        if student is None:
            session.clear()
            flash("Student account not found. Please log in again.", "danger")
            return redirect(url_for("student_login"))

        # Fetch certificates belonging to this student
        cursor.execute("""
            SELECT
                certificate_id,
                student_id,
                certificate_type,
                course,
                issue_date,
                certificate_hash,
                status,
                blockchain_status,
                transaction_hash
            FROM certificates
            WHERE student_id = %s
            ORDER BY certificate_id DESC
        """, (student["student_id"],))

        certificates = cursor.fetchall()

        return render_template(
            "student/dashboard.html",
            student=student,
            certificates=certificates
        )

    except Exception as e:
        print("STUDENT DASHBOARD ERROR:", repr(e))
        flash("Unable to load student dashboard.", "danger")
        return redirect(url_for("student_login"))

    finally:
        if cursor is not None:
            cursor.close()
        connection.close()

@app.route("/view-certificate/<int:certificate_id>")
def view_certificate(certificate_id):
    if "student_id" not in session:
        flash("Please log in as a student.", "warning")
        return redirect(url_for("student_login"))

    connection = get_db_connection()

    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("student_dashboard"))

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                c.certificate_id,
                c.certificate_type,
                c.course,
                c.issue_date,
                c.certificate_hash,
                c.status,
                c.blockchain_status,
                c.transaction_hash,
                s.student_id,
                s.student_name,
                s.department
            FROM certificates c
            JOIN students s
                ON c.student_id = s.student_id
            WHERE c.certificate_id = %s
              AND c.student_id = %s
        """, (certificate_id, session["student_id"]))

        certificate = cursor.fetchone()

        if certificate is None:
            flash("Certificate not found or access denied.", "danger")
            return redirect(url_for("student_dashboard"))

        return render_template(
            "student/certificate.html",
            certificate=certificate
        )

    except Exception as e:
        print("VIEW CERTIFICATE ERROR:", repr(e))
        flash(f"Certificate loading failed: {str(e)}", "danger")
        return redirect(url_for("student_dashboard"))

    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


@app.route("/verified_certificates")
@student_required
def verified_certificates():
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("student_dashboard"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""SELECT v.*, c.certificate_hash, c.certificate_type, c.course, c.issue_date
                          FROM verification_logs v JOIN certificates c ON c.certificate_id=v.certificate_id
                          WHERE v.verifier_email=%s ORDER BY v.verification_id DESC""",
                       (session.get("student_email"),))
        records = cursor.fetchall()
        valid_certificates = [r for r in records if r["result"] == "Valid"]
        invalid_certificates = [r for r in records if r["result"] == "Invalid"]
        return render_template("student/verified_certificates.html",
                               valid_certificates=valid_certificates,
                               invalid_certificates=invalid_certificates)
    finally:
        if cursor:
            cursor.close()
        connection.close()


# ------------------------------ ADMIN DASHBOARD / STUDENTS ------------------------------
@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_login"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT COUNT(*) total FROM students")
        total_students = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) total FROM certificates")
        total_certificates = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) total FROM certificates WHERE status='Verified'")
        verified_certificates = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) total FROM certificates WHERE status='Revoked'")
        revoked_certificates = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) total FROM verification_logs")
        total_verifications = cursor.fetchone()["total"]
        return render_template("admin/dashboard.html", total_students=total_students,
                               total_certificates=total_certificates,
                               verified_certificates=verified_certificates,
                               revoked_certificates=revoked_certificates,
                               total_verifications=total_verifications)
    except Error as exc:
        app.logger.exception("Admin dashboard error: %s", exc)
        flash("Unable to load dashboard data.", "danger")
        return render_template("admin/dashboard.html", total_students=0, total_certificates=0,
                               verified_certificates=0, revoked_certificates=0, total_verifications=0)
    finally:
        if cursor:
            cursor.close()
        connection.close()


@app.route("/admin/students")
@admin_required
def admin_students():
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_dashboard"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""SELECT s.*, COUNT(c.certificate_id) AS certificate_count
                          FROM students s LEFT JOIN certificates c ON c.student_id=s.student_id
                          GROUP BY s.student_id ORDER BY s.student_id DESC""")
        students = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) total FROM students")
        total_students = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) total FROM students WHERE status='Verified'")
        verified_students = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) total FROM students WHERE status='Pending'")
        pending_students = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) total FROM students WHERE status='Inactive'")
        inactive_students = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) total FROM certificates")
        total_certificates = cursor.fetchone()["total"]
        return render_template("admin/student.html", students=students, total_students=total_students,
                               verified_students=verified_students, pending_students=pending_students,
                               inactive_students=inactive_students, total_certificates=total_certificates)
    except Error as exc:
        app.logger.exception("Unable to load students: %s", exc)
        flash("Unable to load students. Check the Flask terminal for the SQL error.", "danger")
        return render_template("admin/student.html", students=[], total_students=0,
                               verified_students=0, pending_students=0, inactive_students=0,
                               total_certificates=0)
    finally:
        if cursor:
            cursor.close()
        connection.close()


@app.route("/admin/students/<int:student_id>")
@admin_required
def admin_student_details(student_id):
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_students"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students WHERE student_id=%s", (student_id,))
        student = cursor.fetchone()
        if not student:
            return "Student not found", 404
        cursor.execute("SELECT * FROM certificates WHERE student_id=%s ORDER BY certificate_id DESC", (student_id,))
        certificates = cursor.fetchall()
        return render_template("admin/student_details.html", student=student, certificates=certificates)
    finally:
        if cursor:
            cursor.close()
        connection.close()


@app.route("/admin/students/<int:student_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_student(student_id):
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_students"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        if request.method == "POST":
            name = request.form.get("student_name", request.form.get("name", "")).strip()
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip()
            department = request.form.get("department", "").strip()
            course = request.form.get("course", "").strip()
            enrollment = request.form.get("enrollment_no", "").strip()
            status = request.form.get("status", "Pending")
            if status not in ("Verified", "Pending", "Inactive"):
                status = "Pending"
            cursor.execute("""UPDATE students SET student_name=%s,email=%s,phone=%s,department=%s,
                              course=%s,enrollment_no=%s,status=%s WHERE student_id=%s""",
                           (name, email, phone or None, department or None, course or None,
                            enrollment or None, status, student_id))
            connection.commit()
            flash("Student updated successfully.", "success")
            return redirect(url_for("admin_student_details", student_id=student_id))
        cursor.execute("SELECT * FROM students WHERE student_id=%s", (student_id,))
        student = cursor.fetchone()
        if not student:
            return "Student not found", 404
        return render_template("admin/edit_student.html", student=student)
    except Error as exc:
        connection.rollback()
        app.logger.exception("Edit student error: %s", exc)
        flash("Unable to update student. Check if email/enrollment number is already used.", "danger")
        return redirect(url_for("admin_students"))
    finally:
        if cursor:
            cursor.close()
        connection.close()


@app.route("/admin/students/<int:student_id>/delete", methods=["POST"])
@admin_required
def delete_student(student_id):
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_students"))
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM students WHERE student_id=%s", (student_id,))
        if cursor.rowcount == 0:
            flash("Student not found.", "warning")
        else:
            connection.commit()
            flash("Student deleted successfully.", "success")
    except Error as exc:
        connection.rollback()
        app.logger.warning("Delete student failed: %s", exc)
        flash("Student cannot be deleted while certificates are linked to them. Deactivate the student instead.", "danger")
    finally:
        if cursor:
            cursor.close()
        connection.close()
    return redirect(url_for("admin_students"))


# ------------------------------ ISSUE / LIST CERTIFICATES ------------------------------
@app.route("/admin/certificate")
@admin_required
def admin_certificates():
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_dashboard"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""SELECT c.*, s.student_name, s.email AS student_email
                          FROM certificates c JOIN students s ON s.student_id=c.student_id
                          ORDER BY c.certificate_id DESC""")
        certificates = cursor.fetchall()
        return render_template("admin/certificate.html", certificates=certificates)
    except Error as exc:
        app.logger.exception("Load certificates error: %s", exc)
        flash("Unable to load certificates.", "danger")
        return render_template("admin/certificate.html", certificates=[])
    finally:
        if cursor:
            cursor.close()
        connection.close()


@app.route("/admin/issue-certificate", methods=["GET", "POST"])
@admin_required
def issue_certificate():
    if request.method == "GET":
        connection = get_db_connection()
        if connection is None:
            flash("Database connection failed.", "danger")
            return render_template("admin/issue_certificate.html", students=[])
        cursor = None
        try:
            cursor = connection.cursor(dictionary=True)
            cursor.execute("SELECT student_id,student_name,email,course FROM students WHERE status <> 'Inactive' ORDER BY student_name")
            students = cursor.fetchall()
            return render_template("admin/issue_certificate.html", students=students)
        except Error as exc:
            app.logger.exception("LOAD STUDENTS ERROR: %s", exc)
            flash("Unable to load students. Confirm students table columns and database connection.", "danger")
            return render_template("admin/issue_certificate.html", students=[])
        finally:
            if cursor:
                cursor.close()
            connection.close()

    student_id_text = request.form.get("student_id", "").strip()
    certificate_type = request.form.get("certificate_type", "").strip()
    course = request.form.get("course", "").strip()
    issue_date = request.form.get("issue_date", "").strip()
    if not student_id_text.isdigit() or not certificate_type or not issue_date:
        flash("Select a student and provide certificate type and issue date.", "danger")
        return redirect(url_for("issue_certificate"))
    try:
        datetime.strptime(issue_date, "%Y-%m-%d")
    except ValueError:
        flash("Enter a valid issue date.", "danger")
        return redirect(url_for("issue_certificate"))

    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("issue_certificate"))
    cursor = None
    certificate_id = None
    cert_hash = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT student_id,student_name,email,course,status FROM students WHERE student_id=%s", (int(student_id_text),))
        student = cursor.fetchone()
        if not student or student["status"] == "Inactive":
            flash("Selected student does not exist or is inactive.", "danger")
            return redirect(url_for("issue_certificate"))
        effective_course = course or student.get("course") or certificate_type
        unique_nonce = uuid.uuid4().hex
        hash_payload = {"student_id": student["student_id"], "student_name": student["student_name"],
                        "email": student["email"].strip().lower(), "certificate_type": certificate_type,
                        "course": effective_course, "issue_date": issue_date, "nonce": unique_nonce}
        cert_hash = hashlib.sha256(json.dumps(hash_payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        cursor.execute("""INSERT INTO certificates
                          (student_id,certificate_type,course,issue_date,certificate_hash,status,blockchain_status)
                          VALUES (%s,%s,%s,%s,%s,'Verified','Pending')""",
                       (student["student_id"], certificate_type, effective_course, issue_date, cert_hash))
        certificate_id = cursor.lastrowid
        # Commit the SQL record first; the numeric DB id is also the contract's string ID.
        connection.commit()
    except Error as exc:
        connection.rollback()
        app.logger.exception("Certificate database insert failed: %s", exc)
        flash("Certificate could not be saved. Check the database error in terminal.", "danger")
        return redirect(url_for("issue_certificate"))
    finally:
        if cursor:
            cursor.close()
        connection.close()

    # Issue to blockchain after DB insert. SQL certificate remains visible even if Ganache fails.
    tx_hash = None
    block_number = None
    chain_status = "Failed"
    chain_error = None
    try:
        if contract is None or not w3.is_connected():
            raise RuntimeError("Ganache or smart contract is not available.")
        accounts = w3.eth.accounts
        if not accounts:
            raise RuntimeError("Ganache has no unlocked accounts.")
        issuer = accounts[0]
        tx_hash_bytes = contract.functions.issueCertificate(
            str(certificate_id), student["student_name"], effective_course,
            INSTITUTION_NAME, cert_hash
        ).transact({"from": issuer})
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash_bytes, timeout=120)
        if receipt.status != 1:
            raise RuntimeError("Blockchain transaction reverted.")
        tx_hash = tx_hash_bytes.hex()
        block_number = receipt.blockNumber
        chain_status = "Confirmed"
    except Exception as exc:
        chain_error = str(exc)
        app.logger.exception("Blockchain issue failed: %s", exc)

    connection = get_db_connection()
    if connection is not None:
        cursor = None
        try:
            cursor = connection.cursor()
            cursor.execute("UPDATE certificates SET blockchain_status=%s, transaction_hash=%s WHERE certificate_id=%s",
                           (chain_status, tx_hash, certificate_id))
            connection.commit()
        except Error as exc:
            connection.rollback()
            app.logger.warning("Could not update certificate blockchain status: %s", exc)
        finally:
            if cursor:
                cursor.close()
            connection.close()
    record_blockchain_result(certificate_id, cert_hash, tx_hash, block_number, chain_status)

    if chain_status == "Confirmed":
        flash(f"Certificate #{certificate_id} issued and recorded on blockchain.", "success")
    else:
        flash(f"Certificate #{certificate_id} saved in database, but blockchain recording failed: {chain_error}", "warning")
    return redirect(url_for("certificate_details", certificate_id=certificate_id))


@app.route("/admin/certificate/<int:certificate_id>")
@admin_required
def certificate_details(certificate_id):
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_certificates"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""SELECT c.*, s.student_name, s.email AS student_email, s.department,
                          s.enrollment_no FROM certificates c JOIN students s ON s.student_id=c.student_id
                          WHERE c.certificate_id=%s""", (certificate_id,))
        certificate = cursor.fetchone()
        if not certificate:
            return "Certificate not found", 404
        return render_template("admin/certificate_success.html", certificate=certificate)
    finally:
        if cursor:
            cursor.close()
        connection.close()


@app.route("/admin/revoked_certificate")
@admin_required
def revoked_certificates():
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_dashboard"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""SELECT c.*,s.student_name,s.email AS student_email FROM certificates c
                          JOIN students s ON s.student_id=c.student_id WHERE c.status='Revoked'
                          ORDER BY c.revoked_at DESC,c.certificate_id DESC""")
        certificates = cursor.fetchall()
        return render_template("admin/revoked_certificate.html", certificates=certificates,
                               total_revoked=len(certificates))
    finally:
        if cursor:
            cursor.close()
        connection.close()


@app.route("/admin/certificate/<int:certificate_id>/revoke", methods=["POST"])
@admin_required
def revoke_certificate(certificate_id):
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_certificates"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT certificate_id,certificate_hash,status FROM certificates WHERE certificate_id=%s", (certificate_id,))
        cert = cursor.fetchone()
        if not cert:
            return "Certificate not found", 404
        reason = request.form.get("revocation_reason", "Revoked by administrator").strip() or "Revoked by administrator"
        chain_ok = False
        tx_hash = None
        block_number = None
        try:
            if contract is None or not w3.is_connected():
                raise RuntimeError("Ganache or smart contract is unavailable")
            accounts = w3.eth.accounts
            if not accounts:
                raise RuntimeError("No unlocked Ganache account")
            tx = contract.functions.revokeCertificate(str(certificate_id)).transact({"from": accounts[0]})
            receipt = w3.eth.wait_for_transaction_receipt(tx, timeout=120)
            if receipt.status != 1:
                raise RuntimeError("Revoke transaction reverted")
            tx_hash, block_number, chain_ok = tx.hex(), receipt.blockNumber, True
        except Exception as exc:
            app.logger.warning("Blockchain revoke failed: %s", exc)
        cursor.execute("""UPDATE certificates SET status='Revoked',revoked_at=NOW(),revoked_by=%s,
                          revocation_reason=%s,blockchain_status=%s,transaction_hash=COALESCE(%s,transaction_hash)
                          WHERE certificate_id=%s""",
                       (session.get("admin_name", "Administrator"), reason,
                        "Confirmed" if chain_ok else "Failed", tx_hash, certificate_id))
        connection.commit()
        record_blockchain_result(certificate_id, cert["certificate_hash"], tx_hash, block_number,
                                 "Confirmed" if chain_ok else "Failed")
        flash("Certificate revoked." + (" Blockchain updated." if chain_ok else " Database updated, but blockchain revocation failed."),
              "success" if chain_ok else "warning")
    except Error as exc:
        connection.rollback()
        app.logger.exception("Revoke certificate DB error: %s", exc)
        flash("Could not revoke certificate.", "danger")
    finally:
        if cursor:
            cursor.close()
        connection.close()
    return redirect(url_for("certificate_details", certificate_id=certificate_id))


# ------------------------------ BLOCKCHAIN RECORDS ------------------------------
@app.route("/admin/blockchain_records")
@admin_required
def blockchain_records():
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_dashboard"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""SELECT b.*,s.student_name FROM blockchain_records b
                          JOIN certificates c ON c.certificate_id=b.certificate_id
                          JOIN students s ON s.student_id=c.student_id ORDER BY b.created_at DESC""")
        records = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) total FROM blockchain_records")
        total_records = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) total FROM blockchain_records WHERE status='Confirmed'")
        confirmed_records = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) total FROM blockchain_records WHERE status='Pending'")
        pending_records = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) total FROM blockchain_records WHERE status='Failed'")
        failed_records = cursor.fetchone()["total"]
        return render_template("admin/blockchain_records.html", blockchain_records=records,
                               total_records=total_records, confirmed_records=confirmed_records,
                               pending_records=pending_records, failed_records=failed_records)
    finally:
        if cursor:
            cursor.close()
        connection.close()


@app.route("/admin/blockchain/<int:record_id>")
@admin_required
def blockchain_record_details(record_id):
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("blockchain_records"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""SELECT b.*,c.course,c.issue_date,c.certificate_type,s.student_name,s.email
                          FROM blockchain_records b JOIN certificates c ON c.certificate_id=b.certificate_id
                          JOIN students s ON s.student_id=c.student_id WHERE b.record_id=%s""", (record_id,))
        record = cursor.fetchone()
        if not record:
            return "Blockchain record not found", 404
        return render_template("admin/blockchain_record_details.html", record=record)
    finally:
        if cursor:
            cursor.close()
        connection.close()


# ------------------------------ CERTIFICATE VERIFICATION ------------------------------
def extract_certificate_id(pdf_bytes):
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
        patterns = [r"Certificate\s*ID\s*[:=\-]?\s*([A-Za-z0-9_-]+)",
                    r"Certificate\s*#\s*([A-Za-z0-9_-]+)"]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
    except Exception as exc:
        app.logger.warning("PDF text extraction failed: %s", exc)
    if fitz is not None and cv2 is not None and np is not None:
        doc = None
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            detector = cv2.QRCodeDetector()
            for page in doc:
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
                data, _, _ = detector.detectAndDecode(img)
                if data:
                    match = re.search(r"certificateId\s*[:=]\s*['\"]?([A-Za-z0-9_-]+)", data, re.I)
                    if match:
                        return match.group(1)
                    if re.fullmatch(r"[A-Za-z0-9_-]+", data.strip()):
                        return data.strip()
        except Exception as exc:
            app.logger.warning("QR extraction failed: %s", exc)
        finally:
            if doc:
                doc.close()
    return None


@app.route("/verify", methods=["GET", "POST"])
def verify_certificate():
    if request.method == "GET":
        return render_template("verifier/verify.html")
    certificate_id = request.form.get("certificate_id", "").strip()
    uploaded = request.files.get("certificate_file")
    if not certificate_id and uploaded and uploaded.filename:
        pdf_bytes = uploaded.read()
        certificate_id = extract_certificate_id(pdf_bytes) or ""
    if not certificate_id:
        return render_template("verifier/verification_result.html", status="CANNOT VERIFY", certificate=None,
                               certificate_id="", message="Enter a certificate ID or upload a readable PDF with a certificate ID.")
    if not w3.is_connected() or contract is None:
        return render_template("verifier/verification_result.html", status="CANNOT VERIFY", certificate=None,
                               certificate_id=certificate_id, message="Ganache blockchain is not connected.")
    try:
        exists, valid = contract.functions.verifyCertificate(str(certificate_id)).call()
        if not exists:
            # Only log when this ID maps to a local DB certificate.
            connection = get_db_connection()
            local = None
            if connection:
                cur = connection.cursor(dictionary=True)
                cur.execute("SELECT certificate_id FROM certificates WHERE certificate_id=%s", (int(certificate_id),)) if certificate_id.isdigit() else None
                local = cur.fetchone() if certificate_id.isdigit() else None
                cur.close(); connection.close()
            if local:
                save_verification_log(local["certificate_id"], "Invalid", "Failed")
            return render_template("verifier/verification_result.html", status="INVALID", certificate=None,
                                   certificate_id=certificate_id, message="Certificate was not found on blockchain.")
        data = contract.functions.getCertificate(str(certificate_id)).call()
        certificate = {"certificate_id": data[0], "student_name": data[1], "course_name": data[2],
                       "institution_name": data[3], "certificate_hash": data[4], "issue_date": data[5],
                       "issuer": data[6], "revoked": data[7]}
        status = "VALID" if valid and not certificate["revoked"] else "INVALID"
        # Compare blockchain record with DB hash/status, not just the certificate ID.
        local_certificate = None
        if str(certificate_id).isdigit():
            connection = get_db_connection()
            if connection:
                cur = connection.cursor(dictionary=True)
                cur.execute("SELECT certificate_id,certificate_hash,status,blockchain_status FROM certificates WHERE certificate_id=%s", (int(certificate_id),))
                local_certificate = cur.fetchone()
                cur.close(); connection.close()
        if not local_certificate or local_certificate["certificate_hash"] != certificate["certificate_hash"] or local_certificate["status"] == "Revoked":
            status = "INVALID"
        if local_certificate:
            save_verification_log(local_certificate["certificate_id"], "Valid" if status == "VALID" else "Invalid",
                                  local_certificate.get("blockchain_status", "Failed"))
        return render_template("verifier/verification_result.html", status=status, certificate=certificate,
                               certificate_id=certificate_id, message="Certificate verification completed.")
    except Exception as exc:
        app.logger.exception("Blockchain verification error: %s", exc)
        return render_template("verifier/verification_result.html", status="CANNOT VERIFY", certificate=None,
                               certificate_id=certificate_id, message="Could not call the smart contract. Check contract address, ABI and Ganache network.")


@app.route("/admin/verifications")
@admin_required
def admin_verification():
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_dashboard"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""SELECT v.*,c.certificate_hash,c.certificate_type,c.course,s.student_name
                          FROM verification_logs v JOIN certificates c ON c.certificate_id=v.certificate_id
                          JOIN students s ON s.student_id=c.student_id ORDER BY v.verification_id DESC""")
        return render_template("admin/verification.html", verifications=cursor.fetchall())
    finally:
        if cursor:
            cursor.close()
        connection.close()


# ------------------------------ ADMIN SETTINGS / PROFILE ------------------------------
@app.route("/admin/settings")
@admin_required
def admin_settings():
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_dashboard"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT admin_id,name,email,phone,role,created_at FROM admins WHERE admin_id=%s", (session["admin_id"],))
        admin = cursor.fetchone()
        if not admin:
            session.clear()
            return redirect(url_for("admin_login"))
        return render_template("admin/setting.html", admin=admin)
    finally:
        if cursor:
            cursor.close()
        connection.close()


@app.route("/admin/profile/update", methods=["POST"])
@admin_required
def update_profile():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    if not name or not email:
        flash("Name and email are required.", "danger")
        return redirect(url_for("admin_settings"))
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_settings"))
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("UPDATE admins SET name=%s,email=%s,phone=%s WHERE admin_id=%s",
                       (name, email, phone or None, session["admin_id"]))
        connection.commit()
        session["admin_name"], session["admin_email"] = name, email
        flash("Profile updated successfully.", "success")
    except Error as exc:
        connection.rollback()
        app.logger.warning("Admin profile update failed: %s", exc)
        flash("Profile update failed. Email may already be in use.", "danger")
    finally:
        if cursor:
            cursor.close()
        connection.close()
    return redirect(url_for("admin_settings"))


@app.route("/admin/password/change", methods=["POST"])
@admin_required
def change_password():
    current = request.form.get("current_password", "")
    new = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    if len(new) < 6:
        flash("New password must contain at least 6 characters.", "danger")
        return redirect(url_for("admin_settings"))
    if new != confirm:
        flash("New passwords do not match.", "danger")
        return redirect(url_for("admin_settings"))
    connection = get_db_connection()
    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_settings"))
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT password FROM admins WHERE admin_id=%s", (session["admin_id"],))
        admin = cursor.fetchone()
        if not admin or not check_password_hash(admin["password"], current):
            flash("Current password is incorrect.", "danger")
            return redirect(url_for("admin_settings"))
        cursor.execute("UPDATE admins SET password=%s WHERE admin_id=%s",
                       (generate_password_hash(new), session["admin_id"]))
        connection.commit()
        flash("Password changed successfully.", "success")
    except Error as exc:
        connection.rollback()
        app.logger.exception("Password update error: %s", exc)
        flash("Failed to change password.", "danger")
    finally:
        if cursor:
            cursor.close()
        connection.close()
    return redirect(url_for("admin_settings"))


@app.route("/admin/logout")
def admin_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("admin_login"))


@app.route("/student/logout")
def student_logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("student_login"))


@app.route("/login")
def login():
    return redirect(url_for("student_login"))


@app.route("/blockchain-test")
def blockchain_test():
    try:
        connected = w3.is_connected()

        result = {
            "connected": connected,
            "contract_address": CONTRACT_ADDRESS,
            "contract_configured": contract is not None
        }

        if connected:
            result["chain_id"] = w3.eth.chain_id
            result["contract_deployed"] = (
                len(
                    w3.eth.get_code(
                        Web3.to_checksum_address(CONTRACT_ADDRESS)
                    )
                ) > 0
            )
        else:
            result["contract_deployed"] = False

        return result

    except Exception as exc:
        app.logger.exception("Blockchain test failed")
        return {"connected": False, "error": str(exc)}, 500

    
if __name__ == "__main__":
    print(app.url_map)
    app.run(debug=True)
