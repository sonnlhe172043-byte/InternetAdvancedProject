import smtplib
from email.mime.text import MIMEText
from contextlib import asynccontextmanager
import time

from db import get_conn, init_db

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from web3 import Web3
import logging
import uuid
import random
import traceback

from dotenv import load_dotenv
import os

from ipfs import add_to_ipfs
from blockchain import store_file, contract

load_dotenv()

# =========================
# LOGGING
# =========================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("app")

# =========================
# CACHE
# =========================
_cache = {
    "files": [],
    "last_updated": 0
}
CACHE_TTL = 60  # cache 60 giay

# =========================
# LIFESPAN
# =========================
@asynccontextmanager
async def lifespan(app):
    logger.info("Server dang khoi dong...")
    try:
        init_db()
        logger.info("Ket noi database thanh cong")
    except Exception as e:
        logger.error(f"Loi khoi tao database: {e}")
        logger.error(traceback.format_exc())
    yield
    logger.info("Server dang tat...")

# =========================
# APP
# =========================
app = FastAPI(lifespan=lifespan)

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

EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# =========================
# SEND EMAIL
# =========================
def send_email(to_email: str, permission_id: str):
    logger.info(f"[EMAIL] Dang gui toi {to_email}...")
    try:
        msg = MIMEText(f"Your Permission ID is: {permission_id}")
        msg["Subject"] = "Web3 Permission ID"
        msg["From"] = EMAIL_SENDER
        msg["To"] = to_email

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        server.quit()
        logger.info(f"[EMAIL] Gui thanh cong toi {to_email} | permission_id: {permission_id}")
    except Exception as e:
        logger.error(f"[EMAIL] Gui that bai toi {to_email}: {e}")
        logger.error(traceback.format_exc())

# =========================
# CREATE PERMISSION
# =========================
@app.post("/create-permission")
def create_permission(email: str = Form(...)):
    logger.info(f"[CREATE-PERMISSION] email: {email}")
    try:
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
            logger.info(f"[CREATE-PERMISSION] Email da ton tai: {email} | permission_id: {permission_id} | address: {user_address}")
            send_email(email, permission_id)
            return {"status": "exists", "permission_id": permission_id, "user_address": user_address}

        permission_id = str(uuid.uuid4())[:12]
        user_address = "0x" + "".join(random.choices("0123456789abcdef", k=40))
        logger.info(f"[CREATE-PERMISSION] Tao moi | permission_id: {permission_id} | address: {user_address}")

        c.execute(
            "INSERT INTO permissions (id, email, user_address) VALUES (%s, %s, %s)",
            (permission_id, email, user_address)
        )
        conn.commit()
        conn.close()
        logger.info(f"[CREATE-PERMISSION] Luu DB thanh cong | email: {email}")

        send_email(email, permission_id)
        return {"status": "success", "permission_id": permission_id, "user_address": user_address}

    except Exception as e:
        logger.error(f"[CREATE-PERMISSION] Loi: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": str(e)})

# =========================
# LOGIN
# =========================
@app.post("/login")
def login(permission_id: str = Form(...)):
    logger.info(f"[LOGIN] permission_id: {permission_id.strip()}")
    try:
        conn = get_conn()
        c = conn.cursor()

        c.execute(
            "SELECT email, user_address FROM permissions WHERE id=%s",
            (permission_id.strip(),)
        )
        row = c.fetchone()
        conn.close()

        if not row:
            logger.warning(f"[LOGIN] Khong tim thay permission_id: {permission_id}")
            return {"error": "invalid permission"}

        email, user_address = row
        logger.info(f"[LOGIN] Thanh cong | email: {email} | address: {user_address}")
        return {"status": "success", "email": email, "user_address": user_address, "permission_id": permission_id}

    except Exception as e:
        logger.error(f"[LOGIN] Loi: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": str(e)})

# =========================
# HELPERS
# =========================
def to_checksum(addr):
    try:
        return Web3.to_checksum_address(addr)
    except Exception as e:
        logger.warning(f"[CHECKSUM] That bai voi addr={addr}: {e}")
        return addr

def build_ipfs_url(cid):
    return f"https://gateway.pinata.cloud/ipfs/{cid}"

# =========================
# FETCH FILES (WITH CACHE)
# =========================
def fetch_all_files():
    global _cache

    now = int(time.time())

    if now - _cache["last_updated"] < CACHE_TTL and _cache["files"]:
        remaining = CACHE_TTL - (now - _cache["last_updated"])
        logger.info(f"[FETCH] Dung cache | tong: {len(_cache['files'])} files | con {remaining}s")
        return _cache["files"]

    logger.info("[FETCH] Cache het han, dang lay tu blockchain...")
    try:
        count = contract.functions.getTotalFiles().call()
        logger.info(f"[FETCH] Tong so files tren blockchain: {count}")
        files = []

        for i in range(1, count + 1):
            cid, owner, uploader, filename, timestamp, is_public = contract.functions.getFile(i).call()
            logger.info(f"[FETCH] File #{i} | name: {filename} | owner: {owner[:10]}... | uploader: {uploader[:10]}...")
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

        _cache["files"] = files
        _cache["last_updated"] = now
        logger.info(f"[FETCH] Cap nhat cache thanh cong | tong: {len(files)} files")
        return files

    except Exception as e:
        logger.error(f"[FETCH] That bai: {e}")
        logger.error(traceback.format_exc())
        raise

# =========================
# UPLOAD
# =========================
@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    permission_id: str = Form(None),
    user_address: str = Form(None)
):
    logger.info(f"[UPLOAD] filename: {file.filename} | permission_id: {permission_id} | user_address: {user_address}")
    try:
        if user_address:
            addr = user_address
            logger.info(f"[UPLOAD] Owner upload | address: {addr}")

        elif permission_id:
            logger.info(f"[UPLOAD] User upload | permission_id: {permission_id}")
            conn = get_conn()
            c = conn.cursor()
            c.execute(
                "SELECT user_address FROM permissions WHERE id=%s",
                (permission_id,)
            )
            row = c.fetchone()
            conn.close()

            if not row:
                logger.warning(f"[UPLOAD] permission_id khong hop le: {permission_id}")
                return JSONResponse(status_code=400, content={"error": "invalid permission"})

            addr = row[0]
            if not addr:
                logger.warning(f"[UPLOAD] user_address trong cho permission_id: {permission_id}")
                return JSONResponse(status_code=400, content={"error": "user_address missing"})

            logger.info(f"[UPLOAD] Tim thay address: {addr}")

        else:
            logger.error("[UPLOAD] Thieu ca permission_id va user_address")
            return JSONResponse(status_code=400, content={"error": "missing permission_id or user_address"})

        logger.info(f"[UPLOAD] Dang upload len IPFS | filename: {file.filename}")
        content = await file.read()
        cid = add_to_ipfs(content, file.filename)
        logger.info(f"[UPLOAD] IPFS thanh cong | CID: {cid}")

        logger.info(f"[UPLOAD] Dang luu len blockchain | CID: {cid} | addr: {addr}")
        tx_hash = store_file(cid, file.filename, addr)
        logger.info(f"[UPLOAD] Blockchain thanh cong | tx_hash: {tx_hash}")

        # Them file moi vao cache luon de hien thi ngay
        new_file = {
            "id": len(_cache["files"]) + 1,
            "cid": cid,
            "owner": to_checksum(addr),
            "uploader": to_checksum(addr),
            "filename": file.filename,
            "timestamp": int(time.time()),
            "isPublic": True,
            "ipfs_url": build_ipfs_url(cid)
        }
        _cache["files"].append(new_file)
        logger.info(f"[UPLOAD] Da them file moi vao cache | filename: {file.filename} | id: {new_file['id']}")

        return {"status": "success", "cid": cid, "tx_hash": tx_hash, "uploader": addr}



    except Exception as e:
        logger.error(f"[UPLOAD] Loi: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": str(e)})

# =========================
# MY FILES
# =========================
@app.get("/my-files/{user_address}")
def get_my_files(user_address: str):
    logger.info(f"[MY-FILES] user_address: {user_address}")
    try:
        user_address = to_checksum(user_address)
        files = fetch_all_files()

        thirty_minutes_ago = int(time.time()) - (30 * 60)
        logger.info(f"[MY-FILES] Chi lay files sau timestamp: {thirty_minutes_ago}")

        result = [
            f for f in files
            if (f["owner"].lower() == user_address.lower()
            or f["uploader"].lower() == user_address.lower())
            and f["timestamp"] >= thirty_minutes_ago
        ]
        logger.info(f"[MY-FILES] Tra ve {len(result)} files cho {user_address[:10]}...")
        return result

    except Exception as e:
        logger.error(f"[MY-FILES] Loi: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": str(e)})

# =========================
# SHARED FILES
# =========================
@app.get("/shared-files/{user_address}")
def get_shared_files(user_address: str):
    logger.info(f"[SHARED-FILES] user_address: {user_address}")
    try:
        user_address = to_checksum(user_address)
        files = fetch_all_files()

        thirty_minutes_ago = int(time.time()) - (30 * 60)
        logger.info(f"[SHARED-FILES] Chi lay files sau timestamp: {thirty_minutes_ago}")

        result = [
            f for f in files
            if f["uploader"].lower() != user_address.lower()
            and f["timestamp"] >= thirty_minutes_ago
        ]
        logger.info(f"[SHARED-FILES] Tra ve {len(result)} files cho {user_address[:10]}...")
        return result

    except Exception as e:
        logger.error(f"[SHARED-FILES] Loi: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": str(e)})

# =========================
# REFRESH
# =========================
@app.get("/refresh")
def refresh():
    logger.info("[REFRESH] Dang refresh...")
    try:
        # Xoa cache de buoc fetch lai tu blockchain
        _cache["last_updated"] = 0
        files = fetch_all_files()
        logger.info(f"[REFRESH] Tong: {len(files)} files")
        return {"total": len(files)}
    except Exception as e:
        logger.error(f"[REFRESH] Loi: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": str(e)})

# =========================
# RUN
# =========================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)