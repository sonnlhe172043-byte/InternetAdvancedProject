

from fastapi import FastAPI # noqa
from fastapi import UploadFile # noqa
from fastapi import File # noqa
from fastapi import Form # noqa

from fastapi.responses import JSONResponse # noqa
from fastapi.middleware.cors import CORSMiddleware # noqa

from contextlib import asynccontextmanager

from dotenv import load_dotenv # noqa

from db import get_conn
from db import init_db

from blockchain import store_file

from ipfs import add_to_ipfs

from queue import Queue

from pathlib import Path # noqa

import traceback
import threading
import smtplib
import uuid
import random
import time
import os

from email.mime.text import MIMEText

# =========================
# LOAD ENV
# =========================
load_dotenv()

# =========================
# FILE VALIDATION
# =========================



# 25 MB
MAX_FILE_SIZE = 25 * 1024 * 1024

# Allowed extensions
ALLOWED_EXTENSIONS = {
    ".pdf",
    ".doc",
    ".docx",

    ".txt",
    ".csv",

    ".ppt",
    ".pptx",

    ".xls",
    ".xlsx",

    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",

    ".mp3",
    ".wav",

    ".mp4",
    ".mov",

    ".zip"
}

# Optional dangerous extensions blacklist
BLOCKED_EXTENSIONS = {
    ".exe",
    ".msi",
    ".bat",
    ".cmd",
    ".sh",
    ".ps1",
    ".scr",
    ".dll",
    ".jar",
    ".apk",
    ".com"
}


EMAIL_SENDER = os.getenv("EMAIL_SENDER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")



# =========================
# BLOCKCHAIN QUEUE
# =========================
blockchain_queue = Queue()

# =========================
# HELPERS
# =========================
def build_ipfs_url(cid):

    return f"https://gateway.pinata.cloud/ipfs/{cid}"

# =========================
# EMAIL
# =========================
def send_email(to_email, permission_id):

    try:

        msg = MIMEText(
            f"Your Permission ID is:\n\n{permission_id}"
        )

        msg["Subject"] = "Permission ID"
        msg["From"] = EMAIL_SENDER
        msg["To"] = to_email

        server = smtplib.SMTP("smtp.gmail.com", 587)

        server.starttls()

        server.login(
            EMAIL_SENDER,
            EMAIL_PASSWORD
        )

        server.sendmail(
            EMAIL_SENDER,
            to_email,
            msg.as_string()
        )

        server.quit()

    except Exception as e:

        print(f"[EMAIL] ERROR: {e}")


# =========================
# BLOCKCHAIN WORKER
# =========================
def blockchain_worker():

    print("[BLOCKCHAIN] Worker started")

    while True:

        task = blockchain_queue.get()

        conn = None

        try:

            file_id = task["file_id"]
            cid = task["cid"]
            filename = task["filename"]
            uploader = task["uploader"]

            print(f"[BLOCKCHAIN] Processing file #{file_id}")

            tx_hash = store_file(
                cid,
                filename,
                uploader
            )

            conn = get_conn()
            c = conn.cursor()

            c.execute("""
                UPDATE files
                SET
                    tx_hash = %s,
                    blockchain_status = 'success'
                WHERE id = %s
            """, (
                tx_hash,
                file_id
            ))

            conn.commit()

            print(f"[BLOCKCHAIN] SUCCESS FILE #{file_id}")

        except Exception as e:

            print(f"[BLOCKCHAIN] FAILED: {e}")

            print(traceback.format_exc())

            if conn:

                c = conn.cursor()

                c.execute("""
                    UPDATE files
                    SET blockchain_status = 'failed'
                    WHERE id = %s
                """, (file_id,)) # noqa

                conn.commit()

        finally:

            if conn:
                conn.close()

            blockchain_queue.task_done()

# =========================
# APP
# =========================
@asynccontextmanager
async def lifespan(app):

    print("[APP] Starting...")

    init_db()

    threading.Thread(
        target=blockchain_worker,
        daemon=True
    ).start()

    yield

    print("[APP] Shutdown")

app = FastAPI(lifespan=lifespan)

# =========================
# CORS
# =========================
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://internet-advanced-project.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# CREATE PERMISSION
# =========================
@app.post("/create-permission")
def create_permission(
    email: str = Form(...)
):

    try:

        conn = get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT id, user_address
            FROM permissions
            WHERE email=%s
        """, (email,))

        existing = c.fetchone()

        if existing:

            permission_id, address = existing

            conn.close()

            send_email(email, permission_id)

            return {
                "status": "exists",
                "permission_id": permission_id,
                "user_address": address
            }

        permission_id = str(uuid.uuid4())[:12]

        user_address = "0x" + "".join(
            random.choices(
                "0123456789abcdef",
                k=40
            )
        )

        c.execute("""
            INSERT INTO permissions
            (
                id,
                email,
                user_address
            )
            VALUES (%s, %s, %s)
        """, (
            permission_id,
            email,
            user_address
        ))

        conn.commit()
        conn.close()

        send_email(email, permission_id)

        return {
            "status": "success",
            "permission_id": permission_id,
            "user_address": user_address
        }

    except Exception as e:

        print(traceback.format_exc())

        return JSONResponse(
            status_code=500,
            content={
                "error": str(e)
            }
        )

# =========================
# LOGIN
# =========================
@app.post("/login")
def login(
    permission_id: str = Form(...)
):

    try:

        conn = get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT email, user_address
            FROM permissions
            WHERE id=%s
        """, (permission_id.strip(),))

        row = c.fetchone()

        conn.close()

        if not row:

            return {
                "error": "invalid permission"
            }

        email, address = row

        return {
            "status": "success",
            "email": email,
            "user_address": address
        }

    except Exception as e:

        return JSONResponse(
            status_code=500,
            content={
                "error": str(e)
            }
        )

# =========================
# USERS
# =========================
@app.get("/users")
def get_users():

    try:

        conn = get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT
                id,
                email,
                user_address
            FROM permissions
        """)

        rows = c.fetchall()

        conn.close()

        return [
            {
                "id": r[0],
                "email": r[1],
                "address": r[2]
            }
            for r in rows
        ]

    except Exception as e:

        return JSONResponse(
            status_code=500,
            content={
                "error": str(e)
            }
        )

# =========================
# UPLOAD
# =========================
@app.post("/upload")
async def upload(
    file: UploadFile = File(...),
    permission_id: str = Form(None),
    user_address: str = Form(None)
):

    conn = None

    try:

        # =========================
        # ADDRESS
        # =========================
        if user_address:

            uploader = user_address

        elif permission_id:

            conn = get_conn()
            c = conn.cursor()

            c.execute("""
                SELECT user_address
                FROM permissions
                WHERE id=%s
            """, (permission_id,))

            row = c.fetchone()

            conn.close()

            if not row:

                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Invalid permission"
                    }
                )

            uploader = row[0]

        else:

            return JSONResponse(
                status_code=400,
                content={
                    "error": "Missing credentials"
                }
            )
        # =========================
        # FILE VALIDATION
        # =========================
        from pathlib import Path

        filename = file.filename.strip()

        if not filename:
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Invalid filename"
                }
            )

        extension = Path(filename).suffix.lower()

        # Dangerous files
        if extension in BLOCKED_EXTENSIONS:
            return JSONResponse(
                status_code=400,
                content={
                    "error": f"{extension} files are not allowed"
                }
            )

        # Unsupported files
        if extension not in ALLOWED_EXTENSIONS:
            return JSONResponse(
                status_code=400,
                content={
                    "error": f"Unsupported file type: {extension}"
                }
            )
        # =========================
        # READ FILE
        # =========================
        content = await file.read()

        # =========================
        # FILE LIMIT
        # =========================
        if len(content) > MAX_FILE_SIZE:

            return JSONResponse(
                status_code=400,
                content={
                    "error": "File too large"
                }
            )

        # =========================
        # IPFS
        # =========================
        cid = add_to_ipfs(
            content,
            file.filename
        )

        ipfs_url = build_ipfs_url(cid)

        # =========================
        # CHECK DUPLICATE CID
        # =========================
        conn = get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT
                id,
                cid,
                filename,
                owner,
                uploader,
                tx_hash,
                ipfs_url,
                uploaded_at,
                blockchain_status
            FROM files
            WHERE cid=%s
            LIMIT 1
        """, (cid,))

        existing = c.fetchone()

        if existing:

            conn.close()

            return {
                "status": "duplicate",
                "message": "File already exists",
                "cid": existing[1],
                "ipfs_url": existing[6]
            }

        # =========================
        # SAVE DB
        # =========================
        uploaded_at = int(time.time())

        c.execute("""
            INSERT INTO files
            (
                cid,
                filename,
                owner,
                uploader,
                ipfs_url,
                uploaded_at,
                blockchain_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (
            cid,
            file.filename,
            uploader,
            uploader,
            ipfs_url,
            uploaded_at,
            "pending"
        ))

        file_id = c.fetchone()[0]

        conn.commit()
        conn.close()

        # =========================
        # BLOCKCHAIN QUEUE
        # =========================
        blockchain_queue.put({
            "file_id": file_id,
            "cid": cid,
            "filename": file.filename,
            "uploader": uploader
        })

        # =========================
        # RETURN FAST
        # =========================
        return {
            "status": "success",
            "message": "Uploaded successfully",
            "cid": cid,
            "ipfs_url": ipfs_url,
            "blockchain_status": "pending"
        }

    except Exception as e:

        print(traceback.format_exc())

        if conn:
            conn.close()

        return JSONResponse(
            status_code=500,
            content={
                "error": str(e)
            }
        )

# =========================
# MY FILES
# =========================
@app.get("/my-files/{address}")
def my_files(address: str):

    try:

        conn = get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT
                id,
                cid,
                filename,
                owner,
                uploader,
                tx_hash,
                ipfs_url,
                uploaded_at,
                blockchain_status
            FROM files
            WHERE
                owner=%s
                OR uploader=%s
            ORDER BY uploaded_at DESC
        """, (
            address,
            address
        ))

        rows = c.fetchall()

        conn.close()

        return [
            {
                "id": r[0],
                "cid": r[1],
                "filename": r[2],
                "owner": r[3],
                "uploader": r[4],
                "tx_hash": r[5],
                "ipfs_url": r[6],
                "timestamp": r[7],
                "blockchain_status": r[8]
            }
            for r in rows
        ]

    except Exception as e:

        return JSONResponse(
            status_code=500,
            content={
                "error": str(e)
            }
        )

# =========================
# SHARED FILES
# =========================
@app.get("/shared-files/{address}")
def shared_files(address: str):

    try:

        conn = get_conn()
        c = conn.cursor()

        c.execute("""
            SELECT
                id,
                cid,
                filename,
                owner,
                uploader,
                tx_hash,
                ipfs_url,
                uploaded_at,
                blockchain_status
            FROM files
            WHERE uploader != %s
            ORDER BY uploaded_at DESC
        """, (address,))

        rows = c.fetchall()

        conn.close()

        return [
            {
                "id": r[0],
                "cid": r[1],
                "filename": r[2],
                "owner": r[3],
                "uploader": r[4],
                "tx_hash": r[5],
                "ipfs_url": r[6],
                "timestamp": r[7],
                "blockchain_status": r[8]
            }
            for r in rows
        ]

    except Exception as e:

        return JSONResponse(
            status_code=500,
            content={
                "error": str(e)
            }
        )

# =========================
# RUN
# =========================
if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )