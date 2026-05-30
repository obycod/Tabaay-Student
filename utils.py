import os
import sys
import time

def get_resource_path(relative_path):
    """حل مسارات ملف الأيقونة والملفات المدمجة عند ضغط البرنامج بـ PyInstaller"""
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def safe_remove_file(filepath, retries=5, delay=0.5):
    """مسح الملفات مع آلية إعادة المحاولة لمنع خطأ الويندوز الشهير WinError 32"""
    for attempt in range(retries):
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            return True
        except OSError:
            time.sleep(delay)
    return False

def safe_rename_file(src, dst, retries=5, delay=0.5):
    """تغيير اسم ملف الـ .tmp المؤقت إلى ملف الملازم النهائي بشكل آمن"""
    for attempt in range(retries):
        try:
            if os.path.exists(dst):
                os.remove(dst)
            os.rename(src, dst)
            return True
        except OSError:
            time.sleep(delay)
    return False