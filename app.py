from flask import Flask, render_template, request, redirect, url_for, session, flash
from blockchain import Blockchain

blockchain = Blockchain()
import mysql.connector
from mysql.connector import Error

from functools import wraps

from werkzeug.security import generate_password_hash, check_password_hash


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

        # Total students
        cursor.execute(
            "SELECT COUNT(*) AS total FROM students"
        )
        total_students = cursor.fetchone()["total"]

        # Total certificates
        cursor.execute(
            "SELECT COUNT(*) AS total FROM certificates"
        )
        total_certificates = cursor.fetchone()["total"]

        # Total verified certificates
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM certificates
            WHERE status = 'Verified'
            """
        )
        verified_certificates = cursor.fetchone()["total"]

        # Total revoked certificates
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM certificates
            WHERE status = 'Revoked'
            """
        )
        revoked_certificates = cursor.fetchone()["total"]

        # Total verifications
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM verification_logs
            """
        )
        total_verifications = cursor.fetchone()["total"]

        # Blockchain records
        cursor.execute(
            """
            SELECT COUNT(*) AS total
            FROM blockchain_records
            """
        )
        total_blockchain_records = cursor.fetchone()["total"]

    except Error as e:

        flash(
            "Error loading dashboard data.",
            "danger"
        )

        print("Dashboard Error:", e)

        return redirect(url_for("admin_login"))

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
        total_blockchain_records=total_blockchain_records
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


        # ---------------------------------------------
        # CHECK PASSWORD
        # ---------------------------------------------

        if password != confirm_password:

            flash(
                "Passwords do not match.",
                "danger"
            )

            return redirect(
                url_for("admin_register")
            )


        # ---------------------------------------------
        # CONNECT DATABASE
        # ---------------------------------------------

        connection = get_db_connection()


        if connection is None:

            flash(
                "Database connection failed.",
                "danger"
            )

            return redirect(
                url_for("admin_register")
            )


        cursor = connection.cursor(
            dictionary=True
        )


        # ---------------------------------------------
        # CHECK EMAIL
        # ---------------------------------------------

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

            cursor.close()
            connection.close()


            flash(
                "An admin account with this email already exists.",
                "danger"
            )

            return redirect(
                url_for("admin_register")
            )


        # ---------------------------------------------
        # HASH PASSWORD
        # ---------------------------------------------

        hashed_password = generate_password_hash(
            password
        )


        # ---------------------------------------------
        # INSERT ADMIN
        # ---------------------------------------------

        cursor.execute(
            """
            INSERT INTO admins
            (
                name,
                email,
                phone,
                password,
                role
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
                hashed_password,
                role
            )
        )


        connection.commit()


        cursor.close()
        connection.close()


        # ---------------------------------------------
        # SUCCESS
        # ---------------------------------------------

        flash(
            "Admin account created successfully. Please login.",
            "success"
        )


        return redirect(
            url_for("admin_login")
        )


    # GET REQUEST

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

    cursor = connection.cursor(dictionary=True)


    cursor.execute(
        """
        SELECT
            s.*,

            (
                SELECT COUNT(*)
                FROM certificates c
                WHERE c.student_id = s.student_id
            ) AS certificates_count

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

    cursor = connection.cursor(dictionary=True)


    cursor.execute(
        """
        SELECT *
        FROM students
        WHERE student_id = %s
        """,
        (student_id,)
    )

    student = cursor.fetchone()


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


    cursor.close()
    connection.close()


    if student is None:

        return "Student not found", 404


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

    cursor = connection.cursor(dictionary=True)


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


    cursor.execute(
        """
        SELECT *
        FROM students
        WHERE student_id = %s
        """,
        (student_id,)
    )

    student = cursor.fetchone()


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

    cursor = connection.cursor(dictionary=True)


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
        WHERE status = 'Verified'
        """
    )

    verified_certificates = cursor.fetchone()["total"]


    cursor.execute(
        """
        SELECT COUNT(*) AS total
        FROM certificates
        WHERE status = 'Pending'
        """
    )

    pending_certificates = cursor.fetchone()["total"]


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

@app.route(
    "/admin/certificates/issue",
    methods=["GET", "POST"]
)
@admin_required
def issue_certificate():

    connection = get_db_connection()

    cursor = connection.cursor(dictionary=True)


    if request.method == "POST":

        student_id = request.form.get("student_id")
        certificate_type = request.form.get("certificate_type")
        course = request.form.get("course")
        issue_date = request.form.get("issue_date")
        certificate_hash = request.form.get("certificate_hash")
        pdf_path = request.form.get("pdf_path")


        cursor.execute(
            """
            INSERT INTO certificates
            (
                student_id,
                certificate_type,
                course,
                issue_date,
                certificate_hash,
                pdf_path,
                status,
                blockchain_status
            )

            VALUES
            (%s,%s,%s,%s,%s,%s,'Verified','Pending')
            """,

            (
                student_id,
                certificate_type,
                course,
                issue_date,
                certificate_hash,
                pdf_path
            )
        )


        certificate_id = cursor.lastrowid


        connection.commit()


        cursor.close()
        connection.close()


        flash(
            "Certificate issued successfully.",
            "success"
        )


        return redirect(
            url_for("admin_certificates")
        )


    cursor.execute(
        """
        SELECT *
        FROM students
        ORDER BY student_name
        """
    )

    students = cursor.fetchall()


    cursor.close()
    connection.close()


    return render_template(
        "admin/issue_certificate.html",
        students=students
    )


# =====================================================
# CERTIFICATE DETAILS
# =====================================================

@app.route(
    "/admin/certificates/<int:certificate_id>"
)
@admin_required
def certificate_details(certificate_id):

    connection = get_db_connection()

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
        "admin/revoked_certificates.html",

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

    cursor = connection.cursor(dictionary=True)


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


    if certificate is None:

        flash(
            "Certificate not found.",
            "danger"
        )

        cursor.close()
        connection.close()

        return redirect(
            url_for("admin_verification")
        )


    # =================================================
    # CHECK CERTIFICATE STATUS
    # =================================================

    if certificate["status"] == "Verified":

        result = "Valid"

    elif certificate["status"] == "Revoked":

        result = "Invalid"

    else:

        result = "Pending"


    blockchain_status = (
        certificate["blockchain_status"]
    )


    # =================================================
    # SAVE VERIFICATION HISTORY
    # =================================================

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
        (%s,%s,%s,%s,%s)
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


# =====================================================
# BLOCKCHAIN RECORDS
# =====================================================

@app.route("/admin/blockchain")
@admin_required
def blockchain_records():

    connection = get_db_connection()

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


    blockchain_records = cursor.fetchall()


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

        blockchain_records=blockchain_records,

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
# PROFILE / SETTINGS
# =====================================================

# =====================================================
# PROFILE / SETTINGS
# =====================================================

@app.route("/admin/settings")
@admin_required
def admin_settings():

    connection = get_db_connection()

    if connection is None:
        flash("Database connection failed.", "error")
        return redirect(url_for("admin_dashboard"))

    cursor = connection.cursor(dictionary=True)

    cursor.execute(
        """
        SELECT *
        FROM admins
        WHERE admin_id = %s
        """,
        (session["admin_id"],)
    )

    admin = cursor.fetchone()

    cursor.close()
    connection.close()

    if admin is None:
        flash("Administrator record not found.", "error")
        return redirect(url_for("admin_dashboard"))

    return render_template(
        "admin/setting.html",
        admin=admin
    )

# =====================================================
# UPDATE PROFILE
# =====================================================

@app.route(
    "/admin/profile/update",
    methods=["POST"]
)
@admin_required
def update_profile():

    name = request.form.get("name")
    email = request.form.get("email")
    phone = request.form.get("phone")


    connection = get_db_connection()

    cursor = connection.cursor()


    cursor.execute(
        """
        UPDATE admins

        SET
            name = %s,
            email = %s,
            phone = %s

        WHERE admin_id = %s
        """,

        (
            name,
            email,
            phone,
            session["admin_id"]
        )
    )


    connection.commit()


    session["admin_name"] = name
    session["admin_email"] = email


    cursor.close()
    connection.close()


    flash(
        "Profile updated successfully.",
        "success"
    )


    return redirect(
        url_for("admin_settings")
    )


# =====================================================
# CHANGE PASSWORD
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


    if not check_password_hash(
        admin["password"],
        current_password
    ):

        flash(
            "Current password is incorrect.",
            "danger"
        )

        cursor.close()
        connection.close()

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

    return redirect(
        url_for("admin_login")
    )


# =====================================================
# RUN APPLICATION
# =====================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )