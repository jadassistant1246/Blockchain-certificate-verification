CREATE DATABASE IF NOT EXISTS blockchain_certificate;
USE blockchain_certificate;

-- =====================================================
-- 1. ADMINS TABLE
-- =====================================================

CREATE TABLE admins (
    admin_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    phone VARCHAR(20),
    password VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'System Administrator',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 2. STUDENTS TABLE
-- =====================================================

CREATE TABLE students (
    student_id INT AUTO_INCREMENT PRIMARY KEY,
    student_name VARCHAR(150) NOT NULL,
    email VARCHAR(150) NOT NULL UNIQUE,
    phone VARCHAR(20),
    department VARCHAR(100),
    course VARCHAR(150),
    enrollment_no VARCHAR(100) UNIQUE,
    admission_year YEAR,
    status ENUM('Verified', 'Pending', 'Inactive') DEFAULT 'Pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =====================================================
-- 3. CERTIFICATES TABLE
-- =====================================================

CREATE TABLE certificates (
    certificate_id INT AUTO_INCREMENT PRIMARY KEY,

    student_id INT NOT NULL,

    certificate_type VARCHAR(100),
    course VARCHAR(150),

    issue_date DATE NOT NULL,

    certificate_hash VARCHAR(255) NOT NULL UNIQUE,

    pdf_path VARCHAR(255),

    status ENUM(
        'Verified',
        'Pending',
        'Revoked'
    ) DEFAULT 'Pending',

    revoked_at DATETIME NULL,

    revoked_by VARCHAR(100) NULL,

    revocation_reason TEXT NULL,

    blockchain_status ENUM(
        'Confirmed',
        'Pending',
        'Failed'
    ) DEFAULT 'Pending',

    transaction_hash VARCHAR(255),

    FOREIGN KEY (student_id)
        REFERENCES students(student_id)
        ON DELETE RESTRICT
);

-- =====================================================
-- 4. VERIFICATION LOGS TABLE
-- =====================================================

CREATE TABLE verification_logs (

    verification_id INT AUTO_INCREMENT PRIMARY KEY,

    certificate_id INT NOT NULL,

    verifier_name VARCHAR(150),
    verifier_email VARCHAR(150),

    verified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    result ENUM(
        'Valid',
        'Invalid',
        'Pending'
    ) DEFAULT 'Pending',

    blockchain_status ENUM(
        'Confirmed',
        'Pending',
        'Failed'
    ) DEFAULT 'Pending',

    FOREIGN KEY (certificate_id)
        REFERENCES certificates(certificate_id)
        ON DELETE RESTRICT
);

-- =====================================================
-- 5. BLOCKCHAIN RECORDS TABLE
-- =====================================================

CREATE TABLE blockchain_records (

    record_id INT AUTO_INCREMENT PRIMARY KEY,

    certificate_id INT NOT NULL,

    certificate_hash VARCHAR(255) NOT NULL,

    transaction_hash VARCHAR(255),

    block_number BIGINT,

    network VARCHAR(100) DEFAULT 'Ethereum',

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    status ENUM(
        'Confirmed',
        'Pending',
        'Failed'
    ) DEFAULT 'Pending',

    FOREIGN KEY (certificate_id)
        REFERENCES certificates(certificate_id)
        ON DELETE RESTRICT
);

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL
);
-- 5. Blockchain certificate