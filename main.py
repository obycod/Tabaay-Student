import json
import sys
import os
import string
import time
import requests
import threading
import shutil
import base64
import urllib3
import urllib.parse
import winsound
import webbrowser
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QProgressBar, 
                             QGraphicsDropShadowEffect, QFrame, QGridLayout, QDialog, QGraphicsBlurEffect, 
                             QListWidget, QListWidgetItem, QAbstractItemView, QSystemTrayIcon, QStyle, QToolButton, QMenu)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer, QRectF
from PyQt6.QtGui import QColor, QFont, QCursor, QPainter, QPen, QAction

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"

try: 
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except: pass

# ===================== إعدادات السيرفر =====================
APP_VERSION = "5.8"
BASE_URL_FILES = "http://pdd.xdt.mybluehost.me/update"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "*/*",
    "Connection": "keep-alive"
}

DISPLAY_STAGES = [
    "اول ابتدائي", "ثاني ابتدائي", "ثالث ابتدائي", "رابع ابتدائي", "خامس ابتدائي", "سادس ابتدائي",
    "اول متوسط", "ثاني متوسط", "ثالث متوسط",
    "رابع علمي", "رابع ادبي",
    "خامس علمي", "خامس ادبي",
    "سادس علمي", "سادس ادبي", "سادس صناعي", "قصص ومغامرات", "مراحل عامة"
]

def play_click_sound():
    try: winsound.PlaySound("SystemDefault", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except: pass

def play_action_sound():
    try: winsound.PlaySound("MenuPopup", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except: pass

def map_and_expand_stages(act, disp_text, raw_stage=None):
    """محرك توزيع المواد المشتركة للعلمي والأدبي (مأخوذ من الوكيل)"""
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
        results.append({"act": act, "stage": "سادس علمي", "is_shared": True})
        results.append({"act": act, "stage": "سادس ادبي", "is_shared": True})
    elif detected_stage == "خامس اعدادي":
        results.append({"act": act, "stage": "خامس علمي", "is_shared": True})
        results.append({"act": act, "stage": "خامس ادبي", "is_shared": True})
    elif detected_stage == "رابع اعدادي":
        results.append({"act": act, "stage": "رابع علمي", "is_shared": True})
        results.append({"act": act, "stage": "رابع ادبي", "is_shared": True})
    else:
        results.append({"act": act, "stage": detected_stage, "is_shared": False})
        
    return results

def find_pens() -> list:
    pens = []
    try:
        import ctypes
        for l in string.ascii_uppercase[3:]:
            drive = f"{l}:\\"
            if os.path.exists(drive):
                if ctypes.windll.kernel32.GetDriveTypeW(drive) == 2:
                    pens.append(drive)
    except: pass
    return pens

def get_remote_size(url):
    try:
        with requests.head(url, headers=HEADERS, timeout=10, verify=False) as r:
            if r.status_code == 200: return int(r.headers.get('content-length', -1))
    except: pass
    try:
        with requests.get(url, headers=HEADERS, stream=True, timeout=10, verify=False) as r:
            if r.status_code == 200: return int(r.headers.get('content-length', -1))
    except: pass
    return 0

# ================= دائرة المساحة الاحترافية =================
class CircularProgress(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(50, 50)
        self.value = 0
        self.bg_color = "#E2E8F0"
        self.text_color = "#1D1D1F"

    def setValue(self, val):
        self.value = val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(5, 5, self.width()-10, self.height()-10)
        
        painter.setPen(QPen(QColor(self.bg_color), 4))
        painter.drawArc(rect, 0, 360 * 16)
        
        color = "#007AFF" if self.value < 85 else "#FF3B30"
        painter.setPen(QPen(QColor(color), 4))
        painter.drawArc(rect, 90 * 16, int(-self.value / 100 * 360 * 16))
        
        painter.setPen(QColor(self.text_color))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{int(self.value)}%")

# ================= بطاقة المكتبة =================
class LibraryCard(QFrame):
    state_changed = pyqtSignal()

    def __init__(self, stage_name, total_files):
        super().__init__()
        self.stage_name = stage_name
        self.total_files = total_files
        self.stage_size_mb = 0
        self.missing_count = 0
        self.status = "NOT_SYNCED" 
        self.is_checked = False  
        
        self.setFixedSize(220, 150)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        self.shadow_effect = QGraphicsDropShadowEffect(self)
        self.shadow_effect.setBlurRadius(15)
        self.shadow_effect.setColor(QColor(0, 0, 0, 20))
        self.shadow_effect.setOffset(0, 4)
        self.setGraphicsEffect(self.shadow_effect)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 10, 15, 10)
        self.layout.setSpacing(4)

        check_lay = QHBoxLayout()
        self.check_box = QLabel("")
        self.check_box.setFixedSize(22, 22)
        self.check_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.check_box.setStyleSheet("border: 2px solid #E2E8F0; border-radius: 11px; background-color: rgba(255, 255, 255, 0.5);")
        
        check_lay.addWidget(self.check_box)
        check_lay.addStretch()
        self.layout.addLayout(check_lay)

        self.lbl_title = QLabel(stage_name)
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent; border: none; color: #1D1D1F;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.lbl_title)

        self.lbl_info = QLabel(f"الحجم: جاري الحساب... ({total_files} ملف)")
        self.lbl_info.setStyleSheet("font-size: 12px; color: #86868B; background: transparent; border: none;")
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.lbl_info)

        self.lbl_status = QLabel("بانتظار الفحص...")
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; background: transparent; border: none; color: #86868B;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.lbl_status)

        # إضافة شريط التحميل الحيوي الخاص بالبطاقة
        self.card_loading_bar = QProgressBar()
        self.card_loading_bar.setRange(0, 0) # لجعله متذبذباً وحيوياً
        self.card_loading_bar.setFixedHeight(6)
        self.card_loading_bar.setTextVisible(False)
        self.card_loading_bar.setStyleSheet("""
            QProgressBar { background-color: #E2E8F0; border-radius: 3px; border: none; }
            QProgressBar::chunk { background-color: #007AFF; border-radius: 3px; }
        """)
        self.card_loading_bar.hide()
        self.layout.addWidget(self.card_loading_bar)

        self.update_ui()

    def set_syncing_state(self, is_syncing):
        # تفعيل شريط التحميل وإخفاء النص إذا كانت البطاقة قيد التحديث
        if is_syncing and self.is_checked:
            self.lbl_status.hide()
            self.card_loading_bar.show()
        else:
            self.card_loading_bar.hide()
            self.lbl_status.show()

    def set_status(self, missing_count, total_files, stage_size_mb):
        self.total_files = total_files
        self.missing_count = missing_count
        self.stage_size_mb = stage_size_mb

        # التعديل الذكي لعرض المساحة: (MB للمساحات الصغيرة، و GB للمساحات الكبيرة)
        if stage_size_mb == 0:
            size_str = "-- MB"
        elif stage_size_mb < 1024:
            size_str = f"{stage_size_mb:.1f} MB"
        else:
            size_gb = stage_size_mb / 1024
            size_str = f"{size_gb:.2f} GB"

        # عرض عدد الملازم بالشكل المطلوب
        self.lbl_info.setText(f"الحجم: {size_str} \n(عدد الملازم: {total_files})")
        
        if self.total_files == 0:
            self.status = "SERVER_EMPTY"
            self.set_checked(False)
            self.setEnabled(False)
        elif missing_count == 0 and self.total_files > 0:
            self.status = "LOADED"
            self.setEnabled(True)
        elif missing_count > 0 and missing_count < self.total_files:
            self.status = "UPDATE"
            self.setEnabled(True)
        else:
            self.status = "NOT_SYNCED"
            self.setEnabled(True)

        self.update_ui()

    def set_checked(self, state):
        self.is_checked = state
        self.update_ui()

    def mousePressEvent(self, event):
        play_click_sound()
        # حماية إضافية: منع النقر تماماً إذا كان البرنامج الرئيسي في حالة مزامنة
        main_app = self.window()
        if hasattr(main_app, 'is_syncing') and main_app.is_syncing:
            return
            
        if self.isEnabled():
            self.is_checked = not self.is_checked
            self.update_ui()
            self.state_changed.emit()

    def apply_theme(self, theme_name):
        self.current_theme = theme_name
        self.update_ui()

    def update_ui(self):
        t_name = getattr(self, 'current_theme', 'light')
        t_bg = "rgba(255, 255, 255, 0.7)"
        t_border = "#E2E8F0"
        t_text = "#1D1D1F"
        t_check_bg = "rgba(255, 255, 255, 0.5)"
        t_primary = "#007AFF"
        t_success = "#34C759"
        
        if t_name == "dark":
            t_bg = "rgba(30, 30, 30, 0.7)"
            t_border = "#333333"
            t_text = "#F7FAFC"
            t_check_bg = "rgba(255, 255, 255, 0.1)"
            t_primary = "#4CAF50"
            t_success = "#4CAF50"
        elif t_name == "ocean":
            t_bg = "rgba(15, 32, 55, 0.7)"
            t_border = "#1E3A8A"
            t_text = "#E2E8F0"
            t_check_bg = "rgba(255, 255, 255, 0.1)"
            t_primary = "#3B82F6"
            t_success = "#10B981"

        self.lbl_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {t_text};")
        
        if self.is_checked:
            self.check_box.setText("✔")
            self.check_box.setStyleSheet(f"background-color: {t_primary}; color: white; border-radius: 11px; font-weight: bold; font-size: 14px; border: none;")
        else:
            self.check_box.setText("")
            self.check_box.setStyleSheet(f"background-color: {t_check_bg}; border: 2px solid {t_border}; border-radius: 11px;")

        if self.status == "LOADED" and not self.is_checked:
            bg = "rgba(255, 60, 60, 0.15)"; border = "#FF3B30"
            self.check_box.setStyleSheet(f"background-color: {t_check_bg}; border: 2px solid #FF3B30; border-radius: 11px;") 
            self.lbl_status.setText("سوف يتم حذف المرحلة ⚠️")
            self.lbl_status.setStyleSheet("color: #FF3B30; font-weight: bold; font-size: 12px; border: none;")
        elif self.is_checked:
            if self.status == "LOADED":
                bg = "rgba(50, 200, 90, 0.15)"; border = t_success
                self.lbl_status.setText(f"مكتملة في القلم")
                self.lbl_status.setStyleSheet(f"color: {t_success}; font-weight: bold; font-size: 12px; border: none;")
            elif self.status == "UPDATE":
                bg = "rgba(255, 150, 0, 0.15)"; border = "#FF9500"
                self.lbl_status.setText(f"ينقصها {self.missing_count} ملف")
                self.lbl_status.setStyleSheet("color: #FF9500; font-weight: bold; font-size: 12px; border: none;")
            else:
                bg = "rgba(0, 120, 255, 0.15)"; border = t_primary
                self.lbl_status.setText(f"جاهزة للتحميل ({self.stage_size_mb:.1f} MB)")
                self.lbl_status.setStyleSheet(f"color: {t_primary}; font-weight: bold; font-size: 12px; border: none;")
        else:
            bg = t_bg
            border = t_border
            if self.status == "UPDATE":
                self.lbl_status.setText("يتوفر تحديث")
                self.lbl_status.setStyleSheet("color: #FF9500; font-weight: bold; font-size: 12px; border: none;")
            else:
                self.lbl_status.setText("جاهزة للتثبيت")
                self.lbl_status.setStyleSheet("color: #4A5568; font-weight: bold; font-size: 12px; border: none;")

        self.setStyleSheet(f"LibraryCard {{ background-color: {bg}; border-radius: 20px; border: 1.5px solid {border}; }}")

    def enterEvent(self, event):
        if hasattr(self, 'shadow_effect'):
            self.shadow_effect.setBlurRadius(25)
            self.shadow_effect.setOffset(0, 8)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if hasattr(self, 'shadow_effect'):
            self.shadow_effect.setBlurRadius(15)
            self.shadow_effect.setOffset(0, 4)
        super().leaveEvent(event)

# ================= إشارات النظام =================
class SignalEmitter(QObject):
    data_ready = pyqtSignal(list)
    sizes_ready = pyqtSignal(dict)
    progress = pyqtSignal(int, str, str, str) 
    sync_done = pyqtSignal(bool, str) 
    net_error = pyqtSignal(bool) # إشارة التحكم بشاشة انقطاع الإنترنت العائمة
    current_stage = pyqtSignal(str) # <-- إضافة هذه الإشارة لمعرفة المرحلة الحالية
    update_available = pyqtSignal(str, str) # version, url

# ================= نافذة تأكيد الحذف النظيفة =================
class ConfirmDialog(QDialog):
    def __init__(self, parent, title, message, stages_to_delete):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(450, 260)
        self.result = False

        container = QFrame(self)
        container.setStyleSheet("background-color: rgba(255, 255, 255, 0.95); border-radius: 20px;")
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20); shadow.setColor(QColor(0,0,0,40)); shadow.setOffset(0,4)
        container.setGraphicsEffect(shadow)
        
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.addWidget(container)

        lay = QVBoxLayout(container)
        lay.setContentsMargins(25, 25, 25, 25)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1D1D1F;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        stages_text = " / ".join(stages_to_delete)
        lbl_msg = QLabel(f"{message}\n\n[ {stages_text} ]\n\nهل ترغب بحذفها؟")
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet("font-size: 15px; color: #4A5568; font-weight: bold;")
        lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_lay = QHBoxLayout()
        btn_yes = QPushButton("استمرار")
        btn_yes.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_yes.setFixedHeight(45)
        btn_yes.setStyleSheet("QPushButton { background-color: #FF3B30; color: white; font-weight: bold; font-size: 14px; border-radius: 12px; border: none; } QPushButton:hover { background-color: #E03126; }")
        btn_yes.clicked.connect(lambda: play_click_sound())
        btn_yes.clicked.connect(self.accept_action)

        btn_no = QPushButton("تراجع")
        btn_no.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_no.setFixedHeight(45)
        btn_no.setStyleSheet("QPushButton { background-color: rgba(0,0,0,0.05); color: #1D1D1F; font-weight: bold; font-size: 14px; border-radius: 12px; border: none; } QPushButton:hover { background-color: rgba(0,0,0,0.1); }")
        btn_no.clicked.connect(lambda: play_click_sound())
        btn_no.clicked.connect(self.reject_action)

        btn_lay.addWidget(btn_no)
        btn_lay.addWidget(btn_yes)

        lay.addWidget(lbl_title)
        lay.addWidget(lbl_msg)
        lay.addLayout(btn_lay)

    def accept_action(self):
        self.result = True
        self.accept()

    def reject_action(self):
        self.result = False
        self.reject()


# ================= نافذة التنبيه بالأخطاء (فصل القلم وما شابه) =================
class ErrorDialog(QDialog):
    def __init__(self, parent, title, message):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(400, 240)
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        try: winsound.MessageBeep(winsound.MB_ICONHAND) 
        except: pass

        container = QFrame(self)
        container.setStyleSheet("""
            QFrame#err_container {
                background-color: rgba(255, 255, 255, 0.95); 
                border-radius: 16px; 
                border: 1px solid rgba(0,0,0,0.1);
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        container.setObjectName("err_container")
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(35)
        shadow.setColor(QColor(0, 0, 0, 45))
        shadow.setOffset(0, 8)
        container.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.addWidget(container)

        lay = QVBoxLayout(container)
        lay.setContentsMargins(30, 25, 30, 25)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(15)

        lbl_icon = QLabel("✕")
        lbl_icon.setFixedSize(56, 56)
        lbl_icon.setStyleSheet("background-color: #FEE2E2; color: #FF3B30; font-size: 30px; font-weight: bold; border-radius: 28px;")
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_lay = QHBoxLayout()
        icon_lay.addWidget(lbl_icon, alignment=Qt.AlignmentFlag.AlignCenter)

        lbl_title = QLabel(title)
        lbl_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #1D1D1F;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_msg = QLabel(message)
        lbl_msg.setStyleSheet("font-size: 14px; color: #4A5568; font-weight: bold;")
        lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_msg.setWordWrap(True)

        btn_ok = QPushButton("موافق")
        btn_ok.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_ok.setFixedHeight(44)
        btn_ok.setStyleSheet("QPushButton { background-color: #FF3B30; color: white; font-weight: bold; font-size: 15px; border-radius: 8px; border: none; margin-top: 10px; } QPushButton:hover { background-color: #E03126; }")
        btn_ok.clicked.connect(lambda: play_click_sound())
        btn_ok.clicked.connect(self.accept)

        lay.addLayout(icon_lay)
        lay.addWidget(lbl_title)
        lay.addWidget(lbl_msg)
        lay.addWidget(btn_ok)


# ================= نافذة التنبيه بنجاح التحديث (التصميم الاحترافي النهائي) =================
from PyQt6.QtWidgets import QListWidget, QListWidgetItem, QAbstractItemView

class SuccessDialog(QDialog):
    def __init__(self, parent, stages_list):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setModal(True)
        self.resize(440, 420)
        
        self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        try:
            winsound.MessageBeep(winsound.MB_ICONINFORMATION) 
        except: 
            pass

        container = QFrame(self)
        container.setStyleSheet("""
            QFrame#main_container {
                background-color: rgba(255, 255, 255, 0.95); 
                border-radius: 16px; 
                border: 1px solid rgba(0,0,0,0.1);
            }
            QLabel {
                border: none;
                background: transparent;
            }
        """)
        container.setObjectName("main_container")
        
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(35)
        shadow.setColor(QColor(0, 0, 0, 45))
        shadow.setOffset(0, 8)
        container.setGraphicsEffect(shadow)

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.addWidget(container)

        lay = QVBoxLayout(container)
        lay.setContentsMargins(30, 25, 30, 25)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.setSpacing(12)

        lbl_icon = QLabel("✓")
        lbl_icon.setFixedSize(56, 56)
        lbl_icon.setStyleSheet("""
            background-color: #E6F4EA; 
            color: #34C759; 
            font-size: 30px; 
            font-weight: bold; 
            border-radius: 28px;
        """)
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        icon_lay = QHBoxLayout()
        icon_lay.addWidget(lbl_icon, alignment=Qt.AlignmentFlag.AlignCenter)

        lbl_title = QLabel("اكتملت العملية بنجاح")
        lbl_title.setStyleSheet("font-size: 22px; font-weight: bold; color: #1D1D1F;")
        lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        lbl_msg = QLabel("تم تحديث القلم الذكي، المراحل المتوفرة حالياً:")
        lbl_msg.setStyleSheet("font-size: 14px; color: #4A5568;")
        lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)

        list_widget = QListWidget()
        list_widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        list_widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        list_widget.setStyleSheet("""
            QListWidget {
                background-color: rgba(248, 250, 252, 0.5); 
                border: 1px solid rgba(0,0,0,0.05);
                border-radius: 12px;
                padding: 10px;
                outline: none;
            }
            QListWidget::item {
                color: #007AFF;
                font-size: 14px;
                font-weight: bold;
                padding: 8px;
            }
            QScrollBar:vertical {
                border: none;
                background: transparent;
                width: 6px;
                margin: 4px;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1;
                border-radius: 3px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94A3B8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)

        if stages_list:
            for stage in stages_list:
                item = QListWidgetItem(f"•  {stage}")
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                list_widget.addItem(item)
        else:
            item = QListWidgetItem("•  لا توجد مراحل مكتملة حالياً")
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            item.setForeground(QColor("#94A3B8"))
            list_widget.addItem(item)

        self.btn_ok = QPushButton("موافق")
        self.btn_ok.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_ok.setFixedHeight(44)
        self.btn_ok.setStyleSheet("""
            QPushButton { 
                background-color: #34C759; 
                color: white; 
                font-weight: bold; 
                font-size: 15px; 
                border-radius: 8px; 
                border: none; 
                margin-top: 6px;
            } 
            QPushButton:hover { 
                background-color: #2EAB4E; 
            }
        """)
        self.btn_ok.clicked.connect(lambda: play_click_sound())
        self.btn_ok.clicked.connect(self.accept)

        lay.addLayout(icon_lay)
        lay.addWidget(lbl_title)
        lay.addWidget(lbl_msg)
        lay.addWidget(list_widget)
        lay.addWidget(self.btn_ok)
        
# ================= الواجهة والمحرك =================
class ObyLibraryApp(QMainWindow):
    def __init__(self):
        super().__init__()
        QApplication.instance().setLayoutDirection(Qt.LayoutDirection.RightToLeft)

        self.setMinimumSize(1100, 750)
        self.showMaximized()
        self.setFont(QFont("Segoe UI", 10))

        self.emitter = SignalEmitter()
        self.emitter.data_ready.connect(self.build_grid)
        self.emitter.sizes_ready.connect(self.on_sizes_ready)
        self.emitter.progress.connect(self.update_progress)
        self.emitter.sync_done.connect(self.on_sync_done)
        self.emitter.net_error.connect(self.toggle_net_overlay)
        self.emitter.current_stage.connect(self.set_active_stage_card)
        self.emitter.update_available.connect(self.show_update_dialog)

        self.all_server_files = []
        self.file_sizes_map = {} 
        self.stage_cards = []
        self.pen_drive = None
        self.is_fetching = False
        self.is_syncing = False
        self.current_theme = "light"

        # إعداد أيقونة شريط المهام (لإشعارات الويندوز)
        self.tray_icon = QSystemTrayIcon(self)
        icon = self.windowIcon() if not self.windowIcon().isNull() else self.style().standardIcon(QStyle.StandardPixmap.SP_DriveFDIcon)
        self.tray_icon.setIcon(icon)
        self.tray_icon.show()

        self.setup_ui()
        threading.Thread(target=self.fetch_manifest, daemon=True).start()
        self.check_for_updates()
        self.monitor_pen()

    def setup_ui(self):
        bg = QWidget(self)
        bg.setStyleSheet("QWidget#MainBG { background-color: #F7FAFC; }")
        bg.setObjectName("MainBG")
        self.setCentralWidget(bg)

        main_lay = QVBoxLayout(bg)
        main_lay.setContentsMargins(30, 20, 30, 20)
        main_lay.setSpacing(15)

        self.header_frame = QFrame()
        self.header_frame.setStyleSheet("background: transparent;")
        header_lay = QHBoxLayout(self.header_frame)
        header_lay.setContentsMargins(0, 0, 0, 0)
        header_lay.setAlignment(Qt.AlignmentFlag.AlignVCenter)

        # 1. Right Side (Title & Subtitle)
        title_container = QWidget()
        title_lay = QVBoxLayout(title_container)
        title_lay.setContentsMargins(0, 0, 0, 0)
        title_lay.setSpacing(6)

        self.lbl_title = QLabel("نظام تحديث القلم الناطق - الذكي")
        self.lbl_title.setStyleSheet("font-size: 26px; font-weight: bold; color: #1D1D1F;")

        self.subtitle = QLabel("📌 حدد المراحل التي ترغب بتثبيتها أو تحديثها")
        self.subtitle.setStyleSheet("background-color: transparent; color: #007AFF; font-weight: bold; font-size: 15px;")
        
        title_lay.addWidget(self.lbl_title)
        title_lay.addWidget(self.subtitle)

        # 2. Left Side Controls
        self.btn_theme = QToolButton()
        self.btn_theme.setText("🎨")
        self.btn_theme.setFixedSize(40, 40)
        self.btn_theme.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_theme.setStyleSheet("QToolButton { background-color: rgba(255,255,255,0.8); border-radius: 20px; font-size: 20px; border: 1.5px solid #E2E8F0; } QToolButton::menu-indicator { image: none; }")
        
        theme_menu = QMenu(self)
        action_light = QAction("☀️ الوضع الفاتح", self)
        action_light.triggered.connect(lambda: self.apply_theme("light"))
        action_dark = QAction("🌙 الوضع الداكن", self)
        action_dark.triggered.connect(lambda: self.apply_theme("dark"))
        action_ocean = QAction("💧 الوضع الأزرق", self)
        action_ocean.triggered.connect(lambda: self.apply_theme("ocean"))
        
        theme_menu.addAction(action_light)
        theme_menu.addAction(action_dark)
        theme_menu.addAction(action_ocean)
        self.btn_theme.setMenu(theme_menu)
        self.btn_theme.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)

        self.pill_status = QLabel("بانتظار القلم...")
        self.pill_status.setFixedSize(140, 36)
        self.pill_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pill_status.setStyleSheet("background-color: rgba(255, 59, 48, 0.1); color: #FF3B30; border-radius: 18px; font-weight: bold; border: 1.5px solid rgba(255, 59, 48, 0.3);")

        storage_container = QWidget()
        storage_lay = QHBoxLayout(storage_container)
        storage_lay.setContentsMargins(0, 0, 0, 0)
        storage_lay.setSpacing(12)
        
        self.lbl_storage_text = QLabel("المساحة المتاحة: —\nالحجم الكلي: —")
        self.lbl_storage_text.setStyleSheet("font-size: 13px; font-weight: bold; color: #4A5568;")
        self.lbl_storage_text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.circular_progress = CircularProgress()
        
        storage_lay.addWidget(self.lbl_storage_text)
        storage_lay.addWidget(self.circular_progress)

        # Assemble Header (Right to Left due to RTL)
        header_lay.addWidget(title_container)
        header_lay.addStretch()
        header_lay.addWidget(self.btn_theme)
        header_lay.addSpacing(20)
        header_lay.addWidget(self.pill_status)
        header_lay.addSpacing(30)
        header_lay.addWidget(storage_container)

        main_lay.addWidget(self.header_frame)
        main_lay.addSpacing(15)

        self.grid_container = QFrame()
        self.grid_container.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(self.grid_container)
        self.grid.setSpacing(20) 
        self.grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_lay.addWidget(self.grid_container, stretch=1)

        prog_container = QFrame()
        prog_container.setStyleSheet("background-color: transparent; border: none;")
        prog_container.setContentsMargins(10, 5, 10, 5)
        prog_vlay = QVBoxLayout(prog_container)
        prog_vlay.setSpacing(8)
        
        self.bar = QProgressBar()
        self.bar.setFixedHeight(8)
        self.bar.setTextVisible(False)
        self.bar.setStyleSheet("QProgressBar { background-color: #E2E8F0; border-radius: 4px; border: none; } QProgressBar::chunk { background-color: #007AFF; border-radius: 4px; }")
        prog_vlay.addWidget(self.bar)

        info_lay = QHBoxLayout()
        info_lay.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_pct = QLabel("0%")
        self.lbl_size = QLabel("0.0 / 0.0 MB")
        self.lbl_speed = QLabel("السرعة: 0.0 MB/s")
        self.lbl_time = QLabel("الوقت المتبقي: --:--:--")
        
        label_style = "font-weight: bold; font-size: 13px; color: #4A5568; background: transparent; border: none;"
        for lbl in [self.lbl_time, self.lbl_speed, self.lbl_size]:
            lbl.setStyleSheet(label_style)
        self.lbl_pct.setStyleSheet("font-weight: bold; font-size: 14px; color: #007AFF; background: transparent; border: none;")
        
        info_lay.addWidget(self.lbl_pct)
        info_lay.addStretch()
        info_lay.addWidget(self.lbl_size)
        info_lay.addStretch()
        info_lay.addWidget(self.lbl_speed)
        info_lay.addStretch()
        info_lay.addWidget(self.lbl_time)
        
        prog_vlay.addLayout(info_lay)
        main_lay.addWidget(prog_container)
        main_lay.addSpacing(5)

        btn_lay = QHBoxLayout()
        self.btn_eject = QPushButton("⏏ إخراج القلم بأمان")
        self.btn_eject.setFixedSize(180, 50)
        self.btn_eject.setStyleSheet("QPushButton { background: rgba(255,255,255,0.8); border: 1.5px solid #E2E8F0; color: #1D1D1F; font-weight: bold; border-radius: 14px; font-size: 14px; } QPushButton:hover { background-color: #FFFFFF; }")
        self.btn_eject.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_eject.clicked.connect(lambda: play_click_sound())
        self.btn_eject.clicked.connect(self.eject_pen)

        self.btn_sync = QPushButton("بدء تحديث القلم")
        self.btn_sync.setFixedHeight(50)
        self.btn_sync.setStyleSheet("QPushButton { background: #007AFF; color: white; font-weight: bold; font-size: 16px; border-radius: 14px; border: none; } QPushButton:disabled { background: #CBD5E1; color: #F7FAFC; } QPushButton:hover { background-color: #0056B3; }")
        self.btn_sync.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_sync.clicked.connect(lambda: play_action_sound())
        self.btn_sync.clicked.connect(self.start_sync)

        btn_lay.addWidget(self.btn_eject)
        btn_lay.addWidget(self.btn_sync, stretch=1)
        main_lay.addLayout(btn_lay)

        # شاشة التنبيه العائمة لقطع الاتصال بالإنترنت في منتصف البرنامج
        self.net_overlay = QFrame(self.centralWidget())
        self.net_overlay.setObjectName("NetOverlay")
        self.net_overlay.setStyleSheet("""
            QFrame#NetOverlay {
                background-color: rgba(255, 255, 255, 0.85);
                border: 2px solid #FF3B30;
                border-radius: 20px;
            }
        """)
        self.net_overlay.setFixedSize(450, 240)
        
        shadow_net = QGraphicsDropShadowEffect(self)
        shadow_net.setBlurRadius(25)
        shadow_net.setColor(QColor(0, 0, 0, 50))
        shadow_net.setOffset(0, 6)
        self.net_overlay.setGraphicsEffect(shadow_net)
        
        overlay_lay = QVBoxLayout(self.net_overlay)
        overlay_lay.setContentsMargins(25, 25, 25, 25)
        overlay_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.lbl_net_err_title = QLabel("⚠️ انقطع الاتصال بالإنترنت")
        self.lbl_net_err_title.setStyleSheet("font-size: 20px; font-weight: bold; color: #FF3B30; background: transparent; border: none;")
        self.lbl_net_err_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # إضافة شريط التحميل المتذبذب (Indeterminate) للحيوية
        self.net_loading_bar = QProgressBar()
        self.net_loading_bar.setRange(0, 0) # نطاق صفر يجعله يتحرك يميناً ويساراً باستمرار
        self.net_loading_bar.setFixedHeight(8)
        self.net_loading_bar.setTextVisible(False)
        self.net_loading_bar.setStyleSheet("""
            QProgressBar { background-color: #FEE2E2; border-radius: 4px; border: none; }
            QProgressBar::chunk { background-color: #FF3B30; border-radius: 4px; }
        """)
        
        self.lbl_net_err_msg = QLabel("جاري محاولة إعادة الاتصال تلقائياً...\nيرجى عدم فصل القلم أو إغلاق البرنامج.")
        self.lbl_net_err_msg.setWordWrap(True)
        self.lbl_net_err_msg.setStyleSheet("font-size: 14px; color: #4A5568; font-weight: bold; background: transparent; border: none;")
        self.lbl_net_err_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        overlay_lay.addWidget(self.lbl_net_err_title)
        overlay_lay.addSpacing(15)
        overlay_lay.addWidget(self.net_loading_bar)
        overlay_lay.addSpacing(15)
        overlay_lay.addWidget(self.lbl_net_err_msg)

        self.net_overlay.hide()

    def check_for_updates(self):
        def worker():
            try:
                url = f"http://pdd.xdt.mybluehost.me/update_Student/student_version.txt?nocache={time.time()}"
                r = requests.get(url, headers=HEADERS, timeout=5)
                if r.status_code == 200:
                    lines = r.text.splitlines()
                    if lines:
                        latest_version_str = lines[0].strip()
                        try:
                            v_local = float(APP_VERSION)
                            v_remote = float(latest_version_str)
                            if v_remote > v_local:
                                download_url = lines[1].strip() if len(lines) > 1 else ""
                                self.emitter.update_available.emit(latest_version_str, download_url)
                        except ValueError:
                            pass
            except:
                pass
        threading.Thread(target=worker, daemon=True).start()

    def show_update_dialog(self, version, url):
        dialog = ConfirmDialog(self, "تحديث جديد متوفر", "يتوفر إصدار أحدث من البرنامج", [f"الإصدار الجديد: {version}"])
        for btn in dialog.findChildren(QPushButton):
            if btn.text() == "استمرار": btn.setText("تحميل الآن")
            if btn.text() == "تراجع": btn.setText("لاحقاً")
        dialog.exec()
        if dialog.result and url:
            import webbrowser
            webbrowser.open(url)

    def apply_theme(self, theme_name):
        self.current_theme = theme_name
        
        themes = {
            "light": {
                "bg": "#F7FAFC",
                "text": "#1D1D1F",
                "sub_text": "#4A5568",
                "btn_bg": "rgba(255,255,255,0.8)",
                "btn_border": "#E2E8F0",
                "circ_bg": "#E2E8F0",
                "sync_btn": "#007AFF",
                "sync_btn_hover": "#0056B3",
                "pill_red_bg": "rgba(255, 59, 48, 0.1)",
                "pill_red_text": "#FF3B30",
                "pill_green_bg": "rgba(52, 199, 89, 0.1)",
                "pill_green_text": "#34C759",
                "prog_bg": "#E2E8F0",
                "prog_chunk": "#007AFF",
                "subtitle_bg": "rgba(0, 122, 255, 0.08)",
                "subtitle_text": "#007AFF"
            },
            "dark": {
                "bg": "#121212",
                "text": "#F7FAFC",
                "sub_text": "#A0AEC0",
                "btn_bg": "rgba(30,30,30,0.8)",
                "btn_border": "#333333",
                "circ_bg": "#333333",
                "sync_btn": "#4CAF50",
                "sync_btn_hover": "#45A049",
                "pill_red_bg": "rgba(255, 82, 82, 0.15)",
                "pill_red_text": "#FF5252",
                "pill_green_bg": "rgba(76, 175, 80, 0.15)",
                "pill_green_text": "#4CAF50",
                "prog_bg": "#333333",
                "prog_chunk": "#4CAF50",
                "subtitle_bg": "rgba(76, 175, 80, 0.15)",
                "subtitle_text": "#4CAF50"
            },
            "ocean": {
                "bg": "#0B192C",
                "text": "#E2E8F0",
                "sub_text": "#94A3B8",
                "btn_bg": "rgba(15, 32, 55, 0.8)",
                "btn_border": "#1E3A8A",
                "circ_bg": "#1E3A8A",
                "sync_btn": "#3B82F6",
                "sync_btn_hover": "#2563EB",
                "pill_red_bg": "rgba(239, 68, 68, 0.15)",
                "pill_red_text": "#EF4444",
                "pill_green_bg": "rgba(16, 185, 129, 0.15)",
                "pill_green_text": "#10B981",
                "prog_bg": "#1E3A8A",
                "prog_chunk": "#3B82F6",
                "subtitle_bg": "rgba(59, 130, 246, 0.15)",
                "subtitle_text": "#3B82F6"
            }
        }
        
        t = themes.get(theme_name, themes["light"])
        
        self.centralWidget().setStyleSheet(f"QWidget#MainBG {{ background-color: {t['bg']}; }}")
        
        if hasattr(self, 'lbl_title'):
            self.lbl_title.setStyleSheet(f"font-size: 28px; font-weight: bold; color: {t['text']};")
            
        if hasattr(self, 'subtitle'):
            self.subtitle.setText("📌 حدد المراحل التي ترغب بتثبيتها أو تحديثها")
            self.subtitle.setStyleSheet(f"background-color: transparent; color: {t['subtitle_text']}; font-weight: bold; font-size: 14px;")
            
        if hasattr(self, 'pill_status'):
            if "متصل" in self.pill_status.text() and "غير" not in self.pill_status.text():
                self.pill_status.setStyleSheet(f"background-color: {t['pill_green_bg']}; color: {t['pill_green_text']}; border-radius: 17px; font-weight: bold; border: 1.5px solid {t['pill_green_bg']};")
            elif "إخراج" in self.pill_status.text() or "آلياً" in self.pill_status.text():
                self.pill_status.setStyleSheet("background-color: rgba(255, 149, 0, 0.1); color: #FF9500; border-radius: 17px; font-weight: bold; border: 1.5px solid rgba(255, 149, 0, 0.3);")
            else:
                self.pill_status.setStyleSheet(f"background-color: {t['pill_red_bg']}; color: {t['pill_red_text']}; border-radius: 17px; font-weight: bold; border: 1.5px solid {t['pill_red_bg']};")
            
        if hasattr(self, 'lbl_storage_text'):
            self.lbl_storage_text.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {t['sub_text']};")
            
        if hasattr(self, 'circular_progress'):
            self.circular_progress.bg_color = t['circ_bg']
            self.circular_progress.text_color = t['text']
            self.circular_progress.update()
            
        if hasattr(self, 'lbl_time'):
            for lbl in [self.lbl_time, self.lbl_speed, self.lbl_size]:
                lbl.setStyleSheet(f"font-weight: bold; font-size: 13px; color: {t['sub_text']}; background: transparent; border: none;")
                
        if hasattr(self, 'bar'):
            self.bar.setStyleSheet(f"QProgressBar {{ background-color: {t['prog_bg']}; border-radius: 4px; border: none; }} QProgressBar::chunk {{ background-color: {t['prog_chunk']}; border-radius: 4px; }}")
            
        if hasattr(self, 'btn_eject'):
            self.btn_eject.setStyleSheet(f"QPushButton {{ background: {t['btn_bg']}; border: 1.5px solid {t['btn_border']}; color: {t['text']}; font-weight: bold; border-radius: 14px; font-size: 14px; }} QPushButton:hover {{ background-color: rgba(255,255,255,0.1); }}")
            
        if hasattr(self, 'btn_sync'):
            self.btn_sync.setStyleSheet(f"QPushButton {{ background: {t['sync_btn']}; color: white; font-weight: bold; font-size: 16px; border-radius: 14px; border: none; }} QPushButton:disabled {{ background: {t['circ_bg']}; color: {t['sub_text']}; }} QPushButton:hover {{ background-color: {t['sync_btn_hover']}; }}")
            
        if hasattr(self, 'btn_theme'):
            self.btn_theme.setStyleSheet(f"QToolButton {{ background-color: {t['btn_bg']}; border-radius: 20px; font-size: 20px; border: 1.5px solid {t['btn_border']}; }} QToolButton::menu-indicator {{ image: none; }}")
            
        for c in self.stage_cards:
            c.apply_theme(theme_name)

    def check_selection(self):
        if self.is_syncing: return
        sel = any(c.is_checked for c in self.stage_cards if c.isEnabled())
        self.btn_sync.setEnabled(sel and self.pen_drive is not None)
        self.update_storage_info() 

    def monitor_pen(self):
        if self.is_syncing:
            QTimer.singleShot(1000, self.monitor_pen)
            return

        pens = find_pens()
        if pens:
            pen_root = pens[0]
            ebook_dir = os.path.join(pen_root, "EBOOK")
            os.makedirs(ebook_dir, exist_ok=True)

            if self.pen_drive != ebook_dir:
                self.pen_drive = ebook_dir
                self.pill_status.setText("● القلم متصل")
                self.pill_status.setStyleSheet("background-color: rgba(52, 199, 89, 0.1); color: #34C759; border-radius: 17px; font-weight: bold; border: 1.5px solid rgba(52, 199, 89, 0.3);")
                self.update_storage_info()
                self.update_cards_state(force_auto_select=True)
            else:
                self.update_storage_info()
        else:
            if self.pen_drive is not None:
                self.pen_drive = None
                self.pill_status.setText("القلم غير متصل ○")
                self.pill_status.setStyleSheet("background-color: rgba(255, 59, 48, 0.1); color: #FF3B30; border-radius: 17px; font-weight: bold; border: 1.5px solid rgba(255, 59, 48, 0.3);")
                self.lbl_storage_text.setText("المساحة المتاحة: —\nالحجم الكلي: —")
                self.circular_progress.setValue(0)
                for c in self.stage_cards:
                    c.status = "NOT_SYNCED"
                    c.set_checked(False)
                self.check_selection()

        QTimer.singleShot(1000, self.monitor_pen)

    def update_storage_info(self):
        if not self.pen_drive: return
        try:
            total, used, free = shutil.disk_usage(self.pen_drive)
            
            # قراءة المساحة المتوقعة للملازم المحددة للتحميل
            predicted_bytes = 0
            selected_acts = set()
            for c in self.stage_cards:
                if c.is_checked:
                    s_files = [f for f in self.all_server_files if f['stage'] == c.stage_name]
                    for item in s_files:
                        selected_acts.add(item['act'])
            
            pen_files = [f.lower() for f in os.listdir(self.pen_drive) if f.lower().endswith('.alt')]
            
            for act in selected_acts:
                if act.lower() not in pen_files:
                    predicted_bytes += self.file_sizes_map.get(act, 0)
            
            used += predicted_bytes
            if used > total: used = total
            
            gb_total = total / (2**30)
            gb_free = (total - used) / (2**30)
            pct = int((used / total) * 100)
            
            self.lbl_storage_text.setText(f"المساحة المتاحة: {gb_free:.1f} GB\nالحجم الكلي: {gb_total:.1f} GB")
            self.circular_progress.setValue(pct)
        except: pass

    def eject_pen(self):
        if self.pen_drive:
            self.pill_status.setText("يمكنك سحب القلم آلياً")
            self.pill_status.setStyleSheet("background-color: rgba(255, 149, 0, 0.1); color: #FF9500; border-radius: 17px; font-weight: bold; border: 1.5px solid rgba(255, 149, 0, 0.3);")

    def fetch_manifest(self):
        if self.is_fetching: return
        self.is_fetching = True
        try:
            url = f"{BASE_URL_FILES}/files.txt?nocache={time.time()}"
            r = requests.get(url, headers=HEADERS, timeout=10)
            r.raise_for_status()
            r.encoding = 'utf-8'
            
            raw_files = []
            for line in r.text.splitlines():
                if "|" in line:
                    parts = [p.strip() for p in line.split("|")]
                    if not parts[0].lower().endswith('.alt'): continue
                    
                    act = parts[0]
                    disp = parts[1]
                    raw_stage = parts[2] if len(parts) >= 3 else None
                    if "(موقوف)" in disp: continue
                    
                    mapped_items = map_and_expand_stages(act, disp, raw_stage)
                    raw_files.extend(mapped_items)
                    
            self.emitter.data_ready.emit(raw_files)
            
            # جلب أحجام الملفات الصافية بالخلفية لضمان عدم تجميد الواجهة
            threading.Thread(target=self.fetch_sizes_worker, args=(raw_files,), daemon=True).start()
            
        except Exception:
            self.is_fetching = False

    def fetch_sizes_worker(self, files):
        import json
        unique_acts = set(f['act'] for f in files)
        sizes_map = {}
        
        cache_file = os.path.join(os.getenv('APPDATA', ''), "Tabaay_Student_Sizes.json")
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r', encoding='utf-8') as cf:
                    sizes_map = json.load(cf)
                self.emitter.sizes_ready.emit(sizes_map)
        except Exception:
            sizes_map = {}

        def get_size(act):
            try:
                if act in sizes_map and sizes_map.get(act, 0) > 0:
                    return act, sizes_map[act]
                
                url = f"{BASE_URL_FILES}/{urllib.parse.quote(act)}"
                return act, get_remote_size(url)
            except Exception:
                return act, 0
                
        updated = False
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = executor.map(get_size, unique_acts)
            for act, size in results:
                if size > 0:
                    if sizes_map.get(act) != size:
                        sizes_map[act] = size
                        updated = True

        if updated:
            try:
                with open(cache_file, 'w', encoding='utf-8') as cf:
                    json.dump(sizes_map, cf)
            except Exception:
                pass
            
        self.emitter.sizes_ready.emit(sizes_map)

    def on_sizes_ready(self, sizes_map):
        self.file_sizes_map = sizes_map
        self.update_cards_state(force_auto_select=False)

    def build_grid(self, files):
        self.is_fetching = False
        self.all_server_files = files
        
        for i in reversed(range(self.grid.count())):
            widget = self.grid.itemAt(i).widget()
            if widget: widget.setParent(None)
        self.stage_cards.clear()

        for s in DISPLAY_STAGES:
            s_files = [f for f in files if f['stage'] == s]
            count = len(s_files)
            if count == 0:
                continue
                
            card = LibraryCard(s, count)
            card.state_changed.connect(self.check_selection)
            self.stage_cards.append(card)

        self.rearrange_grid()
        self.update_cards_state(force_auto_select=True)

    def rearrange_grid(self):
        if not hasattr(self, 'stage_cards') or not self.stage_cards: return
        
        for i in reversed(range(self.grid.count())):
            self.grid.takeAt(i)

        width = self.grid_container.width()
        card_width = self.stage_cards[0].width() + 20
        cols = max(1, width // card_width)
        
        row, col = 0, 0
        for card in self.stage_cards:
            self.grid.addWidget(card, row, col)
            col += 1
            if col >= cols:
                col = 0
                row += 1

    def update_cards_state(self, force_auto_select=False):
        # قفل أمان: منع إعادة تفعيل البطاقات وتحديث حالتها إذا كانت المزامنة قيد التشغيل
        if hasattr(self, 'is_syncing') and self.is_syncing: return 
        if not self.pen_drive or not self.all_server_files: return
        try:
            pen_files = [f.lower() for f in os.listdir(self.pen_drive) if f.lower().endswith('.alt')]
        except: return

        for card in self.stage_cards:
            s_files = [f for f in self.all_server_files if f['stage'] == card.stage_name]
            if not s_files:
                card.set_status(0, 0, 0)
                continue

            missing = 0
            has_exclusive = False
            total_size_bytes = 0
            
            for item in s_files:
                # تحديث الحجم الحقيقي بدقة للمرحلة
                total_size_bytes += getattr(self, 'file_sizes_map', {}).get(item['act'], 0)
                
                if item['act'].lower() not in pen_files:
                    missing += 1
                elif not item.get('is_shared', False):
                    has_exclusive = True

            # حل ذكي لمنع تحذير الحذف الخطأ للمراحل المشتركة
            if not has_exclusive and len(s_files) > 0:
                missing = len(s_files)

            if force_auto_select:
                if has_exclusive and missing < len(s_files):
                    card.set_checked(True)
                else:
                    card.set_checked(False)

            size_mb = total_size_bytes / (1024 * 1024)
            card.set_status(missing, len(s_files), size_mb)

        self.check_selection()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.rearrange_grid()
        if hasattr(self, 'net_overlay') and self.net_overlay.isVisible():
            self.center_net_overlay()

    def center_net_overlay(self):
        if hasattr(self, 'net_overlay'):
            rect = self.centralWidget().geometry()
            x = (rect.width() - self.net_overlay.width()) // 2
            y = (rect.height() - self.net_overlay.height()) // 2
            self.net_overlay.move(x, y)

    def toggle_net_overlay(self, visible):
        if visible:
            try: winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except: pass
            
            blur = QGraphicsBlurEffect(self)
            blur.setBlurRadius(15)
            self.centralWidget().setGraphicsEffect(blur)
            
            self.net_overlay.show()
            self.net_overlay.raise_()
            self.center_net_overlay()
        else:
            if hasattr(self, 'net_overlay'):
                self.net_overlay.hide()
            self.centralWidget().setGraphicsEffect(None)

    def set_active_stage_card(self, active_stage_name):
        # تفعيل شريط التحميل فقط للبطاقة التي يتم تحميل ملزمتها حالياً
        for c in self.stage_cards:
            if c.is_checked and not c.isEnabled():
                if c.stage_name == active_stage_name:
                    c.set_syncing_state(True)
                else:
                    c.set_syncing_state(False)

    def start_sync(self):
        if not self.pen_drive: return
        
        sel_stages = [c.stage_name for c in self.stage_cards if c.is_checked and c.isEnabled()]
        files = [f for f in self.all_server_files if f['stage'] in sel_stages]

        try:
            total_needed_bytes = sum(c.stage_size_mb for c in self.stage_cards if c.is_checked and c.isEnabled()) * 1024 * 1024
            total, used, free = shutil.disk_usage(self.pen_drive)
            if free < total_needed_bytes:
                blur = QGraphicsBlurEffect(self)
                blur.setBlurRadius(15)
                self.centralWidget().setGraphicsEffect(blur)

                msg = (
                    "مساحة القلم غير كافية لتحميل المراحل المحددة.\n\n"
                    f"المساحة المطلوبة: {total_needed_bytes/(1024*1024*1024):.2f} GB\n"
                    f"المساحة المتوفرة: {free/(1024*1024*1024):.2f} GB"
                )
                err_dialog = ErrorDialog(self, "مساحة غير كافية", msg)
                err_dialog.exec()

                self.centralWidget().setGraphicsEffect(None)
                return
        except: pass

        actual_stages_on_pen = set()
        try:
            pen_files = [f.lower() for f in os.listdir(self.pen_drive) if f.lower().endswith('.alt')]
            stage_files_map = {}
            for item in self.all_server_files:
                stage = item['stage']
                if stage not in stage_files_map: stage_files_map[stage] = []
                stage_files_map[stage].append(item)
                
            # تأكيد وجود المرحلة قبل الحذف فقط إذا كانت تمتلك ملفات حصرية
            for stage, s_files in stage_files_map.items():
                has_exclusive = False
                for item in s_files:
                    if item['act'].lower() in pen_files and not item.get('is_shared', False):
                        has_exclusive = True
                        break
                if has_exclusive:
                    actual_stages_on_pen.add(stage)
        except: pass

        stages_to_delete = actual_stages_on_pen - set(sel_stages)

        if stages_to_delete:
            dialog = ConfirmDialog(self, "تنبيه حذف المرحلة المحددة", "تنبيه: لقد ألغيت تحديد بعض المراحل المتواجدة بالقلم.", stages_to_delete)
            dialog.exec()
            if not dialog.result:
                self.update_cards_state(force_auto_select=True)
                return

        self.is_syncing = True
        self.btn_sync.setEnabled(False)
        self.btn_sync.setText("جاري المزامنة المباشرة... يرجى عدم فصل القلم")
        for c in self.stage_cards: 
            c.setEnabled(False)
            c.set_syncing_state(False) # إطفاء الأشرطة بالبداية (سيتم تفعيلها برمجياً كلما بدأ ملف)
        
        threading.Thread(target=self.sync_engine, args=(files,), daemon=True).start()

    def sync_engine(self, files):
        try:
            import ctypes
            # منع الحاسبة من الدخول في وضع النوم وسكون الشاشة
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000002)
        except: pass

        try:
            unique_files = {}
            for f in files:
                unique_files[f['act']] = f
            files_to_sync = list(unique_files.values())

            allowed = [f['act'].lower() for f in files_to_sync]
            if os.path.exists(self.pen_drive):
                for f in os.listdir(self.pen_drive):
                    if f.lower().endswith('.alt') and f.lower() not in allowed:
                        try: os.remove(os.path.join(self.pen_drive, f))
                        except: pass

            total_bytes = 0
            down_bytes = 0
            q = []

            for item in files_to_sync:
                dest = os.path.join(self.pen_drive, item['act'])
                safe_act = urllib.parse.quote(item['act'])
                url = f"{BASE_URL_FILES}/{safe_act}"
                
                size = get_remote_size(url)
                
                if size > 0 and os.path.exists(dest) and os.path.getsize(dest) == size:
                    continue

                tmp = dest + ".tmp"
                ex_size = os.path.getsize(tmp) if os.path.exists(tmp) else 0
                if size > 0 and ex_size > size: ex_size = 0
                
                added_size = size if size > 0 else 0
                total_bytes += added_size
                down_bytes += ex_size
                # تمرير اسم المرحلة مع قائمة التحميل
                q.append((item['act'], dest, url, size, ex_size, item['stage']))

            if not q:
                self.emitter.progress.emit(100, "--:--", "", "")
                self.emitter.sync_done.emit(True, "اكتمل التحديث بنجاح!")
                return

            start_t = time.time()
            speeds = []
            last_u = time.time()

            for fname, dest, url, size, ex_size, stage_name in q:
                self.emitter.current_stage.emit(stage_name)
                
                # التحميل المباشر إلى مسار القلم بدل الـ Temp
                usb_tmp_file = dest + ".tmp"
                
                while True:
                    try:
                        loc = os.path.getsize(usb_tmp_file) if os.path.exists(usb_tmp_file) else 0
                        if size > 0 and loc >= size:
                            self.emitter.net_error.emit(False)
                            break 
                            
                        head = HEADERS.copy()
                        mode = "wb" if loc == 0 else "ab"
                        
                        if loc > 0:
                            head['Range'] = f"bytes={loc}-"

                        with requests.get(url, headers=head, stream=True, timeout=15, verify=False) as r:
                            self.emitter.net_error.emit(False)
                            
                            if r.status_code == 404:
                                break 
                            
                            if r.status_code == 200 and loc > 0:
                                down_bytes -= loc
                                loc = 0
                                mode = "wb"
                                
                            real_size = size
                            if real_size <= 0:
                                real_size = int(r.headers.get('content-length', 0))
                                total_bytes += real_size
                            
                            with open(usb_tmp_file, mode) as f:
                                for chunk in r.iter_content(2 * 1024 * 1024):
                                    if chunk:
                                        f.write(chunk)
                                        loc += len(chunk)
                                        down_bytes += len(chunk)
                                        now = time.time()
                                        
                                        if now - last_u > 0.2 or loc == real_size:
                                            elap = now - start_t
                                            if elap > 1:
                                                spd = (down_bytes - ex_size) / elap
                                                speeds.append(spd)
                                                if len(speeds) > 20: speeds.pop(0)
                                                avg = sum(speeds) / len(speeds)
                                                rem_t = (total_bytes - down_bytes) / avg if avg > 0 else 0
                                            else: rem_t = 0
                                            
                                            pct = int((down_bytes / total_bytes) * 100) if total_bytes > 0 else 0
                                            pct = min(100, max(0, pct))
                                            
                                            down_mb = down_bytes / (1024*1024)
                                            total_mb = total_bytes / (1024*1024)
                                            if total_mb >= 1024:
                                                size_str = f"{down_mb / 1024:.2f} / {total_mb / 1024:.2f} GB"
                                            else:
                                                size_str = f"{down_mb:.1f} / {total_mb:.1f} MB"
                                            
                                            speed_str = f"{avg / (1024*1024):.1f} MB/s" if avg > 0 else "0.0 MB/s"
                                            
                                            self.emitter.progress.emit(pct, self.format_time(rem_t), size_str, speed_str)
                                            last_u = now
                                            
                        self.emitter.net_error.emit(False)
                        break 
                        
                    except (requests.exceptions.RequestException, Exception):
                        if not self.pen_drive or not os.path.exists(self.pen_drive):
                            self.emitter.sync_done.emit(False, "DISCONNECTED")
                            return
                        self.emitter.net_error.emit(True)
                        time.sleep(3) 
                        continue

                try:
                    if os.path.exists(dest): os.remove(dest)
                    os.rename(usb_tmp_file, dest)
                except Exception as e:
                    print(f"Skipped {fname} on copy: {e}")
                    continue

            self.emitter.progress.emit(100, "--:--", "", "")
            self.emitter.sync_done.emit(True, "اكتمل التحديث بنجاح!")
            
        except Exception as e:
            self.emitter.sync_done.emit(False, str(e))
        finally:
            try:
                import ctypes
                # إعادة السماح للحاسبة بالوضع الطبيعي والنوم بعد انتهاء عملية التحميل تماماً
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            except: pass

    def format_time(self, seconds):
        if seconds <= 0 or seconds > 36000: return "--:--:--"
        hours, remainder = divmod(int(seconds), 3600)
        mins, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{mins:02d}:{secs:02d}"
        return f"00:{mins:02d}:{secs:02d}"

    def update_progress(self, pct, time_str, size_str, speed_str):
        self.lbl_time.setText(f"الوقت المتبقي: {time_str}")
        if speed_str == "نقل داخلي":
            self.lbl_speed.setText("جاري النسخ للقلم... ⚡")
        else:
            self.lbl_speed.setText(f"السرعة: {speed_str}")
        self.lbl_size.setText(size_str)
        self.bar.setValue(pct)
        self.lbl_pct.setText(f"{pct}%")

    def on_sync_done(self, success, msg):
        self.is_syncing = False
        self.btn_sync.setText("بدء تحديث القلم")
        
        # نقوم بتحديث حالة البطاقات أولاً لضمان معرفة المراحل المكتملة
        self.update_cards_state(force_auto_select=True)
        self.update_storage_info()
        
        if success:
            try: self.tray_icon.showMessage("تحديث القلم", "اكتمل التحديث بنجاح!", QSystemTrayIcon.MessageIcon.Information, 5000)
            except: pass
            try: winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except: pass
            
            # تصفير شريط التحميل فوراً
            self.lbl_time.setText("تم التحديث بنجاح ✔")
            self.lbl_time.setStyleSheet("color: #34C759; font-weight: bold; font-size: 14px; background:transparent; border:none;")
            self.lbl_speed.setText("")
            self.lbl_size.setText("0.0 / 0.0 MB") 
            self.bar.setValue(0)
            self.lbl_pct.setText("0%")

            # إجبار الواجهة على تحديث نفسها قبل فتح نافذة النجاح
            QApplication.processEvents()

            # 1. استخراج أسماء المراحل الموجودة فعلياً في القلم (المكتملة)
            available_stages = [c.stage_name for c in self.stage_cards if c.status == "LOADED"]

            # 2. تشغيل تأثير الغبش (Blur) على كامل نافذة البرنامج لتركيز الانتباه
            blur = QGraphicsBlurEffect(self)
            blur.setBlurRadius(15)
            self.centralWidget().setGraphicsEffect(blur)

            # 3. عرض شاشة النجاح الرسمية وإرسال قائمة المراحل لها
            success_dialog = SuccessDialog(self, available_stages)
            success_dialog.exec()
            
            # 4. إطفاء تأثير الغبش وإرجاع البرنامج لشكله الطبيعي بعد ضغط "موافق"
            self.centralWidget().setGraphicsEffect(None)
            
        else:
            if msg == "DISCONNECTED":
                self.lbl_time.setText("خطأ: تم فصل القلم!")
                self.lbl_time.setStyleSheet("color: #FF3B30; font-weight: bold; font-size: 14px; background:transparent; border:none;")
                self.lbl_speed.setText("")
                self.lbl_size.setText("0.0 / 0.0 MB") 
                self.bar.setValue(0)
                self.lbl_pct.setText("0%")

                self.emitter.net_error.emit(False)

                blur = QGraphicsBlurEffect(self)
                blur.setBlurRadius(15)
                self.centralWidget().setGraphicsEffect(blur)

                err_dialog = ErrorDialog(self, "خطأ في الاتصال", "تم فصل القلم أثناء التحديث!\nيرجى توصيل القلم والمحاولة مرة أخرى.")
                err_dialog.exec()

                self.centralWidget().setGraphicsEffect(None)
            else:
                self.lbl_time.setText(f"خطأ: {msg}")
                self.lbl_time.setStyleSheet("color: #FF3B30; font-weight: bold; font-size: 13px; background:transparent; border:none;")
            
        for c in self.stage_cards: 
            c.set_syncing_state(False)
            c.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    window = ObyLibraryApp()
    window.show()
    sys.exit(app.exec())