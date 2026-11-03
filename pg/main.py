"""
main.py — ระบบตรวจจับ BSF (desktop app)

Run with:  python main.py
Requires:  pip install -r requirements.txt
"""
import ctypes
from pathlib import Path
import sys
import cv2

import mysql.connector
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QMainWindow, QWidget, QLabel, QPushButton, QComboBox,
    QHBoxLayout, QVBoxLayout, QStackedWidget, QFrame, QTableWidget,
    QTableWidgetItem, QHeaderView, QInputDialog, QMessageBox, QFileDialog,
    QLineEdit, QFormLayout, QGraphicsDropShadowEffect,
    QSizePolicy, QGraphicsScene, QGraphicsView,
)

import database
import detector

BLUE = "#3b6df0"
BLUE_DARK = "#2f57c9"
STAGE_COLORS = {
    "stage2": {"bgr": (31, 121, 183), "hex": "#b7791f"},
    "stage3": {"bgr": (90, 133, 47), "hex": "#2f855a"},
    "stage4": {"bgr": (42, 42, 165), "hex": "#a52a2a"},
}
BORDER = "#e5e7eb"
MUTED = "#8a90a0"
BG = "#f5f6fa"
PANEL = "#ffffff"
APP_ICON_PATH = Path(__file__).with_name("icon.png")
WINDOWS_APP_ID = "BSFDesktop.DetectionApp"

STYLE = f"""
QWidget {{ background: {BG}; color: #1f2430; font-family: 'Segoe UI', Arial; font-size: 13px; }}
#Sidebar {{ background: {PANEL}; border-right: 1px solid {BORDER}; }}
#SidebarTitle {{ font-size: 16px; font-weight: 600; }}
#SidebarSub {{ color: {MUTED}; font-size: 11px; }}
QPushButton#NavItem {{ text-align: left; padding: 10px 12px; border-radius: 8px; border: none; background: transparent; font-size: 14px; }}
QPushButton#NavItem:hover {{ background: {BG}; }}
QPushButton#NavItemActive {{ text-align: left; padding: 10px 12px; border-radius: 8px; border: none; background: {BLUE}; color: white; font-size: 14px; }}
QFrame.card {{ background: {PANEL}; border: 1px solid {BORDER}; border-radius: 12px; }}
QPushButton#Primary {{ background: {BLUE}; color: white; border: none; padding: 9px 16px; border-radius: 8px; font-size: 14px; }}
QPushButton#Primary:hover {{ background: {BLUE_DARK}; }}
QPushButton#Primary:disabled {{ background: #9db3f3; }}
QPushButton#IconBtn {{ border: 1px solid {BORDER}; border-radius: 8px; background: white; padding: 8px 12px; }}
QComboBox {{ border: 1px solid {BORDER}; border-radius: 8px; padding: 8px 10px; background: white; }}
#StatLabel {{ color: {MUTED}; font-size: 12px; }}
#StatValue {{ font-size: 20px; font-weight: 600; }}
#SectionTitle {{ font-size: 13px; font-weight: 600; }}
#CamBox {{ border: 2px dashed {BORDER}; border-radius: 12px; background: {BG}; }}
QTableWidget {{ background: white; border: none; gridline-color: {BORDER}; }}
QHeaderView::section {{ background: white; color: {MUTED}; border: none; border-bottom: 1px solid {BORDER}; padding: 8px; font-size: 12px; }}
"""


def _get_recommendation(result):
    stage2 = result["stage2"]
    stage3 = result["stage3"]
    stage4 = result["stage4"]

    if stage3 > stage2 and stage3 > stage4:
        return "Harvest recommended"
    if stage4 > stage2 and stage4 > stage3:
        return "Breeding recommended"
    return "Harvest not recommended yet"


class SaveDetectionDialog(QDialog):
    def __init__(self, parent, tray, result, can_save):
        super().__init__(parent)
        self.setWindowTitle("Save Detection Results")
        self.setWindowModality(Qt.WindowModal)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setStyleSheet(
            "QDialog { background:transparent; } "
            "QLabel { background:transparent; }"
        )
        self.setFixedWidth(340)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)

        card = QFrame()
        card.setObjectName("SaveDialogCard")
        card.setStyleSheet(
            "#SaveDialogCard { background: white; border-radius: 12px; }"
        )
        shadow = QGraphicsDropShadowEffect(card)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 8)
        shadow.setColor(QColor(15, 23, 42, 45))
        card.setGraphicsEffect(shadow)
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        icon = QLabel("▣")
        icon.setAlignment(Qt.AlignCenter)
        icon.setFixedSize(30, 30)
        icon.setStyleSheet(
            "background:#dcfce7; color:#16a34a; border-radius:7px;"
            "font-size:17px; font-weight:700;"
        )
        header.addWidget(icon)

        title_box = QVBoxLayout()
        title = QLabel("Save Detection Results")
        title.setStyleSheet("font-size:13px; font-weight:700; color:#1f2937;")
        description = QLabel(
            "Review the details before saving"
            if can_save else "Log in to save detection results"
        )
        description.setStyleSheet("font-size:10px; color:#8a90a0;")
        title_box.addWidget(title)
        title_box.addWidget(description)
        header.addLayout(title_box, 1)

        close_button = QPushButton("×")
        close_button.setFixedSize(22, 22)
        close_button.setCursor(Qt.PointingHandCursor)
        close_button.setStyleSheet(
            "QPushButton { border:0; color:#94a3b8; font-size:18px; "
            "background:transparent; }"
            "QPushButton:hover { color:#334155; }"
        )
        close_button.clicked.connect(self.reject)
        header.addWidget(close_button, 0, Qt.AlignTop)
        layout.addLayout(header)

        summary = QFrame()
        summary.setStyleSheet(
            "QFrame { background:#f8fafc; border:1px solid #edf0f3; "
            "border-radius:8px; }"
        )
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(10, 4, 10, 4)
        summary_layout.setSpacing(0)

        no_worms_found = (
            result["stage2"] + result["stage3"] + result["stage4"] == 0
        )
        rows = (
            ("Tray", tray),
            ("Total larvae", str(result["full"])),
            ("Number of 2nd instar BSF larvae", str(result["stage2"])),
            ("Number of 3rd instar BSF larvae", str(result["stage3"])),
            ("Number of 4th instar BSF larvae", str(result["stage4"])),
            ("Confidence", f'{result["confidence"]:.1f}%'),
            (
                "Detection result" if no_worms_found else "Recommendation",
                "No larvae detected" if no_worms_found else _get_recommendation(result),
            ),
        )
        for index, (label_text, value_text) in enumerate(rows):
            row = QHBoxLayout()
            row.setContentsMargins(0, 6, 0, 6)
            label = QLabel(label_text)
            label.setStyleSheet("font-size:10px; color:#64748b;")
            value = QLabel(value_text)
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value.setWordWrap(True)
            value.setStyleSheet(
                "font-size:10px; color:#1f2937; font-weight:600;"
                if index < 2 else
                "font-size:10px; color:#16a34a; font-weight:600;"
                if index == 5 else
                "font-size:10px; color:#1f2937;"
            )
            row.addWidget(label, 1)
            row.addWidget(value, 1)
            summary_layout.addLayout(row)
            if index < len(rows) - 1:
                divider = QFrame()
                divider.setFixedHeight(1)
                divider.setStyleSheet("background:#e9edf2; border:0;")
                summary_layout.addWidget(divider)
        layout.addWidget(summary)

        buttons = QHBoxLayout()
        buttons.setSpacing(6)
        cancel_button = QPushButton("Don't Save")
        cancel_button.setCursor(Qt.PointingHandCursor)
        cancel_button.setFixedHeight(30)
        cancel_button.setStyleSheet(
            "QPushButton { background:white; color:#475569; border:1px solid "
            "#e2e8f0; border-radius:6px; font-size:10px; }"
            "QPushButton:hover { background:#f8fafc; }"
        )
        cancel_button.clicked.connect(self.reject)
        save_button = QPushButton("✓  Save")
        save_button.setCursor(Qt.PointingHandCursor)
        save_button.setFixedHeight(30)
        save_button.setEnabled(can_save)
        save_button.setStyleSheet(
            "QPushButton { background:#00a63c; color:white; border:0; "
            "border-radius:6px; font-size:10px; font-weight:600; }"
            "QPushButton:hover { background:#008f34; }"
            "QPushButton:disabled { background:#94d3a8; }"
        )
        save_button.clicked.connect(self.accept)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)
        layout.addLayout(buttons)

    def exec(self):
        parent = self.parentWidget()
        backdrop = None
        if parent is not None:
            host = parent.window()
            backdrop = QWidget(host)
            backdrop.setAttribute(Qt.WA_TransparentForMouseEvents)
            backdrop.setGeometry(host.rect())
            backdrop.setStyleSheet(
                "background-color:rgba(15, 23, 42, 105);"
            )
            backdrop.show()
            backdrop.raise_()
        self.ensurePolished()
        if self.layout() is not None:
            self.layout().activate()
        self.adjustSize()
        screen = None
        if parent is not None:
            screen = QGuiApplication.screenAt(
                parent.mapToGlobal(parent.rect().center())
            )
        screen = screen or self.screen() or QGuiApplication.primaryScreen()
        if screen is not None:
            center = screen.availableGeometry().center()
            self.move(center - self.rect().center())
        try:
            return super().exec()
        finally:
            if backdrop is not None:
                backdrop.hide()
                backdrop.deleteLater()


class ZoomableImageView(QGraphicsView):
    def __init__(self, pixmap):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.image_item = self.scene.addPixmap(pixmap)
        self.scene.setSceneRect(self.image_item.boundingRect())
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self._zoom = 1.0

    def fit_image(self):
        self.resetTransform()
        self.fitInView(self.image_item, Qt.KeepAspectRatio)
        self._zoom = 1.0

    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        zoom = self._zoom * factor
        if 0.25 <= zoom <= 8:
            self.scale(factor, factor)
            self._zoom = zoom
        event.accept()


class ZoomImageDialog(QDialog):
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Detection Image")
        self.resize(1000, 700)

        layout = QVBoxLayout(self)
        self.image_view = ZoomableImageView(pixmap)
        self.image_view.setStyleSheet(
            f"background:{BG}; border:1px solid {BORDER}; border-radius:8px;"
        )
        layout.addWidget(self.image_view, 1)

        controls = QHBoxLayout()
        hint = QLabel("Scroll to zoom · Drag to pan")
        hint.setStyleSheet(f"color:{MUTED};")
        controls.addWidget(hint)
        controls.addStretch()

        fit_button = QPushButton("Fit to Window")
        fit_button.clicked.connect(self.image_view.fit_image)
        controls.addWidget(fit_button)
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        controls.addWidget(close_button)
        layout.addLayout(controls)

    def showEvent(self, event):
        super().showEvent(event)
        self.image_view.fit_image()


class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.user_id = None
        self.user_name = None
        self.setWindowTitle("Log In")
        self.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self.setFixedWidth(420)
        self.mode = "login"

        layout = QVBoxLayout(self)
        title = QLabel("Log In")
        title.setStyleSheet("font-size:20px; font-weight:600;")
        description = QLabel(
            "Log in with your username or email, or create a new account"
        )
        description.setWordWrap(True)
        description.setStyleSheet(f"color:{MUTED};")
        layout.addWidget(title)
        layout.addWidget(description)

        self.form = QFormLayout()
        self.identifier_input = QLineEdit()
        self.identifier_input.setPlaceholderText("Username or email")
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Letters a-z, numbers 0-9, or _")
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("name@example.com")
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("Re-enter password")
        self.confirm_password_input.setEchoMode(QLineEdit.Password)
        self.form.addRow("Username / email", self.identifier_input)
        self.form.addRow("Username", self.username_input)
        self.form.addRow("Email", self.email_input)
        self.form.addRow("Password", self.password_input)
        self.form.addRow(
            "Confirm Password", self.confirm_password_input
        )
        layout.addLayout(self.form)

        self.error_label = QLabel()
        self.error_label.setWordWrap(True)
        self.error_label.setStyleSheet("color:#c53030;")
        layout.addWidget(self.error_label)

        buttons = QHBoxLayout()
        guest_button = QPushButton("Continue as Guest")
        self.mode_button = QPushButton("Create New Account")
        self.submit_button = QPushButton("Log In")
        self.submit_button.setObjectName("Primary")
        buttons.addWidget(guest_button)
        buttons.addStretch()
        buttons.addWidget(self.mode_button)
        buttons.addWidget(self.submit_button)
        layout.addLayout(buttons)

        guest_button.clicked.connect(self._continue_as_guest)
        self.mode_button.clicked.connect(self._toggle_mode)
        self.submit_button.clicked.connect(self._submit)
        self.password_input.returnPressed.connect(self._submit)
        self._update_form_mode()

    def _update_form_mode(self):
        is_registering = self.mode == "register"
        self.form.labelForField(self.identifier_input).setVisible(not is_registering)
        self.identifier_input.setVisible(not is_registering)
        self.form.labelForField(self.username_input).setVisible(is_registering)
        self.username_input.setVisible(is_registering)
        self.form.labelForField(self.email_input).setVisible(is_registering)
        self.email_input.setVisible(is_registering)
        self.form.labelForField(self.confirm_password_input).setVisible(is_registering)
        self.confirm_password_input.setVisible(is_registering)
        self.submit_button.setText("Create Account" if is_registering else "Log In")
        self.mode_button.setText(
            "Back to Log In" if is_registering else "Create New Account"
        )
        self.error_label.clear()

    def _toggle_mode(self):
        self.mode = "register" if self.mode == "login" else "login"
        self._update_form_mode()

    def _submit(self):
        if self.mode == "register":
            self._register()
        else:
            self._login()

    def _login(self):
        identifier = self.identifier_input.text().strip()
        password = self.password_input.text()
        if not identifier or not password:
            self.error_label.setText("Enter your username/email and password.")
            return
        try:
            account = database.authenticate_user(identifier, password)
        except (mysql.connector.Error, RuntimeError, ValueError) as error:
            self.error_label.setText(f"Database connection failed: {error}")
            return
        if account:
            self.user_id, self.user_name = account
            self.accept()
        else:
            self.error_label.setText("Incorrect username/email or password.")

    def _register(self):
        username = self.username_input.text().strip()
        email = self.email_input.text().strip()
        password = self.password_input.text()
        if password != self.confirm_password_input.text():
            self.error_label.setText("Passwords do not match.")
            return
        try:
            self.user_id = database.create_user(username, email, password)
        except ValueError as error:
            self.error_label.setText(str(error))
            return
        except (mysql.connector.Error, RuntimeError) as error:
            self.error_label.setText(f"Database connection failed: {error}")
            return
        self.user_name = username
        self.accept()

    def _continue_as_guest(self):
        self.user_id = None
        self.user_name = None
        self.accept()


class DetectionPage(QWidget):
    def __init__(self, on_saved, user_id=None):
        super().__init__()
        self.on_saved = on_saved
        self.user_id = user_id
        self.cap = None
        self.mode = "image"
        self.last_result = None
        self.result_pixmap = None
        self.is_running = False
        self.is_video = False
        self.frame_count = 0
        self.tracked_stage_votes = {}
        self.tracked_confidences = {}
        self.max_frame_stage_counts = {
            "stage2": 0, "stage3": 0, "stage4": 0
        }
        self.timer = QTimer()
        self.timer.timeout.connect(self._update_frame)

        root = QVBoxLayout(self)
        title = QLabel("Black Soldier Fly (BSF) Detection system")
        title.setStyleSheet("font-size:20px; font-weight:600;")
        desc = QLabel("Detection system for BSF larvae and pre-pupae")
        desc.setStyleSheet(f"color:{MUTED};")
        root.addWidget(title)
        root.addWidget(desc)

        layout = QHBoxLayout()
        root.addLayout(layout)

        # ---- left card: controls + camera ----
        left = QFrame(); left.setProperty("class", "card")
        left.setStyleSheet(f".QFrame{{background:{PANEL}; border:1px solid {BORDER}; border-radius:12px;}}")
        left_layout = QVBoxLayout(left)

        row = QHBoxLayout()
        self.tray_combo = QComboBox()
        self.tray_combo.addItems(database.get_trays(self.user_id))

        self.add_tray_button = QPushButton("＋")
        self.add_tray_button.setObjectName("IconBtn")
        self.add_tray_button.clicked.connect(self._add_tray)
        self.add_tray_button.setEnabled(self.user_id is not None)

        # เลือกโหมดตรวจจับ
        self.mode_combo = QComboBox()
        self.mode_combo.addItems([
            "Image",
            "Video",
            "Webcam"
        ])
        self.mode_combo.currentIndexChanged.connect(self._change_mode)

        self.start_btn = QPushButton("Start")
        self.start_btn.setObjectName("Primary")
        self.start_btn.clicked.connect(self._start_detection)

        row.addWidget(self.tray_combo, 1)
        row.addWidget(self.add_tray_button)
        row.addWidget(self.mode_combo)
        row.addWidget(self.start_btn)
        left_layout.addLayout(row)

        self.cam_label = QLabel("📷\nPress the start button to begin \ndetection")
        self.cam_label.setObjectName("CamBox")
        self.cam_label.setAlignment(Qt.AlignCenter)
        self.cam_label.setMinimumHeight(380)
        
        # --- เพิ่มบรรทัดนี้เพื่อป้องกันไม่ให้ QLabel ขยายตามขนาดรูปภาพ ---
        self.cam_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        
        self.cam_label.setStyleSheet(f"color:{MUTED}; font-size:14px;")
        left_layout.addWidget(self.cam_label)
        self.zoom_button = QPushButton("Enlarge image")
        self.zoom_button.setObjectName("IconBtn")
        self.zoom_button.setEnabled(False)
        self.zoom_button.clicked.connect(self._open_image_viewer)
        left_layout.addWidget(self.zoom_button, 0, Qt.AlignRight)

        # ---- right card: results ----
        right = QFrame()
        right.setStyleSheet(f"QFrame{{background:{PANEL}; border:1px solid {BORDER}; border-radius:12px;}}")
        right.setFixedWidth(250)
        right_layout = QVBoxLayout(right)
        right_layout.addWidget(self._section_title("Detection"))
        self.lbl_full = self._stat(right_layout, "Total", "0")
        self.lbl_s2 = self._stat(
            right_layout, "Number of 2nd instar BSF larvae", "0", color=STAGE_COLORS["stage2"]["hex"]
        )
        self.lbl_s3 = self._stat(
            right_layout, "Number of 3rd instar BSF larvae", "0", color=STAGE_COLORS["stage3"]["hex"]
        )
        self.lbl_s4 = self._stat(
            right_layout, "Number of 4th instar BSF larvae", "0", color=STAGE_COLORS["stage4"]["hex"]
        )
        line = QFrame(); line.setFrameShape(QFrame.HLine); line.setStyleSheet(f"color:{BORDER};")
        right_layout.addWidget(line)
        right_layout.addWidget(self._section_title("Confidence score"))
        self.lbl_conf = self._stat(right_layout, "Confidence", "0%")
        self.lbl_fps = self._stat(right_layout, "FPS", "0")
        right_layout.addStretch()

        layout.addWidget(left, 1)
        layout.addWidget(right)

    def _section_title(self, text):
        lbl = QLabel(text); lbl.setObjectName("SectionTitle")
        return lbl

    def _stat(self, layout, label, value, color=None):
        box = QVBoxLayout()
        l = QLabel(label); l.setObjectName("StatLabel")
        v = QLabel(value); v.setObjectName("StatValue")
        if color:
            v.setStyleSheet(f"color:{color};")
        box.addWidget(l); box.addWidget(v)
        layout.addLayout(box)
        return v

    def _add_tray(self):
        if self.user_id is None:
            QMessageBox.information(
                self, "Log In Required", "Please log in before adding a tray."
            )
            return
        name, ok = QInputDialog.getText(self, "Add Tray", "New tray name:")
        if ok and name.strip():
            try:
                database.add_tray(name.strip(), self.user_id)
            except mysql.connector.Error as error:
                QMessageBox.critical(self, "Failed to Save Tray", str(error))
                return
            self.tray_combo.clear()
            self.tray_combo.addItems(database.get_trays(self.user_id))
            self.tray_combo.setCurrentText(name.strip())

    def set_user_id(self, user_id):
        self.user_id = user_id
        self.tray_combo.clear()
        self.tray_combo.addItems(database.get_trays(user_id))
        self.add_tray_button.setEnabled(user_id is not None)

    def _change_mode(self, index):
        if self.is_running:
            self._stop_detection()

        modes = ["image", "video", "realtime"]
        self.mode = modes[index]

        self.cam_label.clear()
        self.result_pixmap = None
        self.zoom_button.setEnabled(False)

        if self.mode == "image":
            self.cam_label.setText("select an image to start detection")
        elif self.mode == "video":
            self.cam_label.setText("select a video clip to start detection")
        else:
            self.cam_label.setText("press start to detect through webcam")

        self.start_btn.setText("Start")

    def _start_detection(self):
        # ถ้ากำลังรันอยู่ ให้เปลี่ยนเป็นการกดหยุด
        if self.is_running:
            self._stop_detection()
            return

        if self.mode == "image":
            self._detect_image()
        elif self.mode == "video":
            self._start_video()
        elif self.mode == "realtime":
            self._start_realtime()

    def _detect_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select an Image", "", "Images (*.png *.jpg *.jpeg *.bmp *.webp)"
        )
        if not path:
            return

        frame = cv2.imread(path)
        if frame is None:
            QMessageBox.warning(self, "Error", "Could not open the image.")
            return

        result = detector.detect_frame(frame)
        self._show_result(result)
        self.last_result = result
        self._show_frame(frame, result["boxes"])
        self._save_result(result)

    def _start_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select a Video Clip", "", "Videos (*.mp4 *.avi *.mov *.mkv)"
        )
        if not path:
            return

        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            self.cap.release()
            self.cap = None
            QMessageBox.warning(self, "Error", "Could not open the video.")
            return

        self._reset_stream_tracking()
        self.is_video = True
        self.is_running = True
        self.last_result = None
        self.start_btn.setText("Stop Detection")
        self.mode_combo.setEnabled(False)
        self.timer.start(30)

    def _start_realtime(self):
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            self.cap.release()
            self.cap = None
            QMessageBox.warning(self, "Error", "Could not access the camera.")
            return

        self._reset_stream_tracking()
        self.is_video = False
        self.is_running = True
        self.last_result = None
        self.start_btn.setText("Stop Detection")
        self.mode_combo.setEnabled(False)
        self.timer.start(30)

    def _reset_stream_tracking(self):
        detector.reset_tracker()
        self.frame_count = 0
        self.tracked_stage_votes.clear()
        self.tracked_confidences.clear()
        self.max_frame_stage_counts = {
            "stage2": 0, "stage3": 0, "stage4": 0
        }

    def _record_tracks(self, result):
        for box in result["boxes"]:
            track_id = box[6] if len(box) > 6 else None
            if track_id is None:
                continue

            label = box[4]
            votes = self.tracked_stage_votes.setdefault(track_id, {})
            votes[label] = votes.get(label, 0) + 1
            self.tracked_confidences.setdefault(track_id, []).append(box[5])

    def _get_tracked_result(self):
        stage_counts = {"stage2": 0, "stage3": 0, "stage4": 0}
        for votes in self.tracked_stage_votes.values():
            if votes:
                stage = max(votes, key=votes.get)
                stage_counts[stage] += 1

        if not self.tracked_stage_votes:
            stage_counts = self.max_frame_stage_counts.copy()

        track_confidences = [
            sum(confidences) / len(confidences)
            for confidences in self.tracked_confidences.values()
            if confidences
        ]
        confidence = (
            sum(track_confidences) / len(track_confidences)
            if track_confidences else self.last_result["confidence"]
        )
        return {
            "full": sum(stage_counts.values()),
            **stage_counts,
            "confidence": round(confidence, 1),
            "fps": self.last_result["fps"],
        }

    def _update_frame(self):
        if not self.cap or not self.is_running:
            return

        ok, frame = self.cap.read()
        if not ok:
            # วิดีโอจบแล้ว
            if self.is_video:
                self._stop_detection()
            return

        result = detector.detect_frame(frame, track=True)
        self.last_result = result
        self.frame_count += 1
        self._record_tracks(result)
        if result["full"] > sum(self.max_frame_stage_counts.values()):
            self.max_frame_stage_counts = {
                stage: result[stage] for stage in self.max_frame_stage_counts
            }
        self._show_result(result)
        self._show_frame(frame, result["boxes"])

    def _show_frame(self, frame, boxes=None):
        display_frame = frame.copy()
        for box in boxes or []:
            x1, y1, x2, y2, label, confidence = box[:6]
            track_id = box[6] if len(box) > 6 else None
            top_left = (int(x1), int(y1))
            bottom_right = (int(x2), int(y2))
            color = STAGE_COLORS.get(label, {"bgr": (40, 210, 80)})["bgr"]
            cv2.rectangle(display_frame, top_left, bottom_right, color, 2)
            track_label = f" ID:{track_id}" if track_id is not None else ""
            cv2.putText(
                display_frame,
                f"{label}{track_label} {confidence:.1f}%",
                (top_left[0], max(top_left[1] - 8, 18)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )

        rgb = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape

        img = QImage(rgb.data, w, h, ch * w, QImage.Format_RGB888)
        
        # ใช้ KeepAspectRatio เพื่อไม่ให้ภาพขยายล้นกรอบหรือผิดสัดส่วน
        self.result_pixmap = QPixmap.fromImage(img)
        pix = self.result_pixmap.scaled(
            self.cam_label.size(),
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.cam_label.setPixmap(pix)
        self.zoom_button.setEnabled(True)

    def _open_image_viewer(self):
        if self.result_pixmap is None or self.result_pixmap.isNull():
            return
        ZoomImageDialog(self.result_pixmap, self).exec()

    def _stop_detection(self):
        self.timer.stop()

        if self.cap:
            self.cap.release()
            self.cap = None

        self.is_running = False

        self.start_btn.setText("Start Detection")
        self.mode_combo.setEnabled(True)
        self.cam_label.setText("Detection Stopped")
        self.result_pixmap = None
        self.zoom_button.setEnabled(False)
        detector.reset_tracker()
        if self.frame_count:
            self._save_result(self._get_tracked_result())

    def _save_result(self, result):
        tray = self.tray_combo.currentText()
        if self.user_id is not None and not tray:
            QMessageBox.information(
                self, "No Trays Available",
                "Add a tray before saving detection results."
            )
            return

        popup = SaveDetectionDialog(
            self,
            tray or "—",
            result,
            can_save=self.user_id is not None,
        )
        if popup.exec() != QDialog.Accepted or self.user_id is None:
            return

        recommendation = _get_recommendation(result)
        try:
            database.add_detection(tray, {
                "full": result["full"],
                "stage2": result["stage2"],
                "stage3": result["stage3"],
                "stage4": result["stage4"],
                "confidence": result["confidence"],
                "fps": result["fps"],
                "recommendation": recommendation,
            }, self.user_id)
        except (mysql.connector.Error, ValueError) as error:
            QMessageBox.critical(self, "Failed to Save Results", str(error))
            return
        self.on_saved()

    def _show_result(self, r):
        self.lbl_full.setText(str(r["full"]))
        self.lbl_s2.setText(str(r["stage2"]))
        self.lbl_s3.setText(str(r["stage3"]))
        self.lbl_s4.setText(str(r["stage4"]))
        self.lbl_conf.setText(f'{r["confidence"]}%')
        self.lbl_fps.setText(str(r["fps"]))

    def closeEvent(self, event):
        if self.cap:
            self.cap.release()
        event.accept()


class HistoryPage(QWidget):
    def __init__(self, user_id=None):
        super().__init__()
        self.user_id = user_id
        root = QVBoxLayout(self)
        title = QLabel("History")
        title.setStyleSheet("font-size:20px; font-weight:600;")
        desc = QLabel("View past detection results")
        desc.setStyleSheet(f"color:{MUTED};")
        root.addWidget(title)
        root.addWidget(desc)

        card = QFrame()
        card.setStyleSheet(f"QFrame{{background:{PANEL}; border:1px solid {BORDER}; border-radius:12px;}}")
        card_layout = QVBoxLayout(card)

        self.total_label = QLabel("Total detections: 0")
        self.total_label.setStyleSheet("font-size:15px; font-weight:600;")
        card_layout.addWidget(self.total_label)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Date & Time", "Tray", "Total", "Stage 2", "Stage 3", "Stage 4",
            "Recommendation"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        card_layout.addWidget(self.table)

        root.addWidget(card)
        self.refresh()

    def set_user(self, user_id):
        """Refresh the history when the signed-in user changes."""
        self.user_id = user_id
        self.refresh()

    def refresh(self):
        rows = [] if self.user_id is None else database.get_history(self.user_id)
        self.total_label.setText(f"Total detections: {len(rows)}")
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            values = [
                r["timestamp"], r["tray_name"], r["full_count"], r["stage2_count"],
                r["stage3_count"], r["stage4_count"],
                r["recommendation"] or _get_recommendation({
                    "stage2": r["stage2_count"],
                    "stage3": r["stage3_count"],
                    "stage4": r["stage4_count"],
                })
            ]
            for j, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                if j == 6:
                    item.setForeground(QColor("#16803c"))
                self.table.setItem(i, j, item)


class MainWindow(QMainWindow):
    def __init__(self, user_name=None, user_id=None):
        super().__init__()
        self.setWindowIcon(QIcon(str(APP_ICON_PATH)))
        self.user_name = user_name
        self.user_id = user_id
        self.setWindowTitle("BSF Detection System")
        self.resize(1200, 760)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # sidebar
        sidebar = QFrame(); sidebar.setObjectName("Sidebar"); sidebar.setFixedWidth(220)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(14, 20, 14, 20)
        t = QLabel("BSF Detection System"); t.setObjectName("SidebarTitle")
        side_layout.addWidget(t)
        side_layout.addSpacing(12)

        self.btn_detect = QPushButton("📷  Detect"); self.btn_detect.setObjectName("NavItemActive")
        self.btn_history = QPushButton("🕘  History"); self.btn_history.setObjectName("NavItem")
        side_layout.addWidget(self.btn_detect)
        side_layout.addWidget(self.btn_history)
        self.account_label = QLabel()
        self.account_label.setObjectName("SidebarSub")
        side_layout.addWidget(self.account_label)
        self.account_button = QPushButton()
        self.account_button.setObjectName("NavItem")
        self.account_button.clicked.connect(self._toggle_login)
        side_layout.addWidget(self.account_button)
        side_layout.addStretch()

        # pages
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)
        self.stack = QStackedWidget()
        self.history_page = HistoryPage(user_id=self.user_id)
        self.detect_page = DetectionPage(
            on_saved=self.history_page.refresh, user_id=self.user_id
        )
        self.stack.addWidget(self.detect_page)
        self.stack.addWidget(self.history_page)
        content_layout.addWidget(self.stack)

        layout.addWidget(sidebar)
        layout.addWidget(content, 1)

        self.btn_detect.clicked.connect(lambda: self._switch(0))
        self.btn_history.clicked.connect(lambda: self._switch(1))
        self._update_account_controls()

    def _update_account_controls(self):
        if self.user_name:
            self.account_label.setText(f"Login: {self.user_name}")
            self.account_button.setText("Logout")
        else:
            self.account_label.setText("Status: Guest")
            self.account_button.setText("Login")

    def _toggle_login(self):
        if self.user_name:
            self.user_name = None
            self.user_id = None
        else:
            dialog = LoginDialog(self)
            dialog.exec()
            if dialog.user_name:
                self.user_name = dialog.user_name
                self.user_id = dialog.user_id
        self.detect_page.set_user_id(self.user_id)
        self.history_page.set_user(self.user_id)
        self._update_account_controls()

    def _switch(self, index):
        self.stack.setCurrentIndex(index)
        self.btn_detect.setObjectName("NavItemActive" if index == 0 else "NavItem")
        self.btn_history.setObjectName("NavItemActive" if index == 1 else "NavItem")
        for b in (self.btn_detect, self.btn_history):
            b.style().unpolish(b); b.style().polish(b)
        if index == 1:
            self.history_page.refresh()

    def closeEvent(self, event):
        self.detect_page.closeEvent(event)


def main():
    if sys.platform == "win32":
        set_app_id = ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID
        set_app_id.argtypes = [ctypes.c_wchar_p]
        set_app_id.restype = ctypes.c_long
        result = set_app_id(WINDOWS_APP_ID)
        if result != 0:
            raise OSError(result, "Could not set the Windows application ID")
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    app.setStyleSheet(STYLE)
    try:
        database.init_db()
    except Exception as error:
        QMessageBox.critical(
            None,
            "Failed to connect to Railway MySQL",
            "Please check the configuration in pg/.env and ensure Public Networking "
            f"is enabled for Railway MySQL\n\nDetails: {error}",
        )
        return
    login_dialog = LoginDialog()
    login_dialog.exec()
    win = MainWindow(
        user_name=login_dialog.user_name,
        user_id=login_dialog.user_id,
    )
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
