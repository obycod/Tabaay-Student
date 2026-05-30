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
from concurrent.futures import ThreadPoolExecutor

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QProgressBar, 
                             QGraphicsDropShadowEffect, QFrame, QGridLayout, QDialog)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QTimer, QRectF
from PyQt6.QtGui import QColor, QFont, QCursor, QPainter, QPen

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ["QT_LOGGING_RULES"] = "qt.qpa.window=false"

try: 
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except: pass

# ===================== إعدادات السيرفر =====================
APP_VERSION = 5.8
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

    def setValue(self, val):
        self.value = val
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(5, 5, self.width()-10, self.height()-10)
        
        painter.setPen(QPen(QColor("#E2E8F0"), 4))
        painter.drawArc(rect, 0, 360 * 16)
        
        color = "#10B981" if self.value < 85 else "#FF3B30"
        painter.setPen(QPen(QColor(color), 4))
        painter.drawArc(rect, 90 * 16, int(-self.value / 100 * 360 * 16))
        
        painter.setPen(QColor("#1D1D1F"))
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

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 20))
        shadow.setOffset(0, 4)
        self.setGraphicsEffect(shadow)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(15, 10, 15, 10)
        self.layout.setSpacing(4)

        check_lay = QHBoxLayout()
        self.check_box = QLabel("")
        self.check_box.setFixedSize(22, 22)
        self.check_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.check_box.setStyleSheet("border: 2px solid #E2E8F0; border-radius: 11px; background-color: white;")
        
        check_lay.addWidget(self.check_box)
        check_lay.addStretch()
        self.layout.addLayout(check_lay)

        self.lbl_title = QLabel(stage_name)
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; background: transparent; border: none; color: #1D1D1F;")
        self.lbl_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.lbl_title)

        self.lbl_info = QLabel(f"الحجم: جاري الحساب... ({total_files} ملف)")
        self.lbl_info.setStyleSheet("font-size: 12px; color: #718096; background: transparent; border: none;")
        self.lbl_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.lbl_info)

        self.lbl_status = QLabel("بانتظار الفحص...")
        self.lbl_status.setStyleSheet("font-size: 13px; font-weight: bold; background: transparent; border: none;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.lbl_status)

        self.update_ui()

    def set_status(self, missing_count, total_files, stage_size_mb):
        self.total_files = total_files
        self.missing_count = missing_count
        self.stage_size_mb = stage_size_mb
        
        # عرض الحجم كرقم صحيح بدون أعشار (حسب طلبك)
        size_str = f"{int(stage_size_mb)} MB" if stage_size_mb > 0 else "-- MB"
        self.lbl_info.setText(f"الحجم: {size_str} ({total_files} ملف)")
        
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
        if self.isEnabled():
            self.is_checked = not self.is_checked
            self.update_ui()
            self.state_changed.emit()

    def update_ui(self):
        if self.is_checked:
            self.check_box.setText("✔")
            self.check_box.setStyleSheet("background-color: #007AFF; color: white; border-radius: 11px; font-weight: bold; font-size: 14px; border: none;")
        else:
            self.check_box.setText("")
            self.check_box.setStyleSheet("background-color: white; border: 2px solid #E2E8F0; border-radius: 11px;")

        if self.status == "LOADED" and not self.is_checked:
            bg = "#FFF5F5"; border = "#FF3B30"
            self.check_box.setStyleSheet("background-color: white; border: 2px solid #FF3B30; border-radius: 11px;") 
            self.lbl_status.setText("سوف يتم حذف المرحلة ⚠️")
            self.lbl_status.setStyleSheet("color: #FF3B30; font-weight: bold; font-size: 12px; border: none;")
        elif self.is_checked:
            if self.status == "LOADED":
                bg = "#ECFDF5"; border = "#34C759"
                self.lbl_status.setText(f"مكتملة في القلم")
                self.lbl_status.setStyleSheet("color: #16A34A; font-weight: bold; font-size: 12px; border: none;")
            elif self.status == "UPDATE":
                bg = "#FFFBEB"; border = "#FF9500"
                self.lbl_status.setText(f"نقص ({self.missing_count}) ملزمة ⚠️")
                self.lbl_status.setStyleSheet("color: #D97706; font-weight: bold; font-size: 12px; border: none;")
            else:
                bg = "#F2F7FF"; border = "#007AFF"
                self.lbl_status.setText("جاهزة للتثبيت")
                self.lbl_status.setStyleSheet("color: #007AFF; font-weight: bold; font-size: 12px; border: none;")
        else:
            bg = "#FFFFFF"; border = "#E2E8F0"
            if self.status == "SERVER_EMPTY":
                self.lbl_status.setText("غير متوفرة بالسيرفر")
                self.lbl_status.setStyleSheet("color: #A0AEC0; font-weight: bold; font-size: 12px; border: none;")
            elif self.status == "LOADED":
                self.lbl_status.setText(f"مكتملة في القلم")
                self.lbl_status.setStyleSheet("color: #16A34A; font-weight: bold; font-size: 12px; border: none;")
            elif self.status == "UPDATE":
                self.lbl_status.setText(f"نقص ({self.missing_count}) ملزمة ⚠️")
                self.lbl_status.setStyleSheet("color: #D97706; font-weight: bold; font-size: 12px; border: none;")
            else:
                self.lbl_status.setText("جاهزة للتثبيت")
                self.lbl_status.setStyleSheet("color: #4B5563; font-weight: bold; font-size: 12px; border: none;")

        self.setStyleSheet(f"LibraryCard {{ background-color: {bg}; border-radius: 20px; border: 1.5px solid {border}; }}")

# ================= إشارات النظام =================
class SignalEmitter(QObject):
    data_ready = pyqtSignal(list)
    sizes_ready = pyqtSignal(dict)
    progress = pyqtSignal(int, str, str, str) 
    sync_done = pyqtSignal(bool, str) 

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
        container.setStyleSheet("background-color: #FFFFFF; border-radius: 20px;")
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
        lbl_msg = QLabel(f"{message}\n\n[ {stages_text} ]")
        lbl_msg.setWordWrap(True)
        lbl_msg.setStyleSheet("font-size: 15px; color: #4A5568; font-weight: bold;")
        lbl_msg.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_lay = QHBoxLayout()
        btn_yes = QPushButton("نعم، احذفها لتوفير المساحة")
        btn_yes.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_yes.setFixedHeight(45)
        btn_yes.setStyleSheet("QPushButton { background-color: #FF3B30; color: white; font-weight: bold; font-size: 14px; border-radius: 12px; border: none; } QPushButton:hover { background-color: #E03126; }")
        btn_yes.clicked.connect(self.accept_action)

        btn_no = QPushButton("إلغاء المزامنة ✖")
        btn_no.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_no.setFixedHeight(45)
        btn_no.setStyleSheet("QPushButton { background-color: #F5F5F7; color: #1D1D1F; font-weight: bold; font-size: 14px; border-radius: 12px; border: none; } QPushButton:hover { background-color: #E5E5EA; }")
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

        self.all_server_files = []
        self.file_sizes_map = {} 
        self.stage_cards = []
        self.pen_drive = None
        self.is_fetching = False
        self.is_syncing = False

        self.setup_ui()
        threading.Thread(target=self.fetch_manifest, daemon=True).start()
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

        title = QLabel("نظام تحديث القلم الناطق - الذكي")
        title.setStyleSheet("font-size: 28px; font-weight: bold; color: #1D1D1F;")

        self.pill_status = QLabel("بانتظار القلم...")
        self.pill_status.setFixedSize(140, 35)
        self.pill_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.pill_status.setStyleSheet("background-color: #FFF5F5; color: #FF3B30; border-radius: 17px; font-weight: bold; border: 1.5px solid #FF3B30;")

        header_lay.addWidget(title)
        header_lay.addStretch()
        header_lay.addWidget(self.pill_status)
        header_lay.addStretch()
        
        storage_container = QWidget()
        storage_lay = QHBoxLayout(storage_container)
        storage_lay.setContentsMargins(0,0,0,0)
        
        self.lbl_storage_text = QLabel("المساحة المتوفرة: --\nالإجمالي: --")
        self.lbl_storage_text.setStyleSheet("font-size: 13px; font-weight: bold; color: #4A5568;")
        self.lbl_storage_text.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        
        self.circular_progress = CircularProgress()
        
        storage_lay.addWidget(self.lbl_storage_text)
        storage_lay.addWidget(self.circular_progress)
        
        header_lay.addWidget(storage_container)
        main_lay.addWidget(self.header_frame)

        subtitle = QLabel("تحديد المراحل المطلوبة (يفضل حذف المراحل الغير مطلوبة)")
        subtitle.setStyleSheet("background-color: #FFF5F5; color: #FF3B30; font-weight: bold; font-size: 15px; padding: 12px 30px; border-radius: 15px;")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub_lay = QHBoxLayout(); sub_lay.addWidget(subtitle, alignment=Qt.AlignmentFlag.AlignCenter)
        main_lay.addLayout(sub_lay)
        main_lay.addSpacing(10)

        grid_container = QFrame()
        grid_container.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(grid_container)
        self.grid.setSpacing(20) 
        self.grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_lay.addWidget(grid_container, stretch=1)

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
        self.lbl_time = QLabel("الوقت المتبقي: --:--")
        
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
        btn_eject = QPushButton("⏏ إخراج القلم بأمان")
        btn_eject.setFixedSize(180, 50)
        btn_eject.setStyleSheet("QPushButton { background: white; border: 1.5px solid #E2E8F0; color: #1D1D1F; font-weight: bold; border-radius: 14px; font-size: 14px; } QPushButton:hover { background-color: #F7FAFC; }")
        btn_eject.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        btn_eject.clicked.connect(self.eject_pen)

        self.btn_sync = QPushButton("بدء التحديث المباشر للقلم")
        self.btn_sync.setFixedHeight(50)
        self.btn_sync.setStyleSheet("QPushButton { background: #007AFF; color: white; font-weight: bold; font-size: 16px; border-radius: 14px; border: none; } QPushButton:disabled { background: #CBD5E1; color: #718096; } QPushButton:hover { background-color: #0062CC; }")
        self.btn_sync.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.btn_sync.clicked.connect(self.start_sync)

        btn_lay.addWidget(btn_eject)
        btn_lay.addWidget(self.btn_sync, stretch=1)
        main_lay.addLayout(btn_lay)

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
                self.pill_status.setStyleSheet("background-color: #ECFDF5; color: #10B981; border-radius: 17px; font-weight: bold; border: 1.5px solid #10B981;")
                self.update_storage_info()
                self.update_cards_state(force_auto_select=True)
            else:
                self.update_storage_info()
        else:
            if self.pen_drive is not None:
                self.pen_drive = None
                self.pill_status.setText("القلم غير متصل ○")
                self.pill_status.setStyleSheet("background-color: #FFF5F5; color: #FF3B30; border-radius: 17px; font-weight: bold; border: 1.5px solid #FF3B30;")
                self.lbl_storage_text.setText("المساحة المتوفرة: --\nالإجمالي: --")
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
            
            self.lbl_storage_text.setText(f"المساحة المتوفرة: {gb_free:.1f} جيجا\nالإجمالي: {gb_total:.1f} جيجا")
            self.circular_progress.setValue(pct)
        except: pass

    def eject_pen(self):
        if self.pen_drive:
            self.pill_status.setText("يمكنك سحب القلم آلياً")
            self.pill_status.setStyleSheet("background-color: #FFFBEB; color: #FF9500; border-radius: 17px; font-weight: bold; border: 1.5px solid #FF9500;")

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
        unique_acts = set(f['act'] for f in files)
        sizes_map = {}
        
        def get_size(act):
            url = f"{BASE_URL_FILES}/{urllib.parse.quote(act)}"
            return act, get_remote_size(url)
            
        with ThreadPoolExecutor(max_workers=5) as executor:
            results = executor.map(get_size, unique_acts)
            for act, size in results:
                if size > 0:
                    sizes_map[act] = size
                    
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

        row, col = 0, 0
        for s in DISPLAY_STAGES:
            s_files = [f for f in files if f['stage'] == s]
            count = len(s_files)
            if count == 0:
                continue
                
            card = LibraryCard(s, count)
            card.state_changed.connect(self.check_selection)
            self.stage_cards.append(card)
            self.grid.addWidget(card, row, col)
            
            col += 1
            if col > 3:
                col = 0
                row += 1

        self.update_cards_state(force_auto_select=True)

    def update_cards_state(self, force_auto_select=False):
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

    def start_sync(self):
        if not self.pen_drive: return
        
        sel_stages = [c.stage_name for c in self.stage_cards if c.is_checked and c.isEnabled()]
        files = [f for f in self.all_server_files if f['stage'] in sel_stages]

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
            dialog = ConfirmDialog(self, "تنبيه تنظيف الذاكرة وتوفير المساحة", "لقد ألغيت تحديد بعض المراحل المتواجدة بالقلم، سيقوم البرنامج بمسحها لتفريغ مساحة للملازم الجديدة:", stages_to_delete)
            dialog.exec()
            if not dialog.result:
                self.update_cards_state(force_auto_select=True)
                return

        self.is_syncing = True
        self.btn_sync.setEnabled(False)
        self.btn_sync.setText("جاري المزامنة المباشرة... يرجى عدم فصل القلم")
        for c in self.stage_cards: c.setEnabled(False)
        
        threading.Thread(target=self.sync_engine, args=(files,), daemon=True).start()

    def sync_engine(self, files):
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
                q.append((item['act'], dest, url, size, ex_size))

            if not q:
                self.emitter.progress.emit(100, "--:--", "", "")
                self.emitter.sync_done.emit(True, "اكتمل التحديث بنجاح!")
                return

            start_t = time.time()
            speeds = []
            last_u = time.time()

            bridge_dir = os.path.join(os.getenv('TEMP', ''), "Tabaay_Sync_Bridge")
            os.makedirs(bridge_dir, exist_ok=True)

            for fname, dest, url, size, ex_size in q:
                try:
                    local_bridge_file = os.path.join(bridge_dir, fname + ".tmp")
                    head = HEADERS.copy()
                    mode = "wb"
                    loc = ex_size
                    
                    if loc > 0:
                        head['Range'] = f"bytes={loc}-"
                        mode = "ab"

                    with requests.get(url, headers=head, stream=True, timeout=15, verify=False) as r:
                        if r.status_code == 404:
                            continue 
                        
                        real_size = size
                        if real_size <= 0:
                            real_size = int(r.headers.get('content-length', 0))
                            total_bytes += real_size
                        
                        with open(local_bridge_file, mode) as f:
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
                                        
                                        size_str = f"{down_bytes / (1024*1024):.1f} / {total_bytes / (1024*1024):.1f} MB"
                                        speed_str = f"{avg / (1024*1024):.1f} MB/s" if avg > 0 else "0.0 MB/s"
                                        
                                        self.emitter.progress.emit(pct, self.format_time(rem_t), size_str, speed_str)
                                        last_u = now

                    self.emitter.progress.emit(pct, "جاري التثبيت في القلم...", size_str, "نقل داخلي")
                    
                    usb_tmp_file = dest + ".tmp"
                    with open(local_bridge_file, "rb") as src, open(usb_tmp_file, "wb") as dst:
                        while True:
                            chunk = src.read(4 * 1024 * 1024)
                            if not chunk: break
                            if not self.pen_drive or not os.path.exists(self.pen_drive):
                                raise Exception("تم سحب القلم من الحاسبة!")
                            dst.write(chunk)

                    if os.path.exists(dest): os.remove(dest)
                    os.rename(usb_tmp_file, dest)
                    os.remove(local_bridge_file)
                    
                except Exception as e:
                    print(f"Skipped {fname}: {e}")
                    if os.path.exists(local_bridge_file):
                        try: os.remove(local_bridge_file)
                        except: pass
                    continue

            try: shutil.rmtree(bridge_dir)
            except: pass

            self.emitter.progress.emit(100, "--:--", "", "")
            self.emitter.sync_done.emit(True, "اكتمل التحديث بنجاح!")
            
        except Exception as e:
            self.emitter.sync_done.emit(False, str(e))

    def format_time(self, seconds):
        if seconds <= 0 or seconds > 36000: return "--:--"
        mins, secs = divmod(int(seconds), 60)
        return f"{mins:02d}:{secs:02d}"

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
        self.btn_sync.setText("بدء التحديث المباشر للقلم")
        self.update_cards_state(force_auto_select=True)
        self.update_storage_info()
        
        if success:
            self.lbl_time.setText("تم التحديث بنجاح ✔")
            self.lbl_time.setStyleSheet("color: #34C759; font-weight: bold; font-size: 14px; background:transparent; border:none;")
            self.lbl_speed.setText("")
            self.lbl_size.setText("")
            self.bar.setValue(100)
            self.lbl_pct.setText("100%")
        else:
            self.lbl_time.setText(f"خطأ: {msg}")
            self.lbl_time.setStyleSheet("color: #FF3B30; font-weight: bold; font-size: 13px; background:transparent; border:none;")
            
        for c in self.stage_cards: c.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 10)
    app.setFont(font)
    window = ObyLibraryApp()
    window.show()
    sys.exit(app.exec())