# blockchain.py

from web3 import Web3
from dotenv import load_dotenv

import threading
import os
import json
import time

# =========================
# LOAD ENV
# =========================
load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
INFURA_URL = os.getenv("INFURA_URL")

if not PRIVATE_KEY:
    raise Exception("PRIVATE_KEY missing")

if not CONTRACT_ADDRESS:
    raise Exception("CONTRACT_ADDRESS missing")

if not INFURA_URL:
    raise Exception("INFURA_URL missing")

# =========================
# WEB3
# =========================
w3 = Web3(
    Web3.HTTPProvider(
        INFURA_URL,
        request_kwargs={
            "timeout": 30
        }
    )
)

if not w3.is_connected():
    raise Exception("Cannot connect to blockchain")

# =========================
# ABI
# =========================
BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

ABI_PATH = os.path.join(
    BASE_DIR,
    "contracts",
    "abi",
    "FileStorage.json"
)

with open(ABI_PATH, "r") as f:
    abi = json.load(f)

# =========================
# CONTRACT
# =========================
contract = w3.eth.contract(
    address=Web3.to_checksum_address(
        CONTRACT_ADDRESS
    ),
    abi=abi
)

# =========================
# ACCOUNT
# =========================
account = w3.eth.account.from_key(
    PRIVATE_KEY
)

# =========================
# NONCE LOCK
# =========================
nonce_lock = threading.Lock()

# =========================
# CONFIG
# =========================
CHAIN_ID = 11155111

DEFAULT_PRIORITY_FEE_GWEI = 2

GAS_BUFFER = 1.2

MAX_RETRY = 5

# =========================
# STORE FILE
# =========================
def store_file(
    cid,
    filename,
    user_address,
    retry=MAX_RETRY
):

    # =========================
    # CHECKSUM ADDRESS
    # =========================
    user_address = Web3.to_checksum_address(
        user_address
    )

    for attempt in range(retry):

        try:

            # =========================
            # GET LATEST BLOCK
            # =========================
            latest_block = w3.eth.get_block(
                "latest"
            )

            # =========================
            # EIP-1559 FEES
            # =========================
            base_fee = latest_block.get(
                "baseFeePerGas",
                w3.to_wei(1, "gwei")
            )

            priority_fee = w3.to_wei(
                DEFAULT_PRIORITY_FEE_GWEI,
                "gwei"
            )

            max_fee = int(
                base_fee * 2 + priority_fee
            )

            # =========================
            # NONCE LOCK
            # =========================
            with nonce_lock:

                # =========================
                # NONCE
                # =========================
                nonce = w3.eth.get_transaction_count(
                    account.address,
                    "pending"
                )

                # =========================
                # CONTRACT FUNCTION
                # =========================
                contract_function = (
                    contract.functions.uploadFile(
                        cid,
                        filename,
                        user_address
                    )
                )

                # =========================
                # ESTIMATE GAS
                # =========================
                gas_estimate = (
                    contract_function.estimate_gas({
                        "from": account.address
                    })
                )

                # =========================
                # GAS BUFFER
                # =========================
                gas_limit = int(
                    gas_estimate * GAS_BUFFER
                )

                # =========================
                # BUILD TRANSACTION
                # =========================
                tx = contract_function.build_transaction({
                    "from": account.address,
                    "nonce": nonce,
                    "gas": gas_limit,
                    "chainId": CHAIN_ID,
                    "maxFeePerGas": max_fee,
                    "maxPriorityFeePerGas": priority_fee,
                })

                # =========================
                # SIGN TRANSACTION
                # =========================
                signed_tx = (
                    w3.eth.account.sign_transaction(
                        tx,
                        PRIVATE_KEY
                    )
                )

                # =========================
                # SEND TRANSACTION
                # =========================
                tx_hash = (
                    w3.eth.send_raw_transaction(
                        signed_tx.raw_transaction
                    )
                )

            # =========================
            # TX HASH
            # =========================
            tx_hex = tx_hash.hex()

            print(
                f"[BLOCKCHAIN] "
                f"TX SENT: {tx_hex}"
            )

            # =========================
            # IMPORTANT
            # DO NOT WAIT RECEIPT
            # =========================
            return tx_hex

        except Exception as e:

            print(
                f"[BLOCKCHAIN] "
                f"Retry {attempt + 1}/{retry}: {e}"
            )

            # =========================
            # EXPONENTIAL BACKOFF
            # =========================
            if attempt < retry - 1:

                sleep_time = 2 ** attempt

                print(
                    f"[BLOCKCHAIN] "
                    f"Sleeping {sleep_time}s..."
                )

                time.sleep(sleep_time)

            else:

                raise Exception(
                    f"Blockchain upload failed: {e}"
                )