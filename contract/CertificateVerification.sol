// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract CertificateVerification {

    struct Certificate {
        string certificateId;
        string certificateHash;
        address issuer;
        uint256 issuedAt;
        bool exists;
    }

    mapping(string => Certificate) private certificates;

    function issueCertificate(
        string memory _certificateId,
        string memory _certificateHash
    ) public {

        require(
            !certificates[_certificateId].exists,
            "Certificate already exists"
        );

        certificates[_certificateId] = Certificate(
            _certificateId,
            _certificateHash,
            msg.sender,
            block.timestamp,
            true
        );
    }

    function verifyCertificate(
        string memory _certificateId
    )
        public
        view
        returns (
            string memory,
            string memory,
            address,
            uint256,
            bool
        )
    {
        Certificate memory cert = certificates[_certificateId];

        return (
            cert.certificateId,
            cert.certificateHash,
            cert.issuer,
            cert.issuedAt,
            cert.exists
        );
    }
}