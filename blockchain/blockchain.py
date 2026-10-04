from web3 import Web3
import json

RPC_URL = "http://127.0.0.1:7545"

web3 = Web3(Web3.HTTPProvider(RPC_URL))

CONTRACT_ADDRESS = "YOUR_CONTRACT_ADDRESS"

with open("blockchain/contract_abi.json", "r") as f:
    CONTRACT_ABI = json.load(f)

contract = web3.eth.contract(
    address=Web3.to_checksum_address(CONTRACT_ADDRESS),
    abi=CONTRACT_ABI
)