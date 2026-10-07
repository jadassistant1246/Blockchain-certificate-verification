// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract CertificateValidation {

    // Certificate structure
    struct Certificate {
        string certificateId;
        string studentName;
        string courseName;
        string institutionName;
        string certificateHash;
        uint256 issueDate;
        address issuer;
        bool revoked;
    }

    // Owner of the contract
    address public owner;

    // Certificate ID => Certificate
    mapping(string => Certificate) public certificates;

    // Certificate ID => exists or not
    mapping(string => bool) public certificateExists;

    // Address => authorized or not
    mapping(address => bool) public authorizedIssuers;


    // =========================
    // Events
    // =========================

    event CertificateIssued(
        string certificateId,
        string studentName,
        string courseName,
        string institutionName,
        address issuer
    );

    event CertificateRevoked(
        string certificateId,
        address revokedBy
    );

    event IssuerAuthorized(address issuer);

    event IssuerRemoved(address issuer);


    // =========================
    // Constructor
    // =========================

    constructor() {
        owner = msg.sender;

        // Contract deployer becomes authorized issuer
        authorizedIssuers[msg.sender] = true;
    }


    // =========================
    // Owner Modifier
    // =========================

    modifier onlyOwner() {
        require(
            msg.sender == owner,
            "Only owner can perform this action"
        );
        _;
    }


    // =========================
    // Issuer Modifier
    // =========================

    modifier onlyAuthorizedIssuer() {
        require(
            authorizedIssuers[msg.sender],
            "Not an authorized issuer"
        );
        _;
    }


    // =========================
    // Authorize Issuer
    // =========================

    function authorizeIssuer(address _issuer)
        public
        onlyOwner
    {
        require(
            _issuer != address(0),
            "Invalid issuer address"
        );

        authorizedIssuers[_issuer] = true;

        emit IssuerAuthorized(_issuer);
    }


    // =========================
    // Remove Issuer
    // =========================

    function removeIssuer(address _issuer)
        public
        onlyOwner
    {
        require(
            authorizedIssuers[_issuer],
            "Issuer is not authorized"
        );

        authorizedIssuers[_issuer] = false;

        emit IssuerRemoved(_issuer);
    }


    // =========================
    // Issue Certificate
    // =========================

    function issueCertificate(
        string memory _certificateId,
        string memory _studentName,
        string memory _courseName,
        string memory _institutionName,
        string memory _certificateHash
    )
        public
        onlyAuthorizedIssuer
    {
        require(
            bytes(_certificateId).length > 0,
            "Certificate ID is required"
        );

        require(
            bytes(_studentName).length > 0,
            "Student name is required"
        );

        require(
            bytes(_courseName).length > 0,
            "Course name is required"
        );

        require(
            bytes(_institutionName).length > 0,
            "Institution name is required"
        );

        require(
            !certificateExists[_certificateId],
            "Certificate already exists"
        );


        certificates[_certificateId] = Certificate({
            certificateId: _certificateId,
            studentName: _studentName,
            courseName: _courseName,
            institutionName: _institutionName,
            certificateHash: _certificateHash,
            issueDate: block.timestamp,
            issuer: msg.sender,
            revoked: false
        });


        certificateExists[_certificateId] = true;


        emit CertificateIssued(
            _certificateId,
            _studentName,
            _courseName,
            _institutionName,
            msg.sender
        );
    }


    // =========================
    // Verify Certificate
    // =========================

    function verifyCertificate(
        string memory _certificateId
    )
        public
        view
        returns (
            bool exists,
            bool valid
        )
    {
        exists = certificateExists[_certificateId];

        if (!exists) {
            return (false, false);
        }

        valid = !certificates[_certificateId].revoked;

        return (true, valid);
    }


    // =========================
    // Get Certificate Details
    // =========================

    function getCertificate(
        string memory _certificateId
    )
        public
        view
        returns (
            string memory certificateId,
            string memory studentName,
            string memory courseName,
            string memory institutionName,
            string memory certificateHash,
            uint256 issueDate,
            address issuer,
            bool revoked
        )
    {
        require(
            certificateExists[_certificateId],
            "Certificate does not exist"
        );

        Certificate memory cert = certificates[_certificateId];

        return (
            cert.certificateId,
            cert.studentName,
            cert.courseName,
            cert.institutionName,
            cert.certificateHash,
            cert.issueDate,
            cert.issuer,
            cert.revoked
        );
    }


    // =========================
    // Revoke Certificate
    // =========================

    function revokeCertificate(
        string memory _certificateId
    )
        public
    {
        require(
            certificateExists[_certificateId],
            "Certificate does not exist"
        );

        require(
            msg.sender == owner ||
            msg.sender == certificates[_certificateId].issuer,
            "Not authorized to revoke"
        );

        require(
            !certificates[_certificateId].revoked,
            "Certificate already revoked"
        );


        certificates[_certificateId].revoked = true;


        emit CertificateRevoked(
            _certificateId,
            msg.sender
        );
    }


    // =========================
    // Check Authorized Issuer
    // =========================

    function isAuthorizedIssuer(
        address _issuer
    )
        public
        view
        returns (bool)
    {
        return authorizedIssuers[_issuer];
    }
}