# =========================================================
# IMPORTS
# =========================================================

from web3 import Web3
from flask import Flask, render_template, request, redirect, url_for, flash, session
import mysql.connector
from PyPDF2 import PdfReader

# PDF + QR processing
import io
import re
import fitz
import cv2
import numpy as np


# =========================================================
# FLASK APP
# =========================================================

app = Flask(__name__)

app.secret_key = "certificate_verification_secret"


# =========================================================
# MYSQL CONNECTION
# =========================================================

def get_db_connection():

    connection = mysql.connector.connect(
        host="127.0.0.1",
        user="root",
        password="Rudrayani@123",
        database="certificate_db"
    )

    return connection


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

        name = request.form["name"].strip()
        email = request.form["email"].strip()
        password = request.form["password"]
        role = request.form["role"]

        connection = get_db_connection()
        cursor = connection.cursor()

        # Check existing email
        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE email = %s
            """,
            (email,)
        )

        existing_user = cursor.fetchone()

        if existing_user:

            cursor.close()
            connection.close()

            flash(
                "Email already registered!",
                "error"
            )

            return redirect(
                url_for("register")
            )

        # Insert user
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
            (
                %s,
                %s,
                %s,
                %s
            )
            """,
            (
                name,
                email,
                password,
                role
            )
        )

        connection.commit()

        cursor.close()
        connection.close()

        flash(
            "Registration successful! Please login.",
            "success"
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "register.html"
    )


# =========================================================
# LOGIN
# =========================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"].strip()
        password = request.form["password"]

        connection = get_db_connection()

        cursor = connection.cursor(
            dictionary=True
        )

        cursor.execute(
            """
            SELECT *
            FROM users
            WHERE email = %s
            AND password = %s
            """,
            (
                email,
                password
            )
        )

        user = cursor.fetchone()

        cursor.close()
        connection.close()

        if user:

            # Store session
            session["user_id"] = user["id"]
            session["role"] = user["role"]

            flash(
                "Login successful!",
                "success"
            )

            # Student
            if user["role"] == "student":

                return redirect(
                    url_for("student_dashboard")
                )

            # Admin
            elif user["role"] == "admin":

                return redirect(
                    url_for("admin_dashboard")
                )

        else:

            flash(
                "Invalid email or password",
                "error"
            )

    return render_template(
        "login.html"
    )


# =========================================================
# STUDENT DASHBOARD
# =========================================================

@app.route("/student-dashboard")
def student_dashboard():

    # Login check
    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    # Student check
    if session.get("role") != "student":

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

    cursor.execute(
        """
        SELECT *
        FROM certificates
        WHERE student_id = %s
        ORDER BY id DESC
        """,
        (
            session["user_id"],
        )
    )

    certificates = cursor.fetchall()

    cursor.close()
    connection.close()

    return render_template(
        "student/student_dashboard.html",
        certificates=certificates
    )


# =========================================================
# VIEW CERTIFICATE
# =========================================================

@app.route("/view-certificate/<certificate_id>")
def view_certificate(certificate_id):

    # Login check
    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    # Student check
    if session.get("role") != "student":

        return redirect(
            url_for("login")
        )

    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )

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
# LOGOUT
# =========================================================

@app.route("/logout")
def logout():

    session.clear()

    flash(
        "You have been logged out successfully.",
        "success"
    )

    return redirect(
        url_for("login")
    )


# =========================================================
# ADMIN DASHBOARD
# =========================================================

@app.route("/admin-dashboard")
def admin_dashboard():

    # Login check
    if "user_id" not in session:

        return redirect(
            url_for("login")
        )

    # Admin check
    if session.get("role") != "admin":

        return redirect(
            url_for("login")
        )

    return render_template(
        "admin_dashboard.html"
    )


# =========================================================
# BLOCKCHAIN CONNECTION
# =========================================================

w3 = Web3(
    Web3.HTTPProvider(
        "http://127.0.0.1:7545"
    )
)


# =========================================================
# DEPLOYED CONTRACT ADDRESS
# =========================================================

CONTRACT_ADDRESS = (
    "0x460deEaE67225f91642f2626636206Cc5259F649"
)


# =========================================================
# CONTRACT ABI
# =========================================================

CONTRACT_ABI = [

    # =====================================================
    # verifyCertificate
    # =====================================================

    {
        "inputs": [
            {
                "internalType": "string",
                "name": "_certificateId",
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


    # =====================================================
    # getCertificate
    # =====================================================

    {
        "inputs": [
            {
                "internalType": "string",
                "name": "_certificateId",
                "type": "string"
            }
        ],

        "name": "getCertificate",

        "outputs": [
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
            },
            {
                "internalType": "uint256",
                "name": "issueDate",
                "type": "uint256"
            },
            {
                "internalType": "address",
                "name": "issuer",
                "type": "address"
            },
            {
                "internalType": "bool",
                "name": "revoked",
                "type": "bool"
            }
        ],

        "stateMutability": "view",
        "type": "function"
    }
]


# =========================================================
# CONTRACT OBJECT
# =========================================================

contract = w3.eth.contract(
    address=CONTRACT_ADDRESS,
    abi=CONTRACT_ABI
)


# =========================================================
# EXTRACT CERTIFICATE ID FROM PDF TEXT
# =========================================================

def extract_certificate_id_from_pdf(pdf_bytes):

    try:

        reader = PdfReader(
            io.BytesIO(pdf_bytes)
        )

        pdf_text = ""

        # Read every page
        for page in reader.pages:

            page_text = page.extract_text()

            if page_text:

                pdf_text += (
                    page_text + "\n"
                )

        print("\n========== PDF TEXT ==========")
        print(pdf_text)
        print("===============================\n")


        # -------------------------------------------------
        # Search Certificate ID
        #
        # Examples:
        #
        # Certificate ID: CERT101
        # Certificate ID - CERT101
        # Certificate ID CERT101
        # -------------------------------------------------

        match = re.search(
            r"Certificate\s*ID\s*[:=\-]?\s*([A-Za-z0-9_-]+)",
            pdf_text,
            re.IGNORECASE
        )

        if match:

            certificate_id = (
                match.group(1).strip()
            )

            print(
                "CERTIFICATE ID FROM PDF:",
                certificate_id
            )

            return certificate_id

    except Exception as e:

        print(
            "PDF TEXT ERROR:",
            repr(e)
        )

    return None


# =========================================================
# EXTRACT CERTIFICATE ID FROM QR CODE
# =========================================================

def extract_certificate_id_from_qr(pdf_bytes):

    doc = None

    try:

        doc = fitz.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

        detector = cv2.QRCodeDetector()


        # Scan every page
        for page_number, page in enumerate(doc):

            print(
                "SCANNING QR - PAGE:",
                page_number + 1
            )


            # -------------------------------------------------
            # Convert PDF page into image
            # -------------------------------------------------

            pix = page.get_pixmap(
                matrix=fitz.Matrix(3, 3),
                alpha=False
            )


            img = np.frombuffer(
                pix.samples,
                dtype=np.uint8
            )


            img = img.reshape(
                pix.height,
                pix.width,
                pix.n
            )


            # -------------------------------------------------
            # Convert RGB/RGBA to BGR
            # -------------------------------------------------

            if pix.n == 4:

                img = cv2.cvtColor(
                    img,
                    cv2.COLOR_RGBA2BGR
                )

            else:

                img = cv2.cvtColor(
                    img,
                    cv2.COLOR_RGB2BGR
                )


            # =================================================
            # FIRST QR SCAN
            # =================================================

            data, points, _ = (
                detector.detectAndDecode(img)
            )


            if data:

                certificate_id = data.strip()

                print(
                    "QR DATA FOUND:",
                    certificate_id
                )


                return certificate_id


            # =================================================
            # SECOND QR SCAN - GRAYSCALE
            # =================================================

            gray = cv2.cvtColor(
                img,
                cv2.COLOR_BGR2GRAY
            )


            data, points, _ = (
                detector.detectAndDecode(gray)
            )


            if data:

                certificate_id = data.strip()

                print(
                    "QR DATA FOUND:",
                    certificate_id
                )


                return certificate_id


    except Exception as e:

        print(
            "QR ERROR:",
            repr(e)
        )


    finally:

        if doc:

            try:
                doc.close()
            except:
                pass


    return None


# =========================================================
# SAVE VERIFICATION HISTORY
# =========================================================

def save_verification_history(
    certificate_id,
    certificate=None,
    status="Invalid"
):

    # User must be logged in
    if "user_id" not in session:

        print(
            "USER NOT LOGGED IN."
        )

        return


    connection = None
    cursor = None


    try:

        connection = get_db_connection()

        cursor = connection.cursor()


        # Default values
        student_name = ""
        course_name = ""
        institution_name = ""
        certificate_hash = ""
        issue_date = ""
        issuer = ""


        # If blockchain certificate exists
        if certificate:

            student_name = certificate[1]
            course_name = certificate[2]
            institution_name = certificate[3]
            certificate_hash = certificate[4]
            issue_date = str(certificate[5])
            issuer = str(certificate[6])


        # -------------------------------------------------
        # Insert history
        # -------------------------------------------------

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
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s
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


        print(
            "VERIFICATION HISTORY SAVED:",
            certificate_id,
            status
        )


    except Exception as e:

        print(
            "HISTORY SAVE ERROR:",
            repr(e)
        )

        if connection:

            try:
                connection.rollback()
            except:
                pass


    finally:

        if cursor:

            try:
                cursor.close()
            except:
                pass

        if connection:

            try:
                connection.close()
            except:
                pass


# =========================================================
# VERIFY CERTIFICATE
# =========================================================

@app.route(
    "/verify",
    methods=["GET", "POST"]
)
def verify_certificate():

    # =====================================================
    # GET
    # =====================================================

    if request.method == "GET":

        return render_template(
            "verify.html"
        )


    # =====================================================
    # GET CERTIFICATE ID FROM FORM
    # =====================================================

    certificate_id = request.form.get(
        "certificate_id",
        ""
    ).strip()


    # =====================================================
    # GET PDF FILE
    # =====================================================

    certificate_file = request.files.get(
        "certificate_file"
    )


    # =====================================================
    # PDF UPLOAD
    # =====================================================

    if certificate_file and certificate_file.filename:

        # Check extension
        if not certificate_file.filename.lower().endswith(".pdf"):

            flash(
                "Please upload a PDF certificate.",
                "error"
            )

            return render_template(
                "verify.html"
            )


        try:

            # Read PDF bytes
            pdf_bytes = (
                certificate_file.read()
            )


            # =================================================
            # STEP 1
            # SEARCH CERTIFICATE ID IN PDF TEXT
            # =================================================

            certificate_id = (
                extract_certificate_id_from_pdf(
                    pdf_bytes
                )
            )


            # =================================================
            # STEP 2
            # IF ID NOT FOUND → QR SCAN
            # =================================================

            if not certificate_id:

                print(
                    "Certificate ID not found in PDF text."
                )

                print(
                    "Trying QR code..."
                )


                certificate_id = (
                    extract_certificate_id_from_qr(
                        pdf_bytes
                    )
                )


            # =================================================
            # STEP 3
            # NOTHING FOUND
            # =================================================

            if not certificate_id:

                flash(
                    "Certificate ID and QR code were not found in the PDF.",
                    "error"
                )

                return render_template(
                    "verify.html"
                )


            print(
                "FINAL CERTIFICATE ID:",
                certificate_id
            )


        except Exception as e:

            print(
                "PDF PROCESSING ERROR:",
                repr(e)
            )

            flash(
                "Unable to process the uploaded PDF.",
                "error"
            )

            return render_template(
                "verify.html"
            )


    # =====================================================
    # CHECK CERTIFICATE ID
    # =====================================================

    if not certificate_id:

        flash(
            "Please enter Certificate ID or upload a certificate PDF.",
            "error"
        )

        return render_template(
            "verify.html"
        )


    print(
        "\n================================"
    )

    print(
        "VERIFYING CERTIFICATE:",
        certificate_id
    )

    print(
        "================================"
    )


    # =====================================================
    # BLOCKCHAIN CONNECTION
    # =====================================================

    try:

        if not w3.is_connected():

            print(
                "BLOCKCHAIN NOT CONNECTED"
            )

            return """
            <!DOCTYPE html>
            <html>
            <head>
                <title>Blockchain Error</title>
            </head>

            <body>

                <h2>Blockchain Connection Failed</h2>

                <p>
                    Please make sure Ganache is running.
                </p>

                <a href="/verify">
                    Go Back
                </a>

            </body>
            </html>
            """, 500


        # =================================================
        # BLOCKCHAIN VERIFICATION
        # =================================================

        exists, valid = (
            contract
            .functions
            .verifyCertificate(
                certificate_id
            )
            .call()
        )


        print(
            "EXISTS:",
            exists
        )

        print(
            "VALID:",
            valid
        )


        # =================================================
        # CERTIFICATE DOES NOT EXIST
        # =================================================

        if not exists:

            print(
                "CERTIFICATE NOT FOUND"
            )


            # Save invalid history
            save_verification_history(
                certificate_id=certificate_id,
                certificate=None,
                status="Invalid"
            )


            result = {

                "certificateId":
                    certificate_id,

                "studentName":
                    "",

                "courseName":
                    "",

                "institutionName":
                    "",

                "certificateHash":
                    "",

                "issueDate":
                    "",

                "issuer":
                    "",

                "valid":
                    False,

                "status":
                    "Certificate Not Found"
            }


            return render_template(
                "verification_result.html",
                result=result
            )


        # =================================================
        # GET CERTIFICATE
        # =================================================

        certificate = (
            contract
            .functions
            .getCertificate(
                certificate_id
            )
            .call()
        )


        print(
            "CERTIFICATE DATA:",
            certificate
        )


        # =================================================
        # STATUS
        # =================================================

        if valid:

            status = "Valid"

        else:

            status = "Invalid"


        # =================================================
        # SAVE HISTORY ONLY ONCE
        # =================================================

        save_verification_history(
            certificate_id=certificate_id,
            certificate=certificate,
            status=status
        )


        # =================================================
        # PREPARE RESULT
        # =================================================

        result = {

            "certificateId":
                certificate[0],

            "studentName":
                certificate[1],

            "courseName":
                certificate[2],

            "institutionName":
                certificate[3],

            "certificateHash":
                certificate[4],

            "issueDate":
                certificate[5],

            "issuer":
                certificate[6],

            "valid":
                valid,

            "status":
                status
        }


        print(
            "RESULT:",
            result
        )


        # =================================================
        # SHOW RESULT PAGE
        # =================================================

        return render_template(
            "verification_result.html",
            result=result
        )


    # =====================================================
    # ERROR
    # =====================================================

    except Exception as e:

        print(
            "VERIFY ERROR:",
            repr(e)
        )


        return f"""
        <!DOCTYPE html>

        <html>

        <head>

            <title>
                Verification Error
            </title>

        </head>


        <body>

            <h2>
                Verification Error
            </h2>


            <p>
                {e}
            </p>


            <br>


            <a href="/verify">
                Go Back
            </a>

        </body>

        </html>
        """, 500


# =========================================================
# VERIFIED CERTIFICATES
# =========================================================

@app.route(
    "/verified_certificates"
)
def verified_certificates():

    # =====================================================
    # LOGIN CHECK
    # =====================================================

    if "user_id" not in session:

        return redirect(
            url_for("login")
        )


    connection = get_db_connection()

    cursor = connection.cursor(
        dictionary=True
    )


    try:

        # Only logged-in user's history
        cursor.execute(
            """
            SELECT
                id,
                user_id,
                certificate_id,
                student_name,
                course_name,
                institution_name,
                certificate_hash,
                issue_date,
                issuer,
                status,
                verified_at
            FROM verification_history
            WHERE user_id = %s
            ORDER BY verified_at DESC
            """,
            (
                session["user_id"],
            )
        )


        certificates = (
            cursor.fetchall()
        )


    finally:

        cursor.close()
        connection.close()


    # =====================================================
    # VALID CERTIFICATES
    # =====================================================

    valid_certificates = [

        certificate

        for certificate in certificates

        if certificate["status"] == "Valid"

    ]


    # =====================================================
    # INVALID CERTIFICATES
    # =====================================================

    invalid_certificates = [

        certificate

        for certificate in certificates

        if certificate["status"] != "Valid"

    ]


    # =====================================================
    # SHOW PAGE
    # =====================================================

    return render_template(
        "verified_certificates.html",
        valid_certificates=valid_certificates,
        invalid_certificates=invalid_certificates
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )