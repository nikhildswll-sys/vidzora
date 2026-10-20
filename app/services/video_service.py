import os
import uuid
import threading
import subprocess
import yt_dlp
import imageio_ffmpeg
from app.utils.helpers import format_duration, sanitize_filename, detect_platform

DOWNLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "downloads"))
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

DOWNLOAD_TASKS = {}
TASKS_LOCK = threading.Lock()

class VideoService:
    @staticmethod
    def extract_info(url: str):
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': False,
            'ffmpeg_location': FFMPEG_PATH,
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android', 'web_creator', 'mweb'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
            }
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
            except Exception as e:
                raise RuntimeError(f"Could not load media: {str(e)}")

        if not info:
            raise ValueError("No video found at this URL.")

        if 'entries' in info and info['entries']:
            info = info['entries'][0]

        title = info.get('title', 'Video Download')
        thumbnail = info.get('thumbnail') or (info.get('thumbnails')[-1]['url'] if info.get('thumbnails') else None)
        duration = info.get('duration')
        uploader = info.get('uploader') or info.get('channel') or info.get('creator') or 'Online Video'
        platform = detect_platform(url)

        thumbnail_hd = thumbnail
        if 'thumbnails' in info and info['thumbnails']:
            sorted_thumbs = sorted(info['thumbnails'], key=lambda x: (x.get('width') or 0) * (x.get('height') or 0), reverse=True)
            if sorted_thumbs:
                thumbnail_hd = sorted_thumbs[0].get('url') or thumbnail

        options = [
            {"id": "720", "label": "720p HD", "badge": "Fast", "type": "video", "ext": "mp4", "desc": "High Definition • Fast Direct Download"},
            {"id": "1080", "label": "1080p Full HD", "badge": "Ultra", "type": "video", "ext": "mp4", "desc": "Crisp 1080p Video • Best Quality"},
            {"id": "480", "label": "480p SD", "badge": "Standard", "type": "video", "ext": "mp4", "desc": "Standard Definition"},
            {"id": "360", "label": "360p Data Saver", "badge": "Small", "type": "video", "ext": "mp4", "desc": "Small File Size for Mobile"},
            {"id": "mp3_320", "label": "MP3 Studio Audio", "badge": "320k", "type": "audio", "ext": "mp3", "desc": "Highest Bitrate MP3 Audio"},
            {"id": "mp3_192", "label": "MP3 High Audio", "badge": "192k", "type": "audio", "ext": "mp3", "desc": "Clear MP3 Audio"},
            {"id": "m4a", "label": "M4A Original Audio", "badge": "AAC", "type": "audio", "ext": "m4a", "desc": "Lossless Original Audio Track"}
        ]

        return {
            "title": title,
            "thumbnail": thumbnail,
            "thumbnail_hd": thumbnail_hd,
            "duration": format_duration(duration),
            "uploader": uploader,
            "platform": platform,
            "url": url,
            "options": options
        }

    @staticmethod
    def get_live_stream(url: str, quality_id: str, start_time: str = None, end_time: str = None):
        """
        Extracts media format URLs and returns:
        (generator, media_type, filename)
        Streams audio/video directly to the client's browser with ZERO server disk footprint!
        Supports on-the-fly video trimming with start_time and end_time.
        """
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'extract_flat': False,
            'ffmpeg_location': FFMPEG_PATH,
            'js_runtimes': {'node': {}},
            'extractor_args': {
                'youtube': {
                    'player_client': ['ios', 'android', 'web_creator', 'mweb'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1',
            }
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        if not info:
            raise ValueError("Could not extract stream info.")
        if 'entries' in info and info['entries']:
            info = info['entries'][0]

        title = sanitize_filename(info.get('title', 'video'))
        formats = info.get('formats', [])

        trim_args = []
        if start_time and start_time.strip():
            trim_args.extend(["-ss", start_time.strip()])
        if end_time and end_time.strip():
            trim_args.extend(["-to", end_time.strip()])

        if trim_args:
            title = f"{title}_clip"

        # 1. Audio request (MP3 or M4A)
        if quality_id.startswith("mp3"):
            filename = f"{title}.mp3"
            media_type = "audio/mpeg"
            a_url = None
            for f in formats:
                if f.get('acodec') != 'none' and f.get('url'):
                    a_url = f['url']
                    if f.get('ext') in ['m4a', 'mp3', 'opus']:
                        break
            if not a_url:
                raise ValueError("No audio track found for this link.")

            bitrate = "320k" if "320" in quality_id else ("192k" if "192" in quality_id else "128k")
            cmd = [FFMPEG_PATH, "-y"] + trim_args + [
                "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
                "-i", a_url,
                "-vn", "-ar", "44100", "-ac", "2", "-b:a", bitrate,
                "-f", "mp3", "pipe:1"
            ]
            def stream_audio():
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                try:
                    while True:
                        chunk = proc.stdout.read(65536)
                        if not chunk:
                            break
                        yield chunk
                finally:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            return stream_audio(), media_type, filename

        elif quality_id == "m4a":
            filename = f"{title}.m4a"
            media_type = "audio/mp4"
            a_url = None
            for f in formats:
                if f.get('ext') == 'm4a' and f.get('url'):
                    a_url = f['url']
                    break
            if not a_url:
                for f in formats:
                    if f.get('acodec') != 'none' and f.get('url'):
                        a_url = f['url']
                        break
            if not a_url:
                raise ValueError("No audio track found.")

            cmd = [
                FFMPEG_PATH, "-y",
                "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
                "-i", a_url,
                "-vn", "-c:a", "copy",
                "-movflags", "frag_keyframe+empty_moov+default_base_moof",
                "-f", "mp4", "pipe:1"
            ]
            def stream_m4a():
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                try:
                    while True:
                        chunk = proc.stdout.read(65536)
                        if not chunk:
                            break
                        yield chunk
                finally:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            return stream_m4a(), media_type, filename

        # 2. Video request (1080p, 720p, 480p, 360p, or best)
        filename = f"{title}.mp4"
        media_type = "video/mp4"

        target_h = 720
        if quality_id.isdigit():
            target_h = int(quality_id)

        prog_format = None
        for f in formats:
            if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('url'):
                h = f.get('height') or 0
                if h <= target_h:
                    if not prog_format or h > (prog_format.get('height') or 0):
                        prog_format = f

        if prog_format and prog_format.get('ext') == 'mp4':
            p_url = prog_format['url']
            cmd = [FFMPEG_PATH, "-y"] + trim_args + [
                "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
                "-i", p_url,
                "-c", "copy",
                "-movflags", "frag_keyframe+empty_moov+default_base_moof",
                "-f", "mp4", "pipe:1"
            ]
            def stream_prog():
                proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                try:
                    while True:
                        chunk = proc.stdout.read(65536)
                        if not chunk:
                            break
                        yield chunk
                finally:
                    try:
                        proc.kill()
                    except Exception:
                        pass
            return stream_prog(), media_type, filename

        # Separate video + audio
        v_url = None
        candidates_h264 = [
            f for f in formats 
            if f.get('vcodec') != 'none' 
            and (f.get('vcodec', '').startswith('avc') or f.get('ext') == 'mp4') 
            and f.get('height') and f.get('height') <= target_h 
            and f.get('url')
        ]
        if candidates_h264:
            candidates_h264.sort(key=lambda x: x.get('height') or 0, reverse=True)
            v_url = candidates_h264[0]['url']
        else:
            candidates_any = [
                f for f in formats 
                if f.get('vcodec') != 'none' 
                and f.get('height') and f.get('height') <= target_h 
                and f.get('url')
            ]
            if candidates_any:
                candidates_any.sort(key=lambda x: x.get('height') or 0, reverse=True)
                v_url = candidates_any[0]['url']
            else:
                for f in formats:
                    if f.get('vcodec') != 'none' and f.get('url'):
                        v_url = f['url']
                        break

        a_url = None
        for f in formats:
            if f.get('acodec') != 'none' and f.get('ext') == 'm4a' and f.get('url'):
                a_url = f['url']
                break
        if not a_url:
            for f in formats:
                if f.get('acodec') != 'none' and f.get('url'):
                    a_url = f['url']
                    break

        if not v_url:
            raise ValueError("No video stream found for this link.")

        if a_url:
            cmd = [FFMPEG_PATH, "-y"] + trim_args + [
                "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
                "-i", v_url
            ] + trim_args + [
                "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
                "-i", a_url,
                "-c:v", "copy",
                "-c:a", "aac",
                "-movflags", "frag_keyframe+empty_moov+default_base_moof",
                "-f", "mp4",
                "pipe:1"
            ]
        else:
            cmd = [FFMPEG_PATH, "-y"] + trim_args + [
                "-reconnect", "1", "-reconnect_streamed", "1", "-reconnect_delay_max", "5",
                "-i", v_url,
                "-c:v", "copy",
                "-movflags", "frag_keyframe+empty_moov+default_base_moof",
                "-f", "mp4",
                "pipe:1"
            ]

        def stream_merged():
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            try:
                while True:
                    chunk = proc.stdout.read(65536)
                    if not chunk:
                        break
                    yield chunk
            finally:
                try:
                    proc.kill()
                except Exception:
                    pass

        return stream_merged(), media_type, filename

    @staticmethod
    def process_direct_download(url: str, quality_id: str):
        """Processes and returns file directly for native browser download"""
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        unique_token = str(uuid.uuid4())[:8]
        target_ext = "mp4"

        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_DIR, f"{unique_token}_%(title)s.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'ffmpeg_location': FFMPEG_PATH,
        }

        if quality_id.startswith("mp3"):
            target_ext = "mp3"
            bitrate = "320" if "320" in quality_id else ("192" if "192" in quality_id else "128")
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': bitrate,
                }]
            })
        elif quality_id == "m4a":
            target_ext = "m4a"
            ydl_opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
            })
        elif quality_id == "1080":
            target_ext = "mp4"
            ydl_opts.update({
                'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
                'merge_output_format': 'mp4'
            })
        elif quality_id in ["720", "480", "360"]:
            h = int(quality_id)
            target_ext = "mp4"
            ydl_opts.update({
                'format': f'bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={h}]+bestaudio/best[height<={h}]/best',
                'merge_output_format': 'mp4'
            })
        else: # Default 720p
            target_ext = "mp4"
            ydl_opts.update({
                'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best',
                'merge_output_format': 'mp4'
            })

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            clean_title = sanitize_filename(info.get('title', 'video'))

            matching = [f for f in os.listdir(DOWNLOAD_DIR) if f.startswith(unique_token)]
            if not matching:
                raise FileNotFoundError("Could not find generated media file.")

            full_path = os.path.join(DOWNLOAD_DIR, matching[0])
            friendly_name = f"{clean_title}.{target_ext}"
            return full_path, friendly_name

    @staticmethod
    def start_download_task(url: str, quality_id: str):
        task_id = str(uuid.uuid4())[:12]
        with TASKS_LOCK:
            DOWNLOAD_TASKS[task_id] = {
                "status": "starting",
                "progress": 0,
                "speed": "0 KB/s",
                "eta": "--",
                "file_path": None,
                "filename": None,
                "error": None
            }

        thread = threading.Thread(
            target=VideoService._run_download,
            args=(task_id, url, quality_id),
            daemon=True
        )
        thread.start()
        return task_id

    @staticmethod
    def _run_download(task_id: str, url: str, quality_id: str):
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        unique_prefix = f"dl_{task_id}_"
        target_ext = "mp4"

        def progress_hook(d):
            if d['status'] == 'downloading':
                total = d.get('total_bytes') or d.get('total_bytes_estimate') or 1
                downloaded = d.get('downloaded_bytes', 0)
                pct = min(99.0, round((downloaded / total) * 100, 1))
                speed = d.get('_speed_str', '').strip() or 'Downloading...'
                eta = d.get('_eta_str', '').strip() or ''

                with TASKS_LOCK:
                    if task_id in DOWNLOAD_TASKS:
                        DOWNLOAD_TASKS[task_id].update({
                            "status": "downloading",
                            "progress": pct,
                            "speed": speed,
                            "eta": eta
                        })
            elif d['status'] == 'finished':
                with TASKS_LOCK:
                    if task_id in DOWNLOAD_TASKS:
                        DOWNLOAD_TASKS[task_id].update({
                            "status": "processing",
                            "progress": 99.0,
                            "speed": "Converting...",
                            "eta": ""
                        })

        ydl_opts = {
            'outtmpl': os.path.join(DOWNLOAD_DIR, f"{unique_prefix}%(title)s.%(ext)s"),
            'quiet': True,
            'no_warnings': True,
            'progress_hooks': [progress_hook],
            'ffmpeg_location': FFMPEG_PATH,
        }

        if quality_id.startswith("mp3"):
            target_ext = "mp3"
            bitrate = "320" if "320" in quality_id else ("192" if "192" in quality_id else "128")
            ydl_opts.update({
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': bitrate,
                }]
            })
        elif quality_id == "m4a":
            target_ext = "m4a"
            ydl_opts.update({
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
            })
        elif quality_id == "1080":
            target_ext = "mp4"
            ydl_opts.update({
                'format': 'bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]/best',
                'merge_output_format': 'mp4'
            })
        elif quality_id in ["720", "480", "360"]:
            h = int(quality_id)
            target_ext = "mp4"
            ydl_opts.update({
                'format': f'bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={h}]+bestaudio/best[height<={h}]/best',
                'merge_output_format': 'mp4'
            })
        else: # Default 720p
            target_ext = "mp4"
            ydl_opts.update({
                'format': 'bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<=720]+bestaudio/best[height<=720]/best',
                'merge_output_format': 'mp4'
            })

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = sanitize_filename(info.get('title', 'video'))

                matching = [f for f in os.listdir(DOWNLOAD_DIR) if f.startswith(unique_prefix)]
                if not matching:
                    raise FileNotFoundError("Output file could not be generated.")

                actual_file = matching[0]
                full_path = os.path.join(DOWNLOAD_DIR, actual_file)
                friendly_name = f"{title}.{target_ext}"

                with TASKS_LOCK:
                    if task_id in DOWNLOAD_TASKS:
                        DOWNLOAD_TASKS[task_id].update({
                            "status": "completed",
                            "progress": 100.0,
                            "file_path": full_path,
                            "filename": friendly_name
                        })
        except Exception as e:
            with TASKS_LOCK:
                if task_id in DOWNLOAD_TASKS:
                    DOWNLOAD_TASKS[task_id].update({
                        "status": "error",
                        "error": str(e)
                    })

    @staticmethod
    def get_task_status(task_id: str):
        with TASKS_LOCK:
            return DOWNLOAD_TASKS.get(task_id)

    @staticmethod
    def process_bulk_zip(urls: list, quality_id: str = "720"):
        import zipfile
        os.makedirs(DOWNLOAD_DIR, exist_ok=True)
        unique_token = str(uuid.uuid4())[:8]
        zip_filename = f"vidzora_bulk_{unique_token}.zip"
        zip_path = os.path.join(DOWNLOAD_DIR, zip_filename)

        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for idx, raw_url in enumerate(urls[:5]):
                u = raw_url.strip()
                if not u:
                    continue
                try:
                    file_path, friendly_name = VideoService.process_direct_download(u, quality_id)
                    if os.path.exists(file_path):
                        zipf.write(file_path, arcname=f"{idx+1}_{friendly_name}")
                        try:
                            os.remove(file_path)
                        except Exception:
                            pass
                except Exception:
                    continue

        return zip_path, zip_filename
