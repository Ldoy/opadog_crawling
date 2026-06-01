import os
import subprocess
from fastapi import FastAPI, Header, HTTPException

app = FastAPI()

TOKEN = os.environ.get("CRAWL_TOKEN", "")
CRAWL_DIR = "/root/naver-cafe-crawling"

@app.post("/crawl")
def trigger_crawl(authorization: str = Header(None)):
    if not TOKEN or authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="Unauthorized")
    log_path = f"{CRAWL_DIR}/crawl.log"
    subprocess.Popen(
        ["python3", "crawl.py"],
        cwd=CRAWL_DIR,
        stdout=open(log_path, "a"),
        stderr=subprocess.STDOUT,
    )
    return {"status": "started"}
