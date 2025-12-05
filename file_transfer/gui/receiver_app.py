import sys
import os
import cv2
import numpy as np
import json
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QProgressBar, QTextEdit, QMessageBox, QCheckBox)
from PySide6.QtCore import Qt, QTimer, Slot, Signal, QPoint
from PySide6.QtGui import QImage, QPixmap, QPainter, QPen, QColor
from PIL import Image
from pyzbar.pyzbar import decode as decode_qr

from file_transfer.core.decoding_grid import decode_grid_image

class VideoLabel(QLabel):
    corners_changed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.corners = [] # List of (x, y) normalized 0.0-1.0
        self.active_corner = -1
        self.setMouseTracking(True)

    def set_corners(self, corners):
        self.corners = corners
        self.update()

    def mousePressEvent(self, event):
        if not self.pixmap(): return
        
        # Convert click to normalized coords
        w, h = self.width(), self.height()
        # Calculate actual image rect inside label (KeepAspectRatio)
        pm = self.pixmap()
        pm_w, pm_h = pm.width(), pm.height()
        
        scale = min(w/pm_w, h/pm_h)
        nw, nh = pm_w*scale, pm_h*scale
        ox, oy = (w-nw)/2, (h-nh)/2
        
        x = (event.position().x() - ox) / nw
        y = (event.position().y() - oy) / nh
        
        # Check if clicking near existing corner
        min_d = 0.05
        self.active_corner = -1
        for i, c in enumerate(self.corners):
            d = ((c[0]-x)**2 + (c[1]-y)**2)**0.5
            if d < min_d:
                min_d = d
                self.active_corner = i
        
        if self.active_corner == -1 and len(self.corners) < 4:
            # Add new corner
            self.corners.append((x, y))
            self.corners_changed.emit(self.corners)
            self.update()

    def mouseMoveEvent(self, event):
        if self.active_corner != -1:
            w, h = self.width(), self.height()
            pm = self.pixmap()
            if not pm: return
            pm_w, pm_h = pm.width(), pm.height()
            scale = min(w/pm_w, h/pm_h)
            nw, nh = pm_w*scale, pm_h*scale
            ox, oy = (w-nw)/2, (h-nh)/2
            
            x = (event.position().x() - ox) / nw
            y = (event.position().y() - oy) / nh
            
            # Clamp
            x = max(0.0, min(1.0, x))
            y = max(0.0, min(1.0, y))
            
            self.corners[self.active_corner] = (x, y)
            self.corners_changed.emit(self.corners)
            self.update()

    def mouseReleaseEvent(self, event):
        self.active_corner = -1

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.corners or not self.pixmap(): return
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w, h = self.width(), self.height()
        pm = self.pixmap()
        pm_w, pm_h = pm.width(), pm.height()
        scale = min(w/pm_w, h/pm_h)
        nw, nh = pm_w*scale, pm_h*scale
        ox, oy = (w-nw)/2, (h-nh)/2
        
        # Draw Polygon
        if len(self.corners) == 4:
            pts = []
            for c in self.corners:
                pts.append(QPoint(ox + c[0]*nw, oy + c[1]*nh))
            
            pen = QPen(QColor(0, 255, 0), 2)
            painter.setPen(pen)
            # Draw lines 0-1-2-3-0
            painter.drawLine(pts[0], pts[1])
            painter.drawLine(pts[1], pts[2])
            painter.drawLine(pts[2], pts[3])
            painter.drawLine(pts[3], pts[0])

        # Draw Points
        painter.setBrush(QColor(255, 255, 0))
        for i, c in enumerate(self.corners):
            cx = ox + c[0]*nw
            cy = oy + c[1]*nh
            painter.drawEllipse(QPoint(cx, cy), 5, 5)


class ReceiverApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Optical File Transfer - Receiver")
        self.resize(900, 700)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # Video feed
        self.lbl_video = VideoLabel()
        self.lbl_video.setAlignment(Qt.AlignCenter)
        self.lbl_video.setMinimumSize(640, 480)
        self.lbl_video.setStyleSheet("background-color: #000;")
        self.layout.addWidget(self.lbl_video)
        
        # Controls
        self.controls_layout = QHBoxLayout()
        self.btn_camera = QPushButton("Start Camera")
        self.btn_camera.clicked.connect(self.toggle_camera)
        self.btn_decode = QPushButton("Decode Current Frame")
        self.btn_decode.clicked.connect(self.manual_decode)
        self.lbl_status = QLabel("Status: Idle")
        
        self.controls_layout.addWidget(self.btn_camera)
        self.controls_layout.addWidget(self.btn_decode)
        
        self.chk_auto = QCheckBox("Auto Decode")
        self.controls_layout.addWidget(self.chk_auto)
        
        self.btn_reset_corners = QPushButton("Reset Corners")
        self.btn_reset_corners.clicked.connect(self.reset_corners)
        self.controls_layout.addWidget(self.btn_reset_corners)

        self.btn_load = QPushButton("Load File")
        self.btn_load.clicked.connect(self.load_file_frame)
        self.controls_layout.addWidget(self.btn_load)
        
        self.btn_save = QPushButton("Save File")
        self.btn_save.clicked.connect(self.save_file)
        self.btn_save.setEnabled(False)
        self.controls_layout.addWidget(self.btn_save)
        
        self.controls_layout.addWidget(self.lbl_status)
        self.layout.addLayout(self.controls_layout)
        
        # Progress & Log
        self.progress = QProgressBar()
        self.layout.addWidget(self.progress)
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(150)
        self.layout.addWidget(self.log_view)
        
        # State
        self.cap = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.current_frame_cv = None
        self.received_frames = {}
        self.manifest = None
        self.expected_frames = 0
        self.is_camera_active = False
        
        # Default corners (TL, TR, BR, BL)
        self.corners = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
        self.lbl_video.set_corners(self.corners)
        self.lbl_video.corners_changed.connect(self.update_corners)

    def update_corners(self, corners):
        self.corners = corners

    def reset_corners(self):
        self.corners = [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)]
        self.lbl_video.set_corners(self.corners)


    @Slot()
    def load_file_frame(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Select Frame Image", "", "Images (*.png *.jpg)")
        if path:
            pil_img = Image.open(path)
            # Display it
            qimg = QImage(path)
            self.lbl_video.setPixmap(QPixmap.fromImage(qimg).scaled(self.lbl_video.size(), Qt.KeepAspectRatio))
            
            # Update current_frame_cv so manual decode works
            self.current_frame_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

            # Decode with current corners (mapped to image size)
            w, h = pil_img.size
            pixel_corners = []
            if len(self.corners) == 4:
                for c in self.corners:
                    pixel_corners.append((int(c[0]*w), int(c[1]*h)))

            result = decode_grid_image(pil_img, corners=pixel_corners if len(pixel_corners)==4 else None)
            if result:
                header, payload = result
                seq = header['seq']
                self.log(f"Decoded Frame #{seq} from file")
                if seq not in self.received_frames:
                    self.received_frames[seq] = payload
                    self.update_progress()
            else:
                self.log(f"Failed to decode {os.path.basename(path)}")

    @Slot()
    def toggle_camera(self):
        if self.is_camera_active:
            # Capture/Freeze
            self.timer.stop()
            if self.cap:
                self.cap.release()
            # Do NOT clear the label text/pixmap
            self.btn_camera.setText("Resume Camera")
            self.is_camera_active = False
            self.log("Frame captured. Adjust corners and Decode.")
        else:
            # Resume
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                self.log("Failed to open camera")
                return
            self.timer.start(33)  # ~30 FPS
            self.btn_camera.setText("Capture Frame")
            self.is_camera_active = True

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return
            
        self.current_frame_cv = frame
        
        # Convert to Qt
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qimg = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self.lbl_video.setPixmap(QPixmap.fromImage(qimg).scaled(self.lbl_video.size(), Qt.KeepAspectRatio))

        if self.chk_auto.isChecked():
            self.process_frame(frame, verbose=False)

    def process_frame(self, frame_cv, verbose=False):
        # Convert to PIL
        rgb_frame = cv2.cvtColor(frame_cv, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_frame)
        
        # 1. Try QR Decode (Manifest) - only if not loaded
        if not self.manifest:
            decoded_qrs = decode_qr(pil_img)
            if decoded_qrs:
                for qr in decoded_qrs:
                    try:
                        data = qr.data.decode('utf-8')
                        # Check if it looks like manifest JSON
                        if '"files":' in data and '"total_chunks":' in data:
                            self.manifest = json.loads(data)
                            self.expected_frames = self.manifest.get('total_chunks', 0)
                            self.log(f"Manifest loaded! Expecting {self.expected_frames} frames.")
                            self.progress.setMaximum(self.expected_frames)
                            self.update_progress()
                            return # Found manifest, stop
                    except Exception as e:
                        self.log(f"QR decode error: {e}")

        # 2. Try Grid Decode with Corners
        # Convert normalized corners to pixel coordinates
        h, w, _ = frame_cv.shape
        pixel_corners = []
        if len(self.corners) == 4:
            for c in self.corners:
                pixel_corners.append((int(c[0]*w), int(c[1]*h)))
        
        result = decode_grid_image(pil_img, corners=pixel_corners if len(pixel_corners)==4 else None)
        if result:
            header, payload = result
            seq = header['seq']
            if verbose:
                self.log(f"Decoded Frame #{seq} (len={len(payload)})")
            if seq not in self.received_frames:
                self.received_frames[seq] = payload
                if not verbose:
                    self.log(f"Received Frame #{seq}")
                self.update_progress()
        elif verbose:
            self.log("Decode failed (alignment?)")

    @Slot()
    def manual_decode(self):
        if self.current_frame_cv is None:
            self.log("No frame to decode")
            return
        self.process_frame(self.current_frame_cv, verbose=True)

    @Slot()
    def save_file(self):
        if not self.received_frames:
            return
            
        from PySide6.QtWidgets import QFileDialog
        default_name = "reconstructed.bin"
        if self.manifest and self.manifest.get('files'):
            default_name = self.manifest['files'][0]['path']
            
        path, _ = QFileDialog.getSaveFileName(self, "Save Reconstructed File", default_name)
        if path:
            sorted_seqs = sorted(self.received_frames.keys())
            with open(path, 'wb') as f:
                for seq in sorted_seqs:
                    f.write(self.received_frames[seq])
            self.log(f"Saved to {path}")
            QMessageBox.information(self, "Success", f"File saved to {path}")

    def update_progress(self):
        count = len(self.received_frames)
        if self.expected_frames > 0:
            self.lbl_status.setText(f"Received: {count} / {self.expected_frames}")
            self.progress.setValue(count)
            if count >= self.expected_frames:
                self.btn_save.setEnabled(True)
        else:
            self.lbl_status.setText(f"Received: {count} frames")
            self.progress.setValue(count % 100)
            self.btn_save.setEnabled(count > 0)

    def log(self, msg):
        self.log_view.append(msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ReceiverApp()
    window.show()
    sys.exit(app.exec())

