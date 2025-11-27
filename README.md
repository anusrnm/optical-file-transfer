# Optical File Transfer (Hybrid QR + Color Grid)

This project enables transferring arbitrary files/folders of any size using only a display (sender) and a camera (receiver) with **no network connection**. It begins with a robust QR bootstrap phase and escalates to a high‑density color grid encoding for improved throughput.

## Features
- **Hybrid Encoding**: Uses QR codes for reliable bootstrapping (manifest) and high-density Color Grids for data transfer.
- **Cross-Platform GUI**: Built with PySide6 (Qt) for Windows, Linux, and macOS.
- **Resumable**: Tracks received chunks; allows saving partial progress.
- **Integrity**: SHA-256 file hashing and CRC32 frame validation.
- **Scalable**: Handles large files by streaming chunks.

## Installation

1.  **Prerequisites**: Python 3.11+
2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    *(Includes: `PySide6`, `opencv-python`, `pillow`, `segno`, `pyzbar`, `numpy`, `cryptography`)*

## Usage

### GUI Applications (Recommended)

Launch the unified runner:

```bash
# Run Sender
python run_gui.py sender

# Run Receiver
python run_gui.py receiver
```

**Sender Workflow:**
1.  Select a file to transfer.
2.  The app generates QR frames (manifest) and Grid frames (data).
3.  Click **Start Transfer** to begin the slideshow.
4.  Adjust **Speed (FPS)** slider to match receiver capabilities.

**Receiver Workflow:**
1.  Click **Start Camera** and point at the Sender screen.
2.  The app automatically detects QR codes to load the manifest.
3.  Click **Decode Current Frame** (or enable auto-decode in future) to capture data frames.
4.  Watch the progress bar. When complete, click **Save File**.

### CLI Tools (Headless / Testing)

**Sender:**
```bash
python sender_cli.py --input <file_path> --out <output_folder>
```
Generates a sequence of PNG images (QR + Grid) into the output folder.

**Receiver:**
```bash
python receiver_cli.py --frames <input_folder> --out <output_folder>
```
Decodes a folder of captured/generated images and reconstructs the file.

## Architecture

- **Sender Pipeline**: File discovery → Manifest → Chunking → Frame encoding (QR/Grid) → Display.
- **Receiver Pipeline**: Camera capture → Frame detection → Decode → Reassembly → Integrity verification.
- **Frame Format**:
    - **QR**: Standard QR codes containing JSON manifest.
    - **Grid**: 64x36 symbol matrix (4-color palette) with embedded binary header (Seq ID, CRC32).

## Modules

| Module | Purpose |
|--------|---------|
| `file_transfer/core` | Shared logic (chunking, encoding, decoding, security). |
| `file_transfer/gui` | PySide6 GUI applications. |
| `spec/` | Protocol specifications. |

## Roadmap
- [x] Basic Chunking & Manifest
- [x] QR & Grid Encoding
- [x] Grid Decoding
- [x] Sender & Receiver GUI
- [ ] Automatic Frame Detection & Auto-Decode Loop
- [ ] Reed-Solomon FEC (currently simple parity)
- [ ] Advanced Color Calibration
- [ ] Encryption (AEAD)

## License
Unspecified.

