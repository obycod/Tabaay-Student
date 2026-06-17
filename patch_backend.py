import os

file_path = r"c:\Users\asus\OneDrive\Desktop\main\backend.py"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

injection = """
import hashlib
import subprocess

# --- Auto-Update & Images Sync ---
@eel.expose
def check_app_update():
    try:
        url = "https://app.altabaay.co/update_Student/student_version.txt"
        h = HEADERS.copy()
        h["Cache-Control"] = "no-cache, no-store, must-revalidate"
        h["Pragma"] = "no-cache"
        h["Expires"] = "0"
        r = requests.get(f"{url}?rnd={time.time()}", headers=h, timeout=7)
        if r.status_code == 200:
            lines = r.text.strip().splitlines()
            if lines and len(lines) >= 2:
                remote_version_str = lines[0].strip()
                download_link = lines[1].strip()
                if float(remote_version_str) > float(APP_VERSION):
                    return {"update_available": True, "version": remote_version_str, "link": download_link}
    except Exception as e:
        print("Update check error:", e)
    return {"update_available": False}

@eel.expose
def apply_app_update(download_link):
    def _download_and_install():
        temp_dir = os.getenv('TEMP', os.path.expanduser("~"))
        installer_path = os.path.join(temp_dir, "Tabaay_Student_Setup_New.exe")
        
        if os.path.exists(installer_path):
            for _ in range(5):
                try:
                    os.remove(installer_path)
                    break
                except OSError:
                    time.sleep(0.5)
                    
        try:
            h = HEADERS.copy()
            h["Cache-Control"] = "no-cache, no-store, must-revalidate"
            with requests.get(f"{download_link}?rnd={time.time()}", headers=h, stream=True, timeout=30) as r:
                r.raise_for_status()
                total_size = int(r.headers.get('content-length', 0))
                downloaded = 0
                with open(installer_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024*1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 0:
                            try:
                                eel.update_app_progress((downloaded / total_size) * 100)()
                            except: pass
            
            subprocess.Popen([installer_path, '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'], creationflags=subprocess.CREATE_NO_WINDOW)
            os._exit(0)
        except Exception as e:
            print(f"App Update Download Error: {e}")
            try:
                eel.app_update_failed()()
            except: pass
            
    threading.Thread(target=_download_and_install, daemon=True).start()

@eel.expose
def sync_images_background():
    def _sync():
        try:
            url = "https://app.altabaay.co/update_Student/assets/assets_hash.json"
            h = HEADERS.copy()
            h["Cache-Control"] = "no-cache, no-store, must-revalidate"
            r = requests.get(f"{url}?rnd={time.time()}", headers=h, timeout=10)
            if r.status_code == 200:
                remote_hashes = r.json()
                
                assets_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web", "assets")
                if getattr(sys, 'frozen', False):
                    assets_dir = os.path.join(os.path.dirname(sys.executable), "web", "assets")

                for relative_path, remote_hash in remote_hashes.items():
                    local_file = os.path.join(assets_dir, relative_path.replace('/', os.sep))
                    needs_download = False
                    
                    if not os.path.exists(local_file):
                        needs_download = True
                    else:
                        with open(local_file, "rb") as f:
                            local_hash = hashlib.md5(f.read()).hexdigest().lower()
                        if local_hash != remote_hash:
                            needs_download = True
                            
                    if needs_download:
                        os.makedirs(os.path.dirname(local_file), exist_ok=True)
                        img_url = f"https://app.altabaay.co/update_Student/assets/{relative_path}?rnd={time.time()}"
                        img_r = requests.get(img_url, headers=h, timeout=15)
                        if img_r.status_code == 200:
                            with open(local_file, "wb") as f:
                                f.write(img_r.content)
                                
        except Exception as e:
            print("Sync images error:", e)

    threading.Thread(target=_sync, daemon=True).start()

"""

if "def check_app_update" not in content:
    content = content.replace("if __name__ == '__main__':", injection + "\nif __name__ == '__main__':")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Injected successfully.")
else:
    print("Already injected.")
