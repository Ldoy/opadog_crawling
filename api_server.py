import os
import json
import subprocess
from datetime import datetime
from pathlib import Path
from fastapi import FastAPI, Header, HTTPException

app = FastAPI()

TOKEN = os.environ.get("CRAWL_TOKEN", "")
CRAWL_DIR = "/root/naver-cafe-crawling"
STATUS_FILE = Path(f"{CRAWL_DIR}/crawl_status.json")


def write_status(state: str, message: str = ""):
    STATUS_FILE.write_text(json.dumps({
        "state": state,
        "message": message,
        "updated_at": datetime.now().isoformat(),
    }))


@app.post("/crawl")
def trigger_crawl(authorization: str = Header(None)):
    if not TOKEN or authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    write_status("running")
    log_path = f"{CRAWL_DIR}/crawl.log"
    subprocess.Popen(
        ["python3", "crawl.py"],
        cwd=CRAWL_DIR,
        stdout=open(log_path, "a"),
        stderr=subprocess.STDOUT,
    )
    return {"status": "started"}


@app.get("/status")
def get_status(authorization: str = Header(None)):
    if not TOKEN or authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    if STATUS_FILE.exists():
        return json.loads(STATUS_FILE.read_text())
    return {"state": "idle", "message": "", "updated_at": ""}
