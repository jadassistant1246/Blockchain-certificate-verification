// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract CertificateVerification {

    struct Certificate {
        string certificateId;
        string certificateHash;
        bool exists;
    }

    mapping(string => Certificate) private certificates;

    event CertificateIssued(
        string certificateId,
        string certificateHash
    );

    function issueCertificate(
        string memory _certificateId,
        string memory _certificateHash
    ) public {

        certificates[_certificateId] = Certificate(
            _certificateId,
            _certificateHash,
            true
        );

        emit CertificateIssued(
            _certificateId,
            _certificateHash
        );
    }

    function verifyCertificate(
        string memory _certificateId
    )
        public
        view
        returns (
            string memory,
            bool
        )
    {
        Certificate memory certificate =
            certificates[_certificateId];

        return (
            certificate.certificateHash,
            certificate.exists
        );
    }
}