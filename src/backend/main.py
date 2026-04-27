import smtplib
from email.mime.text import MIMEText
from contextlib import asynccontextmanager
import time
import threading

from db import get_conn, init_db

from fastapi import FastAPI, UploadFile, File, Form  # noqa
from fastapi.middleware.cors import CORSMiddleware # noqa
from fastapi.responses import JSONResponse, Response # noqa

from web3 import Web3 # noqa
import logging
import uuid
import random
import traceback

from dotenv import load_dotenv # noqa
import os

from ipfs import add_to_ipfs
from blockchain import store_file, contract, w3

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
    "last_updated": 0,
    "last_block": 0
}
CACHE_TTL = 300
MAX_BLOCK_RANGE = 40000
DEPLOY_BLOCK = 10398596  # block deploy contract FileStorage tren Sepolia

# =========================
# LIFESPAN
# =========================
@asynccontextmanager
async def lifespan(app): # noqa
    logger.info("Server dang khoi dong...")
    try:
        init_db()
        logger.info("Ket noi database thanh cong")
    except Exception as e:
        logger.error(f"Loi khoi tao database: {e}")
        logger.error(traceback.format_exc())

    threading.Thread(target=fetch_all_files, daemon=True).start()
    logger.info("[LIFESPAN] Dang fetch files ngam...")

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
# FETCH EVENTS WITH RETRY (xu ly 429 cho get_logs)
# =========================
def fetch_events_with_retry(from_block, to_block, retries=3):
    for attempt in range(retries): # noqa
        try:
            return contract.events.FileUploaded.get_logs(
                from_block=from_block,
                to_block=to_block
            )
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                wait = 2 ** attempt
                logger.warning(f"[FETCH] 429 get_logs | thu lai lan {attempt + 1} sau {wait}s...")
                time.sleep(wait)
            else:
                raise

# =========================
# GET FILE WITH RETRY (xu ly 429 cho getFile)
# =========================
def get_file_with_retry(file_id, retries=3):
    for attempt in range(retries): # noqa
        try:
            return contract.functions.getFile(file_id).call()
        except Exception as e:
            if "429" in str(e) and attempt < retries - 1:
                wait = 2 ** attempt
                logger.warning(f"[FETCH] 429 getFile #{file_id} | thu lai lan {attempt + 1} sau {wait}s...")
                time.sleep(wait)
            else:
                raise

# =========================
# FETCH FILES (INCREMENTAL - EVENT LOG)
# =========================
_fetch_lock = threading.Lock()

def fetch_all_files():
    global _cache

    now = int(time.time())

    if now - _cache["last_updated"] < CACHE_TTL and _cache["files"]:
        remaining = CACHE_TTL - (now - _cache["last_updated"])
        logger.info(f"[FETCH] Dung cache | tong: {len(_cache['files'])} files | con {remaining}s")
        return _cache["files"]

    if not _fetch_lock.acquire(blocking=False):
        logger.info("[FETCH] Thread khac dang fetch, dang doi...")
        _fetch_lock.acquire()
        _fetch_lock.release()
        return _cache["files"]

    try:
        now = int(time.time())
        if now - _cache["last_updated"] < CACHE_TTL and _cache["files"]:
            return _cache["files"]

        logger.info("[FETCH] Cache het han, kiem tra block moi tren blockchain...")

        latest_block = w3.eth.block_number
        from_block = _cache["last_block"] if _cache["last_block"] > 0 else DEPLOY_BLOCK

        if from_block > latest_block:
            logger.info(f"[FETCH] Khong co block moi (last={from_block}, latest={latest_block}), giu cache")
            _cache["last_updated"] = now
            return _cache["files"]

        existing_ids = {f["id"] for f in _cache["files"]}
        new_files = []
        total_events = 0
        current = from_block

        while current <= latest_block:
            to_block = min(current + MAX_BLOCK_RANGE, latest_block)
            logger.info(f"[FETCH] Querying events | block {current} -> {to_block}")

            events = fetch_events_with_retry(current, to_block)
            total_events += len(events)

            for e in events:
                file_id = e["args"]["id"]
                if file_id in existing_ids:
                    continue

                raw = get_file_with_retry(file_id)
                new_files.append({
                    "id":        file_id,
                    "cid":       raw[0],
                    "owner":     to_checksum(raw[1]),
                    "uploader":  to_checksum(raw[2]),
                    "filename":  raw[3],
                    "timestamp": raw[4],
                    "isPublic":  raw[5],
                    "ipfs_url":  build_ipfs_url(raw[0])
                })
                existing_ids.add(file_id)
                time.sleep(0.2)

            current = to_block + 1
            time.sleep(0.1)

        if new_files:
            _cache["files"].extend(new_files)
            logger.info(f"[FETCH] Them {len(new_files)} files moi | tong: {len(_cache['files'])}")
        else:
            logger.info(f"[FETCH] Khong co file moi | da quet {total_events} events")

        _cache["last_block"] = latest_block + 1
        _cache["last_updated"] = now
        return _cache["files"]

    except Exception as e:
        logger.error(f"[FETCH] That bai: {e}")
        logger.error(traceback.format_exc())
        raise

    finally:
        _fetch_lock.release()

# =========================
# PING (cho UptimeRobot)
# =========================
@app.api_route("/ping", methods=["GET", "HEAD"])
def ping():
    return Response(status_code=200)

# =========================
# USERS (cho sidebar)
# =========================
@app.get("/users")
def get_users():
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute("SELECT id, email, user_address FROM permissions")
        rows = c.fetchall()
        conn.close()
        return [{"id": r[0], "email": r[1], "address": r[2]} for r in rows]
    except Exception as e:
        logger.error(f"[USERS] Loi: {e}")
        return JSONResponse(status_code=500, content={"error": str(e)})

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

        new_file = {
            "id":        len(_cache["files"]) + 1,
            "cid":       cid,
            "owner":     to_checksum(addr),
            "uploader":  to_checksum(addr),
            "filename":  file.filename,
            "timestamp": int(time.time()),
            "isPublic":  False,
            "ipfs_url":  build_ipfs_url(cid)
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

        one_day_ago = int(time.time()) - (24 * 60 * 60)

        result = [
            f for f in files
            if (f["owner"].lower() == user_address.lower()
            or f["uploader"].lower() == user_address.lower())
            and f["timestamp"] >= one_day_ago
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

        one_day_ago = int(time.time()) - (24 * 60 * 60)

        result = [
            f for f in files
            if f["uploader"].lower() != user_address.lower()
            and f["timestamp"] >= one_day_ago
        ]
        logger.info(f"[SHARED-FILES] Tra ve {len(result)} files cho {user_address[:10]}...")
        return result

    except Exception as e:
        logger.error(f"[SHARED-FILES] Loi: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": str(e)})

@app.get("/shared-files/{user_address}/{filter_address}")
def get_shared_files_filtered(user_address: str, filter_address: str):
    logger.info(f"[SHARED-FILES-FILTER] user: {user_address} | filter: {filter_address}")
    try:
        user_address = to_checksum(user_address)
        filter_address = to_checksum(filter_address)

        files = fetch_all_files()

        one_day_ago = int(time.time()) - (24 * 60 * 60)

        result = [
            f for f in files
            if f["uploader"].lower() != user_address.lower()  # vẫn là shared
            and f["uploader"].lower() == filter_address.lower()  # filter theo user click
            and f["timestamp"] >= one_day_ago
        ]

        logger.info(f"[SHARED-FILES-FILTER] Tra ve {len(result)} files")
        return result

    except Exception as e:
        logger.error(f"[SHARED-FILES-FILTER] Loi: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": str(e)})

# =========================
# REFRESH
# =========================
@app.get("/refresh")
def refresh():
    logger.info("[REFRESH] Dang refresh...")
    try:
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
    import uvicorn # noqa
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)