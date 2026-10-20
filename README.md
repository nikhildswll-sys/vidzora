# 🚀 OmniMedia — Unlimited Media Downloader & Earning Suite

A high-performance, modern all-in-one media downloader web app and REST API powered by the top 5 open-source media engines:

1. **yt-dlp**: Core extraction engine for YouTube, Facebook, Twitter/X, TikTok, Reddit, and 1,000+ video platforms.
2. **Cobalt**: Modern multi-platform architecture with instant direct streaming/downloading.
3. **SpotDL & Audio Engine**: High-fidelity MP3 conversion (up to 320 kbps) with metadata tagging.
4. **Gallery-DL**: Bulk photo and image scraper for Pinterest, Reddit, Instagram albums, and Twitter media.
5. **Instaloader**: Dedicated Reels, Stories, and IGTV extraction.

---

## 💻 How to Run the App

Simply run:
```bash
python run.py
```
This starts the local FastAPI server and automatically opens **`http://127.0.0.1:8000`** in your default web browser!

---

## 💰 How to Make Money with This Project

### 1. Website Ad Revenue (Google AdSense / Adsterra / PopAds)
- Open `static/index.html`.
- Locate the marked ad space comment: `<!-- Top Monetization / Ad Slot Banner -->`.
- Paste your AdSense or Adsterra ad code snippet there.
- You can also add a popunder script or interstitial ad whenever the user clicks the "Download" button.

### 2. Sell API Access on RapidAPI
- Go to [RapidAPI.com](https://rapidapi.com) and create an API listing (e.g., *"Universal Video & Reels Downloader API"*).
- Connect it to your hosted `/api/extract` and `/api/download` endpoints.
- Charge developers **$9.99/month for 5,000 requests** or **$49.99/month for unlimited requests**.

### 3. Deploy for Free on VPS or Cloud
- You can host this for free or cheap on **Render, Railway, Fly.io, or an Oracle Free Tier VPS** using Docker or standard Python.

---

## 🛠️ REST API Endpoints

- **`POST /api/extract`**: Extract video title, thumbnail, duration, uploader, and available formats.
- **`GET /api/download?url=...&quality=...`**: Stream and download MP4 video or 320kbps MP3 audio.
- **`POST /api/gallery`**: Extract high-resolution photo URLs from Pinterest, Reddit, or Instagram galleries.
- **`POST /api/gallery/zip`**: Download selected gallery photos bundled into a ZIP file.
- **`GET /docs`**: Interactive Swagger UI with live testing.
