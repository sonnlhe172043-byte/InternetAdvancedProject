from web3 import Web3
import os
import json
from dotenv import load_dotenv

# ======================
# BASE DIRECTORY
# ======================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ======================
# LOAD ENV
# ======================
load_dotenv()

private_key = os.getenv("PRIVATE_KEY")
contract_address = os.getenv("CONTRACT_ADDRESS")

if not contract_address:
    raise Exception("CONTRACT_ADDRESS not found in .env")

if not private_key:
    raise Exception("PRIVATE_KEY not found in .env")

# ======================
# CONNECT WEB3
# ======================
w3 = Web3(Web3.HTTPProvider(os.getenv("INFURA_URL")))

if not w3.is_connected():
    raise Exception("Failed to connect to blockchain")

# ======================
# LOAD ABI
# ======================
ABI_PATH = os.path.join(BASE_DIR, "..", "..", "contracts", "abi", "FileStorage.json")

with open(ABI_PATH, "r") as f:
    abi = json.load(f)

# ======================
# CONTRACT
# ======================
contract = w3.eth.contract(
    address=Web3.to_checksum_address(contract_address),
    abi=abi
)

# ======================
# STORE FILE
# ======================
def store_file(cid, filename, user_address):
    try:
        # checksum address
        user_address = Web3.to_checksum_address(user_address)

        account = w3.eth.account.from_key(private_key)

        nonce = w3.eth.get_transaction_count(account.address)

        tx = contract.functions.uploadFile(
            cid,
            filename,
            user_address
        ).build_transaction({
            "from": account.address,
            "nonce": nonce,
            "gas": 300000,
            "chainId": 11155111,
            "maxFeePerGas": w3.to_wei("2", "gwei"),
            "maxPriorityFeePerGas": w3.to_wei("1", "gwei"),
        })

        signed_tx = w3.eth.account.sign_transaction(tx, private_key)

        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)

        tx_hex = tx_hash.hex()

        print("TX HASH:", tx_hex)

        return tx_hex

    except Exception as e:
        print("ERROR store_file:", str(e))
        raise