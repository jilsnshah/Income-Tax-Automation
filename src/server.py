from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List
import pandas as pd
from fastapi.middleware.cors import CORSMiddleware
import os
from loguru import logger
from collections import deque
from src.scraper import download_26as_for_client

# Custom loguru sink for API streaming
memory_logs = deque(maxlen=200)

def memory_sink(message):
    memory_logs.append(message.strip())

# Add the sink
logger.add(memory_sink, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

global_tracker = {
    "is_processing": False,
    "queue": [],
    "output_dir": "",
    "headless": True
}

class StartBatchRequest(BaseModel):
    base_output_dir: str
    headless: bool = True
    clients: List[dict]

@app.get("/api/browse_directory")
def browse_directory():
    import subprocess
    import sys
    
    script = """
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.call('wm', 'attributes', '.', '-topmost', True)
folder_path = filedialog.askdirectory(parent=root)
root.destroy()
print(folder_path)
"""
    try:
        # Run script in a new process to avoid macOS GUI thread issues
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        folder_path = result.stdout.strip()
        return {"path": folder_path}
    except Exception as e:
        logger.error(f"Error opening directory picker: {e}")
        return {"path": ""}

@app.get("/api/logs")
def get_logs():
    return {"logs": list(memory_logs)}

@app.get("/api/status")
def get_status():
    return global_tracker

def process_batch_background():
    base_output_dir = global_tracker["output_dir"]
    headless = global_tracker["headless"]
    
    for i, client in enumerate(global_tracker["queue"]):
        # Skip if already processed
        if client.get("status") in ["success", "error"]:
            continue
            
        global_tracker["queue"][i]["status"] = "running"
        
        pan = str(client.get("pan", "")).strip()
        password = str(client.get("password", "")).strip()
        file_no = str(client.get("fileNo", "")).strip()
        dob = str(client.get("dob", "")).strip()
        
        clean_dob = dob.replace('/', '').replace('-', '')
        client_output_dir = os.path.join(base_output_dir, file_no)
        os.makedirs(client_output_dir, exist_ok=True)
        
        logger.info(f"Background worker starting PAN: {pan}, File No: {file_no}")
        
        try:
            success, msg = download_26as_for_client(pan, password, clean_dob, client_output_dir, headless=headless)
        except Exception as e:
            success, msg = False, f"Unexpected error: {str(e)}"
            
        global_tracker["queue"][i]["status"] = "success" if success else "error"
        global_tracker["queue"][i]["message"] = msg
        
        # update excel
        excel_path = os.path.join(base_output_dir, "output.xlsx")
        if os.path.exists(excel_path):
            try:
                df = pd.read_excel(excel_path)
                mask = (df['pan'].astype(str).str.strip() == pan) & ((df['fileNo'].astype(str).str.strip() == file_no) | (df['fileNo'].isna()))
                if success:
                    df.loc[mask, 'status'] = 'success'
                    df.loc[mask, 'message'] = 'OK'
                else:
                    df.loc[mask, 'status'] = 'error'
                    df.loc[mask, 'message'] = msg
                df.to_excel(excel_path, index=False)
            except Exception as e:
                logger.error(f"Could not update excel tracker: {e}")
                
    global_tracker["is_processing"] = False
    logger.info("Background batch processing completed.")

@app.post("/api/start_batch")
def start_batch(req: StartBatchRequest, background_tasks: BackgroundTasks):
    if global_tracker["is_processing"]:
        raise HTTPException(status_code=400, detail="A batch is already processing.")
        
    global_tracker["is_processing"] = True
    global_tracker["queue"] = req.clients
    global_tracker["output_dir"] = req.base_output_dir
    global_tracker["headless"] = req.headless
    
    if not os.path.exists(req.base_output_dir):
        os.makedirs(req.base_output_dir, exist_ok=True)
        
    excel_path = os.path.join(req.base_output_dir, "output.xlsx")
    df = pd.DataFrame(req.clients)
    if 'pan' in df.columns:
        cols = ['pan', 'fileNo', 'dob', 'status', 'message']
        df = df[[c for c in cols if c in df.columns]]
        df.to_excel(excel_path, index=False)
        
    background_tasks.add_task(process_batch_background)
    return {"status": "success", "message": "Batch started"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
