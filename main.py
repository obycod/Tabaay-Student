import eel
import threading
import requests
import os
import string
import time
import shutil
import concurrent.futures
import base64
import urllib3
import socket
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ===================== الإعدادات =====================
APP_VERSION = "5.1_Apple_Pro_Smooth"
# إرجاع الرابط إلى HTTPS لتجنب حظر Bluehost لمنفذ 80
# الرابط المشفر الأساسي للملازم يقرأ من مجلد update (حيث توجد ملفات alt و files.txt)
_ENC_URL = "aHR0cDovL3BkZC54ZHQubXlibHVlaG9zdC5tZS91cGRhdGU="
BASE_URL_FILES = base64.b64decode(_ENC_URL).decode('utf-8')
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive"
}

STAGES_ORDER = [
    "اول ابتدائي", "ثاني ابتدائي", "ثالث ابتدائي", "رابع ابتدائي", "خامس ابتدائي", "سادس ابتدائي",
    "اول متوسط", "ثاني متوسط", "ثالث متوسط",
    "رابع اعدادي", "رابع علمي", "رابع ادبي",
    "خامس اعدادي", "خامس علمي", "خامس ادبي",
    "سادس اعدادي", "سادس علمي", "سادس ادبي", "سادس صناعي", "مراحل عامة"
]

def get_remote_size(url: str):
    try:
        with requests.get(f"{url}?nocache={time.time()}", headers=HEADERS, stream=True, timeout=20, verify=False) as r:
            if r.status_code == 200: return int(r.headers.get("Content-Length", -1))
    except: pass
    return -1

def find_pens() -> list:
    return [f"{l}:\\EBOOK" for l in string.ascii_uppercase[3:] if os.path.exists(f"{l}:\\EBOOK")]

def eject_pen_safely(drive_letter: str):
    try:
        script = f"$drive = New-Object -ComObject Shell.Application; $drive.Namespace(17).ParseName('{drive_letter}').InvokeVerb('Eject')"
        import subprocess
        subprocess.run(["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command", script], 
                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000), timeout=5)
        return True
    except: return False

class BackendEngine:
    def __init__(self):
        self.pen_drive = None
        self.all_files_data = []
        self.is_fetching = False
        self.running_sync = False
        self.is_online = True
        self.first_run = True

    def fetch_sizes_background(self, files):
        stage_sizes = {f['stage']: 0 for f in files}
        def get_size(f):
            url = f"{BASE_URL_FILES}/{f['act']}"
            sz = get_remote_size(url)
            return f['stage'], sz if sz > 0 else 0

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(get_size, f) for f in files]
            for future in concurrent.futures.as_completed(futures):
                st, sz = future.result()
                stage_sizes[st] += sz
        
        for st, sz in stage_sizes.items():
            if sz > 0:
                mb = sz / (1024 * 1024)
                try: eel.updateStageSize(st, f"{mb:.1f} MB")()
                except: pass

    def start_monitor(self):
        threading.Thread(target=self.monitor_loop, daemon=True).start()

    def monitor_loop(self):
        # تأخير بدء المراقبة 3 ثواني حتى تكتمل الواجهة وتستقبل الأوامر
        time.sleep(3)
        while True:
            try:
                # فحص الإنترنت عبر خوادم عالمية سريعة لتجنب حظر سيرفرك (Bluehost) لكثرة الطلبات
                socket.create_connection(("1.1.1.1", 53), timeout=2)
                online = True
            except:
                online = False
                
            if online != self.is_online:
                self.is_online = online
                try: eel.setNetworkStatus(online)()
                except: pass

            pens = find_pens()
            current_pen = pens[0] if pens else None

            if self.first_run:
                self.first_run = False
                if not current_pen:
                    try: eel.setPenStatus(False, "", 0)()
                    except: pass

            if current_pen and self.pen_drive != current_pen:
                self.pen_drive = current_pen
                try: import winsound; winsound.MessageBeep(winsound.MB_OK)
                except: pass
                
                if not self.all_files_data and not self.is_fetching:
                    self.fetch_data()
                else:
                    self.evaluate_pen()

            elif not current_pen and self.pen_drive is not None:
                self.pen_drive = None
                eel.setPenStatus(False, "", 0)()

            time.sleep(2)

    def fetch_data(self):
        self.is_fetching = True
        try:
            r = requests.get(f"{BASE_URL_FILES}/files.txt?nocache={time.time()}", headers=HEADERS, timeout=30, verify=False)
            r.raise_for_status()
            r.encoding = 'utf-8'
            files = []
            for line in r.text.splitlines():
                if "|" in line:
                    act, disp = line.split("|", 1)
                    act = act.strip()
                    if act.lower().endswith('.alt') and "(موقوف)" not in disp:
                        stage_name = next((s for s in STAGES_ORDER if s in disp), "مراحل عامة")
                        files.append({"act": act, "stage": stage_name})
            self.all_files_data = files
            
            unique_stages = sorted(list(set([f['stage'] for f in files])), key=lambda x: STAGES_ORDER.index(x) if x in STAGES_ORDER else 99)
            ui_data = [{"stage": s} for s in unique_stages]
            eel.buildUI(ui_data)()
            
            self.evaluate_pen()
            
            # تشغيل فحص المساحات في الخلفية حتى لا يتجمد البرنامج
            threading.Thread(target=self.fetch_sizes_background, args=(files,), daemon=True).start()
        except Exception as e:
            print("Error fetching:", e)
            self.pen_drive = None
            # إنهاء حالة التعليق في حال فشل الإنترنت وإرجاع الواجهة للوضع الطبيعي
            try: eel.setPenStatus(False, "", 0)()
            except: pass
        finally:
            self.is_fetching = False

    def evaluate_pen(self):
        if not self.pen_drive: return
        
        try:
            total, used, free = shutil.disk_usage(self.pen_drive)
            gb_free = free / (1024**3)
            storage_text = f"المساحة المتوفرة: {gb_free:.1f} GB"
        except: storage_text = "المساحة المتوفرة: غير معروفة"
        
        eel.setPenStatus(True, storage_text)()

        try: pen_files = [f.lower() for f in os.listdir(self.pen_drive) if f.lower().endswith('.alt') and os.path.getsize(os.path.join(self.pen_drive, f)) > 0]
        except: pen_files = []

        unique_stages = set([f['stage'] for f in self.all_files_data])
        for stage in unique_stages:
            stage_files = [f for f in self.all_files_data if f['stage'] == stage]
            total = len(stage_files)
            missing = sum(1 for f in stage_files if f['act'].lower() not in pen_files)
            
            is_selected = False
            if total > 0 and missing < total: is_selected = True 
            
            on_pen = (total - missing) > 0
            eel.updateCardState(stage, is_selected, missing, total, on_pen)()

engine = BackendEngine()

@eel.expose
def start_sync_python(selected_stages):
    if engine.running_sync or not engine.pen_drive: return
    files_to_sync = [f for f in engine.all_files_data if f['stage'] in selected_stages]
    engine.running_sync = True
    eel.updateProgress(0, "متبقي: --:--")()
    threading.Thread(target=sync_logic, args=(files_to_sync, selected_stages), daemon=True).start()

@eel.expose
def cancel_sync_python():
    engine.running_sync = False

@eel.expose
def refresh_data_python():
    # دالة إضافية يمكن استدعاؤها من الواجهة عند ضغط زر "تحديث" لإنعاش حالة البيانات 
    if not engine.running_sync and not engine.is_fetching:
        threading.Thread(target=engine.fetch_data, daemon=True).start()

def sync_logic(files, selected_stages):
    drive = engine.pen_drive
    deleted_count = 0
    downloaded_count = 0
    try:
        allowed = [f['act'].lower() for f in files]
        to_delete = [f for f in os.listdir(drive) if f.lower().endswith('.alt') and f.lower() not in allowed]
        
        if to_delete:
            deleted_count = len(to_delete)
            total_del = len(to_delete)
            for i, f in enumerate(to_delete):
                if not engine.running_sync: raise Exception("CANCELLED")
                # ربط عملية الحذف بالشريط الرئيسي وشريط المرحلة
                stage = next((item['stage'] for item in engine.all_files_data if item['act'].lower() == f.lower()), "مراحل عامة")
                eel.updateProgress((i / total_del) * 100, f"جاري إزالة المواد المحذوفة... ({i+1}/{total_del})")()
                eel.setCardProgressVisible(stage, True)()
                eel.updateCardProgress(stage, 100)()
                
                fpath = os.path.join(drive, f)
                try:
                    import stat
                    os.chmod(fpath, stat.S_IWRITE)
                    os.remove(fpath)
                except: pass
                
                eel.setCardProgressVisible(stage, False)()
            
            engine.evaluate_pen() # تحديث الواجهة فوراً بعد الحذف

        q = []; total_bytes = 0; copied_bytes = 0
        temp_dir = os.path.join(os.getenv('TEMP', ''), "TabaayFastSync")
        os.makedirs(temp_dir, exist_ok=True)

        total_files = len(files)
        for i, item in enumerate(files):
            if not engine.running_sync: raise Exception("CANCELLED")
            dest = os.path.join(drive, item['act'])
            url = f"{BASE_URL_FILES}/{item['act']}"
            pc_tmp = os.path.join(temp_dir, item['act'])
            
            # تخطي الملفات الموجودة والمكتملة مسبقاً لمنع فحص כל المراحل وتسريع العملية
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                continue

            pct = int((i / total_files) * 100) if total_files > 0 else 0
            eel.updateProgress(pct, "متبقي: --:--")()
            
            size = get_remote_size(url)
            
            if size <= 0: size = 5000000 
            if os.path.exists(dest) and os.path.getsize(dest) == size: continue
            
            ex_size = os.path.getsize(pc_tmp) if os.path.exists(pc_tmp) else 0
            if ex_size > size: ex_size = 0
                
            total_bytes += size
            copied_bytes += ex_size
            q.append((item['act'], dest, url, size, ex_size, item['stage']))

        if total_bytes == 0:
            eel.updateProgress(100, "مكتمل")()
            # إعادة الزر لشكله الطبيعي بدلاً من تغيير نصه
            eel.syncFinished("تحديث")()
            try: 
                import winsound
                winsound.PlaySound("SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC)
            except: pass
            
            report_msg = f"جميع المواد محُدثة مسبقاً!\n\n🗑️ تم حذف: {deleted_count} مواد إضافية." if deleted_count > 0 else "الكل محُدث مسبقاً ولا يوجد جديد!"
            # إرسال إشارة للواجهة لتشغيل نافذة منبثقة مخصصة من تصميمك
            try: eel.triggerCustomAlert(report_msg)()
            except: pass
            engine.evaluate_pen()
            engine.running_sync = False
            return

        sync_start = time.time(); last_u = time.time(); speeds = []; bytes_in_window = 0
        session = requests.Session()
        
        for fname, dest, url, size, ex_size, stage in q:
            if not engine.running_sync: raise Exception("CANCELLED")
            pc_tmp = os.path.join(temp_dir, fname)
            usb_tmp = dest + ".tmp"
            loc = ex_size
            success = False

            eel.setCardProgressVisible(stage, True)()

            for attempt in range(10):
                if not engine.running_sync: raise Exception("CANCELLED")
                head = HEADERS.copy(); mode = "wb"
                if loc > 0: head['Range'] = f"bytes={loc}-"; mode = "ab"
                
                try:
                    with session.get(url, headers=head, stream=True, timeout=15, verify=False) as r:
                        # كسر المحاولات فوراً في حال كان الملف محذوفاً من السيرفر لمنع تجميد البرنامج 30 ثانية لكل ملف
                        if r.status_code == 404:
                            success = False
                            break
                            
                        if r.status_code not in [200, 206]:
                            if loc > 0: copied_bytes -= loc; loc = 0; mode = "wb"; head.pop('Range', None); r = session.get(url, headers=head, stream=True, timeout=15)
                            r.raise_for_status()
                        if r.status_code == 200 and loc > 0: copied_bytes -= loc; loc = 0; mode = "wb"

                        with open(pc_tmp, mode) as f:
                            # تكبير حجم الكتلة إلى 1 ميجابايت لسحب أقصى سرعة من السيرفر بدون توقف
                            for chunk in r.iter_content(1024 * 1024):
                                if not engine.running_sync: raise Exception("CANCELLED")
                                if chunk:
                                    f.write(chunk)
                                    c_len = len(chunk); loc += c_len; copied_bytes += c_len; bytes_in_window += c_len
                                    now = time.time()
                                    
                                    # التحديث كل نصف ثانية (0.5) لعدم إشغال المعالج
                                    if now - last_u > 0.5:
                                        elapsed = now - last_u
                                        if elapsed > 0:
                                            spd = bytes_in_window / elapsed
                                            speeds.append(spd)
                                            if len(speeds) > 10: speeds.pop(0)
                                            avg = sum(speeds) / len(speeds)
                                            rem_t = (total_bytes - copied_bytes) / avg if avg > 0 else 0
                                            speed_mb = avg / (1024 * 1024)
                                            
                                            pct = (copied_bytes / total_bytes) * 100
                                            mins, secs = divmod(int(rem_t), 60)
                                            eel.updateProgress(pct, f"متبقي: {mins:02d}:{secs:02d} | {speed_mb:.1f} MB/s")
                                            
                                            file_pct = (loc / size) * 100 if size > 0 else 0
                                            eel.updateCardProgress(stage, file_pct)
                                            
                                        last_u = time.time()
                                        bytes_in_window = 0
                    success = True
                    break 
                except:
                    time.sleep(3)
                    new_loc = os.path.getsize(pc_tmp) if os.path.exists(pc_tmp) else 0
                    if new_loc > loc: copied_bytes += (new_loc - loc)
                    elif new_loc < loc: copied_bytes -= (loc - new_loc)
                    loc = new_loc

            if success:
                # بمرحلة النقل للفلاش، نصفر شريط البطاقة ونخليه يقرأ سرعة النقل الحقيقية
                eel.updateCardProgress(stage, 0)()
                
                total_usb_size = os.path.getsize(pc_tmp)
                copied_to_usb = 0
                
                with open(pc_tmp, 'rb') as fs, open(usb_tmp, 'wb') as fd:
                    while True:
                        buf = fs.read(1024 * 1024) 
                        if not buf: break
                        if not engine.running_sync: raise Exception("CANCELLED")
                        fd.write(buf)
                        copied_to_usb += len(buf)
                        
                        now = time.time()
                        if now - last_u > 0.5:
                            usb_pct = (copied_to_usb / total_usb_size) * 100 if total_usb_size > 0 else 100
                            eel.updateCardProgress(stage, usb_pct)
                            eel.updateProgress((copied_bytes / total_bytes) * 100, "جاري النقل للقلم...")
                            last_u = time.time()
                            
                if os.path.exists(dest): os.remove(dest)
                os.rename(usb_tmp, dest)
                try: os.remove(pc_tmp)
                except: pass
                downloaded_count += 1
            
            # إخفاء شريط التحميل للمرحلة دائماً سواء نجح أو فشل (لمنع الشاشة من التعليق)
            eel.setCardProgressVisible(stage, False)() 

        eel.updateProgress(100, "مكتمل")()
        # إعادة الزر لشكله الطبيعي بدلاً من تغيير نصه
        eel.syncFinished("تحديث")()
        engine.evaluate_pen()
        try: 
            import winsound
            winsound.PlaySound("SystemNotification", winsound.SND_ALIAS | winsound.SND_ASYNC)
        except: pass
        
        report_msg = f"تم إنجاز المزامنة بنجاح!\n\n📥 تم تحميل: {downloaded_count} مواد جديدة\n🗑️ تم إزالة: {deleted_count} مواد"
        # إرسال إشارة للواجهة لتشغيل نافذة منبثقة مخصصة من تصميمك
        try: eel.triggerCustomAlert(report_msg)()
        except: pass
        
    except Exception as e:
        if str(e) == "CANCELLED":
            eel.updateProgress(0, "تم الإلغاء")()
            eel.syncFinished("تم الإلغاء")()
            try:
                for f in os.listdir(drive):
                    if f.endswith('.tmp'):
                        try: os.remove(os.path.join(drive, f))
                        except: pass
            except: pass
            engine.evaluate_pen()
        else:
            print(f"Error during sync: {e}")
            eel.syncFinished("حدث خطأ!")()
    finally:
        try: eel.resetAllProgress()()
        except: pass
        engine.running_sync = False

@eel.expose
def eject_pen_python():
    if not engine.pen_drive: return
    threading.Thread(target=eject_logic, args=(engine.pen_drive[:2],), daemon=True).start()

def eject_logic(drive_letter):
    eject_pen_safely(drive_letter)
    time.sleep(2)
    eel.ejectFinished()()

def check_for_app_updates():
    # تأخير 3 ثواني لضمان فتح الواجهة بالكامل قبل إرسال أمر إظهار النافذة
    time.sleep(3)
    try:
        url = f"https://app.altabaay.co/update_Student/student_version.txt?nocache={time.time()}"
        r = requests.get(url, headers=HEADERS, timeout=5, verify=False)
        if r.status_code == 200:
            lines = r.text.strip().splitlines()
            if len(lines) >= 2:
                latest_version = lines[0].strip()
                download_link = lines[1].strip()
                # إذا كان إصدار السيرفر يختلف عن إصدار البرنامج الحالي
                if latest_version != APP_VERSION:
                    eel.showUpdateAlert(latest_version, download_link)()
    except:
        pass

if __name__ == '__main__':
    eel.init('web')
    engine.start_monitor()
    threading.Thread(target=check_for_app_updates, daemon=True).start()
    
    # الحصول على أبعاد الشاشة الحقيقية لإجبار المتصفح على الفتح بحجم الشاشة بالكامل
    w, h = 1000, 700
    try:
        import tkinter as tk
        root = tk.Tk()
        w, h = root.winfo_screenwidth(), root.winfo_screenheight()
        root.destroy()
    except: pass

    try:
        eel.start('index.html', size=(w, h), position=(0, 0), mode='edge', cmdline_args=['--start-maximized'])
    except EnvironmentError:
        eel.start('index.html', size=(w, h), position=(0, 0), mode='chrome', cmdline_args=['--start-maximized'])