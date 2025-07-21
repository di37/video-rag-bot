"""
YouTube Video Downloader and Frame Extractor

Downloads YouTube videos and extracts frames for the Video RAG system.
"""

import os
import json
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import yt_dlp
import ffmpeg
from datetime import datetime
import hashlib

from ..core import config


class YouTubeDownloader:
    """Downloads YouTube videos and extracts frames for indexing."""
    
    def __init__(self, 
                 output_dir: str = "video-downloads",
                 frame_interval: int = 5,
                 max_resolution: str = "720p",
                 delete_video_after_processing: bool = True):
        """
        Initialize the YouTube downloader.
        
        Args:
            output_dir: Directory to save videos and frames
            frame_interval: Seconds between extracted frames
            max_resolution: Maximum video resolution to download
            delete_video_after_processing: Whether to delete video files after extracting frames (saves space)
        """
        self.output_dir = Path(output_dir)
        self.frame_interval = frame_interval
        self.max_resolution = max_resolution
        self.delete_video_after_processing = delete_video_after_processing
        
        # Create directory structure
        self.output_dir.mkdir(exist_ok=True)
        
    def get_video_id(self, url: str) -> str:
        """Extract video ID from YouTube URL."""
        video_id_match = re.search(r'(?:v=|\/)([0-9A-Za-z_-]{11}).*', url)
        if video_id_match:
            return video_id_match.group(1)
        else:
            # Generate hash from URL as fallback
            return hashlib.md5(url.encode()).hexdigest()[:11]
    
    def get_video_info(self, url: str) -> Dict:
        """Get video information without downloading and check availability."""
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            # Add headers for info extraction too
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info = ydl.extract_info(url, download=False)
                
                # Check if video is available for download
                availability = info.get('availability', 'unknown')
                if availability == 'private':
                    raise Exception("Video is private and cannot be downloaded")
                elif availability == 'premium_only':
                    raise Exception("Video requires YouTube Premium and cannot be downloaded")
                elif info.get('live_status') == 'is_live':
                    raise Exception("Cannot download live streams")
                
                return {
                    'id': self.get_video_id(url),
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Unknown'),
                    'upload_date': info.get('upload_date', ''),
                    'view_count': info.get('view_count', 0),
                    'url': url,
                    'thumbnail': info.get('thumbnail', ''),
                    'description': info.get('description', '')[:500],  # Limit description
                    'availability': availability
                }
            except Exception as e:
                if "403" in str(e) or "Forbidden" in str(e):
                    raise Exception(f"YouTube blocked access to this video. This might be due to:\n"
                                  f"• Geographic restrictions\n"
                                  f"• Anti-bot measures\n"
                                  f"• Rate limiting\n\n"
                                  f"💡 Try again in a few minutes or try a different video.")
                elif "404" in str(e) or "Not Found" in str(e):
                    raise Exception("Video not found. Please check the URL.")
                else:
                    raise Exception(f"Failed to get video info: {str(e)}")
    
    def download_video(self, url: str, video_info: Optional[Dict] = None) -> Tuple[str, Dict]:
        """
        Download a YouTube video.
        
        Args:
            url: YouTube video URL
            video_info: Pre-fetched video info (optional)
            
        Returns:
            Tuple of (video_path, video_info_dict)
        """
        if video_info is None:
            video_info = self.get_video_info(url)
        
        video_id = video_info['id']
        safe_title = re.sub(r'[^\w\s-]', '', video_info['title']).strip()
        safe_title = re.sub(r'[-\s]+', '-', safe_title)
        
        video_filename = f"{video_id}_{safe_title}.%(ext)s"
        video_path = self.output_dir / video_filename
        
        # Configure yt-dlp options with robust settings to avoid 403 errors
        ydl_opts = {
            'outtmpl': str(video_path),
            # No format specification - let yt-dlp choose automatically
            'cookiefile': None,  # Don't use cookies
            'no_warnings': False,
            'extractaudio': False,
            'embed_subs': False,
            'writesubtitles': False,
            'writeautomaticsub': False,
            # Add headers to avoid bot detection
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            },
            # Retry options
            'retries': 3,
            'fragment_retries': 3,
            'sleep_interval': 1,
            'max_sleep_interval': 5,
        }
        
        # Try downloading with multiple strategies
        download_success = False
        last_error = None
        downloaded_file = None
        
        # Strategy 1: Standard download
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                print(f"📥 Downloading: {video_info['title']}")
                ydl.download([url])
                
                # Find the actual downloaded file
                for ext in ['mp4', 'webm', 'mkv']:
                    potential_path = str(video_path).replace('%(ext)s', ext)
                    if os.path.exists(potential_path):
                        downloaded_file = potential_path
                        download_success = True
                        break
                        
                if not download_success:
                    raise Exception("Downloaded video file not found")
                    
        except Exception as e:
            last_error = str(e)
            print(f"⚠️  Standard download failed: {last_error}")
            
        # Strategy 2: Try with different format if first attempt failed
        if not download_success and ("403" in str(last_error) or "Forbidden" in str(last_error) or "HTTP Error" in str(last_error)):
            print("🔄 Trying alternative download strategy...")
            try:
                # Use more conservative options
                fallback_opts = ydl_opts.copy()
                fallback_opts.update({
                    'format': 'worst',  # Try lower quality
                    'sleep_interval': 2,
                    'max_sleep_interval': 10,
                })
                
                with yt_dlp.YoutubeDL(fallback_opts) as ydl:
                    print("📥 Downloading with fallback settings...")
                    ydl.download([url])
                    
                    # Find the actual downloaded file
                    for ext in ['mp4', 'webm', 'mkv']:
                        potential_path = str(video_path).replace('%(ext)s', ext)
                        if os.path.exists(potential_path):
                            downloaded_file = potential_path
                            download_success = True
                            break
                    
                    if download_success:
                        print("✅ Fallback download successful!")
                    else:
                        raise Exception("Downloaded video file not found with fallback")
                        
            except Exception as fallback_error:
                last_error = str(fallback_error)
                print(f"⚠️  Fallback download also failed: {last_error}")
        
        if not download_success:
            raise Exception(f"All download strategies failed. Last error: {last_error}")
            
        print("✅ Video download completed successfully!")
        return downloaded_file, video_info
    
    def extract_frames(self, video_path: str, video_info: Dict) -> Tuple[str, List[Dict]]:
        """
        Extract frames from downloaded video.
        
        Args:
            video_path: Path to the video file
            video_info: Video information dictionary
            
        Returns:
            Tuple of (screenshots_dir, frames_list)
        """
        video_id = video_info['id']
        screenshots_dir = self.output_dir / f"{video_id}_screenshots"
        screenshots_dir.mkdir(exist_ok=True)
        
        try:
            print(f"🎬 Extracting frames every {self.frame_interval} seconds...")
            
            # Use ffmpeg to extract frames
            (
                ffmpeg
                .input(video_path)
                .output(
                    str(screenshots_dir / f"{video_id}_frame_%04d.jpg"),
                    vf=f'fps=1/{self.frame_interval}',
                    q=2  # High quality
                )
                .overwrite_output()
                .run(quiet=True)
            )
            
            # Generate frame metadata
            frames = []
            frame_files = sorted([f for f in os.listdir(screenshots_dir) if f.endswith('.jpg')])
            
            for i, frame_file in enumerate(frame_files):
                frame_number = i + 1
                timestamp_seconds = i * self.frame_interval
                timestamp_formatted = f"{timestamp_seconds // 60:02d}:{timestamp_seconds % 60:02d}"
                
                frame_info = {
                    "frame_number": frame_number,
                    "filename": frame_file,
                    "path": f"{video_id}_screenshots/{frame_file}",
                    "timestamp_seconds": timestamp_seconds,
                    "timestamp_formatted": timestamp_formatted,
                    "video_id": video_id
                }
                frames.append(frame_info)
            
            print(f"✅ Extracted {len(frames)} frames")
            return str(screenshots_dir), frames
            
        except Exception as e:
            raise Exception(f"Failed to extract frames: {str(e)}")
    
    def create_video_metadata(self, video_info: Dict, frames: List[Dict], screenshots_dir: str) -> str:
        """
        Create metadata file for the processed video.
        
        Args:
            video_info: Video information
            frames: List of frame metadata
            screenshots_dir: Directory containing screenshots
            
        Returns:
            Path to the metadata file
        """
        metadata = {
            "video_info": {
                "id": video_info['id'],
                "title": video_info['title'],
                "url": video_info['url'],
                "duration_seconds": video_info['duration'],
                "uploader": video_info['uploader'],
                "upload_date": video_info['upload_date'],
                "view_count": video_info['view_count'],
                "description": video_info['description'],
                "fps_extraction": 1 / self.frame_interval,
                "frame_interval_seconds": self.frame_interval,
                "processed_date": datetime.now().isoformat(),
                "screenshots_dir": screenshots_dir
            },
            "frames": frames
        }
        
        metadata_file = self.output_dir / f"{video_info['id']}_metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Created metadata: {metadata_file}")
        return str(metadata_file)
    
    def process_video(self, url: str) -> Dict:
        """
        Complete pipeline: download video, extract frames, create metadata.
        
        Args:
            url: YouTube video URL
            
        Returns:
            Dictionary with processing results
        """
        try:
            print(f"🚀 Starting processing for: {url}")
            
            # Get video info
            video_info = self.get_video_info(url)
            print(f"📺 Video: {video_info['title']} ({video_info['duration']}s)")
            
            # Check if already processed
            video_id = video_info['id']
            metadata_file = self.output_dir / f"{video_id}_metadata.json"
            if metadata_file.exists():
                print(f"⚠️  Video already processed: {video_id}")
                return {
                    'success': True,
                    'video_id': video_id,
                    'metadata_file': str(metadata_file),
                    'message': 'Video already processed'
                }
            
            # Download video
            video_path, video_info = self.download_video(url, video_info)
            
            # Extract frames
            screenshots_dir, frames = self.extract_frames(video_path, video_info)
            
            # Create metadata
            metadata_file = self.create_video_metadata(video_info, frames, screenshots_dir)
            
            # Clean up video file to save disk space (keeping only frames + metadata)
            video_path_obj = Path(video_path)  # Convert string to Path object
            if self.delete_video_after_processing:
                try:
                    if video_path_obj.exists():
                        file_size_mb = video_path_obj.stat().st_size / (1024 * 1024)
                        os.remove(video_path_obj)
                        print(f"🗑️  Deleted video file: {video_path_obj.name} ({file_size_mb:.1f} MB saved)")
                    else:
                        print(f"⚠️  Video file not found for cleanup: {video_path_obj}")
                except Exception as e:
                    print(f"⚠️  Could not delete video file {video_path_obj}: {e}")
                    # Continue anyway - this is not a critical error
            else:
                file_size_mb = video_path_obj.stat().st_size / (1024 * 1024) if video_path_obj.exists() else 0
                print(f"💾 Kept video file: {video_path_obj.name} ({file_size_mb:.1f} MB)")
            
            return {
                'success': True,
                'video_id': video_id,
                'video_info': video_info,
                'frames_count': len(frames),
                'metadata_file': metadata_file,
                'screenshots_dir': screenshots_dir,
                'message': f'Successfully processed {len(frames)} frames'
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': f'Failed to process video: {str(e)}'
            }
    
    def list_processed_videos(self) -> List[Dict]:
        """List all processed videos."""
        videos = []
        for metadata_file in self.output_dir.glob("*_metadata.json"):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                    video_info = metadata['video_info']
                    videos.append({
                        'id': video_info['id'],
                        'title': video_info['title'],
                        'url': video_info['url'],
                        'duration': video_info['duration_seconds'],
                        'frames_count': len(metadata['frames']),
                        'processed_date': video_info.get('processed_date', ''),
                        'metadata_file': str(metadata_file)
                    })
            except Exception as e:
                print(f"Error reading {metadata_file}: {e}")
                continue
        
        return sorted(videos, key=lambda x: x.get('processed_date', ''), reverse=True)
    
    def get_video_metadata(self, video_id: str) -> Optional[Dict]:
        """Get metadata for a specific video."""
        metadata_file = self.output_dir / f"{video_id}_metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return None 
    
    def test_youtube_connection(self) -> Dict:
        """Test if YouTube downloading is working properly."""
        try:
            # Test with a simple, always-available video
            test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Roll - classic test video
            
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                },
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(test_url, download=False)
                return {
                    'success': True,
                    'message': 'YouTube connection is working properly',
                    'test_video_title': info.get('title', 'Unknown')
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'YouTube connection test failed: {str(e)}',
                'suggestion': 'Try updating yt-dlp: pip install --upgrade yt-dlp'
            }