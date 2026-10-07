from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)

import mysql.connector
from mysql.connector import Error

from werkzeug.security import generate_password_hash, check_password_hash

from web3 import Web3

import re
import io


# Optional PDF / QR libraries
try:
    import fitz
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


# =========================================================
# FLASK APPLICATION
# =========================================================

app = Flask(__name__)

app.secret_key = "certificate_verification_secret"


# =========================================================
# MYSQL DATABASE
# =========================================================

def get_db_connection():

    try:

        connection = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="Rudrayani@123",
            database="certificate_db"
        )

        return connection

    except Error as e:

        print("Database connection error:", e)

        return None


# =========================================================
# BLOCKCHAIN CONFIGURATION
# =========================================================

GANACHE_URL = "http://127.0.0.1:7545"

CONTRACT_ADDRESS = "0x460deEaE67225f91642f2626636206Cc5259F649"


# Connect to Ganache
w3 = Web3(
    Web3.HTTPProvider(GANACHE_URL)
)


# =========================================================
# SMART CONTRACT ABI
# =========================================================

CONTRACT_ABI = [

    {
        "inputs": [
            {
                "internalType": "address",
                "name": "issuer",
                "type": "address"
            }
        ],
        "name": "authorizeIssuer",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },

    {
        "inputs": [
            {
                "internalType": "address",
                "name": "issuer",
                "type": "address"
            }
        ],
        "name": "removeIssuer",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },

    {
        "inputs": [
            {
                "internalType": "string",
                "name": "certificateId",
                "type": "string"
            },
            {
                "internalType": "string",
                "name": "studentName",
                "type": "string"
            },
            {
                "internalType": "string",
                "name": "courseName",
                "type": "string"
            },
            {
                "internalType": "string",
                "name": "institutionName",
                "type": "string"
            },
            {
                "internalType": "string",
                "name": "certificateHash",
                "type": "string"
            }
        ],
        "name": "issueCertificate",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },

    {
        "inputs": [
            {
                "internalType": "string",
                "name": "certificateId",
                "type": "string"
            }
        ],
        "name": "revokeCertificate",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },

    {
        "inputs": [
            {
                "internalType": "string",
                "name": "certificateId",
                "type": "string"
            }
        ],
        "name": "certificateExists",
        "outputs": [
            {
                "internalType": "bool",
                "name": "",
                "type": "bool"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },

    {
        "inputs": [
            {
                "internalType": "string",
                "name": "certificateId",
                "type": "string"
            }
        ],
        "name": "verifyCertificate",
        "outputs": [
            {
                "internalType": "bool",
                "name": "exists",
                "type": "bool"
            },
            {
                "internalType": "bool",
                "name": "valid",
                "type": "bool"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },

    {
        "inputs": [
            {
                "internalType": "string",
                "name": "certificateId",
                "type": "string"
            }
        ],
        "name": "getCertificate",
        "outputs": [
            {
                "internalType": "string",
                "name": "",
                "type": "string"
            },
            {
                "internalType": "string",
                "name": "",
                "type": "string"
            },
            {
                "internalType": "string",
                "name": "",
                "type": "string"
            },
            {
                "internalType": "string",
                "name": "",
                "type": "string"
            },
            {
                "internalType": "string",
                "name": "",
                "type": "string"
            },
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            },
            {
                "internalType": "address",
                "name": "",
                "type": "address"
            },
            {
                "internalType": "bool",
                "name": "",
                "type": "bool"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }

]


# Create contract object
contract = w3.eth.contract(
    address=Web3.to_checksum_address(CONTRACT_ADDRESS),
    abi=CONTRACT_ABI
)


# =========================================================
# ADMIN REQUIRED
# =========================================================

def admin_required(function):

    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        if session.get("role") != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("login"))

        return function(*args, **kwargs)

    wrapper.__name__ = function.__name__

    return wrapper


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template("index.html")


# =========================================================
# REGISTER
# =========================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "student")

        if not name or not email or not password:

            flash("Please fill all required fields.", "error")

            return redirect(url_for("register"))

        # Do not allow public users to create admin accounts
        if role not in ["student", "verifier"]:

            role = "student"

        connection = get_db_connection()

        if connection is None:

            flash("Database connection failed.", "error")

            return redirect(url_for("register"))

        cursor = connection.cursor(dictionary=True)

        try:

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            existing_user = cursor.fetchone()

            if existing_user:

                flash("Email already registered.", "error")

                return redirect(url_for("register"))

            # Keep password compatible with your current database.
            cursor.execute(
                """
                INSERT INTO users
                (
                    name,
                    email,
                    password,
                    role
                )
                VALUES
                (%s, %s, %s, %s)
                """,
                (
                    name,
                    email,
                    password,
                    role
                )
            )

            connection.commit()

            flash(
                "Registration successful. Please login.",
                "success"
            )

            return redirect(url_for("login"))

        except Error as e:

            connection.rollback()

            print("Registration error:", e)

            flash(
                "Registration failed.",
                "error"
            )

            return redirect(url_for("register"))

        finally:

            cursor.close()
            connection.close()

    return render_template("student/register.html")


# =========================================================
# LOGIN
# =========================================================
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter email and password.", "error")
            return render_template("student/login.html")

        connection = get_db_connection()

        if connection is None:
            flash("Database connection failed.", "error")
            return render_template("student/login.html")

        cursor = connection.cursor(dictionary=True)

        try:

            cursor.execute(
                """
                SELECT id, name, email, password, role
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            user = cursor.fetchone()

        except Error as e:

            print("Login database error:", e)
            user = None

        finally:

            cursor.close()
            connection.close()

        # -------------------------------------------------
        # USER NOT FOUND
        # -------------------------------------------------
        if user is None:

            flash("Invalid email or password.", "error")

            return render_template(
                "student/login.html"
            )

        # -------------------------------------------------
        # PASSWORD CHECK
        # -------------------------------------------------
        stored_password = user["password"]

        password_correct = False

        # Your current database uses plain-text passwords
        if stored_password == password:

            password_correct = True

        else:

            # Also support hashed passwords
            try:
                password_correct = check_password_hash(
                    stored_password,
                    password
                )
            except Exception:
                password_correct = False

        # -------------------------------------------------
        # WRONG PASSWORD
        # -------------------------------------------------
        if not password_correct:

            flash("Invalid email or password.", "error")

            return render_template(
                "student/login.html"
            )

        # -------------------------------------------------
        # LOGIN SUCCESS
        # -------------------------------------------------
        session.clear()

        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["email"] = user["email"]
        session["role"] = user["role"]

        flash(
            "Login successful!",
            "success"
        )

        # -------------------------------------------------
        # ROLE REDIRECT
        # -------------------------------------------------
        if user["role"] == "student":

            return redirect(
                url_for("student_dashboard")
            )

        if user["role"] == "admin":

            return redirect(
                url_for("admin_dashboard")
            )

        if user["role"] == "verifier":

            return redirect(
                url_for("verify_certificate")
            )

        # -------------------------------------------------
        # UNKNOWN ROLE
        # -------------------------------------------------
        flash("Invalid user role.", "error")

        return render_template(
            "student/login.html"
        )

    # -----------------------------------------------------
    # GET REQUEST
    # -----------------------------------------------------
    return render_template(
        "student/login.html"
    )
# =========================================================
# ADMIN REGISTRATION
# =========================================================

@app.route("/admin/register", methods=["GET", "POST"])
def admin_register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "error"
            )

            return redirect(
                url_for("admin_register")
            )

        connection = get_db_connection()

        if connection is None:

            flash(
                "Database connection failed.",
                "error"
            )

            return redirect(
                url_for("admin_register")
            )

        cursor = connection.cursor(dictionary=True)

        try:

            cursor.execute(
                """
                SELECT id
                FROM users
                WHERE email = %s
                """,
                (email,)
            )

            existing_admin = cursor.fetchone()

            if existing_admin:

                flash(
                    "An account with this email already exists.",
                    "error"
                )

                return redirect(
                    url_for("admin_register")
                )

            # Keep same password format as your current users table
            cursor.execute(
                """
                INSERT INTO users
                (
                    name,
                    email,
                    password,
                    role
                )
                VALUES
                (%s, %s, %s, 'admin')
                """,
                (
                    name,
                    email,
                    password
                )
            )

            connection.commit()

            flash(
                "Admin account created successfully. Please login.",
                "success"
            )

            return redirect(
                url_for("login")
            )

        except Error as e:

            connection.rollback()

            print("Admin registration error:", e)

            flash(
                "Admin registration failed.",
                "error"
            )

        finally:

            cursor.close()
            connection.close()

    return render_template("student/register.html")


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route("/student/dashboard")
def student_dashboard():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "student":

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "error"
        )

        return redirect(
            url_for("login")
        )

    cursor = connection.cursor(dictionary=True)

    try:

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

    except Error as e:

        print("Student dashboard error:", e)

        certificates = []

    finally:

        cursor.close()
        connection.close()

    return render_template(
        "student/dashboard.html",
        certificates=certificates
    )


# =========================================================
# VIEW CERTIFICATE
# =========================================================

@app.route("/view-certificate/<certificate_id>")
def view_certificate(certificate_id):

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    if session.get("role") != "student":

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "error"
        )

        return redirect(
            url_for("student_dashboard")
        )

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM certificates
        WHERE certificate_id = %s
        AND student_id = %s
        """,
        (
            certificate_id,
            session["user_id"]
        )
    )

    certificate = cursor.fetchone()

    cursor.close()
    connection.close()

    if certificate is None:

        flash(
            "Certificate not found.",
            "error"
        )

        return redirect(
            url_for("student_dashboard")
        )

    return render_template(
        "certificate.html",
        certificate=certificate
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "error"
        )

        return redirect(
            url_for("login")
        )

    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM users
            WHERE role = 'student'
            """
        )

        total_students = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM certificates
            """
        )

        total_certificates = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM certificates
            WHERE blockchain_status = 'Valid'
            """
        )

        verified_certificates = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM certificates
            WHERE blockchain_status = 'Revoked'
            """
        )

        revoked_certificates = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM verification_history
            """
        )

        total_verifications = cursor.fetchone()["total"]

    except Error as e:

        print("Admin dashboard error:", e)

        total_students = 0
        total_certificates = 0
        verified_certificates = 0
        revoked_certificates = 0
        total_verifications = 0

    finally:

        cursor.close()
        connection.close()

    return render_template(
        "admin_dashboard.html",
        total_students=total_students,
        total_certificates=total_certificates,
        verified_certificates=verified_certificates,
        revoked_certificates=revoked_certificates,
        total_verifications=total_verifications
    )


# =========================================================
# ADMIN STUDENTS
# =========================================================

@app.route("/admin/students")
@admin_required
def admin_students():

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            u.id,
            u.name,
            u.email,

            (
                SELECT COUNT(*)
                FROM certificates c
                WHERE c.student_id = u.id
            ) AS certificates_count

        FROM users u

        WHERE u.role = 'student'

        ORDER BY u.id DESC
        """
    )

    students = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin/student.html",
        students=students
    )


# =========================================================
# ADMIN STUDENT DETAILS
# =========================================================

@app.route("/admin/students/<int:student_id>")
@admin_required
def admin_student_details(student_id):

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM users
        WHERE id = %s
        AND role = 'student'
        """,
        (student_id,)
    )

    student = cursor.fetchone()

    if student is None:

        cursor.close()
        connection.close()

        return "Student not found", 404

    cursor.execute(
        """
        SELECT *
        FROM certificates
        WHERE student_id = %s
        ORDER BY id DESC
        """,
        (student_id,)
    )

    certificates = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin/student_details.html",
        student=student,
        certificates=certificates
    )


# =========================================================
# EDIT STUDENT
# =========================================================

@app.route(
    "/admin/students/<int:student_id>/edit",
    methods=["GET", "POST"]
)
@admin_required
def edit_student(student_id):

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    if request.method == "POST":

        name = request.form.get("name")
        email = request.form.get("email")

        cursor.execute(
            """
            UPDATE users
            SET
                name = %s,
                email = %s
            WHERE id = %s
            AND role = 'student'
            """,
            (
                name,
                email,
                student_id
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        flash(
            "Student updated successfully.",
            "success"
        )

        return redirect(
            url_for(
                "admin_student_details",
                student_id=student_id
            )
        )

    cursor.execute(
        """
        SELECT *
        FROM users
        WHERE id = %s
        AND role = 'student'
        """,
        (student_id,)
    )

    student = cursor.fetchone()

    cursor.close()
    connection.close()

    if student is None:

        return "Student not found", 404

    return render_template(
        "admin/edit_student.html",
        student=student
    )


# =========================================================
# DELETE STUDENT
# =========================================================

@app.route(
    "/admin/students/<int:student_id>/delete",
    methods=["POST"]
)
@admin_required
def delete_student(student_id):

    connection = get_db_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM users
        WHERE id = %s
        AND role = 'student'
        """,
        (student_id,)
    )

    connection.commit()

    cursor.close()
    connection.close()

    flash(
        "Student deleted successfully.",
        "success"
    )

    return redirect(
        url_for("admin_students")
    )


# =========================================================
# ADMIN CERTIFICATES
# =========================================================

@app.route("/admin/certificate")
@admin_required
def admin_certificates():

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            c.*,
            u.name AS student_name,
            u.email AS student_email

        FROM certificates c

        JOIN users u
        ON c.student_id = u.id

        ORDER BY c.id DESC
        """
    )

    certificates = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin/certificate.html",
        certificates=certificates
    )


# =========================================================
# ISSUE CERTIFICATE
# =========================================================

@app.route(
    "/admin/certificate/issue_certificate",
    methods=["GET", "POST"]
)
@admin_required
def issue_certificate():

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    cursor = connection.cursor(dictionary=True)

    if request.method == "POST":

        certificate_id = request.form.get(
            "certificate_id"
        )

        certificate_name = request.form.get(
            "certificate_name"
        )

        student_id = request.form.get(
            "student_id"
        )

        student_name = request.form.get(
            "student_name"
        )

        course_name = request.form.get(
            "course_name"
        )

        institution_name = request.form.get(
            "institution_name"
        )

        issue_date = request.form.get(
            "issue_date"
        )

        certificate_hash = request.form.get(
            "certificate_hash"
        )

        if not certificate_id:

            flash(
                "Certificate ID is required.",
                "error"
            )

            cursor.close()
            connection.close()

            return redirect(
                url_for("issue_certificate")
            )

        # Check duplicate certificate
        cursor.execute(
            """
            SELECT id
            FROM certificates
            WHERE certificate_id = %s
            """,
            (certificate_id,)
        )

        existing = cursor.fetchone()

        if existing:

            flash(
                "Certificate ID already exists.",
                "error"
            )

            cursor.close()
            connection.close()

            return redirect(
                url_for("issue_certificate")
            )

        # =================================================
        # BLOCKCHAIN ISSUE
        # =================================================

        blockchain_success = False

        try:

            if w3.is_connected():

                accounts = w3.eth.accounts

                if accounts:

                    issuer = accounts[0]

                    transaction = contract.functions.issueCertificate(
                        certificate_id,
                        student_name,
                        course_name,
                        institution_name,
                        certificate_hash
                    ).transact({
                        "from": issuer
                    })

                    w3.eth.wait_for_transaction_receipt(
                        transaction
                    )

                    blockchain_success = True

        except Exception as e:

            print(
                "Blockchain issue error:",
                e
            )

        if blockchain_success:

            blockchain_status = "Valid"

        else:

            blockchain_status = "Pending"

        # =================================================
        # SAVE TO MYSQL
        # =================================================

        cursor.execute(
            """
            INSERT INTO certificates
            (
                certificate_id,
                student_id,
                certificate_name,
                student_name,
                course_name,
                institution_name,
                issue_date,
                certificate_hash,
                blockchain_status
            )

            VALUES
            (
                %s,%s,%s,%s,%s,%s,%s,%s,%s
            )
            """,
            (
                certificate_id,
                student_id,
                certificate_name,
                student_name,
                course_name,
                institution_name,
                issue_date,
                certificate_hash,
                blockchain_status
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        if blockchain_success:

            flash(
                "Certificate issued and recorded on blockchain.",
                "success"
            )

        else:

            flash(
                "Certificate saved in database, but blockchain transaction failed.",
                "error"
            )

        return redirect(
            url_for("admin_certificates")
        )

    # GET request
    cursor.execute(
        """
        SELECT id, name, email
        FROM users
        WHERE role = 'student'
        ORDER BY name
        """
    )

    students = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin/issue_certificate.html",
        students=students
    )


# =========================================================
# CERTIFICATE DETAILS
# =========================================================

@app.route(
    "/admin/certificate/<certificate_id>"
)
@admin_required
def certificate_details(certificate_id):

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            c.*,
            u.name AS student_name,
            u.email AS student_email

        FROM certificates c

        JOIN users u
        ON c.student_id = u.id

        WHERE c.certificate_id = %s
        """,
        (certificate_id,)
    )

    certificate = cursor.fetchone()

    cursor.close()
    connection.close()

    if certificate is None:

        return "Certificate not found", 404

    return render_template(
        "admin/certificate_details.html",
        certificate=certificate
    )


# =========================================================
# REVOKE CERTIFICATE
# =========================================================

@app.route(
    "/admin/certificate/<certificate_id>/revoke",
    methods=["POST"]
)
@admin_required
def revoke_certificate(certificate_id):

    connection = get_db_connection()

    cursor = connection.cursor()

    # Blockchain revoke
    try:

        if w3.is_connected():

            accounts = w3.eth.accounts

            if accounts:

                transaction = contract.functions.revokeCertificate(
                    certificate_id
                ).transact({
                    "from": accounts[0]
                })

                w3.eth.wait_for_transaction_receipt(
                    transaction
                )

    except Exception as e:

        print(
            "Blockchain revoke error:",
            e
        )

    cursor.execute(
        """
        UPDATE certificates

        SET blockchain_status = 'Revoked'

        WHERE certificate_id = %s
        """,
        (certificate_id,)
    )

    connection.commit()

    cursor.close()
    connection.close()

    flash(
        "Certificate revoked successfully.",
        "success"
    )

    return redirect(
        url_for(
            "certificate_details",
            certificate_id=certificate_id
        )
    )


# =========================================================
# VERIFY CERTIFICATE
# =========================================================

@app.route(
    "/verify",
    methods=["GET", "POST"]
)
def verify_certificate():

    if request.method == "GET":

        return render_template(
            "verify.html"
        )

    certificate_id = request.form.get(
        "certificate_id",
        ""
    ).strip()

    uploaded_file = request.files.get(
        "certificate_file"
    )

    # =====================================================
    # 1. PDF TEXT SEARCH
    # =====================================================

    if uploaded_file and uploaded_file.filename:

        try:

            pdf_bytes = uploaded_file.read()

            # -------------------------------------------------
            # Extract PDF text
            # -------------------------------------------------

            if fitz is not None:

                document = fitz.open(
                    stream=pdf_bytes,
                    filetype="pdf"
                )

                pdf_text = ""

                for page in document:

                    pdf_text += page.get_text()

                document.close()

            else:

                reader = PdfReader(
                    io.BytesIO(pdf_bytes)
                )

                pdf_text = ""

                for page in reader.pages:

                    text = page.extract_text()

                    if text:

                        pdf_text += text

            # -------------------------------------------------
            # Search Certificate ID
            # -------------------------------------------------

            match = re.search(
                r"Certificate\s*ID\s*[:=\-]?\s*([A-Za-z0-9_-]+)",
                pdf_text,
                re.IGNORECASE
            )

            if match:

                certificate_id = match.group(1).strip()

                print(
                    "CERTIFICATE ID FROM PDF:",
                    certificate_id
                )

        except Exception as e:

            print(
                "PDF extraction error:",
                e
            )

    # =====================================================
    # 2. IF NO ID -> QR SCAN
    # =====================================================

    if not certificate_id and uploaded_file:

        if (
            fitz is not None
            and cv2 is not None
            and np is not None
        ):

            try:

                document = fitz.open(
                    stream=pdf_bytes,
                    filetype="pdf"
                )

                detector = cv2.QRCodeDetector()

                for page in document:

                    pix = page.get_pixmap(
                        matrix=fitz.Matrix(3, 3)
                    )

                    image = np.frombuffer(
                        pix.samples,
                        dtype=np.uint8
                    )

                    image = image.reshape(
                        pix.height,
                        pix.width,
                        pix.n
                    )

                    if pix.n == 4:

                        image = cv2.cvtColor(
                            image,
                            cv2.COLOR_RGBA2RGB
                        )

                    else:

                        image = cv2.cvtColor(
                            image,
                            cv2.COLOR_RGB2BGR
                        )

                    data, points, _ = detector.detectAndDecode(
                        image
                    )

                    if data:

                        print(
                            "QR DATA:",
                            data
                        )

                        # QR contains plain certificate ID
                        qr_match = re.search(
                            r"certificateId\s*['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9_-]+)",
                            data,
                            re.IGNORECASE
                        )

                        if qr_match:

                            certificate_id = (
                                qr_match.group(1)
                            )

                        else:

                            # If QR itself is just the ID
                            simple_match = re.fullmatch(
                                r"[A-Za-z0-9_-]+",
                                data.strip()
                            )

                            if simple_match:

                                certificate_id = data.strip()

                    if certificate_id:

                        break

                document.close()

            except Exception as e:

                print(
                    "QR scan error:",
                    e
                )

    # =====================================================
    # 3. CANNOT VERIFY
    # =====================================================

    if not certificate_id:

        return render_template(
            "verification_result.html",
            status="CANNOT VERIFY",
            certificate=None,
            message="Certificate ID or usable QR code was not found."
        )

    print(
        "FINAL CERTIFICATE ID:",
        certificate_id
    )

    # =====================================================
    # 4. BLOCKCHAIN CHECK
    # =====================================================

    if not w3.is_connected():

        return render_template(
            "verification_result.html",
            status="CANNOT VERIFY",
            certificate=None,
            message="Blockchain network is not connected."
        )

    try:

        exists, valid = contract.functions.verifyCertificate(
            certificate_id
        ).call()

        print(
            "VERIFYING CERTIFICATE:",
            certificate_id
        )

        print(
            "EXISTS:",
            exists
        )

        print(
            "VALID:",
            valid
        )

    except Exception as e:

        print(
            "Blockchain verification error:",
            e
        )

        return render_template(
            "verification_result.html",
            status="CANNOT VERIFY",
            certificate=None,
            message="Unable to verify certificate on blockchain."
        )

    # =====================================================
    # 5. CERTIFICATE NOT FOUND
    # =====================================================

    if not exists:

        save_verification_history(
            certificate_id,
            None,
            "Invalid"
        )

        return render_template(
            "verification_result.html",
            status="INVALID",
            certificate=None,
            message="Certificate was not found on blockchain."
        )

    # =====================================================
    # 6. GET BLOCKCHAIN DATA
    # =====================================================

    try:

        blockchain_certificate = (
            contract.functions.getCertificate(
                certificate_id
            ).call()
        )

        certificate = {

            "certificate_id":
                blockchain_certificate[0],

            "student_name":
                blockchain_certificate[1],

            "course_name":
                blockchain_certificate[2],

            "institution_name":
                blockchain_certificate[3],

            "certificate_hash":
                blockchain_certificate[4],

            "issue_date":
                blockchain_certificate[5],

            "issuer":
                blockchain_certificate[6],

            "revoked":
                blockchain_certificate[7]
        }

    except Exception as e:

        print(
            "Get certificate error:",
            e
        )

        return render_template(
            "verification_result.html",
            status="CANNOT VERIFY",
            certificate=None,
            message="Certificate data could not be retrieved."
        )

    # =====================================================
    # 7. FINAL STATUS
    # =====================================================

    if valid and not certificate["revoked"]:

        status = "VALID"

    else:

        status = "INVALID"

    # =====================================================
    # 8. SAVE HISTORY
    # =====================================================

    save_verification_history(
        certificate_id,
        certificate,
        status
    )

    # =====================================================
    # 9. SHOW RESULT
    # =====================================================

    return render_template(
        "verification_result.html",
        status=status,
        certificate=certificate,
        message="Certificate verification completed."
    )


# =========================================================
# SAVE VERIFICATION HISTORY
# =========================================================

def save_verification_history(
    certificate_id,
    certificate=None,
    status="Invalid"
):

    if "user_id" not in session:

        print(
            "USER NOT LOGGED IN."
        )

        return

    connection = get_db_connection()

    if connection is None:

        return

    cursor = connection.cursor()

    try:

        if certificate:

            student_name = certificate.get(
                "student_name"
            )

            course_name = certificate.get(
                "course_name"
            )

            institution_name = certificate.get(
                "institution_name"
            )

            certificate_hash = certificate.get(
                "certificate_hash"
            )

            issue_date = str(
                certificate.get(
                    "issue_date"
                )
            )

            issuer = str(
                certificate.get(
                    "issuer"
                )
            )

        else:

            student_name = None
            course_name = None
            institution_name = None
            certificate_hash = None
            issue_date = None
            issuer = None

        cursor.execute(
            """
            INSERT INTO verification_history
            (
                user_id,
                certificate_id,
                student_name,
                course_name,
                institution_name,
                certificate_hash,
                issue_date,
                issuer,
                status
            )

            VALUES
            (
                %s,%s,%s,%s,%s,%s,%s,%s,%s
            )
            """,
            (
                session["user_id"],
                certificate_id,
                student_name,
                course_name,
                institution_name,
                certificate_hash,
                issue_date,
                issuer,
                status
            )
        )

        connection.commit()

    except Error as e:

        connection.rollback()

        print(
            "Verification history error:",
            e
        )

    finally:

        cursor.close()
        connection.close()


# =========================================================
# VERIFIED CERTIFICATES
# =========================================================

@app.route("/verified_certificates")
def verified_certificates():

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "error"
        )

        return redirect(
            url_for("login")
        )

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM verification_history
        WHERE user_id = %s
        ORDER BY id DESC
        """,
        (session["user_id"],)
    )

    records = cursor.fetchall()

    cursor.close()
    connection.close()

    valid_certificates = [
        record
        for record in records
        if record["status"] == "VALID"
        or record["status"] == "Valid"
    ]

    invalid_certificates = [
        record
        for record in records
        if record["status"] == "INVALID"
        or record["status"] == "Invalid"
    ]

    return render_template(
        "verified_certificates.html",
        valid_certificates=valid_certificates,
        invalid_certificates=invalid_certificates
    )


# =========================================================
# ADMIN VERIFICATION HISTORY
# =========================================================

@app.route("/admin/verifications")
@admin_required
def admin_verification():

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM verification_history
        ORDER BY id DESC
        """
    )

    verifications = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "admin/verification.html",
        verifications=verifications
    )


# =========================================================
# ADMIN SETTINGS
# =========================================================

@app.route("/admin/settings")
@admin_required
def admin_settings():

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM users
        WHERE id = %s
        AND role = 'admin'
        """,
        (session["user_id"],)
    )

    admin = cursor.fetchone()

    cursor.close()
    connection.close()

    if admin is None:

        flash(
            "Administrator record not found.",
            "error"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    return render_template(
        "admin/setting.html",
        admin=admin
    )


# =========================================================
# UPDATE ADMIN PROFILE
# =========================================================

@app.route(
    "/admin/profile/update",
    methods=["POST"]
)
@admin_required
def update_profile():

    name = request.form.get("name")
    email = request.form.get("email")

    connection = get_db_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE users

        SET
            name = %s,
            email = %s

        WHERE id = %s
        AND role = 'admin'
        """,
        (
            name,
            email,
            session["user_id"]
        )
    )

    connection.commit()

    cursor.close()
    connection.close()

    session["name"] = name
    session["email"] = email

    flash(
        "Profile updated successfully.",
        "success"
    )

    return redirect(
        url_for("admin_settings")
    )


# =========================================================
# ADMIN LOGOUT
# =========================================================

@app.route("/admin/logout")
def admin_logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("login")
    )


# =========================================================
# STUDENT LOGOUT
# =========================================================

@app.route("/student/logout")
def student_logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("login")
    )


# =========================================================
# GENERAL LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("login")
    )


# =========================================================
# BLOCKCHAIN TEST
# =========================================================

@app.route("/blockchain-test")
def blockchain_test():

    try:

        connected = w3.is_connected()

        chain_id = w3.eth.chain_id

        code = w3.eth.get_code(
            Web3.to_checksum_address(
                CONTRACT_ADDRESS
            )
        )

        return {
            "connected": connected,
            "chain_id": chain_id,
            "contract_address": CONTRACT_ADDRESS,
            "contract_deployed": (
                len(code) > 0
            )
        }

    except Exception as e:

        return {
            "connected": False,
            "error": str(e)
        }


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
