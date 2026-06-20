import gevent.monkey
gevent.monkey.patch_all()
import os
import sys
import json
import time
import string
import shutil
# تم استرجاع gevent لحل مشكلة wsgiref
import threading
import queue
import requests
import urllib3
import eel

import base64

def _d(s):
    k = "TAB3Y"
    try:
        decoded = base64.b64decode(s).decode('utf-8')
        return "".join(chr(ord(c) ^ ord(k[i % len(k)])) for i, c in enumerate(decoded))
    except:
        return ""

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

APP_VERSION = "10.1"
APP_NAME = "Tabaay_Student"
BASE_URL_FILES = _d("PDU2Qypubm1DPTBvOlcteiw7UTUhJCpcKiBvL1Z2ITEmUi0x")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Connection": "keep-alive",
    "X-Tabaay-Auth": "TABAAY_SECURE_77x9"
}

# مجلد مؤقت محلي على جهاز الكمبيوتر لتسريع التحميل
TEMP_FOLDER = os.path.join(os.getenv('APPDATA', ''), 'TabaayTemp')
os.makedirs(TEMP_FOLDER, exist_ok=True)

DISPLAY_STAGES = [
    "اول ابتدائي", "ثاني ابتدائي", "ثالث ابتدائي", "رابع ابتدائي", "خامس ابتدائي", "سادس ابتدائي",
    "اول متوسط", "ثاني متوسط", "ثالث متوسط",
    "رابع علمي", "رابع ادبي", "خامس علمي", "خامس ادبي", "سادس علمي", "سادس ادبي", "اول صناعي", "ثاني صناعي", "سادس صناعي", "قصص ومغامرات", "مراحل عامة"
]

# --- Utilities ---
def map_and_expand_stages(act, disp_text, raw_stage=None):
    cleaned = disp_text.strip()
    results = []
    detected_stage = raw_stage if raw_stage else None
    if not detected_stage:
        ALL_POSSIBLE = [
            "سادس اعدادي", "سادس علمي", "سادس ادبي", "سادس صناعي",
            "خامس اعدادي", "خامس علمي", "خامس ادبي",
            "رابع اعدادي", "رابع علمي", "رابع ادبي",
            "ثالث متوسط", "ثاني متوسط", "اول متوسط",
            "سادس ابتدائي", "خامس ابتدائي", "رابع ابتدائي", "ثالث ابتدائي", "ثاني ابتدائي", "اول ابتدائي",
            "قصص ومغامرات"
        ]
        for s in ALL_POSSIBLE:
            if s in cleaned:
                detected_stage = s
                break
        if not detected_stage:
            detected_stage = "مراحل عامة"
            
    if detected_stage == "سادس اعدادي":
        results.append({"act": act, "stage": "سادس علمي", "is_shared": True, "subject": disp_text})
        results.append({"act": act, "stage": "سادس ادبي", "is_shared": True, "subject": disp_text})
    elif detected_stage == "خامس اعدادي":
        results.append({"act": act, "stage": "خامس علمي", "is_shared": True, "subject": disp_text})
        results.append({"act": act, "stage": "خامس ادبي", "is_shared": True, "subject": disp_text})
    elif detected_stage == "رابع اعدادي":
        results.append({"act": act, "stage": "رابع علمي", "is_shared": True, "subject": disp_text})
        results.append({"act": act, "stage": "رابع ادبي", "is_shared": True, "subject": disp_text})
    else:
        results.append({"act": act, "stage": detected_stage, "is_shared": False, "subject": disp_text})
        
    return results

def get_remote_size(url):
    try:
        with requests.head(url, headers=HEADERS, timeout=5, verify=False) as r:
            if r.status_code == 200: return int(r.headers.get('content-length', -1))
    except: pass
    return 0

# --- State ---
is_syncing = False

# قفل خيوط للأمان - يمنع التعارض بين الخيوط المتعددة
_state_lock = threading.Lock()
_cancel_lock = threading.Lock()
_pause_lock  = threading.Lock()

cancel_flags = {}
pause_flags = {}
act_to_name = {}
global_dl_state = {}
global_speed_history = []

usb_queue = queue.Queue()
usb_thread_running = False

def usb_copier_worker():
    global usb_thread_running
    while is_syncing or not usb_queue.empty():
        try:
            item = usb_queue.get(timeout=1.0)
            act, tmp_local, dest_pen, pen_drive, ebook_dir, finished_counter, total_files = item
            
            try:
                # إصلاح: التحقق من وجود القلم قبل النقل
                if not os.path.exists(pen_drive):
                    try: eel.show_pen_disconnected()()
                    except: pass
                    while not os.path.exists(pen_drive):
                        time.sleep(2)
                    try: os.makedirs(ebook_dir, exist_ok=True)
                    except: pass
                    try: eel.show_pen_reconnected(pen_drive)()
                    except: pass
                    
                copied = 0
                start_t = time.time()
                last_u = start_t
                down_bytes = 0
                speeds = []
                size = os.path.getsize(tmp_local) if os.path.exists(tmp_local) else 0
                disp = act_to_name.get(act.lower(), act)
                
                try: eel.start_usb_sync(act)()
                except: pass
                
                with open(tmp_local, 'rb') as fsrc, open(dest_pen, 'wb') as fdst:
                    while True:
                        buf = fsrc.read(1024 * 1024)
                        if not buf:
                            break
                        fdst.write(buf)
                        chunk_len = len(buf)
                        copied += chunk_len
                        down_bytes += chunk_len
                        
                        now = time.time()
                        if now - last_u > 0.2 or copied == size:
                            elap = now - start_t
                            if elap > 1:
                                spd = down_bytes / elap
                                speeds.append(spd)
                                if len(speeds) > 20: speeds.pop(0)
                                avg = sum(speeds) / len(speeds)
                            else:
                                avg = 0
                                
                            loc_mb = copied / (1024 * 1024)
                            size_mb = size / (1024 * 1024)
                            pct = int((copied / size) * 100) if size > 0 else 0
                            pct = min(100, max(0, pct))
                            progress_str = f"{loc_mb:.1f} MB / {size_mb:.1f} MB"
                            # تحديث الحالة الكلية لكي يحسب وقت التنزيل والنقل معاً
                            with _state_lock:
                                state = global_dl_state.get(act, {"net_loc": size, "pen_loc": 0, "size": size, "net_speed": 0, "pen_speed": 0})
                                state["pen_loc"] = copied
                                state["pen_speed"] = avg
                                state["net_speed"] = 0
                                global_dl_state[act] = state
                            try: eel.update_progress(act, pct, disp, progress_str)()
                            except: pass
                            last_u = now

                try: os.remove(tmp_local)
                except: pass
                
                try: eel.item_finished(act, True, "")()
                except: pass
            except Exception as e:
                if not os.path.exists(pen_drive) or isinstance(e, OSError):
                    with _pause_lock:
                        pause_flags[act] = True
                    try:
                        eel.show_pen_disconnected()()
                        eel.notify_pen_error(act)()
                    except: pass
                else:
                    try: eel.item_finished(act, False, f"فشل النقل: {str(e)}")()
                    except: pass
            finally:
                _notify_finished(finished_counter, total_files)
        except queue.Empty:
            pass
    usb_thread_running = False

@eel.expose
def check_pen():
    pens = []
    try:
        import ctypes
        import string
        for l in string.ascii_uppercase[3:]:
            drive = f"{l}:\\"
            if os.path.exists(drive):
                if ctypes.windll.kernel32.GetDriveTypeW(drive) == 2:
                    pens.append(drive)
    except Exception as e: 
        print('Error in check_pen:', e)
    
    if pens:
        eel.update_pen_status(True, pens[0])()
        return pens[0]
    else:
        eel.update_pen_status(False, "")()
        return None

@eel.expose
def get_pen_contents(pen_drive):
    if not pen_drive or not os.path.exists(pen_drive):
        return []
        
    ebook_dir = os.path.join(pen_drive, "EBOOK")
    if not os.path.exists(ebook_dir):
        try: os.makedirs(ebook_dir, exist_ok=True)
        except: pass
        return []
    
    files = []
    try:
        for f in os.listdir(ebook_dir):
            if f.endswith('.tmp'): continue
            
            act_lower = f.lower()
            subject_name = act_to_name.get(act_lower, f.replace('.ALT', '').replace('.alt', '').replace('.ALI', '').replace('.ali', ''))
            size_bytes = os.path.getsize(os.path.join(ebook_dir, f))
            size_mb = size_bytes / (1024 * 1024)
            files.append({"act": f, "subject": subject_name, "size_mb": size_mb})
    except: pass
    return files

@eel.expose
def get_pen_space(pen_drive):
    try:
        total, used, free = shutil.disk_usage(pen_drive)
        total_gb = round(total / (1024**3), 1)
        used_gb = round(used / (1024**3), 1)
        return {
            "total_gb": total_gb, 
            "used_gb": used_gb,
            "free_bytes": free,
            "total_bytes": total
        }
    except:
        return {"total_gb": 0, "used_gb": 0, "free_bytes": 0, "total_bytes": 0}

@eel.expose
def delete_pen_file(pen_drive, act):
    ebook_dir = os.path.join(pen_drive, "EBOOK")
    if not os.path.exists(ebook_dir):
        return False
        
    success = False
    
    # حذف الملف بكل الامتدادات الممكنة
    for ext in ['.ALT', '.alt', '.ALI', '.ali', '.tmp', '']:
        target = os.path.join(ebook_dir, act + ext)
        if os.path.exists(target):
            try:
                os.remove(target)
                success = True
            except:
                pass
                
    return success

@eel.expose
def fetch_stages():
    # تحميل من الكاش أولاً
    cache_file = os.path.join(os.getenv('APPDATA', ''), "Tabaay_Student_StagesCache.json")
    cached_data = {}
    try:
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
    except: pass
    
    # تشغيل التحديث في الخلفية
    threading.Thread(target=fetch_stages_background, daemon=True).start()
    
    if cached_data:
        return cached_data
    
    # إذا لم يوجد كاش، نجلب مباشرة
    res = fetch_stages_logic()
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False)
    except: pass
    return res

def fetch_stages_background():
    res = fetch_stages_logic()
    if "error" not in res:
        cache_file = os.path.join(os.getenv('APPDATA', ''), "Tabaay_Student_StagesCache.json")
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(res, f, ensure_ascii=False)
        except: pass
        try:
            eel.silently_update_stages(res)()
        except: pass
        
        # جلب أحجام الملفات في الخلفية
        import concurrent.futures
        sizes_cache = {}
        cache_file_sz = os.path.join(os.getenv('APPDATA', ''), "Tabaay_Student_Sizes.json")
        try:
            if os.path.exists(cache_file_sz):
                with open(cache_file_sz, 'r', encoding='utf-8') as cf:
                    sizes_cache = json.load(cf)
        except: pass
        
        acts_to_fetch = []
        for stage, subjects in res.get('stages_data', {}).items():
            for subj in subjects:
                cached_size = sizes_cache.get(subj['act'], 0)
                if isinstance(cached_size, dict):
                    cached_size = cached_size.get("size_bytes", 0)
                try:
                    cached_size = int(cached_size)
                except (ValueError, TypeError):
                    cached_size = 0
                
                if cached_size == 0:
                    acts_to_fetch.append(subj['act'])
        
        acts_to_fetch = list(set(acts_to_fetch))
        
        if acts_to_fetch:
            def fetch_size(act):
                try:
                    url = f"{BASE_URL_FILES}/{act}"
                    with requests.get(url, headers=HEADERS, stream=True, timeout=(5, 15), verify=False) as r:
                        if r.status_code == 200:
                            return act, int(r.headers.get('content-length', 0))
                except: pass
                return act, 0
                
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                results = executor.map(fetch_size, acts_to_fetch)
                for act, sz in results:
                    if sz > 0:
                        sizes_cache[act] = sz
                        
            try:
                with open(cache_file_sz, 'w', encoding='utf-8') as cf:
                    json.dump(sizes_cache, cf)
            except: pass
            
            # إعادة تحديث الواجهة بالأحجام الجديدة
            res2 = fetch_stages_logic()
            try:
                eel.silently_update_stages(res2)()
            except: pass

def fetch_stages_logic():
    """جلب قائمة الملفات من السيرفر وتجميعها حسب المراحل"""
    global act_to_name
    act_to_name.clear()
    
    url = f"{BASE_URL_FILES}/files.txt?v={time.time()}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=10, verify=False)
        if resp.status_code != 200:
            return {"error": "Failed to connect to server."}
        resp.encoding = 'utf-8'
        text = resp.text
    except Exception as e:
        return {"error": str(e)}

    # تحميل كاش الأحجام
    import json
    sizes_cache = {}
    cache_file_sz = os.path.join(os.getenv('APPDATA', ''), "Tabaay_Student_Sizes.json")
    try:
        if os.path.exists(cache_file_sz):
            with open(cache_file_sz, 'r', encoding='utf-8') as cf:
                sizes_cache = json.load(cf)
    except: pass

    stages_data = {}
    for line in text.splitlines():
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if not parts[0].lower().endswith('.alt') and not parts[0].lower().endswith('.ali'): continue
            
            act = parts[0]
            disp = parts[1]
            raw_stage = parts[2] if len(parts) >= 3 else None
            if "(موقوف)" in disp: continue
            
            act_to_name[act.lower()] = disp
            
            mapped = map_and_expand_stages(act, disp, raw_stage)
            for m in mapped:
                s_name = m['stage']
                
                size_bytes_raw = sizes_cache.get(act, 0)
                if isinstance(size_bytes_raw, dict):
                    size_bytes = size_bytes_raw.get("size_bytes", 0)
                else:
                    try:
                        size_bytes = int(size_bytes_raw)
                    except (ValueError, TypeError):
                        size_bytes = 0
                size_mb = size_bytes / (1024 * 1024) if size_bytes else 0
                
                if s_name not in stages_data:
                    stages_data[s_name] = []
                stages_data[s_name].append({
                    "act": m['act'],
                    "subject": m['subject'],
                    "size_mb": size_mb,
                    "size_bytes": size_bytes
                })
    return {"stages_data": stages_data, "display_order": DISPLAY_STAGES}

@eel.expose
def get_downloaded_acts(pen_drive):
    ebook_dir = os.path.join(pen_drive, "EBOOK")
    if not os.path.exists(ebook_dir): return []
    
    acts = []
    try:
        for f in os.listdir(ebook_dir):
            size_b = os.path.getsize(os.path.join(ebook_dir, f))
            is_tmp = f.endswith('.tmp')
            act_name = f[:-4] if is_tmp else f
            acts.append({"act": act_name, "size_bytes": size_b, "is_tmp": is_tmp})
    except: pass
    return acts

monitor_thread_instance = None

def monitor_sync():
    global is_syncing, global_dl_state, global_speed_history
    while is_syncing:
        time.sleep(1)
        total_loc = 0
        total_size = 0
        total_speed = 0
        
        with _state_lock:
            state_copy = dict(global_dl_state)
        
        for act, data in state_copy.items():
            n_loc = data.get("net_loc", 0)
            p_loc = data.get("pen_loc", 0)
            total_loc += (n_loc + p_loc) / 2
            total_size += data.get("size", 0)
            total_speed += data.get("net_speed", 0) + data.get("pen_speed", 0)
            
        if total_size > 0:
            pct = int((total_loc / total_size) * 100)
        else:
            pct = 0
            
        pct = min(100, max(0, pct))
        
        remaining_bytes = total_size - total_loc
        if total_speed > 0 and remaining_bytes > 0:
            eta_seconds = int(remaining_bytes / total_speed)
            m, s = divmod(eta_seconds, 60)
            eta_str = f"{m:02d}:{s:02d} متبقي"
        else:
            eta_str = "--:--"
            
        speed_mb = total_speed / (1024 * 1024)
        speed_str = f"{speed_mb:.1f} MB/s"
        
        global_speed_history.append(speed_mb)
        if len(global_speed_history) > 40:
            global_speed_history.pop(0)
            
        loc_mb = total_loc / (1024 * 1024)
        size_mb = total_size / (1024 * 1024)
        sizes_str = f"{loc_mb:.1f} / {size_mb:.1f} MB"
        
        try:
            eel.update_global_progress(pct, sizes_str, speed_str, eta_str, global_speed_history)()
        except: pass

@eel.expose
def start_sync(files, pen_drive):
    global is_syncing, cancel_flags, global_dl_state, global_speed_history, monitor_thread_instance, usb_thread_running
    is_syncing = True

    if not usb_thread_running:
        usb_thread_running = True
        threading.Thread(target=usb_copier_worker, daemon=True).start()

    # إعادة تعيين الحالة بشكل آمن
    with _cancel_lock:
        cancel_flags.clear()
    with _state_lock:
        global_dl_state.clear()
    global_speed_history.clear()
    
    total_files = len(files)
    finished_counter = {"count": 0, "lock": threading.Lock()}
    
    if monitor_thread_instance is None or not monitor_thread_instance.is_alive():
        monitor_thread_instance = threading.Thread(target=monitor_sync, daemon=True)
        monitor_thread_instance.start()
    
    # تشغيل كل ملف في خيط منفصل مع تمرير العداد المشترك لتبدأ جميع التنزيلات في نفس الوقت
    for f in files:
        threading.Thread(
            target=sync_worker,
            args=([f], pen_drive, finished_counter, total_files),
            daemon=True
        ).start()

def sync_worker(files_subset, pen_drive, finished_counter=None, total_files=1):
    """
    خيط التحميل الرئيسي:
    - يحمّل الملفات إلى مجلد مؤقت محلي أولاً (لتجاوز بطء القلم)
    - بعد اكتمال الملف 100%، ينقله إلى القلم بسرعة
    - finished_counter: عداد مشترك لمعرفة متى تنتهي جميع الملفات
    - total_files: العدد الإجمالي للملفات في الدفعة الحالية
    """
    global is_syncing, global_dl_state, cancel_flags, pause_flags, act_to_name

    if not pen_drive or not os.path.exists(pen_drive):
        is_syncing = False
        eel.sync_finished(False, "القلم غير متصل.")()
        return
        
    ebook_dir = os.path.join(pen_drive, "EBOOK")
    if not os.path.exists(ebook_dir):
        try: os.makedirs(ebook_dir, exist_ok=True)
        except: pass
    
    # التأكد من وجود المجلد المؤقت المحلي
    os.makedirs(TEMP_FOLDER, exist_ok=True)

    # جلب أحجام الملفات من السيرفر
    for f in files_subset:
        act = f['act']
        try:
            url = f"{BASE_URL_FILES}/{act}"
            with requests.head(url, headers=HEADERS, timeout=(5, 10), verify=False) as r:
                if r.status_code == 200:
                    size = int(r.headers.get('content-length', 0))
                    if size > 0:
                        f['size_bytes'] = size
        except: pass
        
    for f in files_subset:
        act = f['act']
        disp = f['subject']
        size = f.get('size_bytes', 0)
        
        # تخطي إذا كان ملغياً أو موقوفاً قبل البدء
        with _cancel_lock:
            if cancel_flags.get(act, False) or cancel_flags.get('ALL', False):
                _notify_finished(finished_counter, total_files)
                continue
        with _pause_lock:
            if pause_flags.get(act, False):
                _notify_finished(finished_counter, total_files)
                continue
            
        url = f"{BASE_URL_FILES}/{act}"
        
        # مسارات الملفات: المؤقت المحلي (PC) والنهائي (القلم)
        tmp_local = os.path.join(TEMP_FOLDER, act + ".tmp")   # الملف المؤقت على الكمبيوتر
        dest_pen  = os.path.join(ebook_dir, act)               # الملف النهائي في القلم

        # إذا كان الملف موجوداً في القلم ومكتملاً، تخطَّه
        dest_size = os.path.getsize(dest_pen) if os.path.exists(dest_pen) else 0
        if size > 0 and dest_size >= size:
            eel.item_finished(act, True, "")()
            _notify_finished(finished_counter, total_files)
            continue
            
        # التحقق من الملف المؤقت المحلي (استئناف محتمل)
        loc = os.path.getsize(tmp_local) if os.path.exists(tmp_local) else 0
        
        # إذا كان الملف المؤقت مكتملاً، أرسله فوراً لطابور النقل
        if size > 0 and loc >= size:
            with _state_lock:
                state = global_dl_state.get(act, {"net_loc": 0, "pen_loc": 0, "size": size, "net_speed": 0, "pen_speed": 0})
                state["net_loc"] = size
                state["size"] = size
                state["net_speed"] = 0
                global_dl_state[act] = state
            try: eel.update_progress(act, 100, disp, "جاري الاستعداد للنقل...")()
            except: pass
            usb_queue.put((act, tmp_local, dest_pen, pen_drive, ebook_dir, finished_counter, total_files))
            continue

        head = HEADERS.copy()
        mode = "wb" if loc == 0 else "ab"
        if loc > 0: head['Range'] = f"bytes={loc}-"
            
        down_bytes = 0
        start_t = time.time()
        last_u = time.time()
        speeds = []
        
        try:
            # timeout=(10, 30): 10 ثوانٍ للاتصال، 30 ثانية لكل block لحماية التحميل المتوازي من الانقطاع
            with requests.get(url, headers=head, stream=True, timeout=(10, 30), verify=False) as r:
                if r.status_code == 404:
                    eel.item_finished(act, False, "Not Found")()
                    _notify_finished(finished_counter, total_files)
                    continue
                    
                if r.status_code == 200 and loc > 0:
                    loc = 0
                    mode = "wb"
                    
                content_length = int(r.headers.get('content-length', 0))
                actual_size = (loc + content_length) if content_length > 0 else size
                if actual_size > 0: size = actual_size
                
                # التحميل إلى المجلد المؤقت المحلي أولاً
                with open(tmp_local, mode) as fw:
                    for chunk in r.iter_content(128 * 1024):  # 128 KB chunk لجعل التحميل سلساً وبأقصى سرعة
                        # التحقق من الإلغاء بشكل آمن
                        with _cancel_lock:
                            cancelled = cancel_flags.get(act, False) or cancel_flags.get('ALL', False)
                        if cancelled:
                            raise Exception("cancelled")
                        
                        # التحقق من الإيقاف المؤقت بشكل آمن
                        with _pause_lock:
                            paused = pause_flags.get(act, False)
                        if paused:
                            raise Exception("paused")
                            
                        # التحقق الفوري من وجود القلم أثناء التحميل
                        if not os.path.exists(pen_drive):
                            try: eel.show_pen_disconnected()()
                            except: pass
                            
                            while not os.path.exists(pen_drive):
                                time.sleep(2)
                                # السماح بالإلغاء أو الإيقاف حتى أثناء فصل القلم
                                with _cancel_lock:
                                    if cancel_flags.get(act, False) or cancel_flags.get('ALL', False):
                                        raise Exception("cancelled")
                                with _pause_lock:
                                    if pause_flags.get(act, False):
                                        raise Exception("paused")
                                        
                            try: eel.show_pen_reconnected(pen_drive)()
                            except: pass
                        
                        if chunk:
                            fw.write(chunk)
                            loc += len(chunk)
                            down_bytes += len(chunk)
                            
                            now = time.time()
                            if now - last_u > 0.2 or loc == size:
                                elap = now - start_t
                                if elap > 1:
                                    spd = down_bytes / elap
                                    speeds.append(spd)
                                    if len(speeds) > 20: speeds.pop(0)
                                    avg = sum(speeds) / len(speeds)
                                else:
                                    avg = 0
                                
                                pct = int((loc / size) * 100) if size > 0 else 0
                                pct = min(100, max(0, pct))
                                loc_mb = loc / (1024 * 1024)
                                size_mb = size / (1024 * 1024)
                                progress_str = f"{loc_mb:.1f} MB / {size_mb:.1f} MB"
                                
                                # تحديث الحالة بشكل آمن
                                with _state_lock:
                                    state = global_dl_state.get(act, {"net_loc": 0, "pen_loc": 0, "size": size, "net_speed": 0, "pen_speed": 0})
                                    state["net_loc"] = loc
                                    state["size"] = size
                                    state["net_speed"] = avg
                                    global_dl_state[act] = state
                                
                                eel.update_progress(act, pct, disp, progress_str)()
                                last_u = now
                            
            # بعد اكتمال التحميل في المجلد المؤقت، انقل الملف إلى القلم
            if os.path.exists(tmp_local):
                if (size > 0 and loc >= size) or (size == 0):
                    with _state_lock:
                        state = global_dl_state.get(act, {"net_loc": 0, "pen_loc": 0, "size": size, "net_speed": 0, "pen_speed": 0})
                        state["net_loc"] = size
                        state["size"] = size
                        state["net_speed"] = 0
                        global_dl_state[act] = state
                    
                    try: eel.update_progress(act, 100, disp, "جاري الاستعداد للنقل...")()
                    except: pass
                    
                    # إرسال الملف إلى طابور النقل للقلم
                    usb_queue.put((act, tmp_local, dest_pen, pen_drive, ebook_dir, finished_counter, total_files))
                else:
                    raise Exception("Incomplete download")
                
        except requests.exceptions.RequestException as net_err:
            # انقطاع الإنترنت: أوقف الملف مؤقتاً وأبلغ المستخدم
            # الملف المؤقت يبقى للاستئناف لاحقاً
            with _pause_lock:
                pause_flags[act] = True
            try:
                eel.notify_network_error(act)()
            except: pass
            _notify_finished(finished_counter, total_files)
            
        except Exception as e:
            if str(e) == "paused":
                # الإيقاف المؤقت: الملف المؤقت يبقى للاستئناف
                _notify_finished(finished_counter, total_files)
            else:
                if str(e) == "cancelled":
                    # الإلغاء: احذف الملف المؤقت المحلي نهائياً لمنع ظهوره كملف تالف
                    try:
                        if os.path.exists(tmp_local):
                            os.remove(tmp_local)
                    except: pass
                    eel.item_finished(act, False, "cancelled")()
                else:
                    # خطأ آخر
                    with _state_lock:
                        global_dl_state[act] = {"net_loc": 0, "pen_loc": 0, "size": size, "net_speed": 0, "pen_speed": 0}
                    eel.item_finished(act, False, str(e))()
                _notify_finished(finished_counter, total_files)


def _notify_finished(finished_counter=None, total_files=1):
    """
    إشعار داخلي: يُحصي عدد الملفات المنتهية
    عندما تنتهي جميع الملفات، يستدعي sync_batch_complete مرة واحدة فقط
    """
    if finished_counter is None:
        return
    with finished_counter["lock"]:
        finished_counter["count"] += 1
        if finished_counter["count"] >= total_files:
            # استدعاء sync_batch_complete مرة واحدة بعد انتهاء جميع الملفات
            try:
                eel.sync_batch_complete()()
            except: pass


@eel.expose
def cancel_download(act=None):
    global cancel_flags
    with _cancel_lock:
        if act:
            cancel_flags[act] = True
        else:
            cancel_flags['ALL'] = True

@eel.expose
def set_syncing_false():
    global is_syncing
    is_syncing = False

@eel.expose
def pause_download(act):
    global pause_flags
    with _pause_lock:
        pause_flags[act] = True

@eel.expose
def resume_download(item, pen_drive):
    global pause_flags, cancel_flags, is_syncing, monitor_thread_instance
    act = item.get('act')
    with _pause_lock:
        pause_flags[act] = False
    with _cancel_lock:
        cancel_flags[act] = False
    is_syncing = True
    
    if monitor_thread_instance is None or not monitor_thread_instance.is_alive():
        monitor_thread_instance = threading.Thread(target=monitor_sync, daemon=True)
        monitor_thread_instance.start()
        
    global usb_thread_running
    if not usb_thread_running:
        usb_thread_running = True
        threading.Thread(target=usb_copier_worker, daemon=True).start()
        
    # عند الاستئناف، نمرر counter=None لأننا لا نريد sync_batch_complete عند استئناف ملف واحد
    threading.Thread(target=sync_worker, args=([item], pen_drive, None, 1), daemon=True).start()


@eel.expose
def minimize_app():
    """
    إصلاح #1: تصغير النافذة الأمامية الفعلية (نافذة Chrome/المتصفح)
    بدلاً من نافذة الـ Console المخفية
    GetForegroundWindow تُعيد مقبض النافذة النشطة التي يراها المستخدم
    """
    try:
        import ctypes
        # SW_MINIMIZE = 6
        # GetForegroundWindow تُعيد مقبض النافذة الأمامية النشطة (نافذة Eel/Chrome)
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 6)
    except Exception as e:
        print("minimize_app error:", e)


# دالة مكشوفة لـ JS: تُستدعى من Python عند فصل القلم أثناء نقل الملفات
# (لا نُعرّفها كـ @eel.expose لأنها تُستدعى من Python نحو JS، وليس العكس)


@eel.expose
def close_app():
    os._exit(0)

# Initialization

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
        r = requests.get(f"{url}?rnd={time.time()}", headers=h, timeout=7, verify=False)
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
    download_link = "https://app.altabaay.co/update_Student/Tabaay_Student_Setup.exe"
    
    def _download_and_install():
        try:
            temp_dir = os.getenv('TEMP', os.path.expanduser("~"))
            installer_path = os.path.join(temp_dir, "Tabaay_Student_Setup_New.exe")
            
            if os.path.exists(installer_path):
                try: os.remove(installer_path)
                except: pass
            
            h = HEADERS.copy()
            h["Cache-Control"] = "no-cache, no-store, must-revalidate"
            
            total_size = 0
            try:
                head_r = requests.head(f"{download_link}?rnd={time.time()}", headers=h, timeout=10, allow_redirects=True, verify=False)
                total_size = int(head_r.headers.get('content-length', 0))
            except: pass
            
            with requests.get(f"{download_link}?rnd={time.time()}", headers=h, stream=True, timeout=30, verify=False) as r:
                r.raise_for_status()
                if total_size == 0:
                    total_size = int(r.headers.get('content-length', 0))
                downloaded = 0
                with open(installer_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=1024*1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        try:
                            if total_size > 0:
                                # Fire-and-forget: No trailing () to prevent deadlock!
                                eel.update_app_progress((downloaded / total_size) * 100, None)
                            else:
                                eel.update_app_progress(None, downloaded / (1024 * 1024))
                        except: pass
            
            updater_bat = os.path.join(temp_dir, "updater.bat")
            updater_vbs = os.path.join(temp_dir, "updater.vbs")
            my_pid = os.getpid()
            
            with open(updater_bat, "w", encoding="utf-8") as f:
                f.write("@echo off\n")
                f.write("timeout /t 2 /nobreak > NUL\n")
                f.write(f"taskkill /F /T /PID {my_pid} > NUL 2>&1\n")
                f.write("taskkill /F /IM Tabaay_Student.exe > NUL 2>&1\n")
                f.write(f'"{installer_path}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART\n')

            with open(updater_vbs, "w", encoding="utf-8") as f:
                f.write(f'CreateObject("WScript.Shell").Run """{updater_bat}""", 0, False\n')

            os.startfile(updater_vbs)
            
            try: eel.close_window()()
            except: pass
            os._exit(0)
        except Exception as e:
            print(f"App Update Download Error: {e}")
            try: eel.app_update_failed()()
            except: pass
            
    threading.Thread(target=_download_and_install, daemon=True).start()

@eel.expose
def sync_images_background():
    def _sync():
        try:
            url = "https://app.altabaay.co/update_Student/assets/assets_hash.json"
            h = HEADERS.copy()
            h["Cache-Control"] = "no-cache, no-store, must-revalidate"
            r = requests.get(f"{url}?rnd={time.time()}", headers=h, timeout=10, verify=False)
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
                        img_r = requests.get(img_url, headers=h, timeout=15, verify=False)
                        if img_r.status_code == 200:
                            with open(local_file, "wb") as f:
                                f.write(img_r.content)
                                
                if len(remote_hashes) == 0:
                    print("No remote hashes, skipping cleanup")
                    return

                # تنظيف الصور المحلية التي تم حذفها من السيرفر
                subjects_dir = os.path.join(assets_dir, "subjects")
                if os.path.exists(subjects_dir):
                    for root, dirs, files in os.walk(subjects_dir):
                        for file in files:
                            if file.endswith('.png'):
                                local_path = os.path.join(root, file)
                                rel_path = os.path.relpath(local_path, assets_dir).replace(os.sep, '/')
                                if rel_path not in remote_hashes:
                                    try: os.remove(local_path)
                                    except: pass

        except Exception as e:
            print("Sync images error:", e)

    threading.Thread(target=_sync, daemon=True).start()


if __name__ == '__main__':
    chrome_profile = os.path.join(os.getenv('APPDATA', ''), 'TabaayStudentChromeProfile')
    if getattr(sys, 'frozen', False):
        web_dir = os.path.join(os.path.dirname(sys.executable), "web")
    else:
        web_dir = "web"
    eel.init(web_dir)
    
    flags = [
        '--kiosk', 
        f'--user-data-dir={chrome_profile}', 
        '--disable-extensions', 
        '--disable-translate', 
        '--disable-features=Translate,TranslateUI', 
        '--no-default-browser-check',
        '--disable-infobars',
        '--disable-notifications',
        '--no-first-run',
        '--disable-sync'
    ]
    try:
        eel.start('index.html?v=50', mode='chrome', cmdline_args=flags)
    except EnvironmentError:
        try:
            eel.start('index.html?v=50', mode='edge', cmdline_args=flags)
        except EnvironmentError:
            try:
                eel.start('index.html?v=50', mode='default')
            except Exception as e:
                print("Failed to start browser:", e)
