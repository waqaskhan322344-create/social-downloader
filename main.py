"""
Social Media Downloader Pro v4.0
Complete Android App with Playlist Support
Fully Fixed for AAB/APK Build
"""

import os
import sys
import threading
import queue
import re
from datetime import datetime

# ==================== ANDROID PATH FIX (MUST BE FIRST) ====================
# This ensures the app works correctly on Android devices

# Set download paths based on platform
if hasattr(sys, 'android') or 'android' in sys.platform:
    # Running on Android
    try:
        from android.permissions import request_permissions, Permission
        from android.storage import primary_external_storage_path
        
        # Request all needed permissions at startup
        request_permissions([
            Permission.INTERNET,
            Permission.WRITE_EXTERNAL_STORAGE,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.ACCESS_NETWORK_STATE,
            Permission.ACCESS_WIFI_STATE
        ])
        
        # Get proper storage paths
        DOWNLOAD_DIR = primary_external_storage_path() + '/Download'
        SOCIAL_DIR = DOWNLOAD_DIR + '/SocialMedia'
    except:
        # Fallback paths if imports fail
        DOWNLOAD_DIR = '/storage/emulated/0/Download'
        SOCIAL_DIR = '/storage/emulated/0/Download/SocialMedia'
else:
    # Running on Windows/Linux for testing
    DOWNLOAD_DIR = os.path.expanduser('~/Downloads')
    SOCIAL_DIR = os.path.expanduser('~/Downloads/SocialMedia')

# Create directories
try:
    os.makedirs(SOCIAL_DIR, exist_ok=True)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
except:
    pass

# ==================== KIVY IMPORTS ====================
import kivy
kivy.require('2.2.0')

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.clipboard import Clipboard
from kivy.metrics import dp
from kivy.utils import platform
from kivy.graphics import Color, RoundedRectangle
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.spinner import Spinner
from kivy.uix.checkbox import CheckBox
from kivy.uix.switch import Switch
from kivy.storage.jsonstore import JsonStore

# ==================== YT-DLP IMPORT ====================
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    YTDLP_AVAILABLE = False
    print("WARNING: yt-dlp not available")

# Suppress warnings
import warnings
warnings.filterwarnings('ignore')


# ==================== CUSTOM WIDGETS ====================

class RoundedButton(Button):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ''
        self.background_down = ''
        self.bind(pos=self.update_canvas, size=self.update_canvas)
        Clock.schedule_once(self.update_canvas, 0)
    
    def update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0.2, 0.6, 0.86, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])


class RoundedTextInput(TextInput):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_color = (0.15, 0.15, 0.15, 1)
        self.foreground_color = (1, 1, 1, 1)
        self.cursor_color = (0.2, 0.6, 0.86, 1)
        self.padding = [dp(15), dp(10), dp(15), dp(10)]
        self.size_hint_y = None
        self.height = dp(50)


class Card(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = dp(15)
        self.spacing = dp(10)
        self.size_hint_y = None
        self.bind(minimum_height=self.setter('height'))
        Clock.schedule_once(self.update_rect, 0)
    
    def update_rect(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(0.12, 0.12, 0.12, 1)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])


# ==================== MAIN DOWNLOADER SCREEN ====================

class DownloaderScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.queue = queue.Queue()
        self.is_downloading = False
        self.current_video_info = None
        self.playlist_info = None
        self.current_playlist_index = 0
        self.playlist_total = 0
        self.cancel_download_flag = False
        
        # Main layout
        main_layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        
        # Scrollable content
        scroll = ScrollView()
        content = BoxLayout(orientation='vertical', size_hint_y=None, spacing=dp(10))
        content.bind(minimum_height=content.setter('height'))
        
        # Platform Selector Card
        platform_card = Card()
        platform_label = Label(text='Platform', size_hint_y=None, height=dp(30), 
                               color=(1, 1, 1, 1), font_size=dp(16), bold=True)
        platform_card.add_widget(platform_label)
        
        platform_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        self.platform_spinner = Spinner(
            text='Auto-Detect',
            values=('Auto-Detect', 'YouTube', 'TikTok', 'Instagram', 'Facebook'),
            size_hint=(0.8, 1),
            background_color=(0.2, 0.6, 0.86, 1),
            color=(1, 1, 1, 1)
        )
        platform_layout.add_widget(self.platform_spinner)
        platform_card.add_widget(platform_layout)
        content.add_widget(platform_card)
        
        # URL Input Card
        url_card = Card()
        url_label = Label(text='Video/Playlist URL', size_hint_y=None, height=dp(30),
                         color=(1, 1, 1, 1), font_size=dp(16), bold=True)
        url_card.add_widget(url_label)
        
        self.url_input = RoundedTextInput(hint_text='Paste video or playlist URL here...', multiline=False)
        url_card.add_widget(self.url_input)
        
        # Buttons row
        button_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        self.fetch_btn = RoundedButton(text='Fetch Info', on_press=self.fetch_info)
        paste_btn = RoundedButton(text='Paste', on_press=self.paste_url)
        clear_btn = RoundedButton(text='Clear', on_press=self.clear_url)
        
        button_layout.add_widget(self.fetch_btn)
        button_layout.add_widget(paste_btn)
        button_layout.add_widget(clear_btn)
        url_card.add_widget(button_layout)
        content.add_widget(url_card)
        
        # Playlist Range Card
        playlist_range_card = Card()
        playlist_range_label = Label(text='Playlist Range', size_hint_y=None, height=dp(30),
                                     color=(1, 1, 1, 1), font_size=dp(16), bold=True)
        playlist_range_card.add_widget(playlist_range_label)
        
        range_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        range_layout.add_widget(Label(text='From:', color=(1, 1, 1, 1), size_hint_x=0.15))
        self.playlist_start = TextInput(text='1', multiline=False, size_hint_x=0.2, 
                                        background_color=(0.15, 0.15, 0.15, 1), 
                                        foreground_color=(1, 1, 1, 1))
        range_layout.add_widget(self.playlist_start)
        range_layout.add_widget(Label(text='To:', color=(1, 1, 1, 1), size_hint_x=0.15))
        self.playlist_end = TextInput(text='all', multiline=False, size_hint_x=0.2,
                                      background_color=(0.15, 0.15, 0.15, 1), 
                                      foreground_color=(1, 1, 1, 1))
        range_layout.add_widget(self.playlist_end)
        range_layout.add_widget(Label(text='', size_hint_x=0.3))
        playlist_range_card.add_widget(range_layout)
        content.add_widget(playlist_range_card)
        
        # Video Info Card
        info_card = Card()
        info_label = Label(text='Content Information', size_hint_y=None, height=dp(30),
                          color=(1, 1, 1, 1), font_size=dp(16), bold=True)
        info_card.add_widget(info_label)
        
        self.info_text = Label(text='No content loaded', size_hint_y=None, 
                               color=(0.7, 0.7, 0.7, 1), font_size=dp(12),
                               halign='left', valign='top')
        self.info_text.bind(size=self.info_text.setter('text_size'))
        info_card.add_widget(self.info_text)
        content.add_widget(info_card)
        
        # Playlist Progress Card
        self.playlist_progress_card = Card()
        self.playlist_progress_label = Label(text='Playlist Progress', size_hint_y=None, height=dp(30),
                                             color=(1, 1, 1, 1), font_size=dp(16), bold=True)
        self.playlist_progress_card.add_widget(self.playlist_progress_label)
        
        self.playlist_progress_bar = ProgressBar(value=0, size_hint_y=None, height=dp(20))
        self.playlist_progress_card.add_widget(self.playlist_progress_bar)
        
        self.playlist_status_label = Label(text='', color=(0.7, 0.7, 0.7, 1), 
                                           size_hint_y=None, height=dp(25))
        self.playlist_progress_card.add_widget(self.playlist_status_label)
        content.add_widget(self.playlist_progress_card)
        
        # Quality Selection Card
        quality_card = Card()
        quality_label = Label(text='Quality Options', size_hint_y=None, height=dp(30),
                             color=(1, 1, 1, 1), font_size=dp(16), bold=True)
        quality_card.add_widget(quality_label)
        
        quality_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        quality_layout.add_widget(Label(text='Quality:', size_hint_x=0.3, color=(1, 1, 1, 1)))
        self.quality_spinner = Spinner(
            text='Best Quality',
            values=('Best Quality', '1080p', '720p', '480p', '360p', 'Audio Only'),
            size_hint=(0.7, 1),
            background_color=(0.2, 0.6, 0.86, 1),
            color=(1, 1, 1, 1)
        )
        quality_layout.add_widget(self.quality_spinner)
        quality_card.add_widget(quality_layout)
        content.add_widget(quality_card)
        
        # Save Location Card
        save_card = Card()
        save_label = Label(text='Save Location', size_hint_y=None, height=dp(30),
                          color=(1, 1, 1, 1), font_size=dp(16), bold=True)
        save_card.add_widget(save_label)
        
        save_type_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        save_type_layout.add_widget(Label(text='Save to:', size_hint_x=0.3, color=(1, 1, 1, 1)))
        self.save_location_spinner = Spinner(
            text='Social Media Folder',
            values=('Social Media Folder', 'Downloads Folder'),
            size_hint=(0.7, 1),
            background_color=(0.2, 0.6, 0.86, 1),
            color=(1, 1, 1, 1)
        )
        save_type_layout.add_widget(self.save_location_spinner)
        save_card.add_widget(save_type_layout)
        
        self.path_display = Label(text=f"Save path: {SOCIAL_DIR}", 
                                  color=(0.7, 0.7, 0.7, 1), size_hint_y=None, height=dp(30),
                                  font_size=dp(10))
        save_card.add_widget(self.path_display)
        content.add_widget(save_card)
        
        # Options Card
        options_card = Card()
        options_label = Label(text='Additional Options', size_hint_y=None, height=dp(30),
                             color=(1, 1, 1, 1), font_size=dp(16), bold=True)
        options_card.add_widget(options_label)
        
        # Playlist option
        playlist_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
        self.playlist_check = CheckBox(size_hint_x=0.1, active=True)
        playlist_layout.add_widget(self.playlist_check)
        playlist_layout.add_widget(Label(text='Download playlist (if available)', 
                                         size_hint_x=0.9, color=(1, 1, 1, 1)))
        options_card.add_widget(playlist_layout)
        
        # Organize by platform
        organize_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
        self.organize_check = CheckBox(size_hint_x=0.1, active=True)
        organize_layout.add_widget(self.organize_check)
        organize_layout.add_widget(Label(text='Organize by platform', 
                                         size_hint_x=0.9, color=(1, 1, 1, 1)))
        options_card.add_widget(organize_layout)
        
        # Create playlist folder
        playlist_folder_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=dp(10))
        self.playlist_folder_check = CheckBox(size_hint_x=0.1, active=True)
        playlist_folder_layout.add_widget(self.playlist_folder_check)
        playlist_folder_layout.add_widget(Label(text='Create playlist folder', 
                                                size_hint_x=0.9, color=(1, 1, 1, 1)))
        options_card.add_widget(playlist_folder_layout)
        
        content.add_widget(options_card)
        
        # Download Button
        self.download_btn = RoundedButton(text='START DOWNLOAD', size_hint_y=None, height=dp(60),
                                          on_press=self.start_download, disabled=True)
        content.add_widget(self.download_btn)
        
        # Cancel Button
        self.cancel_btn = RoundedButton(text='Cancel Download', size_hint_y=None, height=dp(50),
                                        on_press=self.cancel_download, disabled=True)
        content.add_widget(self.cancel_btn)
        
        # Progress Section
        progress_card = Card()
        progress_label = Label(text='Download Progress', size_hint_y=None, height=dp(30),
                              color=(1, 1, 1, 1), font_size=dp(16), bold=True)
        progress_card.add_widget(progress_label)
        
        self.percentage_label = Label(text='0%', size_hint_y=None, height=dp(40),
                                      color=(0.2, 0.6, 0.86, 1), font_size=dp(24), bold=True)
        progress_card.add_widget(self.percentage_label)
        
        self.progress_bar = ProgressBar(value=0, size_hint_y=None, height=dp(20))
        progress_card.add_widget(self.progress_bar)
        
        # Stats layout
        stats_layout = BoxLayout(orientation='vertical', spacing=dp(5))
        self.size_label = Label(text='0 MB / 0 MB', color=(0.7, 0.7, 0.7, 1), 
                                size_hint_y=None, height=dp(25))
        self.speed_label = Label(text='Speed: 0 KB/s', color=(0.7, 0.7, 0.7, 1), 
                                 size_hint_y=None, height=dp(25))
        self.eta_label = Label(text='ETA: --:--', color=(0.7, 0.7, 0.7, 1), 
                               size_hint_y=None, height=dp(25))
        self.status_label = Label(text='Ready', color=(0.4, 0.8, 0.4, 1), 
                                  size_hint_y=None, height=dp(25))
        
        stats_layout.add_widget(self.size_label)
        stats_layout.add_widget(self.speed_label)
        stats_layout.add_widget(self.eta_label)
        stats_layout.add_widget(self.status_label)
        progress_card.add_widget(stats_layout)
        content.add_widget(progress_card)
        
        scroll.add_widget(content)
        main_layout.add_widget(scroll)
        
        # Bottom status bar
        status_bar = BoxLayout(size_hint_y=None, height=dp(30), padding=dp(10))
        with status_bar.canvas.before:
            Color(0.08, 0.08, 0.08, 1)
            RoundedRectangle(pos=status_bar.pos, size=status_bar.size)
        
        self.status_bar_label = Label(text='Ready', color=(0.7, 0.7, 0.7, 1), size_hint_x=0.7)
        self.platform_indicator = Label(text='', color=(0.2, 0.6, 0.86, 1), size_hint_x=0.3)
        status_bar.add_widget(self.status_bar_label)
        status_bar.add_widget(self.platform_indicator)
        main_layout.add_widget(status_bar)
        
        self.add_widget(main_layout)
        
        # Start queue processing
        Clock.schedule_interval(self.process_queue, 0.1)
        
        # Bind save location change
        self.save_location_spinner.bind(text=self.on_save_location_change)
        
        # Hide playlist progress card initially
        self.playlist_progress_card.opacity = 0
        self.playlist_progress_card.disabled = True
    
    def on_save_location_change(self, spinner, text):
        """Handle save location change"""
        if text == 'Social Media Folder':
            self.path_display.text = f"Save path: {SOCIAL_DIR}"
        else:
            self.path_display.text = f"Save path: {DOWNLOAD_DIR}"
    
    def get_current_save_path(self):
        """Get current save path based on selection"""
        if self.save_location_spinner.text == 'Social Media Folder':
            return SOCIAL_DIR
        else:
            return DOWNLOAD_DIR
    
    def get_platform_subfolder(self, platform_name):
        """Get platform-specific subfolder"""
        if not self.organize_check.active:
            return ""
        
        platform_map = {
            'YouTube': 'YouTube',
            'TikTok': 'TikTok',
            'Instagram': 'Instagram',
            'Facebook': 'Facebook'
        }
        return platform_map.get(platform_name, 'Other')
    
    def cancel_download(self, instance):
        """Cancel ongoing download"""
        self.cancel_download_flag = True
        self.show_message('Cancelling download...', 'warning')
    
    def paste_url(self, instance):
        """Paste from clipboard"""
        try:
            clipboard_text = Clipboard.paste()
            if clipboard_text:
                self.url_input.text = clipboard_text
                self.show_message('URL pasted successfully!', 'success')
        except Exception as e:
            self.show_message('Could not paste from clipboard', 'error')
    
    def clear_url(self, instance):
        """Clear URL input"""
        self.url_input.text = ''
        self.info_text.text = 'No content loaded'
        self.download_btn.disabled = True
        self.playlist_info = None
        self.current_video_info = None
    
    def fetch_info(self, instance):
        """Fetch video/playlist information"""
        url = self.url_input.text.strip()
        if not url:
            self.show_message('Please enter a URL', 'error')
            return
        
        if not YTDLP_AVAILABLE:
            self.show_message('yt-dlp not available. Please reinstall app.', 'error')
            return
        
        self.fetch_btn.disabled = True
        self.fetch_btn.text = 'Fetching...'
        self.info_text.text = 'Fetching content information...'
        self.download_btn.disabled = True
        
        # Detect platform
        platform_type = self.detect_platform(url)
        self.platform_indicator.text = f'{platform_type}'
        
        # Start fetching thread
        thread = threading.Thread(target=self.fetch_info_thread, args=(url,))
        thread.daemon = True
        thread.start()
    
    def detect_platform(self, url):
        """Detect platform from URL"""
        url_lower = url.lower()
        
        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'YouTube'
        elif 'tiktok.com' in url_lower:
            return 'TikTok'
        elif 'instagram.com' in url_lower or 'instagr.am' in url_lower:
            return 'Instagram'
        elif 'facebook.com' in url_lower or 'fb.com' in url_lower or 'fb.watch' in url_lower:
            return 'Facebook'
        else:
            return 'Unknown'
    
    def parse_playlist_range(self):
        """Parse playlist range from input"""
        start_str = self.playlist_start.text.strip()
        end_str = self.playlist_end.text.strip()
        
        try:
            start = int(start_str) if start_str and start_str != '' else 1
        except:
            start = 1
        
        if end_str.lower() == 'all' or end_str == '':
            end = None
        else:
            try:
                end = int(end_str)
            except:
                end = None
        
        return start, end
    
    def fetch_info_thread(self, url):
        """Thread to fetch video/playlist info"""
        try:
            # Base options for all platforms
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': True,
                'ignoreerrors': True,
                'no_check_certificate': True,
                'prefer_insecure': True,
                'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                }
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if info is None:
                    self.queue.put(('error', 'Could not extract information. URL might be invalid.'))
                    return
                
                # Check if it's a playlist
                if 'entries' in info and info['entries'] and len(info['entries']) > 1:
                    # It's a playlist
                    playlist_title = info.get('title', 'Unknown Playlist')
                    video_count = len(info['entries'])
                    
                    # Get playlist range
                    start_idx, end_idx = self.parse_playlist_range()
                    start_idx = max(1, start_idx) - 1
                    if end_idx is not None:
                        end_idx = min(end_idx, video_count)
                    else:
                        end_idx = video_count
                    
                    entries = info['entries'][start_idx:end_idx]
                    filtered_count = len(entries)
                    
                    self.playlist_info = {
                        'title': playlist_title,
                        'total': video_count,
                        'filtered_total': filtered_count,
                        'start': start_idx + 1,
                        'end': end_idx,
                        'entries': entries,
                        'url': url
                    }
                    
                    info_text = f"PLAYLIST: {playlist_title}\n"
                    info_text += f"Total videos: {video_count}\n"
                    info_text += f"Downloading: {filtered_count} videos (from {start_idx+1} to {end_idx})\n"
                    info_text += f"Platform: {self.detect_platform(url)}\n"
                    
                    self.current_video_info = info
                    self.queue.put(('info', info_text))
                    self.queue.put(('enable_download', True))
                    self.queue.put(('playlist_detected', filtered_count))
                    
                else:
                    # Single video
                    entry = info.get('entries', [info])[0] if info.get('entries') else info
                    self.process_single_video(entry, self.detect_platform(url))
                
        except Exception as e:
            error_msg = f"Failed to fetch info: {str(e)[:200]}"
            self.queue.put(('error', error_msg))
        finally:
            self.queue.put(('fetch_done', None))
    
    def process_single_video(self, info, platform):
        """Process single video information"""
        title = info.get('title', 'Unknown Title')
        if isinstance(title, bytes):
            title = title.decode('utf-8', errors='ignore')
        
        duration = info.get('duration', 0)
        uploader = info.get('uploader', 'Unknown')
        
        # Format duration
        if duration and duration > 0:
            minutes = int(duration // 60)
            seconds = int(duration % 60)
            duration_str = f"{minutes}:{seconds:02d}"
        else:
            duration_str = "Unknown"
        
        info_text = f"Title: {title[:80]}\n"
        info_text += f"Uploader: {uploader}\n"
        info_text += f"Duration: {duration_str}\n"
        info_text += f"Platform: {platform}"
        
        self.current_video_info = info
        self.playlist_info = None
        
        self.queue.put(('info', info_text))
        self.queue.put(('enable_download', True))
    
    def start_download(self, instance):
        """Start download process"""
        if self.is_downloading:
            self.show_message('Download already in progress', 'warning')
            return
        
        if not self.current_video_info:
            self.show_message('Please fetch content info first', 'error')
            return
        
        url = self.url_input.text.strip()
        self.cancel_download_flag = False
        
        # Get save path
        base_save_path = self.get_current_save_path()
        platform_name = self.detect_platform(url)
        platform_folder = self.get_platform_subfolder(platform_name)
        
        if platform_folder:
            save_path = os.path.join(base_save_path, platform_folder)
        else:
            save_path = base_save_path
        
        # If it's a playlist and playlist folder option is enabled
        if self.playlist_info and self.playlist_folder_check.active:
            safe_playlist_title = self.sanitize_filename(self.playlist_info['title'])
            save_path = os.path.join(save_path, safe_playlist_title)
        
        # Ensure save path exists
        try:
            os.makedirs(save_path, exist_ok=True)
            self.status_bar_label.text = f"Saving to: {save_path}"
        except Exception as e:
            self.show_message(f'Could not create save folder: {str(e)}', 'error')
            return
        
        # Quality mapping
        quality_map = {
            'Best Quality': 'best[ext=mp4]/best',
            '1080p': 'best[height<=1080][ext=mp4]/best[height<=1080]',
            '720p': 'best[height<=720][ext=mp4]/best[height<=720]',
            '480p': 'best[height<=480][ext=mp4]/best[height<=480]',
            '360p': 'best[height<=360][ext=mp4]/best[height<=360]',
            'Audio Only': 'bestaudio/best'
        }
        
        quality = quality_map.get(self.quality_spinner.text, 'best[ext=mp4]/best')
        is_audio = self.quality_spinner.text == 'Audio Only'
        
        # Output template
        if self.playlist_info and self.playlist_folder_check.active:
            output_template = os.path.join(save_path, '%(playlist_index)02d - %(title)s.%(ext)s')
        else:
            output_template = os.path.join(save_path, '%(title)s_%(id)s.%(ext)s')
        
        # yt-dlp options
        ydl_opts = {
            'outtmpl': output_template,
            'quiet': True,
            'no_warnings': True,
            'no_check_certificate': True,
            'prefer_insecure': True,
            'noplaylist': not (self.playlist_info and self.playlist_check.active),
            'progress_hooks': [self.progress_hook],
            'ignoreerrors': True,
            'retries': 5,
            'fragment_retries': 5,
            'restrictfilenames': True,
            'format': quality,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }
        
        # Audio-only handling
        if is_audio:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }]
        
        self.is_downloading = True
        self.download_btn.disabled = True
        self.cancel_btn.disabled = False
        self.download_btn.text = 'Downloading...'
        self.status_label.text = 'Downloading...'
        self.status_label.color = (0.9, 0.5, 0.2, 1)
        
        # Show playlist progress if it's a playlist
        if self.playlist_info and self.playlist_check.active:
            self.playlist_progress_card.opacity = 1
            self.playlist_progress_card.disabled = False
            self.current_playlist_index = 0
            self.playlist_total = self.playlist_info['filtered_total']
            self.update_playlist_progress(0)
        
        # Reset progress
        self.progress_bar.value = 0
        self.percentage_label.text = '0%'
        self.size_label.text = '0 MB / 0 MB'
        self.speed_label.text = 'Speed: 0 KB/s'
        self.eta_label.text = 'ETA: --:--'
        
        # Start download thread
        download_thread = threading.Thread(target=self.download_thread, args=(url, ydl_opts, save_path))
        download_thread.daemon = True
        download_thread.start()
    
    def update_playlist_progress(self, current_index):
        """Update playlist progress display"""
        if self.playlist_total > 0:
            percentage = (current_index / self.playlist_total) * 100
            self.playlist_progress_bar.value = percentage
            self.playlist_status_label.text = f"Playlist: {current_index}/{self.playlist_total} videos"
    
    def sanitize_filename(self, filename):
        """Sanitize filename for safe saving"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        if len(filename) > 100:
            filename = filename[:100]
        return filename.strip()
    
    def download_thread(self, url, ydl_opts, save_path):
        """Thread for downloading"""
        try:
            self.cancel_download_flag = False
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            if not self.cancel_download_flag:
                self.queue.put(('complete', save_path))
            else:
                self.queue.put(('message', 'Download cancelled by user'))
                self.queue.put(('download_done', None))
        except Exception as e:
            error_msg = str(e)[:200]
            if 'Unsupported URL' in error_msg:
                error_msg = "URL format not supported"
            elif 'Private video' in error_msg:
                error_msg = "This video is private"
            elif 'login' in error_msg.lower():
                error_msg = "This content requires login"
            self.queue.put(('error', error_msg))
        finally:
            self.queue.put(('download_done', None))
    
    def progress_hook(self, d):
        """Progress hook for yt-dlp"""
        if self.cancel_download_flag:
            raise Exception("Download cancelled")
        
        if d['status'] == 'downloading':
            try:
                total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                downloaded = d.get('downloaded_bytes', 0)
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                
                if total > 0 and downloaded > 0:
                    percentage = (downloaded / total) * 100
                    downloaded_mb = downloaded / (1024 * 1024)
                    total_mb = total / (1024 * 1024)
                    
                    self.queue.put(('progress', {
                        'percentage': percentage,
                        'downloaded': downloaded_mb,
                        'total': total_mb,
                        'speed': speed,
                        'eta': eta
                    }))
            except:
                pass
        elif d['status'] == 'finished':
            if self.playlist_info and self.playlist_check.active:
                self.current_playlist_index += 1
                self.update_playlist_progress(self.current_playlist_index)
    
    def process_queue(self, dt):
        """Process queue in main thread"""
        try:
            while True:
                msg = self.queue.get_nowait()
                msg_type = msg[0]
                msg_data = msg[1]
                
                if msg_type == 'info':
                    self.info_text.text = msg_data
                elif msg_type == 'progress':
                    self.update_progress(msg_data)
                elif msg_type == 'complete':
                    self.download_complete(msg_data)
                elif msg_type == 'error':
                    self.show_error(msg_data)
                elif msg_type == 'enable_download':
                    self.download_btn.disabled = False
                    self.download_btn.text = 'START DOWNLOAD'
                elif msg_type == 'fetch_done':
                    self.fetch_btn.disabled = False
                    self.fetch_btn.text = 'Fetch Info'
                elif msg_type == 'download_done':
                    self.is_downloading = False
                    self.cancel_btn.disabled = True
                elif msg_type == 'message':
                    self.show_message(msg_data, 'info')
                elif msg_type == 'playlist_detected':
                    self.playlist_progress_card.opacity = 0.5
                    self.show_message(f'Playlist detected! {msg_data} videos to download.', 'success')
        except queue.Empty:
            pass
    
    def update_progress(self, data):
        """Update progress display"""
        try:
            percentage = min(data['percentage'], 100)
            self.progress_bar.value = percentage
            self.percentage_label.text = f"{percentage:.1f}%"
            
            downloaded = data.get('downloaded', 0)
            total = data.get('total', 0)
            self.size_label.text = f"{downloaded:.1f} MB / {total:.1f} MB"
            
            speed = data.get('speed', 0)
            if speed:
                if speed < 1024:
                    speed_text = f"{speed:.0f} B/s"
                elif speed < 1024 * 1024:
                    speed_text = f"{speed/1024:.1f} KB/s"
                else:
                    speed_text = f"{speed/(1024*1024):.1f} MB/s"
                self.speed_label.text = f"Speed: {speed_text}"
            
            eta = data.get('eta', 0)
            if eta > 0:
                eta_min = eta // 60
                eta_sec = eta % 60
                self.eta_label.text = f"ETA: {eta_min:02d}:{eta_sec:02d}"
        except:
            pass
    
    def download_complete(self, save_path):
        """Handle download completion"""
        self.progress_bar.value = 100
        self.percentage_label.text = '100%'
        self.status_label.text = 'Complete!'
        self.status_label.color = (0.4, 0.8, 0.4, 1)
        self.download_btn.disabled = False
        self.download_btn.text = 'START DOWNLOAD'
        
        # Save to history
        if self.current_video_info:
            self.save_to_history(self.current_video_info, save_path)
        
        # Hide playlist progress card
        if self.playlist_info:
            Clock.schedule_once(lambda dt: self.hide_playlist_progress(), 2)
        
        self.show_message(f'Download completed!\nSaved to: {save_path}', 'success')
        self.status_bar_label.text = f"Saved to: {save_path}"
        Clock.schedule_once(lambda dt: self.reset_progress(), 3)
    
    def hide_playlist_progress(self):
        """Hide playlist progress card"""
        self.playlist_progress_card.opacity = 0
        self.playlist_progress_card.disabled = True
        self.playlist_progress_bar.value = 0
        self.playlist_status_label.text = ''
    
    def reset_progress(self):
        """Reset progress display"""
        if not self.is_downloading:
            self.progress_bar.value = 0
            self.percentage_label.text = '0%'
            self.size_label.text = '0 MB / 0 MB'
            self.speed_label.text = 'Speed: 0 KB/s'
            self.eta_label.text = 'ETA: --:--'
            self.status_label.text = 'Ready'
            self.status_label.color = (0.4, 0.8, 0.4, 1)
    
    def save_to_history(self, info, save_path):
        """Save download to history"""
        try:
            store = JsonStore('download_history.json')
            history = store.get('history')['items'] if store.exists('history') else []
            
            title = info.get('title', 'Unknown')
            if isinstance(title, bytes):
                title = title.decode('utf-8', errors='ignore')
            
            if self.playlist_info and self.playlist_check.active:
                title = f"[PLAYLIST] {title}"
            
            history.append({
                'title': str(title)[:100],
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'platform': self.platform_indicator.text,
                'url': self.url_input.text,
                'save_path': save_path,
                'is_playlist': bool(self.playlist_info)
            })
            
            if len(history) > 100:
                history = history[-100:]
            
            store.put('history', items=history)
        except:
            pass
    
    def show_error(self, error_msg):
        """Show error message"""
        self.show_message(error_msg, 'error')
        self.status_label.text = 'Error!'
        self.status_label.color = (0.9, 0.2, 0.2, 1)
        self.download_btn.disabled = False
        self.download_btn.text = 'START DOWNLOAD'
        self.fetch_btn.disabled = False
        self.fetch_btn.text = 'Fetch Info'
        self.is_downloading = False
        self.cancel_btn.disabled = True
        self.hide_playlist_progress()
    
    def show_message(self, message, msg_type='info'):
        """Show popup message"""
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(15))
        
        icon = '✓' if msg_type == 'success' else '⚠️' if msg_type == 'warning' else 'ℹ️'
        color = (0.4, 0.8, 0.4, 1) if msg_type == 'success' else (0.9, 0.5, 0.2, 1) if msg_type == 'warning' else (0.2, 0.6, 0.86, 1)
        
        msg_label = Label(text=f'{icon} {message}', color=color, font_size=dp(14), halign='center')
        content.add_widget(msg_label)
        
        close_btn = Button(text='OK', size_hint_y=None, height=dp(50), background_color=(0.2, 0.6, 0.86, 1))
        content.add_widget(close_btn)
        
        popup = Popup(title='Message', content=content, size_hint=(0.8, 0.4))
        close_btn.bind(on_press=popup.dismiss)
        popup.open()


# ==================== SETTINGS SCREEN ====================

class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(15))
        
        title = Label(text='Settings', font_size=dp(24), bold=True, color=(1, 1, 1, 1), 
                      size_hint_y=None, height=dp(50))
        layout.add_widget(title)
        
        settings_card = Card()
        
        # Default save location
        save_layout = BoxLayout(orientation='vertical', spacing=dp(10), size_hint_y=None, height=dp(100))
        save_layout.add_widget(Label(text='Default Save Location', color=(1, 1, 1, 1), 
                                      size_hint_y=None, height=dp(30)))
        self.save_default_spinner = Spinner(
            text='Social Media Folder',
            values=('Social Media Folder', 'Downloads Folder'),
            size_hint=(1, None),
            height=dp(40),
            background_color=(0.2, 0.6, 0.86, 1),
            color=(1, 1, 1, 1)
        )
        save_layout.add_widget(self.save_default_spinner)
        settings_card.add_widget(save_layout)
        
        # Organize by platform
        organize_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        organize_layout.add_widget(Label(text='Organize downloads by platform', color=(1, 1, 1, 1), size_hint_x=0.7))
        self.organize_switch = Switch(active=True, size_hint_x=0.3)
        organize_layout.add_widget(self.organize_switch)
        settings_card.add_widget(organize_layout)
        
        layout.add_widget(settings_card)
        
        # Storage Info Card
        storage_card = Card()
        storage_card.add_widget(Label(text='Storage Information', color=(1, 1, 1, 1), 
                                       font_size=dp(16), bold=True, size_hint_y=None, height=dp(30)))
        
        self.social_storage_label = Label(text=f"Social Media Folder: {SOCIAL_DIR}", 
                                          color=(0.7, 0.7, 0.7, 1), size_hint_y=None, height=dp(25))
        self.downloads_storage_label = Label(text=f"Downloads Folder: {DOWNLOAD_DIR}", 
                                             color=(0.7, 0.7, 0.7, 1), size_hint_y=None, height=dp(25))
        
        storage_card.add_widget(self.social_storage_label)
        storage_card.add_widget(self.downloads_storage_label)
        layout.add_widget(storage_card)
        
        # About section
        about_card = Card()
        about_card.add_widget(Label(text='About', color=(1, 1, 1, 1), font_size=dp(16), bold=True, 
                                     size_hint_y=None, height=dp(30)))
        about_card.add_widget(Label(text='Social Media Downloader Pro v4.0', color=(0.7, 0.7, 0.7, 1), 
                                     size_hint_y=None, height=dp(25)))
        about_card.add_widget(Label(text='Supports: YouTube, TikTok, Instagram, Facebook', 
                                     color=(0.7, 0.7, 0.7, 1), size_hint_y=None, height=dp(25)))
        layout.add_widget(about_card)
        
        back_btn = RoundedButton(text='Back', size_hint_y=None, height=dp(50), on_press=self.go_back)
        layout.add_widget(back_btn)
        
        self.add_widget(layout)
    
    def go_back(self, instance):
        self.manager.current = 'downloader'


# ==================== HISTORY SCREEN ====================

class HistoryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(15))
        
        title = Label(text='Download History', font_size=dp(24), bold=True, color=(1, 1, 1, 1), 
                      size_hint_y=None, height=dp(50))
        layout.add_widget(title)
        
        scroll = ScrollView()
        self.history_list = GridLayout(cols=1, spacing=dp(10), size_hint_y=None)
        self.history_list.bind(minimum_height=self.history_list.setter('height'))
        scroll.add_widget(self.history_list)
        layout.add_widget(scroll)
        
        button_layout = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(10))
        clear_btn = RoundedButton(text='Clear History', on_press=self.clear_history)
        refresh_btn = RoundedButton(text='Refresh', on_press=self.refresh_history)
        
        button_layout.add_widget(clear_btn)
        button_layout.add_widget(refresh_btn)
        layout.add_widget(button_layout)
        
        back_btn = RoundedButton(text='Back', size_hint_y=None, height=dp(50), on_press=self.go_back)
        layout.add_widget(back_btn)
        
        self.add_widget(layout)
        self.load_history()
    
    def load_history(self):
        """Load download history"""
        try:
            store = JsonStore('download_history.json')
            if store.exists('history'):
                history = store.get('history')['items']
                self.history_list.clear_widgets()
                
                if not history:
                    self.history_list.add_widget(Label(text='No downloads yet', 
                                                        color=(0.7, 0.7, 0.7, 1), 
                                                        size_hint_y=None, height=dp(40)))
                else:
                    for item in reversed(history[-20:]):  # Show last 20 items
                        item_card = Card()
                        title_text = str(item.get('title', 'Unknown'))[:50]
                        if item.get('is_playlist', False):
                            title_text = f"Playlist: {title_text}"
                        item_card.add_widget(Label(text=title_text, color=(1, 1, 1, 1), 
                                                    bold=True, size_hint_y=None, height=dp(30)))
                        item_card.add_widget(Label(text=f"Date: {item.get('date', 'Unknown')}", 
                                                    color=(0.7, 0.7, 0.7, 1), 
                                                    size_hint_y=None, height=dp(25)))
                        item_card.add_widget(Label(text=f"Platform: {item.get('platform', 'Unknown')}", 
                                                    color=(0.7, 0.7, 0.7, 1), 
                                                    size_hint_y=None, height=dp(25)))
                        self.history_list.add_widget(item_card)
            else:
                self.history_list.add_widget(Label(text='No history found', color=(0.7, 0.7, 0.7, 1), 
                                                    size_hint_y=None, height=dp(40)))
        except:
            self.history_list.add_widget(Label(text='Error loading history', color=(0.9, 0.2, 0.2, 1), 
                                                size_hint_y=None, height=dp(40)))
    
    def refresh_history(self, instance):
        self.load_history()
        self.show_message('History refreshed!', 'success')
    
    def clear_history(self, instance):
        try:
            store = JsonStore('download_history.json')
            store.put('history', items=[])
            self.load_history()
            self.show_message('History cleared!', 'success')
        except:
            self.show_message('Failed to clear history', 'error')
    
    def show_message(self, message, msg_type='info'):
        content = BoxLayout(orientation='vertical', padding=dp(15), spacing=dp(15))
        icon = '✓' if msg_type == 'success' else '⚠️' if msg_type == 'warning' else 'ℹ️'
        color = (0.4, 0.8, 0.4, 1) if msg_type == 'success' else (0.9, 0.5, 0.2, 1) if msg_type == 'warning' else (0.2, 0.6, 0.86, 1)
        
        msg_label = Label(text=f'{icon} {message}', color=color, font_size=dp(14), halign='center')
        content.add_widget(msg_label)
        
        close_btn = Button(text='OK', size_hint_y=None, height=dp(50), background_color=(0.2, 0.6, 0.86, 1))
        content.add_widget(close_btn)
        
        popup = Popup(title='Message', content=content, size_hint=(0.8, 0.3))
        close_btn.bind(on_press=popup.dismiss)
        popup.open()
    
    def go_back(self, instance):
        self.manager.current = 'downloader'


# ==================== MAIN APP ====================

class SocialMediaDownloaderApp(App):
    def build(self):
        from kivy.core.window import Window
        Window.clearcolor = (0.05, 0.05, 0.05, 1)
        
        sm = ScreenManager()
        sm.add_widget(DownloaderScreen(name='downloader'))
        sm.add_widget(SettingsScreen(name='settings'))
        sm.add_widget(HistoryScreen(name='history'))
        
        nav_layout = BoxLayout(orientation='vertical')
        nav_layout.add_widget(sm)
        
        nav_bar = BoxLayout(size_hint_y=None, height=dp(60), padding=dp(10), spacing=dp(10))
        with nav_bar.canvas.before:
            Color(0.08, 0.08, 0.08, 1)
            RoundedRectangle(pos=nav_bar.pos, size=nav_bar.size)
        
        download_btn = Button(text='Download', background_color=(0.2, 0.6, 0.86, 1))
        history_btn = Button(text='History', background_color=(0.1, 0.1, 0.1, 1))
        settings_btn = Button(text='Settings', background_color=(0.1, 0.1, 0.1, 1))
        
        download_btn.bind(on_press=lambda x: setattr(sm, 'current', 'downloader'))
        history_btn.bind(on_press=lambda x: setattr(sm, 'current', 'history'))
        settings_btn.bind(on_press=lambda x: setattr(sm, 'current', 'settings'))
        
        nav_bar.add_widget(download_btn)
        nav_bar.add_widget(history_btn)
        nav_bar.add_widget(settings_btn)
        nav_layout.add_widget(nav_bar)
        
        def on_screen_change(*args):
            download_btn.background_color = (0.2, 0.6, 0.86, 1) if sm.current == 'downloader' else (0.1, 0.1, 0.1, 1)
            history_btn.background_color = (0.2, 0.6, 0.86, 1) if sm.current == 'history' else (0.1, 0.1, 0.1, 1)
            settings_btn.background_color = (0.2, 0.6, 0.86, 1) if sm.current == 'settings' else (0.1, 0.1, 0.1, 1)
        
        sm.bind(current=on_screen_change)
        
        return nav_layout
    
    def on_start(self):
        if platform == 'android':
            try:
                from android.permissions import request_permissions, Permission
                request_permissions([
                    Permission.WRITE_EXTERNAL_STORAGE,
                    Permission.READ_EXTERNAL_STORAGE,
                    Permission.INTERNET
                ])
            except:
                pass


if __name__ == '__main__':
    SocialMediaDownloaderApp().run()