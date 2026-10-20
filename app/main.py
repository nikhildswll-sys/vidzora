import os
import io
import uuid
import subprocess
import socket
import httpx
import qrcode
import time
from collections import defaultdict
from fastapi import FastAPI, HTTPException, BackgroundTasks, Response, Query, UploadFile, File, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import List, Optional

from app.services.video_service import VideoService, FFMPEG_PATH
from app.services.gallery_service import GalleryService
from app.utils.helpers import clean_old_files, sanitize_filename

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STATIC_DIR = os.path.join(BASE_DIR, "static")
DOWNLOAD_DIR = os.path.join(BASE_DIR, "downloads")

app = FastAPI(title="VidZora Pro")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory IP rate limiter: sliding 60-second window
_RATE_LIMIT_STORE = defaultdict(list)
_MAX_REQUESTS_PER_MINUTE = 45

# Known automated scrapers and malicious exploit scanners
BLOCKED_USER_AGENTS = [
    "scrapy", "aiohttp", "mechanize", "nikto", "sqlmap", 
    "zgrab", "masscan", "phantomjs"
]

@app.middleware("http")
async def security_and_rate_limit_middleware(request: Request, call_next):
    # Enforce strict protection for API routes
    if request.url.path.startswith("/api/"):
        ua = (request.headers.get("user-agent") or "").lower()
        
        # 1. Block known automated scraping bots and tools
        if any(bot in ua for bot in BLOCKED_USER_AGENTS):
            return JSONResponse(
                status_code=403,
                content={"detail": "Access denied: Automated scraper bots are prohibited."}
            )

        # 2. Extract real client IP (Cloudflare / reverse proxy aware)
        client_ip = (
            request.headers.get("cf-connecting-ip")
            or request.headers.get("x-real-ip")
            or (request.headers.get("x-forwarded-for", "").split(",")[0].strip())
            or (request.client.host if request.client else "unknown")
        )

        # 3. Sliding window rate limiter (max requests/min per IP)
        now = time.time()
        timestamps = _RATE_LIMIT_STORE[client_ip]
        _RATE_LIMIT_STORE[client_ip] = [t for t in timestamps if now - t < 60]

        if len(_RATE_LIMIT_STORE[client_ip]) >= _MAX_REQUESTS_PER_MINUTE:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please slow down and wait a minute."},
                headers={"Retry-After": "60"}
            )
        
        _RATE_LIMIT_STORE[client_ip].append(now)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

class ExtractRequest(BaseModel):
    url: str

class StartDownloadRequest(BaseModel):
    url: str
    quality: str = "720"

class GalleryZipRequest(BaseModel):
    images: List[str]
    title: Optional[str] = "gallery_download"

class BulkExtractRequest(BaseModel):
    urls: List[str]

class BulkDownloadRequest(BaseModel):
    urls: List[str]
    quality: Optional[str] = "720"

@app.on_event("startup")
async def startup_event():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    clean_old_files(DOWNLOAD_DIR)

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "VidZora Pro"}

@app.get("/robots.txt", response_class=Response)
def get_robots():
    robots_path = os.path.join(STATIC_DIR, "robots.txt")
    if os.path.exists(robots_path):
        with open(robots_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="text/plain")
    return Response(content="User-agent: *\nAllow: /\nSitemap: /sitemap.xml", media_type="text/plain")

@app.get("/sitemap.xml", response_class=Response)
def get_sitemap():
    sitemap_path = os.path.join(STATIC_DIR, "sitemap.xml")
    if os.path.exists(sitemap_path):
        with open(sitemap_path, "r", encoding="utf-8") as f:
            return Response(content=f.read(), media_type="application/xml")
    return Response(content="<urlset></urlset>", media_type="application/xml")

@app.post("/api/extract")
def extract_media(req: ExtractRequest, background_tasks: BackgroundTasks):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="Please enter a valid link.")

    # Guard against self-referential or local URLs that freeze yt-dlp
    lower_u = url.lower()
    if any(blocked in lower_u for blocked in ["127.0.0.1", "localhost", "0.0.0.0", "loca.lt", "ngrok", "trycloudflare"]):
        raise HTTPException(status_code=400, detail="Please enter a public media URL from YouTube, Instagram, Facebook, TikTok, Twitter, etc.")

    background_tasks.add_task(clean_old_files, DOWNLOAD_DIR)

    try:
        data = VideoService.extract_info(url)
        return {"success": True, "data": data}
    except Exception as e:
        try:
            gallery_data = GalleryService.extract_gallery(url)
            if gallery_data and gallery_data.get("count", 0) > 0:
                return {"success": True, "data": gallery_data, "is_gallery": True}
        except Exception:
            pass
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/bulk/extract")
def bulk_extract(req: BulkExtractRequest):
    results = []
    for u in req.urls[:6]:
        u = u.strip()
        if not u:
            continue
        lower_u = u.lower()
        if any(blocked in lower_u for blocked in ["127.0.0.1", "localhost", "0.0.0.0", "loca.lt"]):
            results.append({"success": False, "url": u, "error": "Invalid URL"})
            continue
        try:
            info = VideoService.extract_info(u)
            results.append({"success": True, "url": u, "data": info})
        except Exception as e:
            results.append({"success": False, "url": u, "error": str(e)})
    return {"success": True, "results": results}

@app.post("/api/bulk/download")
def bulk_download(req: BulkDownloadRequest, background_tasks: BackgroundTasks):
    if not req.urls:
        raise HTTPException(status_code=400, detail="No URLs provided")
    zip_path, zip_filename = VideoService.process_bulk_zip(req.urls, req.quality or "720")
    background_tasks.add_task(clean_old_files, DOWNLOAD_DIR)
    return FileResponse(
        path=zip_path,
        filename=zip_filename,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'}
    )

@app.post("/api/upload/convert")
async def upload_convert(
    file: UploadFile = File(...), 
    target_format: str = Query("mp3"),
    background_tasks: BackgroundTasks = BackgroundTasks()
):
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    unique_token = str(uuid.uuid4())[:8]
    original_name = file.filename or "uploaded_media"
    clean_base = sanitize_filename(os.path.splitext(original_name)[0])
    
    in_ext = os.path.splitext(original_name)[1] or ".mp4"
    temp_in = os.path.join(DOWNLOAD_DIR, f"up_{unique_token}{in_ext}")
    temp_out = os.path.join(DOWNLOAD_DIR, f"{clean_base}_{unique_token}.{target_format}")
    
    with open(temp_in, "wb") as f:
        f.write(await file.read())
        
    cmd = [FFMPEG_PATH, "-y", "-i", temp_in]
    if target_format == "mp3":
        cmd.extend(["-vn", "-ar", "44100", "-ac", "2", "-b:a", "320k"])
    else:
        cmd.extend(["-c:v", "libx264", "-c:a", "aac"])
    cmd.append(temp_out)
    
    subprocess.run(cmd, capture_output=True, timeout=60)
    
    try:
        os.remove(temp_in)
    except Exception:
        pass
        
    if not os.path.exists(temp_out):
        raise HTTPException(status_code=500, detail="Conversion failed on server.")
        
    background_tasks.add_task(clean_old_files, DOWNLOAD_DIR)
    out_filename = f"{clean_base}.{target_format}"
    return FileResponse(
        path=temp_out,
        filename=out_filename,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{out_filename}"'}
    )

@app.get("/api/stream/download")
@app.get("/api/download/direct")
async def live_stream_download(
    url: str = Query(...), 
    quality: str = Query("720"),
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None)
):
    try:
        stream_gen, media_type, filename = VideoService.get_live_stream(
            url.strip(), 
            quality, 
            start_time=start_time, 
            end_time=end_time
        )
        return StreamingResponse(
            stream_gen,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        try:
            file_path, friendly_name = VideoService.process_direct_download(url.strip(), quality)
            return FileResponse(
                path=file_path,
                filename=friendly_name,
                media_type="application/octet-stream",
                headers={"Content-Disposition": f'attachment; filename="{friendly_name}"'}
            )
        except Exception:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stream/preview")
async def live_preview_stream(
    url: str = Query(...),
    quality: str = Query("360")
):
    try:
        stream_gen, media_type, filename = VideoService.get_live_stream(url.strip(), quality)
        return StreamingResponse(
            stream_gen,
            media_type=media_type,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
                "Accept-Ranges": "bytes",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/download/start")
async def start_download_post(req: StartDownloadRequest):
    url = req.url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    task_id = VideoService.start_download_task(url, req.quality)
    return {"success": True, "task_id": task_id}

@app.get("/api/download/start")
async def start_download_get(url: str = Query(...), quality: str = Query("720")):
    url = url.strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL cannot be empty")
    task_id = VideoService.start_download_task(url, quality)
    return {"success": True, "task_id": task_id}

@app.get("/api/download")
async def api_download_compat_get(url: str = Query(...), quality: str = Query("720")):
    task_id = VideoService.start_download_task(url.strip(), quality)
    return {"success": True, "task_id": task_id}

@app.post("/api/download")
async def api_download_compat_post(req: StartDownloadRequest):
    task_id = VideoService.start_download_task(req.url.strip(), req.quality)
    return {"success": True, "task_id": task_id}

@app.get("/api/download/status/{task_id}")
async def get_download_status(task_id: str):
    status = VideoService.get_task_status(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Download task not found")
    return {"success": True, "task": status}

@app.get("/api/download/file/{task_id}")
async def download_file(task_id: str, background_tasks: BackgroundTasks):
    status = VideoService.get_task_status(task_id)
    if not status or status.get("status") != "completed":
        raise HTTPException(status_code=400, detail="File is not ready yet")

    file_path = status.get("file_path")
    filename = status.get("filename")

    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File expired or not found")

    background_tasks.add_task(clean_old_files, DOWNLOAD_DIR)

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.get("/api/qrcode")
def generate_qr(text: str = Query(..., description="URL or text to encode")):
    qr = qrcode.QRCode(
        version=1,
        box_size=8,
        border=2,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(content=buf.getvalue(), media_type="image/png")

@app.post("/api/gallery/zip")
async def zip_gallery_endpoint(req: GalleryZipRequest, background_tasks: BackgroundTasks):
    if not req.images:
        raise HTTPException(status_code=400, detail="No images provided")
    try:
        zip_path, friendly_name = GalleryService.create_zip(req.images, req.title or "gallery")
        background_tasks.add_task(clean_old_files, DOWNLOAD_DIR)
        return FileResponse(
            path=zip_path,
            filename=friendly_name,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{friendly_name}"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/network-info")
def get_network_info():
    lan_ip = "192.168.1.102"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        lan_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    return {
        "lan_ip": lan_ip,
        "lan_url": f"http://{lan_ip}:8000",
        "tunnel_url": "https://throwing-inspired-agents-terminal.trycloudflare.com",
        "tunnel_password": ""
    }

@app.get("/api/thumbnail/download")
async def download_thumbnail_image(
    url: str = Query(..., description="Direct image URL"),
    title: Optional[str] = Query("thumbnail", description="Filename title")
):
    """
    Downloads and streams the video thumbnail image as a direct attachment file.
    Bypasses CORS restrictions and ensures direct browser saving.
    """
    clean_title = sanitize_filename(title) if title else "thumbnail"
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url.strip())
            if resp.status_code != 200:
                raise HTTPException(status_code=400, detail="Could not fetch thumbnail from source URL.")

            content_type = resp.headers.get("content-type", "image/jpeg")
            ext = ".jpg"
            if "png" in content_type:
                ext = ".png"
            elif "webp" in content_type:
                ext = ".webp"

            filename = f"{clean_title}_thumbnail{ext}"
            return Response(
                content=resp.content,
                media_type=content_type,
                headers={
                    "Content-Disposition": f'attachment; filename="{filename}"',
                    "Cache-Control": "public, max-age=86400"
                }
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Thumbnail download failed: {str(e)}")

if os.path.exists(STATIC_DIR):
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
