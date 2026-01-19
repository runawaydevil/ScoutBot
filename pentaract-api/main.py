"""
Pentaract API - Minimal implementation for ScoutBot integration
"""
from fastapi import FastAPI, HTTPException, Depends, File, UploadFile, Form, Header
from fastapi.responses import JSONResponse, StreamingResponse, Response
from pydantic import BaseModel, EmailStr
from typing import Optional, List
import os
from datetime import datetime
import hashlib
import json
from pathlib import Path

app = FastAPI(title="Pentaract API", version="1.0.0")

# Storage directory
STORAGE_DIR = Path("/data/storage")
METADATA_DIR = Path("/data/metadata")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
METADATA_DIR.mkdir(parents=True, exist_ok=True)

# Simple in-memory user storage (for demo)
USERS = {}
TOKENS = {}

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    username: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class StorageCreate(BaseModel):
    name: str

@app.get("/")
async def root():
    """Root endpoint"""
    return {"status": "ok", "service": "Pentaract API", "version": "1.0.0"}

@app.get("/api/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.post("/api/auth/register")
async def register(user: UserRegister):
    """Register a new user"""
    if user.email in USERS:
        raise HTTPException(status_code=400, detail="User already exists")
    
    # Hash password (simple for demo)
    password_hash = hashlib.sha256(user.password.encode()).hexdigest()
    
    USERS[user.email] = {
        "email": user.email,
        "username": user.username,
        "password_hash": password_hash,
        "created_at": datetime.utcnow().isoformat()
    }
    
    return {"message": "User registered successfully", "email": user.email}

@app.post("/api/auth/login")
async def login(user: UserLogin):
    """Login and get access token"""
    if user.email not in USERS:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    password_hash = hashlib.sha256(user.password.encode()).hexdigest()
    
    if USERS[user.email]["password_hash"] != password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Generate simple token
    token = hashlib.sha256(f"{user.email}{datetime.utcnow()}".encode()).hexdigest()
    TOKENS[token] = user.email
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "email": user.email
    }

def get_current_user(authorization: Optional[str] = Header(None)):
    """Get current user from token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    token = authorization.replace("Bearer ", "")
    
    if token not in TOKENS:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    email = TOKENS[token]
    return USERS[email]

@app.get("/api/storages")
async def list_storages(user: dict = Depends(get_current_user)):
    """List user storages"""
    # Return default storage
    return [{
        "id": "default",
        "name": "ScoutBot-Storage",
        "created_at": datetime.utcnow().isoformat()
    }]

@app.post("/api/storages")
async def create_storage(storage: StorageCreate, user: dict = Depends(get_current_user)):
    """Create a new storage"""
    return {
        "id": "default",
        "name": storage.name,
        "created_at": datetime.utcnow().isoformat()
    }

@app.post("/api/files/upload")
async def upload_file(
    file: UploadFile = File(...),
    path: str = Form(...),
    storage_id: str = Form(...),
    user: dict = Depends(get_current_user)
):
    """Upload a file"""
    # Save file
    file_path = STORAGE_DIR / path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    content = await file.read()
    file_path.write_bytes(content)
    
    # Save metadata
    metadata = {
        "name": file.filename,
        "path": path,
        "size": len(content),
        "uploaded_at": datetime.utcnow().isoformat(),
        "user": user["email"]
    }
    
    metadata_path = METADATA_DIR / f"{path}.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.write_text(json.dumps(metadata))
    
    return JSONResponse(
        status_code=201,
        content={
            "success": True,
            "path": path,
            "size": len(content),
            "uploaded_at": metadata["uploaded_at"]
        }
    )

@app.get("/api/files/download")
async def download_file(
    path: str,
    storage_id: str,
    user: dict = Depends(get_current_user)
):
    """Download a file"""
    file_path = STORAGE_DIR / path
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    def iterfile():
        with open(file_path, "rb") as f:
            yield from f
    
    return StreamingResponse(
        iterfile(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={file_path.name}"}
    )

@app.get("/api/files/list")
async def list_files(
    storage_id: str,
    path: str = "",
    user: dict = Depends(get_current_user)
):
    """List files in storage"""
    files = []
    
    for metadata_file in METADATA_DIR.glob("**/*.json"):
        try:
            metadata = json.loads(metadata_file.read_text())
            if metadata.get("user") == user["email"]:
                files.append({
                    "name": metadata["name"],
                    "path": metadata["path"],
                    "size": metadata["size"],
                    "uploaded_at": metadata["uploaded_at"],
                    "is_file": True
                })
        except Exception:
            pass
    
    return files

@app.delete("/api/files")
async def delete_file(
    path: str,
    storage_id: str,
    user: dict = Depends(get_current_user)
):
    """Delete a file"""
    file_path = STORAGE_DIR / path
    metadata_path = METADATA_DIR / f"{path}.json"
    
    if file_path.exists():
        file_path.unlink()
    
    if metadata_path.exists():
        metadata_path.unlink()
    
    return Response(status_code=204)

@app.get("/api/files/info")
async def get_file_info(
    path: str,
    storage_id: str,
    user: dict = Depends(get_current_user)
):
    """Get file information"""
    metadata_path = METADATA_DIR / f"{path}.json"
    
    if not metadata_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    metadata = json.loads(metadata_path.read_text())
    
    return {
        "name": metadata["name"],
        "path": metadata["path"],
        "size": metadata["size"],
        "uploaded_at": metadata["uploaded_at"],
        "mime_type": "application/octet-stream"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8547)
