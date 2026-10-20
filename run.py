import uvicorn
import webbrowser
import threading
import time
import socket

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def open_browser():
    time.sleep(1.5)
    print("\n[+] Opening ClipVault Ultra in your browser...")
    webbrowser.open("http://127.0.0.1:8000")

if __name__ == "__main__":
    local_ip = get_local_ip()
    print("=" * 60)
    print("   ClipVault Ultra - Online Media Downloader")
    print("=" * 60)
    print(f"[*] PC Local Link  : http://localhost:8000")
    print(f"[*] Mobile Wi-Fi Link: http://{local_ip}:8000")
    print("=" * 60)
    print("   (Mobile aur PC same Wi-Fi par hone chahiye)")
    print("=" * 60)

    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
