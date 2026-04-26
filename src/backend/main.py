import smtplib
from email.mime.text import MIMEText

from db import get_conn, init_db

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from web3 import Web3
import logging
import uuid
import random

from dotenv import load_dotenv
import os

from ipfs import add_to_ipfs
from blockchain import store_file, contract

app = FastAPI()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("app")

# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://internet-advanced-project.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# =========================
# STARTUP
# =========================
@app.on_event("startup")
def startup():
    init_db()

# =========================
# SEND EMAIL
# =========================
def send_email(to_email: str, permission_id: str):
    msg = MIMEText(f"Your Permission ID is: {permission_id}")
    msg["Subject"] = "Web3 Permission ID"
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(EMAIL_SENDER, EMAIL_PASSWORD)
    server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
    server.quit()

    print(f"[EMAIL SENT] {to_email} -> {permission_id}")

# =========================
# CREATE PERMISSION
# =========================
@app.post("/create-permission")
def create_permission(email: str = Form(...)):
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        "SELECT id, user_address FROM permissions WHERE email=%s",
        (email,)
    )
    existing = c.fetchone()

    if existing:
        permission_id, user_address = existing
        conn.close()
        send_email(email, permission_id)
        return {"status": "exists", "permission_id": permission_id, "user_address": user_address}

    permission_id = str(uuid.uuid4())[:12]
    user_address = "0x" + "".join(random.choices("0123456789abcdef", k=40))

    c.execute(
        "INSERT INTO permissions (id, email, user_address) VALUES (%s, %s, %s)",
        (permission_id, email, user_address)
    )
    conn.commit()
    conn.close()

    send_email(email, permission_id)
    return {"status": "success", "permission_id": permission_id, "user_address": user_address}

# =========================
# LOGIN
# =========================
@app.post("/login")
def login(permission_id: str = Form(...)):
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        "SELECT email, user_address FROM permissions WHERE id=%s",
        (permission_id.strip(),)
    )
    row = c.fetchone()
    conn.close()

    if not row:
        return {"error": "invalid permission"}

    email, user_address = row
    return {"status": "success", "email": email, "user_address": user_address, "permission_id": permission_id}

# =========================
# HELPERS
# =========================
def to_checksum(addr):
    try:
        return Web3.to_checksum_address(addr)
    except:
        return addr

def build_ipfs_url(cid):
    return f"https://gateway.pinata.cloud/ipfs/{cid}"

# =========================
# FETCH FILES
# =========================
def fetch_all_files():
    count = contract.functions.getTotalFiles().call()
    files = []

    for i in range(1, count + 1):
        cid, owner, uploader, filename, timestamp, is_public = contract.functions.getFile(i).call()
        files.append({
            "id": i,
            "cid": cid,
            "owner": to_checksum(owner),
            "uploader": to_checksum(uploader),
            "filename": filename,
            "timestamp": timestamp,
            "isPublic": is_public,
            "ipfs_url": build_ipfs_url(cid)
        })

    return files

# =========================
# UPLOAD
# =========================
@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    permission_id: str = Form(None),
    user_address: str = Form(None)
):
    logger.info("===== UPLOAD START =====")

    if user_address:
        addr = user_address

    elif permission_id:
        conn = get_conn()
        c = conn.cursor()
        c.execute(
            "SELECT user_address FROM permissions WHERE id=%s",
            (permission_id,)
        )
        row = c.fetchone()
        conn.close()

        if not row:
            return JSONResponse(status_code=400, content={"error": "invalid permission"})

        addr = row[0]
        if not addr:
            return JSONResponse(status_code=400, content={"error": "user_address missing"})

    else:
        return JSONResponse(status_code=400, content={"error": "missing permission_id or user_address"})

    content = await file.read()
    cid = add_to_ipfs(content, file.filename)
    tx_hash = store_file(cid, file.filename, addr)

    return {"status": "success", "cid": cid, "tx_hash": tx_hash, "uploader": addr}

# =========================
# MY FILES
# =========================
@app.get("/my-files/{user_address}")
def get_my_files(user_address: str):
    user_address = to_checksum(user_address)
    files = fetch_all_files()
    return [
        f for f in files
        if f["owner"].lower() == user_address.lower()
        or f["uploader"].lower() == user_address.lower()
    ]

# =========================
# SHARED FILES
# =========================
@app.get("/shared-files/{user_address}")
def get_shared_files(user_address: str):
    user_address = to_checksum(user_address)
    files = fetch_all_files()
    return [
        f for f in files
        if f["uploader"].lower() != user_address.lower()
    ]

# =========================
# REFRESH
# =========================
@app.get("/refresh")
def refresh():
    files = fetch_all_files()
    return {"total": len(files)}

# =========================
# RUN
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)