import requests
import os
from dotenv import load_dotenv

load_dotenv()

PINATA_API_KEY = os.getenv("PINATA_API_KEY")
PINATA_SECRET_API_KEY = os.getenv("PINATA_SECRET_API_KEY")

PINATA_URL = "https://api.pinata.cloud/pinning/pinFileToIPFS"


# =========================
# UPLOAD FILE TO PINATA
# =========================
def add_to_ipfs(file_bytes, filename="file"):
    headers = {
        "pinata_api_key": PINATA_API_KEY,
        "pinata_secret_api_key": PINATA_SECRET_API_KEY,
    }

    files = {
        "file": (filename, file_bytes, "application/octet-stream")
    }

    print("\n--- PINATA REQUEST ---")
    print("Filename:", filename)
    print("Size:", len(file_bytes))

    response = requests.post(PINATA_URL, files=files, headers=headers)

    print("Status:", response.status_code)
    print("Response:", response.text)
    print("----------------------\n")

    if response.status_code != 200:
        raise Exception(f"Pinata error: {response.text}")

    return response.json()["IpfsHash"]


# =========================
# GET FILE FROM IPFS
# =========================
def get_from_ipfs(cid):
    return f"https://gateway.pinata.cloud/ipfs/{cid}"