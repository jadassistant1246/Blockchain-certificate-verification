from flask import Flask, render_template, request, redirect, url_for, session, flash
from blockchain import Blockchain
from web3 import Web3
import json

from datetime import datetime
import hashlib
import uuid

blockchain = Blockchain()
import mysql.connector
from mysql.connector import Error

from functools import wraps

from werkzeug.security import generate_password_hash, check_password_hash


from web3 import Web3
import json

GANACHE_URL = "http://127.0.0.1:7545"

web3 = Web3(
    Web3.HTTPProvider(GANACHE_URL)
)

print("Blockchain connected:", web3.is_connected())

with open("blockchain/contract_abi.json", "r") as file:
    CONTRACT_ABI = json.load(file)

CONTRACT_ADDRESS = "0xd8b934580fcE35a11B58C6D73aDeE468a2833fa8"
contract = web3.eth.contract(
    address=CONTRACT_ADDRESS,
    abi=CONTRACT_ABI
)
# =====================================================
# FLASK APPLICATION
# =====================================================

app = Flask(__name__)

app.secret_key = "blockcert_secret_key_change_this"


# =====================================================
# MYSQL DATABASE CONFIGURATION
# =====================================================

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Jadhav@1234",
    "database": "blockchain_certificate"
}


# =====================================================
# DATABASE CONNECTION
# =====================================================

def get_db_connection():

    try:

        connection = mysql.connector.connect(
            host=DB_CONFIG["host"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"]
        )

        return connection

    except Error as e:

        print("Database connection error:", e)

        return None

@app.route('/test-blockchain')
def test_blockchain():

    try:

        # Ganache account
        blockchain_account = web3.eth.accounts[0]

        # Dummy certificate information
        certificate_id = "TEST001"
        certificate_hash = "abc123dummyhash456"

        # Send certificate hash to blockchain
        transaction = contract.functions.issueCertificate(
            certificate_id,
            certificate_hash
        ).transact({
            "from": blockchain_account
        })

        # Wait for transaction confirmation
        receipt = web3.eth.wait_for_transaction_receipt(
            transaction
        )

        return f"""
        <h2>Blockchain Test Successful</h2>

        <p><b>Certificate ID:</b> {certificate_id}</p>

        <p><b>Certificate Hash:</b> {certificate_hash}</p>

        <p><b>Transaction Hash:</b> {receipt.transactionHash.hex()}</p>

        <p><b>Block Number:</b> {receipt.blockNumber}</p>
        """

    except Exception as e:

        return f"""
        <h2>Blockchain Test Failed</h2>

        <p>{str(e)}</p>
        """

@app.route('/test-blockchain-verify')
def test_blockchain_verify():

    try:

        certificate_id = "TEST001"

        certificate_hash, exists = contract.functions.verifyCertificate(
            certificate_id
        ).call()

        return f"""
        <h2>Blockchain Verification Test</h2>

        <p><b>Certificate ID:</b> {certificate_id}</p>

        <p><b>Hash from Blockchain:</b> {certificate_hash}</p>

        <p><b>Certificate Exists:</b> {exists}</p>
        """

    except Exception as e:

        return f"""
        <h2>Blockchain Verification Failed</h2>

        <p>{str(e)}</p>
        """
# =====================================================
# ADMIN LOGIN REQUIRED
# =====================================================

def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if "admin_id" not in session:

            return redirect(url_for("admin_login"))

        return function(*args, **kwargs)

    return wrapper


@app.route("/")
def home():
    return render_template("index.html")

#student login 
@app.route('/student/login', methods=['GET', 'POST'])
def student_login():

    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        if not email or not password:
            flash("Please enter email and password.", "danger")
            return redirect(url_for('student_login'))

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM students
            WHERE email = %s
            """,
            (email,)
        )

        student = cursor.fetchone()

        cursor.close()
        connection.close()

        # Check login credentials
        if student and check_password_hash(
            student["password"],
            password
        ):

            session.clear()

            session["student_id"] = student["student_id"]
            session["role"] = "student"

            return redirect(
                url_for("student_dashboard")
            )

        flash("Invalid email or password.", "danger")

        return redirect(url_for('student_login'))

    return render_template('student/login.html')


# student registration

@app.route('/student/register', methods=['GET', 'POST'])
def student_register():

    if request.method == 'POST':

        student_name = request.form.get('student_name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        department = request.form.get('department')
        course = request.form.get('course')
        enrollment_no = request.form.get('enrollment_no')
        admission_year = request.form.get('admission_year')
        password = request.form.get('password')

        # Check required fields
        if not student_name or not email or not password:
            flash("Please fill all required fields.", "danger")
            return redirect(url_for('student_register'))

        # Database connection
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        # Check whether email already exists
        cursor.execute(
            "SELECT student_id FROM students WHERE email = %s",
            (email,)
        )

        existing_student = cursor.fetchone()

        if existing_student:
            cursor.close()
            connection.close()

            flash(
                "Student with this email already exists.",
                "danger"
            )

            return redirect(url_for('student_register'))

        # Check enrollment number
        if enrollment_no:

            cursor.execute(
                """
                SELECT student_id
                FROM students
                WHERE enrollment_no = %s
                """,
                (enrollment_no,)
            )

            existing_enrollment = cursor.fetchone()

            if existing_enrollment:
                cursor.close()
                connection.close()

                flash(
                    "Enrollment number already exists.",
                    "danger"
                )

                return redirect(url_for('student_register'))

        # Hash password
        hashed_password = generate_password_hash(password)

        # Insert student
        cursor.execute(
            """
            INSERT INTO students
            (
                student_name,
                email,
                phone,
                department,
                course,
                enrollment_no,
                admission_year,
                password
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                student_name,
                email,
                phone,
                department,
                course,
                enrollment_no,
                admission_year,
                hashed_password
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        flash(
            "Student registration successful. Please login.",
            "success"
        )

        return redirect(url_for('student_login'))

    return render_template('student/register.html')

#==================================================
# STUDENT DASHBOARD
#==============================================
@app.route('/student/dashboard')
def student_dashboard():

    if "student_id" not in session:
        flash("Please login first.", "danger")
        return redirect(url_for("student_login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:

        # Get logged-in student
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
                status
            FROM students
            WHERE student_id = %s
        """, (session["student_id"],))

        student = cursor.fetchone()

        # Get certificates of logged-in student
        cursor.execute("""
            SELECT
                certificate_id,
                student_id,
                certificate_type,
                course,
                issue_date,
                certificate_hash,
                pdf_path,
                status,
                blockchain_status,
                transaction_hash
            FROM certificates
            WHERE student_id = %s
            ORDER BY issue_date DESC
        """, (session["student_id"],))

        certificates = cursor.fetchall()

    finally:
        cursor.close()
        connection.close()

    if not student:
        session.clear()
        flash("Student account not found.", "danger")
        return redirect(url_for("student_login"))

    return render_template(
        "student/dashboard.html",
        student=student,
        certificates=certificates
    )

@app.route('/student/certificate/<int:certificate_id>')
def student_certificate(certificate_id):

    # Check student login
    if "student_id" not in session:
        flash("Please login first.", "danger")
        return redirect(url_for("student_login"))

    connection = get_db_connection()

    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("student_dashboard"))

    cursor = connection.cursor(dictionary=True)

    try:

        # Get ONLY the selected certificate
        # belonging to the logged-in student
        cursor.execute("""
            SELECT
                c.certificate_id,
                c.student_id,
                c.certificate_type,
                c.course,
                c.issue_date,
                c.certificate_hash,
                c.pdf_path,
                c.status,
                c.blockchain_status,
                c.transaction_hash,

                s.student_name,
                s.email,
                s.department,
                s.enrollment_no

            FROM certificates c

            INNER JOIN students s
                ON c.student_id = s.student_id

            WHERE c.certificate_id = %s
            AND c.student_id = %s

        """, (
            certificate_id,
            session["student_id"]
        ))

        certificate = cursor.fetchone()

    except Error as e:

        print("Student certificate error:", e)

        flash(
            "Error loading certificate.",
            "danger"
        )

        return redirect(
            url_for("student_dashboard")
        )

    finally:

        cursor.close()
        connection.close()

    # Certificate doesn't exist
    # or doesn't belong to this student
    if certificate is None:

        flash(
            "Certificate not found.",
            "danger"
        )

        return redirect(
            url_for("student_dashboard")
        )

    # Send ONE certificate to HTML
    return render_template(
        "student/certificate.html",
        certificate=certificate
    )


# =====================================================
# ADMIN LOGIN
# =====================================================

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():

    if request.method == "POST":

        email = request.form.get("email")
        password = request.form.get("password")

        connection = get_db_connection()

        if connection is None:

            flash("Database connection failed.", "danger")

            return render_template("admin/login.html")


        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT *
            FROM admins
            WHERE email = %s
            """,
            (email,)
        )

        admin = cursor.fetchone()

        cursor.close()
        connection.close()


        if admin and check_password_hash(
            admin["password"],
            password
        ):

            session["admin_id"] = admin["admin_id"]
            session["admin_name"] = admin["name"]
            session["admin_email"] = admin["email"]

            return redirect(
                url_for("admin_dashboard")
            )

        else:

            flash(
                "Invalid email or password.",
                "danger"
            )

    return render_template("admin/login.html")

# =====================================================
# DASHBOARD
# =====================================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    connection = get_db_connection()

    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_login"))

    cursor = connection.cursor(dictionary=True)

    try:

        # -----------------------------
        # TOTAL STUDENTS
        # -----------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM students
        """)

        total_students = cursor.fetchone()["total"]


        # -----------------------------
        # TOTAL CERTIFICATES
        # -----------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM certificates
        """)

        total_certificates = cursor.fetchone()["total"]


        # -----------------------------
        # VERIFIED CERTIFICATES
        # -----------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM certificates
            WHERE status = 'Verified'
        """)

        verified_certificates = cursor.fetchone()["total"]


        # -----------------------------
        # REVOKED CERTIFICATES
        # -----------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM certificates
            WHERE status = 'Revoked'
        """)

        revoked_certificates = cursor.fetchone()["total"]


        # -----------------------------
        # TOTAL VERIFICATIONS
        # -----------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM verification_logs
        """)

        total_verifications = cursor.fetchone()["total"]


        # -----------------------------
        # SUCCESSFUL VERIFICATIONS
        # -----------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM verification_logs
            WHERE result = 'Valid'
        """)

        successful_verifications = cursor.fetchone()["total"]


        # -----------------------------
        # FAILED VERIFICATIONS
        # -----------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM verification_logs
            WHERE result = 'Invalid'
        """)

        failed_verifications = cursor.fetchone()["total"]


        # -----------------------------
        # VERIFICATION SUCCESS RATE
        # -----------------------------

        if total_verifications > 0:
            verification_success_rate = round(
                (successful_verifications / total_verifications) * 100,
                2
            )
        else:
            verification_success_rate = 0


        # -----------------------------
        # TOTAL BLOCKCHAIN RECORDS
        # -----------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM blockchain_records
        """)

        total_blockchain_records = cursor.fetchone()["total"]


        # -----------------------------
        # CONFIRMED BLOCKCHAIN RECORDS
        # -----------------------------

        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM blockchain_records
            WHERE status = 'Confirmed'
        """)

        confirmed_blockchain_records = cursor.fetchone()["total"]


    except Error as e:

        print("Dashboard Error:", e)

        flash(
            "Error loading dashboard data.",
            "danger"
        )

        return redirect(
            url_for("admin_login")
        )

    finally:

        cursor.close()
        connection.close()


    return render_template(
        "admin/dashboard.html",

        total_students=total_students,

        total_certificates=total_certificates,

        verified_certificates=verified_certificates,

        revoked_certificates=revoked_certificates,

        total_verifications=total_verifications,

        successful_verifications=successful_verifications,

        failed_verifications=failed_verifications,

        verification_success_rate=verification_success_rate,

        total_blockchain_records=total_blockchain_records,

        confirmed_blockchain_records=confirmed_blockchain_records
    )
# =====================================================
# ADMIN REGISTRATION
# =====================================================

@app.route("/admin/register", methods=["GET", "POST"])
def admin_register():

    if request.method == "POST":

        # Get form data
        name = request.form.get("name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        role = request.form.get("role")
        password = request.form.get("password")
        confirm_password = request.form.get("confirm_password")

        # -------------------------------------------------
        # BASIC VALIDATION
        # -------------------------------------------------

        if not name or not email or not password:
            flash(
                "Please fill all required fields.",
                "danger"
            )
            return redirect(url_for("admin_register"))

        if password != confirm_password:
            flash(
                "Passwords do not match.",
                "danger"
            )
            return redirect(url_for("admin_register"))

        # -------------------------------------------------
        # DATABASE CONNECTION
        # -------------------------------------------------

        connection = get_db_connection()

        if connection is None:
            flash(
                "Database connection failed.",
                "danger"
            )
            return redirect(url_for("admin_register"))

        cursor = connection.cursor(dictionary=True)

        try:

            # -------------------------------------------------
            # CHECK IF EMAIL ALREADY EXISTS
            # -------------------------------------------------

            cursor.execute(
                """
                SELECT admin_id
                FROM admins
                WHERE email = %s
                """,
                (email,)
            )

            existing_admin = cursor.fetchone()

            if existing_admin:
                flash(
                    "An admin account with this email already exists.",
                    "danger"
                )
                return redirect(
                    url_for("admin_register")
                )

            # -------------------------------------------------
            # HASH PASSWORD
            # -------------------------------------------------

            password_hash = generate_password_hash(
                password
            )

            # -------------------------------------------------
            # INSERT ADMIN
            # -------------------------------------------------

            cursor.execute(
                """
                INSERT INTO admins
                (
                    name,
                    email,
                    phone,
                    role,
                    password
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
                """,
                (
                    name,
                    email,
                    phone,
                    role,
                    password_hash
                )
            )

            connection.commit()

            flash(
                "Admin registration successful! Please login.",
                "success"
            )

            return redirect(
                url_for("admin_login")
            )

        except Error as e:

            connection.rollback()

            print(
                "Admin registration error:",
                e
            )

            flash(
                "Error creating admin account.",
                "danger"
            )

            return redirect(
                url_for("admin_register")
            )

        finally:

            cursor.close()
            connection.close()

    return render_template(
        "admin/register.html"
    )


# =====================================================
# STUDENTS
# =====================================================
@app.route("/admin/students")
@admin_required
def admin_students():

    connection = get_db_connection()

    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_dashboard"))

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            s.*,

            (
                SELECT COUNT(*)
                FROM certificates c
                WHERE c.student_id = s.student_id
            ) AS certificate_count

        FROM students s

        ORDER BY s.student_id DESC
        """
    )

    students = cursor.fetchall()

    cursor.execute(
        "SELECT COUNT(*) AS total FROM students"
    )

    total_students = cursor.fetchone()["total"]

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM students
        WHERE status = 'Verified'
        """
    )

    verified_students = cursor.fetchone()["total"]

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM students
        WHERE status = 'Pending'
        """
    )

    pending_students = cursor.fetchone()["total"]

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM certificates
        """
    )

    total_certificates = cursor.fetchone()["total"]

    cursor.close()
    connection.close()

    return render_template(
        "admin/student.html",
        students=students,
        total_students=total_students,
        verified_students=verified_students,
        pending_students=pending_students,
        total_certificates=total_certificates
    )

# =====================================================
# ADD STUDENT
# =====================================================

@app.route("/admin/students/add", methods=["GET", "POST"])
@admin_required
def add_student():

    if request.method == "POST":

        student_name = request.form.get("student_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        department = request.form.get("department")
        course = request.form.get("course")
        enrollment_no = request.form.get("enrollment_no")
        admission_year = request.form.get("admission_year")


        connection = get_db_connection()

        cursor = connection.cursor()


        cursor.execute(
            """
            INSERT INTO students
            (
                student_name,
                email,
                phone,
                department,
                course,
                enrollment_no,
                admission_year
            )

            VALUES
            (%s,%s,%s,%s,%s,%s,%s)
            """,

            (
                student_name,
                email,
                phone,
                department,
                course,
                enrollment_no,
                admission_year
            )
        )


        connection.commit()

        cursor.close()
        connection.close()

        flash(
            "Student added successfully.",
            "success"
        )

        return redirect(
            url_for("admin_students")
        )

    return render_template(
        "admin/add_student.html"
    )



# =====================================================
# STUDENT DETAILS
# =====================================================

@app.route("/admin/students/<int:student_id>")
@admin_required
def admin_student_details(student_id):

    connection = get_db_connection()

    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_students"))

    cursor = connection.cursor(dictionary=True)

    try:
        # Get student
        cursor.execute(
            """
            SELECT *
            FROM students
            WHERE student_id = %s
            """,
            (student_id,)
        )

        student = cursor.fetchone()

        if student is None:
            flash("Student not found.", "danger")
            return redirect(url_for("admin_students"))

        # Get student's certificates
        cursor.execute(
            """
            SELECT *
            FROM certificates
            WHERE student_id = %s
            ORDER BY issue_date DESC
            """,
            (student_id,)
        )

        certificates = cursor.fetchall()

    except Error as e:
        print("Student details error:", e)
        flash("Error loading student details.", "danger")
        return redirect(url_for("admin_students"))

    finally:
        cursor.close()
        connection.close()

    return render_template(
        "admin/student_details.html",
        student=student,
        certificates=certificates
    )


# =====================================================
# EDIT STUDENT
# =====================================================

@app.route(
    "/admin/students/<int:student_id>/edit",
    methods=["GET", "POST"]
)
@admin_required
def edit_student(student_id):

    connection = get_db_connection()

    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_students"))

    cursor = connection.cursor(dictionary=True)

    # -------------------------------------------------
    # UPDATE STUDENT
    # -------------------------------------------------

    if request.method == "POST":

        student_name = request.form.get("student_name")
        email = request.form.get("email")
        phone = request.form.get("phone")
        department = request.form.get("department")
        course = request.form.get("course")
        enrollment_no = request.form.get("enrollment_no")
        admission_year = request.form.get("admission_year")
        status = request.form.get("status")

        cursor.execute(
            """
            UPDATE students
            SET
                student_name = %s,
                email = %s,
                phone = %s,
                department = %s,
                course = %s,
                enrollment_no = %s,
                admission_year = %s,
                status = %s
            WHERE student_id = %s
            """,
            (
                student_name,
                email,
                phone,
                department,
                course,
                enrollment_no,
                admission_year,
                status,
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

    # -------------------------------------------------
    # GET STUDENT DETAILS
    # -------------------------------------------------

    cursor.execute(
        """
        SELECT *
        FROM students
        WHERE student_id = %s
        """,
        (student_id,)
    )

    student = cursor.fetchone()

    if student is None:

        cursor.close()
        connection.close()

        flash(
            "Student not found.",
            "danger"
        )

        return redirect(
            url_for("admin_students")
        )

    cursor.close()
    connection.close()

    return render_template(
        "admin/edit_student.html",
        student=student
    )


# =====================================================
# DELETE STUDENT
# =====================================================

@app.route(
    "/admin/students/<int:student_id>/delete",
    methods=["POST"]
)
@admin_required
def delete_student(student_id):

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "danger"
        )
        return redirect(
            url_for("admin_students")
        )

    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM students
        WHERE student_id = %s
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


# =====================================================
# CERTIFICATES
# =====================================================

@app.route("/admin/certificates")
@admin_required
def admin_certificates():

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "danger"
        )
        return redirect(
            url_for("admin_dashboard")
        )

    cursor = connection.cursor(dictionary=True)

    # -------------------------------------------------
    # ALL CERTIFICATES
    # -------------------------------------------------

    cursor.execute(
        """
        SELECT
            c.*,
            s.student_name
        FROM certificates c
        JOIN students s
            ON c.student_id = s.student_id
        ORDER BY c.certificate_id DESC
        """
    )

    certificates = cursor.fetchall()

    # -------------------------------------------------
    # TOTAL CERTIFICATES
    # -------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM certificates
        """
    )

    total_certificates = cursor.fetchone()["total"]

    # -------------------------------------------------
    # VERIFIED CERTIFICATES
    # -------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM certificates
        WHERE status = 'Verified'
        """
    )

    verified_certificates = cursor.fetchone()["total"]

    # -------------------------------------------------
    # PENDING CERTIFICATES
    # -------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM certificates
        WHERE status = 'Pending'
        """
    )

    pending_certificates = cursor.fetchone()["total"]

    # -------------------------------------------------
    # REVOKED CERTIFICATES
    # -------------------------------------------------

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM certificates
        WHERE status = 'Revoked'
        """
    )

    revoked_certificates = cursor.fetchone()["total"]

    cursor.close()
    connection.close()

    return render_template(
        "admin/certificate.html",
        certificates=certificates,
        total_certificates=total_certificates,
        verified_certificates=verified_certificates,
        pending_certificates=pending_certificates,
        revoked_certificates=revoked_certificates
    )


# =====================================================
# ISSUE CERTIFICATE
# =====================================================
@app.route("/admin/issue-certificate", methods=["GET", "POST"])
def issue_certificate():

    # Check admin login
    if "admin_id" not in session:
        flash("Please login as admin first.", "warning")
        return redirect(url_for("admin_login"))

    if request.method == "POST":

        # Get form data
        student_id = request.form.get("student_id")
        certificate_type = request.form.get("certificate_type")
        course = request.form.get("course")
        issue_date = request.form.get("issue_date")

        # Basic validation
        if not student_id:
            flash("Please select a student.", "danger")
            return redirect(url_for("issue_certificate"))

        if not certificate_type:
            flash("Please select a certificate type.", "danger")
            return redirect(url_for("issue_certificate"))

        if not course:
            flash("Please enter the course.", "danger")
            return redirect(url_for("issue_certificate"))

        if not issue_date:
            flash("Please select the issue date.", "danger")
            return redirect(url_for("issue_certificate"))

        connection = None
        cursor = None

        try:

            # Connect to MySQL
            connection = get_db_connection()
            cursor = connection.cursor(dictionary=True)

            # -----------------------------------------
            # Get selected student
            # -----------------------------------------

            cursor.execute("""
                SELECT
                    student_id,
                    student_name,
                    email,
                    course
                FROM students
                WHERE student_id = %s
            """, (student_id,))

            student = cursor.fetchone()

            if not student:
                flash("Selected student does not exist.", "danger")
                return redirect(url_for("issue_certificate"))

            # -----------------------------------------
            # Generate certificate ID
            # -----------------------------------------

            certificate_id = (
                "CERT-" +
                datetime.now().strftime("%Y%m%d") +
                "-" +
                uuid.uuid4().hex[:6].upper()
            )

            # -----------------------------------------
            # Create certificate data
            # -----------------------------------------

            certificate_data = (
                f"{certificate_id}|"
                f"{student['student_id']}|"
                f"{certificate_type}|"
                f"{course}|"
                f"{issue_date}"
            )

            # -----------------------------------------
            # Generate SHA-256 hash
            # -----------------------------------------

            certificate_hash = hashlib.sha256(
                certificate_data.encode("utf-8")
            ).hexdigest()

            # -----------------------------------------
            # Insert certificate into database
            # -----------------------------------------

            query = """
                INSERT INTO certificates
                (
                    student_id,
                    certificate_type,
                    course,
                    issue_date,
                    certificate_hash,
                    status,
                    blockchain_status
                )
                VALUES
                (
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s,
                    %s
                )
            """

            values = (
                student["student_id"],
                certificate_type,
                course,
                issue_date,
                certificate_hash,
                "Verified",
                "Pending"
            )

            cursor.execute(query, values)

            # -----------------------------------------
            # Get generated database ID
            # -----------------------------------------

            database_certificate_id = cursor.lastrowid

            # -----------------------------------------
            # Save changes
            # -----------------------------------------

            connection.commit()

            print("----------------------------------------")
            print("CERTIFICATE ISSUED SUCCESSFULLY")
            print("Database ID:", database_certificate_id)
            print("Student ID:", student["student_id"])
            print("Student Name:", student["student_name"])
            print("Certificate Type:", certificate_type)
            print("Certificate Hash:", certificate_hash)
            print("----------------------------------------")

            flash(
                f"Certificate issued successfully to {student['student_name']}!",
                "success"
            )

            return redirect(
                url_for(
                    "certificate_success",
                    certificate_id=database_certificate_id
                )
            )

        except Exception as e:

            if connection:
                connection.rollback()

            print("ERROR ISSUING CERTIFICATE:", str(e))

            flash(
                f"Error issuing certificate: {str(e)}",
                "danger"
            )

            return redirect(url_for("issue_certificate"))

        finally:

            if cursor:
                cursor.close()

    return render_template("admin/issue_certificate.html")


@app.route("/admin/certificate-success/<int:certificate_id>")
def certificate_success(certificate_id):

    if "admin_id" not in session:
        flash("Please login as admin first.", "warning")
        return redirect(url_for("admin_login"))

    connection = None
    cursor = None

    try:

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT
                c.certificate_id,
                c.student_id,
                c.certificate_type,
                c.course,
                c.issue_date,
                c.certificate_hash,
                c.status,
                c.blockchain_status,
                c.transaction_hash,
                s.student_name,
                s.email
            FROM certificates c
            INNER JOIN students s
                ON c.student_id = s.student_id
            WHERE c.certificate_id = %s
        """, (certificate_id,))

        certificate = cursor.fetchone()

        if not certificate:
            flash("Certificate not found.", "danger")
            return redirect(url_for("admin_certificates"))

        return render_template(
            "admin/certificate_success.html",
            certificate=certificate
        )

    except Exception as e:

        print("CERTIFICATE SUCCESS ERROR:", str(e))

        flash(
            f"Error loading certificate: {str(e)}",
            "danger"
        )

        return redirect(url_for("admin_certificates"))

    finally:

        if cursor:
            cursor.close()

# =====================================================
# CERTIFICATE DETAILS
# =====================================================

@app.route(
    "/admin/certificates/<int:certificate_id>"
)
@admin_required
def certificate_details(certificate_id):

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "danger"
        )
        return redirect(
            url_for("admin_certificates")
        )

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            c.*,
            s.student_name,
            s.email,
            s.department,
            s.enrollment_no
        FROM certificates c
        JOIN students s
            ON c.student_id = s.student_id
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


# =====================================================
# REVOKED CERTIFICATES
# =====================================================

@app.route("/admin/revoked-certificates")
@admin_required
def revoked_certificates():

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "danger"
        )
        return redirect(
            url_for("admin_dashboard")
        )

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            c.*,
            s.student_name
        FROM certificates c
        JOIN students s
            ON c.student_id = s.student_id
        WHERE c.status = 'Revoked'
        ORDER BY c.revoked_at DESC
        """
    )

    certificates = cursor.fetchall()

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM certificates
        WHERE status = 'Revoked'
        """
    )

    total_revoked = cursor.fetchone()["total"]

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM certificates
        WHERE status = 'Revoked'
        AND blockchain_status = 'Confirmed'
        """
    )

    blockchain_recorded = cursor.fetchone()["total"]

    cursor.close()
    connection.close()

    return render_template(
        "admin/revoked_certificate.html",
        certificates=certificates,
        total_revoked=total_revoked,
        blockchain_recorded=blockchain_recorded,
        recent_revocations=total_revoked
    )


# =====================================================
# REVOKE CERTIFICATE
# =====================================================

@app.route(
    "/admin/certificates/<int:certificate_id>/revoke",
    methods=["POST"]
)
@admin_required
def revoke_certificate(certificate_id):

    reason = request.form.get(
        "revocation_reason"
    )

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "danger"
        )
        return redirect(
            url_for(
                "certificate_details",
                certificate_id=certificate_id
            )
        )

    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE certificates
        SET
            status = 'Revoked',
            revoked_at = NOW(),
            revoked_by = %s,
            revocation_reason = %s
        WHERE certificate_id = %s
        """,
        (
            session.get("admin_name"),
            reason,
            certificate_id
        )
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


# =====================================================
# VERIFICATION HISTORY
# =====================================================
@app.route("/admin/verifications")
@admin_required
def admin_verification():

    connection = get_db_connection()

    if connection is None:

        flash(
            "Database connection failed.",
            "danger"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                v.*,
                c.certificate_hash,
                s.student_name
            FROM verification_logs v
            JOIN certificates c
                ON v.certificate_id = c.certificate_id
            JOIN students s
                ON c.student_id = s.student_id
            ORDER BY v.verified_at DESC
            """
        )

        verifications = cursor.fetchall()

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM verification_logs
            """
        )

        total_verifications = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM verification_logs
            WHERE result = 'Valid'
            """
        )

        valid_verifications = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM verification_logs
            WHERE result = 'Invalid'
            """
        )

        invalid_verifications = cursor.fetchone()["total"]

        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM verification_logs
            WHERE blockchain_status = 'Confirmed'
            """
        )

        blockchain_confirmed = cursor.fetchone()["total"]

    except Error as e:

        print("Verification Error:", e)

        flash(
            "Error loading verification data.",
            "danger"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    finally:

        cursor.close()
        connection.close()

    return render_template(
        "admin/verification.html",
        verifications=verifications,
        total_verifications=total_verifications,
        valid_verifications=valid_verifications,
        invalid_verifications=invalid_verifications,
        blockchain_confirmed=blockchain_confirmed
    )


# =====================================================
# VERIFY CERTIFICATE
# =====================================================

@app.route(
    "/verify-certificate",
    methods=["POST"]
)
@admin_required
def verify_certificate():

    certificate_input = request.form.get(
        "certificate_input"
    )

    verifier_name = session.get(
        "admin_name",
        "Administrator"
    )

    verifier_email = session.get(
        "admin_email",
        ""
    )

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "danger"
        )
        return redirect(
            url_for("admin_verification")
        )

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM certificates
        WHERE certificate_id = %s
        OR certificate_hash = %s
        """,
        (
            certificate_input,
            certificate_input
        )
    )

    certificate = cursor.fetchone()

    # -------------------------------------------------
    # CERTIFICATE NOT FOUND
    # -------------------------------------------------

    if certificate is None:

        cursor.close()
        connection.close()

        flash(
            "Certificate not found.",
            "danger"
        )

        return redirect(
            url_for("admin_verification")
        )

    # -------------------------------------------------
    # CHECK CERTIFICATE STATUS
    # -------------------------------------------------

    if certificate["status"] == "Verified":
        result = "Valid"

    elif certificate["status"] == "Revoked":
        result = "Invalid"

    else:
        result = "Pending"

    blockchain_status = certificate[
        "blockchain_status"
    ]

    # -------------------------------------------------
    # SAVE VERIFICATION HISTORY
    # -------------------------------------------------

    cursor.execute(
        """
        INSERT INTO verification_logs
        (
            certificate_id,
            verifier_name,
            verifier_email,
            result,
            blockchain_status
        )
        VALUES
        (%s, %s, %s, %s, %s)
        """,
        (
            certificate["certificate_id"],
            verifier_name,
            verifier_email,
            result,
            blockchain_status
        )
    )

    connection.commit()

    cursor.close()
    connection.close()

    flash(
        f"Certificate verification result: {result}",
        "success" if result == "Valid" else "danger"
    )

    return redirect(
        url_for("admin_verification")
    )


# =====================================================
# VERIFICATION DETAILS
# =====================================================

@app.route(
    "/admin/verifications/<int:verification_id>"
)
@admin_required
def verification_details(verification_id):

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "danger"
        )
        return redirect(
            url_for("admin_verification")
        )

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            v.*,
            c.certificate_hash,
            c.course,
            c.issue_date,
            c.status AS certificate_status,
            s.student_name,
            s.email
        FROM verification_logs v
        JOIN certificates c
            ON v.certificate_id = c.certificate_id
        JOIN students s
            ON c.student_id = s.student_id
        WHERE v.verification_id = %s
        """,
        (verification_id,)
    )

    verification = cursor.fetchone()

    cursor.close()
    connection.close()

    if verification is None:
        return "Verification record not found", 404

    return render_template(
      "admin/verification_details.html",
    verification=verification
    )


@app.route("/admin/profile/update", methods=["POST"])
@admin_required
def update_profile():

    name = request.form.get("name")
    email = request.form.get("email")

    connection = get_db_connection()

    if connection is None:
        flash("Database connection failed.", "danger")
        return redirect(url_for("admin_settings"))

    cursor = connection.cursor()

    try:
        cursor.execute(
            """
            UPDATE admins
            SET name = %s,
                email = %s
            WHERE admin_id = %s
            """,
            (name, email, session["admin_id"])
        )

        connection.commit()

        # Update session values
        session["admin_name"] = name
        session["admin_email"] = email

        flash("Profile updated successfully.", "success")

    except Error as e:
        connection.rollback()
        print("Profile Update Error:", e)
        flash("Error updating profile.", "danger")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("admin_settings"))
# =====================================================
# BLOCKCHAIN RECORDS
# =====================================================

@app.route("/admin/blockchain")
@admin_required
def blockchain_records():

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "danger"
        )
        return redirect(
            url_for("admin_dashboard")
        )

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            b.*,
            s.student_name
        FROM blockchain_records b
        JOIN certificates c
            ON b.certificate_id = c.certificate_id
        JOIN students s
            ON c.student_id = s.student_id
        ORDER BY b.created_at DESC
        """
    )

    records = cursor.fetchall()

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM blockchain_records
        """
    )

    total_records = cursor.fetchone()["total"]

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM blockchain_records
        WHERE status = 'Confirmed'
        """
    )

    confirmed_records = cursor.fetchone()["total"]

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM blockchain_records
        WHERE status = 'Pending'
        """
    )

    pending_records = cursor.fetchone()["total"]

    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM blockchain_records
        WHERE status = 'Failed'
        """
    )

    failed_records = cursor.fetchone()["total"]

    cursor.close()
    connection.close()

    return render_template(
        "admin/blockchain_records.html",
        blockchain_records=records,
        total_records=total_records,
        confirmed_records=confirmed_records,
        pending_records=pending_records,
        failed_records=failed_records
    )


# =====================================================
# BLOCKCHAIN RECORD DETAILS
# =====================================================

@app.route(
    "/admin/blockchain/<int:record_id>"
)
@admin_required
def blockchain_record_details(record_id):

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "danger"
        )
        return redirect(
            url_for("blockchain_records")
        )

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT
            b.*,
            c.course,
            c.issue_date,
            s.student_name,
            s.email
        FROM blockchain_records b
        JOIN certificates c
            ON b.certificate_id = c.certificate_id
        JOIN students s
            ON c.student_id = s.student_id
        WHERE b.record_id = %s
        """,
        (record_id,)
    )

    record = cursor.fetchone()

    cursor.close()
    connection.close()

    if record is None:
        return "Blockchain record not found", 404

    return render_template(
        "admin/blockchain_record_details.html",
        record=record
    )


# =====================================================
# ADMIN PROFILE / SETTINGS
# =====================================================

@app.route("/admin/settings")
@admin_required
def admin_settings():

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "danger"
        )
        return redirect(
            url_for("admin_dashboard")
        )

    cursor = connection.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT *
            FROM admins
            WHERE admin_id = %s
            """,
            (session["admin_id"],)
        )

        admin = cursor.fetchone()

    except Error as e:

        print("Settings Error:", e)

        flash(
            "Error loading settings.",
            "danger"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    finally:

        cursor.close()
        connection.close()

    if admin is None:

        flash(
            "Administrator record not found.",
            "danger"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    return render_template(
        "admin/setting.html",
        admin=admin
    )
# =====================================================
# CHANGE ADMIN PASSWORD
# =====================================================

@app.route(
    "/admin/password/change",
    methods=["POST"]
)
@admin_required
def change_password():

    current_password = request.form.get(
        "current_password"
    )

    new_password = request.form.get(
        "new_password"
    )

    confirm_password = request.form.get(
        "confirm_password"
    )

    if new_password != confirm_password:

        flash(
            "New passwords do not match.",
            "danger"
        )

        return redirect(
            url_for("admin_settings")
        )

    connection = get_db_connection()

    if connection is None:
        flash(
            "Database connection failed.",
            "danger"
        )
        return redirect(
            url_for("admin_settings")
        )

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT password
        FROM admins
        WHERE admin_id = %s
        """,
        (session["admin_id"],)
    )

    admin = cursor.fetchone()

    if admin is None:

        cursor.close()
        connection.close()

        flash(
            "Administrator not found.",
            "danger"
        )

        return redirect(
            url_for("admin_settings")
        )

    if not check_password_hash(
        admin["password"],
        current_password
    ):

        cursor.close()
        connection.close()

        flash(
            "Current password is incorrect.",
            "danger"
        )

        return redirect(
            url_for("admin_settings")
        )

    new_password_hash = generate_password_hash(
        new_password
    )

    cursor.execute(
        """
        UPDATE admins
        SET password = %s
        WHERE admin_id = %s
        """,
        (
            new_password_hash,
            session["admin_id"]
        )
    )

    connection.commit()

    cursor.close()
    connection.close()

    flash(
        "Password changed successfully.",
        "success"
    )

    return redirect(
        url_for("admin_settings")
    )


# =====================================================
# LOGOUT
# =====================================================

@app.route("/admin/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out successfully.",
        "success"
    )

    return redirect(
        url_for("admin_login")
    )

@app.route('/student/logout')
def student_logout():

    session.clear()

    flash("You have been logged out.", "success")

    return redirect(url_for('student_login'))
# =====================================================
# APPLICATION RUN
# =====================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )