import sys
import os
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, QVBoxLayout, QHBoxLayout, QWidget, QProgressBar, QFileDialog
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import yt_dlp

class DownloadThread(QThread):
    progress = pyqtSignal(float)
    status = pyqtSignal(str)
    finished_success = pyqtSignal()
    finished_error = pyqtSignal(str)

    def __init__(self, url, quality, audio_only, playlist, download_dir, parent=None):
        super().__init__(parent)
        self.url = url
        self.quality = quality
        self.audio_only = audio_only
        self.playlist = playlist
        self.downloads_dir = download_dir

    def run(self):
        def progress_hook(d):
            if d['status'] == 'downloading':
                if '_percent_str' in d:
                    percent_str = d['_percent_str'].strip()
                    if percent_str.endswith('%'):
                        try:
                            self.progress.emit(float(percent_str[:-1]) / 100)
                        except ValueError:
                            pass
                
                if 'speed' in d and d['speed'] and '_eta_str' in d:
                    speed = d['speed'] / 1024 / 1024  # Convert to MB/s
                    self.status.emit(f"Downloading: {speed:.2f} MB/s, ETA: {d['_eta_str']}")
                    
            elif d['status'] == 'finished':
                self.status.emit(f"Processing: {d.get('filename', 'file')}")

        try:
            # Format selection
            formats = {
                "4K": 'bestvideo[ext=mp4][height<=2160]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                "1080p": 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                "720p": 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                "480p": 'bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                "360p": 'bestvideo[ext=mp4][height<=360]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                "Audio Only": 'bestaudio[ext=m4a]/best'
            }
            format_str = formats.get(self.quality, 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best')
            
            ydl_opts = {
                'format': format_str,
                'merge_output_format': 'mp3' if self.audio_only else 'mp4',
                'outtmpl': os.path.join(self.downloads_dir, '%(title)s.%(ext)s'),
                'restrictfilenames': True,
                'noplaylist': not self.playlist,
                'progress_hooks': [progress_hook],
                'writethumbnail': True,
                'postprocessors': [
                    {'key': 'FFmpegMetadata'},
                    {'key': 'EmbedThumbnail'},
                ],
            }
            
            # If audio only, add audio extraction postprocessor
            if self.audio_only:
                ydl_opts['postprocessors'].append({
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([self.url])
            
            self.finished_success.emit()
        except Exception as e:
            self.finished_error.emit(str(e))


class YouTubeDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("YouTube Downloader")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        
        # Default download directory
        self.download_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        
        self.init_ui()
        
    def init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        # URL input
        url_layout = QHBoxLayout()
        url_label = QLabel("Enter YouTube URL:")
        self.url_input = QLineEdit()
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)
        
        # Quality selection
        quality_layout = QHBoxLayout()
        quality_label = QLabel("Quality:")
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["1080p", "720p", "480p", "360p", "4K", "Audio Only"])
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo)
        layout.addLayout(quality_layout)
        
        # Download directory selection
        dir_layout = QHBoxLayout()
        dir_label = QLabel("Save to:")
        self.dir_input = QLineEdit(self.download_dir)
        self.dir_input.setReadOnly(True)
        self.browse_btn = QPushButton("Browse...")
        self.browse_btn.clicked.connect(self.browse_folder)
        dir_layout.addWidget(dir_label)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.browse_btn)
        layout.addLayout(dir_layout)
        
        # Options
        options_layout = QHBoxLayout()
        self.audio_checkbox = QCheckBox("Extract Audio (MP3)")
        self.playlist_checkbox = QCheckBox("Download entire playlist")
        options_layout.addWidget(self.audio_checkbox)
        options_layout.addWidget(self.playlist_checkbox)
        layout.addLayout(options_layout)
        
        # Connect quality and audio checkboxes
        self.quality_combo.currentTextChanged.connect(self.on_quality_changed)
        
        # Download button
        self.download_btn = QPushButton("Download")
        self.download_btn.clicked.connect(self.start_download)
        layout.addWidget(self.download_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        
        # Status label
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        
        main_widget.setLayout(layout)
        self.setCentralWidget(main_widget)
    
    def browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Download Folder", self.download_dir)
        if folder:
            self.download_dir = folder
            self.dir_input.setText(folder)
    
    def on_quality_changed(self, quality):
        if quality == "Audio Only":
            self.audio_checkbox.setChecked(True)
            self.audio_checkbox.setEnabled(False)
        else:
            self.audio_checkbox.setEnabled(True)
    
    def start_download(self):
        url = self.url_input.text().strip()
        if not url:
            self.status_label.setText("Please enter a YouTube URL")
            return
        
        quality = self.quality_combo.currentText()
        audio_only = self.audio_checkbox.isChecked()
        playlist = self.playlist_checkbox.isChecked()
        
        # Disable the download button during download
        self.download_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        
        # Create and start the download thread
        self.download_thread = DownloadThread(url, quality, audio_only, playlist, self.download_dir)
        self.download_thread.progress.connect(self.update_progress)
        self.download_thread.status.connect(self.update_status)
        self.download_thread.finished_success.connect(self.download_finished)
        self.download_thread.finished_error.connect(self.download_error)
        self.download_thread.start()
    
    def update_progress(self, value):
        self.progress_bar.setValue(int(value * 100))
    
    def update_status(self, message):
        self.status_label.setText(message)
    
    def download_finished(self):
        self.status_label.setText("Download completed successfully!")
        self.progress_bar.setValue(100)
        self.download_btn.setEnabled(True)
    
    def download_error(self, error):
        self.status_label.setText(f"Error: {error}")
        self.download_btn.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = YouTubeDownloader()
    window.show()
    sys.exit(app.exec_())