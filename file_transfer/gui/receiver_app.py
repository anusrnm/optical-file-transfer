import sys
import os
import cv2
import numpy as np
import json
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QProgressBar, QTextEdit, QMessageBox)
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QImage, QPixmap
from PIL import Image
from pyzbar.pyzbar import decode as decode_qr

from file_transfer.core.decoding_grid import decode_grid_image


class ReceiverApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Optical File Transfer - Receiver")
        self.resize(900, 700)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # Video feed
        self.lbl_video = QLabel("Camera Feed")
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
        self.received_chunks = {}
        self.manifest = None
        self.expected_chunks = 0
        self.is_camera_active = False


    @Slot()
    def load_file_frame(self):
        from PySide6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(self, "Select Frame Image", "", "Images (*.png *.jpg)")
        if path:
            pil_img = Image.open(path)
            # Display it
            qimg = QImage(path)
            self.lbl_video.setPixmap(QPixmap.fromImage(qimg).scaled(self.lbl_video.size(), Qt.KeepAspectRatio))
            
            # Decode
            result = decode_grid_image(pil_img)
            if result:
                header, payload = result
                seq = header['seq']
                self.log(f"Decoded Frame #{seq} from file")
                if seq not in self.received_chunks:
                    self.received_chunks[seq] = payload
                    self.update_progress()
            else:
                self.log(f"Failed to decode {os.path.basename(path)}")

    @Slot()
    def toggle_camera(self):

        if self.is_camera_active:
            self.timer.stop()
            if self.cap:
                self.cap.release()
            self.lbl_video.setText("Camera Stopped")
            self.btn_camera.setText("Start Camera")
            self.is_camera_active = False
        else:
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                self.log("Failed to open camera")
                return
            self.timer.start(33)  # ~30 FPS
            self.btn_camera.setText("Stop Camera")
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

    @Slot()
    def manual_decode(self):
        if self.current_frame_cv is None:
            self.log("No frame to decode")
            return
            
        # Convert to PIL
        rgb_frame = cv2.cvtColor(self.current_frame_cv, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_frame)
        
        # 1. Try QR Decode (Manifest)
        decoded_qrs = decode_qr(pil_img)
        if decoded_qrs:
            for qr in decoded_qrs:
                try:
                    data = qr.data.decode('utf-8')
                    # Check if it looks like manifest JSON
                    if '"files":' in data and '"total_chunks":' in data:
                        self.manifest = json.loads(data)
                        self.expected_chunks = self.manifest.get('total_chunks', 0)
                        self.log(f"Manifest loaded! Expecting {self.expected_chunks} chunks.")
                        self.progress.setMaximum(self.expected_chunks)
                        self.update_progress()
                        return # Found manifest, stop
                except Exception as e:
                    self.log(f"QR decode error: {e}")

        # 2. Try Grid Decode
        result = decode_grid_image(pil_img)
        if result:
            header, payload = result
            seq = header['seq']
            self.log(f"Decoded Frame #{seq} (len={len(payload)})")
            if seq not in self.received_chunks:
                self.received_chunks[seq] = payload
                self.update_progress()
        else:
            self.log("Decode failed (alignment?)")

    @Slot()
    def save_file(self):
        if not self.received_chunks:
            return
            
        from PySide6.QtWidgets import QFileDialog
        default_name = "reconstructed.bin"
        if self.manifest and self.manifest.get('files'):
            default_name = self.manifest['files'][0]['path']
            
        path, _ = QFileDialog.getSaveFileName(self, "Save Reconstructed File", default_name)
        if path:
            sorted_seqs = sorted(self.received_chunks.keys())
            with open(path, 'wb') as f:
                for seq in sorted_seqs:
                    f.write(self.received_chunks[seq])
            self.log(f"Saved to {path}")
            QMessageBox.information(self, "Success", f"File saved to {path}")

    def update_progress(self):
        count = len(self.received_chunks)
        if self.expected_chunks > 0:
            self.lbl_status.setText(f"Received: {count} / {self.expected_chunks}")
            self.progress.setValue(count)
            if count >= self.expected_chunks:
                self.btn_save.setEnabled(True)
        else:
            self.lbl_status.setText(f"Received: {count} chunks")
            self.progress.setValue(count % 100)
            self.btn_save.setEnabled(count > 0)

    def log(self, msg):
        self.log_view.append(msg)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ReceiverApp()
    window.show()
    sys.exit(app.exec())

