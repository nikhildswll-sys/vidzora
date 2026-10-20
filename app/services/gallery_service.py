import os
import subprocess
import json
import uuid
import zipfile
import requests
from app.utils.helpers import sanitize_filename

DOWNLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "downloads"))

class GalleryService:
    @staticmethod
    def extract_gallery(url: str):
        """
        Uses gallery-dl -g (or --dump-json) to extract image URLs from posts/galleries
        """
        try:
            # First try gallery-dl -j to get rich metadata
            cmd = ["gallery-dl", "-j", "--range", "1-30", url]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            images = []
            title = "Extracted Gallery"

            if result.returncode == 0 and result.stdout.strip():
                for line in result.stdout.strip().split("\n"):
                    try:
                        data = json.loads(line)
                        # Extract image url
                        img_url = None
                        if isinstance(data, list) and len(data) >= 3 and isinstance(data[2], dict):
                            img_url = data[1] if isinstance(data[1], str) and data[1].startswith("http") else None
                            if not img_url and 'url' in data[2]:
                                img_url = data[2]['url']
                            if 'title' in data[2] and data[2]['title']:
                                title = data[2]['title']
                        elif isinstance(data, dict):
                            img_url = data.get('url') or data.get('preview_url')
                            if data.get('title'):
                                title = data.get('title')

                        if img_url and img_url not in [img['url'] for img in images]:
                            images.append({
                                "url": img_url,
                                "id": len(images) + 1
                            })
                    except Exception:
                        continue

            # Fallback to simple -g (URLs only)
            if not images:
                cmd_urls = ["gallery-dl", "-g", "--range", "1-30", url]
                res_urls = subprocess.run(cmd_urls, capture_output=True, text=True, timeout=30)
                if res_urls.returncode == 0 and res_urls.stdout.strip():
                    lines = [l.strip() for l in res_urls.stdout.strip().split("\n") if l.strip().startswith("http")]
                    for idx, u in enumerate(lines[:30]):
                        images.append({
                            "url": u,
                            "id": idx + 1
                        })

            return {
                "title": title,
                "count": len(images),
                "images": images,
                "url": url
            }
        except Exception as e:
            raise RuntimeError(f"Gallery extraction error: {str(e)}")

    @staticmethod
    def create_zip(image_urls: list, title: str = "gallery"):
        """Downloads selected images and zips them for 1-click batch download"""
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        unique_token = str(uuid.uuid4())[:8]
        safe_title = sanitize_filename(title)
        zip_filename = f"{safe_title}_{unique_token}.zip"
        zip_path = os.path.join(DOWNLOAD_DIR, zip_filename)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for idx, img_url in enumerate(image_urls[:25]): # limit to 25 to be safe
                try:
                    r = requests.get(img_url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                    if r.status_code == 200:
                        ext = "jpg"
                        if ".png" in img_url:
                            ext = "png"
                        elif ".webp" in img_url:
                            ext = "webp"
                        zipf.writestr(f"image_{idx+1:02d}.{ext}", r.content)
                except Exception:
                    continue

        return zip_path, f"{safe_title}.zip"
