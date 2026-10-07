import hashlib
import json
from datetime import datetime


class Block:
    def __init__(self, index, certificate_id, certificate_hash, previous_hash):
        self.index = index
        self.timestamp = str(datetime.now())
        self.certificate_id = certificate_id
        self.certificate_hash = certificate_hash
        self.previous_hash = previous_hash

        self.hash = self.calculate_hash()

    def calculate_hash(self):
        block_data = (
            str(self.index) +
            self.timestamp +
            self.certificate_id +
            self.certificate_hash +
            self.previous_hash
        )

        return hashlib.sha256(block_data.encode()).hexdigest()


class Blockchain:

    def __init__(self):
        self.chain = []

        # Create first block
        self.create_genesis_block()

    def create_genesis_block(self):
        genesis = Block(
            0,
            "GENESIS",
            "GENESIS",
            "0"
        )

        self.chain.append(genesis)

    def get_latest_block(self):
        return self.chain[-1]

    def add_certificate(self, certificate_id, certificate_hash):

        previous_block = self.get_latest_block()

        new_block = Block(
            len(self.chain),
            certificate_id,
            certificate_hash,
            previous_block.hash
        )

        self.chain.append(new_block)

        return new_block

    def find_certificate(self, certificate_id):

        for block in self.chain:

            if block.certificate_id == certificate_id:
                return block

        return None