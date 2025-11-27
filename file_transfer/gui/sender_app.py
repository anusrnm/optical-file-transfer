import sys
import os
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QPushButton, QLabel, QFileDialog, 
                               QSlider, QProgressBar, QSizePolicy)
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QImage, QPixmap


# Import core logic
from file_transfer.core.manifest import build_manifest
from file_transfer.core.encoding_qr import manifest_to_qr_frames
from file_transfer.core.encoding_grid import encode_grid_frame
from file_transfer.core.chunking import iter_file_chunks, DEFAULT_CHUNK_SIZE

FRAME_PAYLOAD_SIZE = 544

class SenderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Optical File Transfer - Sender")
        self.setFixedSize(800, 600)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        # Top controls
        self.top_layout = QHBoxLayout()
        self.btn_select = QPushButton("Select File")
        self.btn_select.clicked.connect(self.select_file)
        self.lbl_file = QLabel("No file selected")
        
        self.btn_start = QPushButton("Start Transfer")
        self.btn_start.clicked.connect(self.start_transfer)
        self.btn_start.setEnabled(False)
        
        self.top_layout.addWidget(self.btn_select)
        self.top_layout.addWidget(self.btn_start)
        self.top_layout.addWidget(self.lbl_file)
        self.layout.addLayout(self.top_layout)
        
        # Image display
        self.lbl_display = QLabel()
        self.lbl_display.setAlignment(Qt.AlignCenter)
        self.lbl_display.setStyleSheet("background-color: #222; border: 2px solid #444;")
        self.lbl_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.layout.addWidget(self.lbl_display)
        
        # Playback controls
        self.controls_layout = QHBoxLayout()
        
        self.slider_fps = QSlider(Qt.Horizontal)
        self.slider_fps.setRange(1, 30)
        self.slider_fps.setValue(5)
        self.lbl_fps = QLabel("5 FPS")
        self.slider_fps.valueChanged.connect(lambda v: self.lbl_fps.setText(f"{v} FPS"))
        
        self.controls_layout.addWidget(QLabel("Speed:"))
        self.controls_layout.addWidget(self.slider_fps)
        self.controls_layout.addWidget(self.lbl_fps)
        self.layout.addLayout(self.controls_layout)
        
        # Progress
        self.progress = QProgressBar()
        self.layout.addWidget(self.progress)
        
        # State
        self.file_path = None
        self.frames = []  # List of (type, data/image)
        self.timer = QTimer()

        self.timer.timeout.connect(self.next_frame)
        self.current_frame_idx = 0
        self.is_running = False

    @Slot()
    def select_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File to Send")
        if path:
            self.file_path = path
            self.lbl_file.setText(os.path.basename(path))
            self.btn_start.setEnabled(True)
            self.prepare_frames()

    def prepare_frames(self):
        self.frames = []
        self.lbl_display.setText("Generating frames...")
        QApplication.processEvents()
        
        # 1. Manifest & QR
        manifest = build_manifest(self.file_path)
        for idx, qr in manifest_to_qr_frames(manifest):
            # Convert segno QR to PIL Image
            import io
            buff = io.BytesIO()
            qr.save(buff, kind='png', scale=10)
            buff.seek(0)
            from PIL import Image
            img = Image.open(buff)
            self.frames.append(img)
            
        # 2. Data Grid Frames
        frame_seq = 0
        with open(self.file_path, 'rb') as f:
            while True:
                data = f.read(FRAME_PAYLOAD_SIZE)
                if not data:
                    break
                img = encode_grid_frame(data, seq=frame_seq, chunk_idx=frame_seq)
                # No need to pre-scale here, we scale in next_frame to fit window
                self.frames.append(img)
                frame_seq += 1

                
        self.lbl_display.setText(f"Ready: {len(self.frames)} frames generated.")
        self.progress.setMaximum(len(self.frames))
        self.progress.setValue(0)

    @Slot()
    def start_transfer(self):
        if not self.frames:
            return
            
        if self.is_running:
            self.timer.stop()
            self.btn_start.setText("Resume Transfer")
            self.is_running = False
        else:
            fps = self.slider_fps.value()
            self.timer.start(1000 // fps)
            self.btn_start.setText("Pause Transfer")
            self.is_running = True

    def next_frame(self):
        if self.current_frame_idx >= len(self.frames):
            self.current_frame_idx = 0  # Loop or stop? Let's loop for now
            
        pil_img = self.frames[self.current_frame_idx]
        
        # Convert PIL to QPixmap
        data = pil_img.convert("RGBA").tobytes("raw", "RGBA")
        qimg = QImage(data, pil_img.width, pil_img.height, QImage.Format_RGBA8888)
        pixmap = QPixmap.fromImage(qimg)
        
        # Scale to fit label
        scaled_pixmap = pixmap.scaled(self.lbl_display.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.lbl_display.setPixmap(scaled_pixmap)
        self.progress.setValue(self.current_frame_idx + 1)
        
        self.current_frame_idx += 1

        
        # Update timer if FPS changed
        fps = self.slider_fps.value()
        self.timer.setInterval(1000 // fps)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SenderApp()
    window.show()
    sys.exit(app.exec())
