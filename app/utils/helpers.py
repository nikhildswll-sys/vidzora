import re
import os
import time
from urllib.parse import urlparse

def format_duration(seconds):
    if not seconds:
        return "Unknown"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def format_filesize(bytes_val):
    if not bytes_val or bytes_val <= 0:
        return "Dynamic / Stream"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024.0:
            return f"{bytes_val:.1f} {unit}"
        bytes_val /= 1024.0
    return f"{bytes_val:.1f} PB"

def sanitize_filename(name):
    # Remove characters that are illegal in Windows filenames
    cleaned = re.sub(r'[\\/*?:"<>|]', "", name)
    cleaned = cleaned.strip().replace(" ", "_")
    return cleaned[:100] if len(cleaned) > 100 else cleaned

def detect_platform(url):
    domain = urlparse(url).netloc.lower()
    if any(k in domain for k in ['youtube.com', 'youtu.be']):
        return "youtube"
    elif any(k in domain for k in ['instagram.com', 'instagr.am']):
        return "instagram"
    elif any(k in domain for k in ['tiktok.com']):
        return "tiktok"
    elif any(k in domain for k in ['twitter.com', 'x.com']):
        return "twitter"
    elif any(k in domain for k in ['reddit.com', 'redd.it']):
        return "reddit"
    elif any(k in domain for k in ['pinterest.com', 'pin.it']):
        return "pinterest"
    elif any(k in domain for k in ['facebook.com', 'fb.watch', 'fb.com']):
        return "facebook"
    elif any(k in domain for k in ['spotify.com']):
        return "spotify"
    elif any(k in domain for k in ['soundcloud.com']):
        return "soundcloud"
    return "universal"

def clean_old_files(directory, max_age_seconds=1800):
    """Deletes files older than 30 minutes in downloads directory to save disk space"""
    now = time.time()
    try:
        if os.path.exists(directory):
            for filename in os.listdir(directory):
                filepath = os.path.join(directory, filename)
                if os.path.isfile(filepath):
                    if now - os.path.getmtime(filepath) > max_age_seconds:
                        try:
                            os.remove(filepath)
                        except Exception:
                            pass
    except Exception:
        pass
