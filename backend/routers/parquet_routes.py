"""5-second Nifty 50 volume parquet capture endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from auth import get_current_user
from models import User
from services.parquet_capture import (
    list_parquet_files, parquet_capture, parquet_file_path, read_parquet_preview,
)

router = APIRouter(prefix="/parquet", tags=["parquet"])


@router.get("/status")
async def status(user: User = Depends(get_current_user)):
    return parquet_capture.stats()


@router.post("/start")
async def start(user: User = Depends(get_current_user)):
    parquet_capture.start()
    return parquet_capture.stats()


@router.post("/stop")
async def stop(user: User = Depends(get_current_user)):
    parquet_capture.stop()
    return parquet_capture.stats()


@router.get("/files")
async def files(user: User = Depends(get_current_user)):
    return {"files": list_parquet_files()}


@router.get("/preview")
async def preview(path: str, limit: int = 100, user: User = Depends(get_current_user)):
    rows = read_parquet_preview(path, limit=limit)
    return {"path": path, "rows": rows}


@router.get("/download")
async def download(path: str, user: User = Depends(get_current_user)):
    p = parquet_file_path(path)
    if not p:
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(p, media_type="application/octet-stream", filename=p.name)
