from web3 import Web3 # noqa
import os
import json
import threading
import time
from dotenv import load_dotenv # noqa

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
ABI_PATH = os.path.join(BASE_DIR, "contracts", "abi", "FileStorage.json")

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
# NONCE LOCK (chi lock phan lay nonce, khong lock ca tx)
# ======================
nonce_lock = threading.Lock()

# ======================
# STORE FILE
# ======================
def store_file(cid, filename, user_address, retry=3):
    user_address = Web3.to_checksum_address(user_address)
    account = w3.eth.account.from_key(private_key)

    for attempt in range(retry):
        try:
            # ✅ Chi lock luc lay nonce (vai ms), khong lock ca qua trinh gui tx
            with nonce_lock:
                nonce = w3.eth.get_transaction_count(account.address, 'pending')

            # ✅ Gas dong theo network
            base_fee = w3.eth.get_block('pending')['baseFeePerGas']

            tx = contract.functions.uploadFile(
                cid,
                filename,
                user_address
            ).build_transaction({
                "from": account.address,
                "nonce": nonce,
                "gas": 300000,
                "chainId": 11155111,
                "maxFeePerGas": int(base_fee * 2),
                "maxPriorityFeePerGas": w3.to_wei("1.5", "gwei"),
            })

            signed_tx = w3.eth.account.sign_transaction(tx, private_key)
            tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
            tx_hex = tx_hash.hex()

            print(f"TX HASH: {tx_hex}")
            return tx_hex

        except Exception as e:
            print(f"LOI store_file lan {attempt + 1}/{retry}: {str(e)}")
            if attempt < retry - 1:
                time.sleep(1)
            else:
                raise