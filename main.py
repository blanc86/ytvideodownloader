import sys
import os
import re
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox, QVBoxLayout, QHBoxLayout, QWidget, QProgressBar, QFileDialog, QMessageBox, QGroupBox
from PyQt5.QtCore import Qt, QThread, pyqtSignal
import yt_dlp

class DownloadThread(QThread):
    progress = pyqtSignal(float)
    status = pyqtSignal(str)
    finished_success = pyqtSignal()
    finished_error = pyqtSignal(str)

    def __init__(self, url, quality, audio_only, playlist, download_dir, platform, custom_filename=None, parent=None):
        super().__init__(parent)
        self.url = url
        self.quality = quality
        self.audio_only = audio_only
        self.playlist = playlist
        self.downloads_dir = download_dir
        self.platform = platform
        self.custom_filename = custom_filename

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
            # Determine output template based on whether a custom filename is provided
            if self.custom_filename:
                # If playlist, we need to keep index to prevent filename conflicts
                if self.playlist:
                    output_template = os.path.join(self.downloads_dir, f"{self.custom_filename}_%(playlist_index)s.%(ext)s")
                else:
                    output_template = os.path.join(self.downloads_dir, f"{self.custom_filename}.%(ext)s")
            else:
                output_template = os.path.join(self.downloads_dir, '%(title)s.%(ext)s')

            # Common options for all platforms
            ydl_opts = {
                'outtmpl': output_template,
                'restrictfilenames': True,
                'progress_hooks': [progress_hook],
                'writethumbnail': True,
                'postprocessors': [
                    {'key': 'FFmpegMetadata'},
                    {'key': 'EmbedThumbnail'},
                ],
            }
            
            # Platform-specific options
            if self.platform == "youtube":
                # Format selection for YouTube
                formats = {
                    "4K": 'bestvideo[ext=mp4][height<=2160]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    "1080p": 'bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    "720p": 'bestvideo[ext=mp4][height<=720]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    "480p": 'bestvideo[ext=mp4][height<=480]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    "360p": 'bestvideo[ext=mp4][height<=360]+bestaudio[ext=m4a]/best[ext=mp4]/best',
                    "Audio Only": 'bestaudio[ext=m4a]/best'
                }
                format_str = formats.get(self.quality, 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best')
                ydl_opts['format'] = format_str
                ydl_opts['noplaylist'] = not self.playlist
            
            elif self.platform == "instagram":
                # Instagram usually has limited format options
                ydl_opts['format'] = 'best'
            
            elif self.platform == "reddit":
                # Reddit usually has limited format options
                ydl_opts['format'] = 'best'
            
            # Set output format based on audio_only
            ydl_opts['merge_output_format'] = 'mp3' if self.audio_only else 'mp4'
            
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


class MultiPlatformDownloader(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Multi-Platform Video Downloader")
        self.setMinimumWidth(650)
        self.setMinimumHeight(400)
        
        # Default download directory
        self.download_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        
        self.init_ui()
        
    def init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout()
        
        # URL input
        url_layout = QHBoxLayout()
        url_label = QLabel("Enter URL:")
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("YouTube, Instagram or Reddit URL")
        self.url_input.textChanged.connect(self.detect_platform)
        url_layout.addWidget(url_label)
        url_layout.addWidget(self.url_input)
        layout.addLayout(url_layout)

        # Platform indicator
        platform_layout = QHBoxLayout()
        platform_label = QLabel("Platform:")
        self.platform_indicator = QLabel("Not detected")
        platform_layout.addWidget(platform_label)
        platform_layout.addWidget(self.platform_indicator)
        layout.addLayout(platform_layout)
        
        # Custom filename option
        filename_group = QGroupBox("File Naming")
        filename_layout = QVBoxLayout()
        
        # Radio buttons for naming option
        naming_layout = QHBoxLayout()
        self.default_name_radio = QCheckBox("Use default name")
        self.custom_name_radio = QCheckBox("Use custom name:")
        self.default_name_radio.setChecked(True)
        self.custom_filename_input = QLineEdit()
        self.custom_filename_input.setPlaceholderText("Enter custom filename (without extension)")
        self.custom_filename_input.setEnabled(False)
        
        naming_layout.addWidget(self.default_name_radio)
        naming_layout.addWidget(self.custom_name_radio)
        filename_layout.addLayout(naming_layout)
        filename_layout.addWidget(self.custom_filename_input)
        
        # Connect radio buttons
        self.default_name_radio.clicked.connect(self.toggle_filename_options)
        self.custom_name_radio.clicked.connect(self.toggle_filename_options)
        
        filename_group.setLayout(filename_layout)
        layout.addWidget(filename_group)
        
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
    
    def toggle_filename_options(self):
        if self.sender() == self.default_name_radio:
            self.default_name_radio.setChecked(True)
            self.custom_name_radio.setChecked(False)
            self.custom_filename_input.setEnabled(False)
        else:  # Custom name radio
            self.default_name_radio.setChecked(False)
            self.custom_name_radio.setChecked(True)
            self.custom_filename_input.setEnabled(True)
            self.custom_filename_input.setFocus()
    
    def detect_platform(self):
        url = self.url_input.text().strip()
        
        if not url:
            self.platform_indicator.setText("Not detected")
            return "unknown"
        
        # YouTube URL patterns
        youtube_patterns = [
            r'(?:https?://)?(?:www\.)?youtube\.com/watch\?v=[\w-]+',
            r'(?:https?://)?(?:www\.)?youtu\.be/[\w-]+',
            r'(?:https?://)?(?:www\.)?youtube\.com/shorts/[\w-]+'
        ]
        
        # Instagram URL patterns
        instagram_patterns = [
            r'(?:https?://)?(?:www\.)?instagram\.com/p/[\w-]+',
            r'(?:https?://)?(?:www\.)?instagram\.com/reel/[\w-]+',
            r'(?:https?://)?(?:www\.)?instagram\.com/tv/[\w-]+'
        ]
        
        # Reddit URL patterns
        reddit_patterns = [
            r'(?:https?://)?(?:www\.)?reddit\.com/r/[\w-]+/comments/[\w-]+',
            r'(?:https?://)?(?:www\.)?v\.redd\.it/[\w-]+'
        ]
        
        for pattern in youtube_patterns:
            if re.match(pattern, url):
                self.platform_indicator.setText("YouTube")
                self.quality_combo.setEnabled(True)
                self.playlist_checkbox.setEnabled(True)
                return "youtube"
        
        for pattern in instagram_patterns:
            if re.match(pattern, url):
                self.platform_indicator.setText("Instagram")
                self.quality_combo.setEnabled(False)
                self.playlist_checkbox.setEnabled(False)
                return "instagram"
        
        for pattern in reddit_patterns:
            if re.match(pattern, url):
                self.platform_indicator.setText("Reddit")
                self.quality_combo.setEnabled(False)
                self.playlist_checkbox.setEnabled(False)
                return "reddit"
        
        self.platform_indicator.setText("Unknown")
        return "unknown"
    
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
            self.status_label.setText("Please enter a URL")
            return
        
        platform = self.detect_platform()
        if platform == "unknown":
            QMessageBox.warning(self, "Unsupported URL", 
                               "The URL format is not recognized. Please enter a valid YouTube, Instagram, or Reddit URL.")
            return
        
        # Get custom filename if enabled
        custom_filename = None
        if self.custom_name_radio.isChecked():
            custom_filename = self.custom_filename_input.text().strip()
            if not custom_filename:
                QMessageBox.warning(self, "Filename Required", 
                                   "Please enter a custom filename or select 'Use default name'.")
                return
            
            # Remove illegal characters from filename
            custom_filename = re.sub(r'[\\/*?:"<>|]', "", custom_filename)
        
        quality = self.quality_combo.currentText()
        audio_only = self.audio_checkbox.isChecked()
        playlist = self.playlist_checkbox.isChecked() and platform == "youtube"
        
        # Disable the download button during download
        self.download_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        
        # Create and start the download thread
        self.download_thread = DownloadThread(
            url, quality, audio_only, playlist, self.download_dir, platform, custom_filename
        )
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
    window = MultiPlatformDownloader()
    window.show()
    sys.exit(app.exec_())