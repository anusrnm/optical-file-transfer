import sys
import argparse
from PySide6.QtWidgets import QApplication
from file_transfer.gui.sender_app import SenderApp
from file_transfer.gui.receiver_app import ReceiverApp

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=['sender', 'receiver'], help='Mode to run')
    args = parser.parse_args()
    
    app = QApplication(sys.argv)
    
    if args.mode == 'sender':
        window = SenderApp()
    else:
        window = ReceiverApp()
        
    window.show()
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
