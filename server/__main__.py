"""Run the single-instance local service."""

import multiprocessing
import os

import uvicorn
from dotenv import load_dotenv

from server.config import ROOT


if __name__ == "__main__":
    multiprocessing.freeze_support()
    load_dotenv(ROOT / ".env", override=False)
    uvicorn.run("server.app:create_app", factory=True,
                host=os.environ.get("APP_HOST", "127.0.0.1"),
                port=int(os.environ.get("APP_PORT", "8000")), workers=1,
                access_log=False, log_level="info")
