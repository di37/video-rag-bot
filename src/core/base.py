"""Base classes for the Video RAG system."""

import json
from typing import List, Dict, Optional
from dataclasses import dataclass
import numpy as np
from PIL import Image
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams
from sentence_transformers import SentenceTransformer

from . import config


@dataclass
class FrameData:
    """Data structure for video frame information."""
    frame_id: str
    frame_number: int
    timestamp_seconds: int
    timestamp_formatted: str
    file_path: str
    video_id: str
    video_title: str
    video_url: str
    embedding: Optional[np.ndarray] = None


class VideoRAGBase:
    """Base class for Video RAG operations."""
    
    def __init__(self):
        """Initialize the base Video RAG system."""
        self.client = QdrantClient(host=config.QDRANT_HOST, port=config.QDRANT_PORT)
        self.collection_name = config.COLLECTION_NAME
        self.model = SentenceTransformer(config.MODEL_NAME)
        self.embedding_dim = config.EMBEDDING_DIM
        
    def create_collection(self, recreate: bool = False):
        """Create or recreate the Qdrant collection."""
        collections = self.client.get_collections().collections
        exists = any(col.name == self.collection_name for col in collections)
        
        if exists and recreate:
            self.client.delete_collection(self.collection_name)
            print(f"🗑️  Deleted existing collection: {self.collection_name}")
            exists = False
            
        if not exists:
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.embedding_dim,
                    distance=Distance.COSINE
                )
            )
            print(f"✅ Created collection: {self.collection_name}")
            return True
        else:
            print(f"📦 Collection {self.collection_name} already exists")
            return False
            
    def load_frame_metadata(self, metadata_path: str = config.METADATA_FILE) -> List[FrameData]:
        """Load frame metadata from JSON file (legacy single video support)."""
        with open(metadata_path, "r") as f:
            metadata = json.load(f)
            
        frames = []
        video_info = metadata["video_info"]
        
        for frame_info in metadata["frames"]:
            frame = FrameData(
                frame_id=f"frame_{frame_info['frame_number']:04d}",
                frame_number=frame_info["frame_number"],
                timestamp_seconds=frame_info["timestamp_seconds"],
                timestamp_formatted=frame_info["timestamp_formatted"],
                file_path=frame_info["path"],
                video_id=video_info.get("id", "default"),
                video_title=video_info.get("title", "Unknown Video"),
                video_url=video_info.get("url", config.VIDEO_URL)
            )
            frames.append(frame)
            
        return frames
    
    def load_all_videos_metadata(self, video_dir: str = "video-downloads") -> List[FrameData]:
        """Load frame metadata from all processed videos."""
        video_dir_path = Path(video_dir)
        frames = []
        
        # Load metadata files
        metadata_files = list(video_dir_path.glob("*_metadata.json"))
        
        # Also check for legacy metadata file
        legacy_metadata = Path(config.METADATA_FILE)
        if legacy_metadata.exists():
            metadata_files.append(legacy_metadata)
        
        print(f"📚 Loading metadata from {len(metadata_files)} video(s)...")
        
        for metadata_file in metadata_files:
            try:
                frames.extend(self._load_video_metadata(metadata_file))
            except Exception as e:
                print(f"❌ Error loading {metadata_file}: {e}")
                continue
        
        print(f"✅ Loaded {len(frames)} frames from {len(metadata_files)} video(s)")
        return frames
    
    def _load_video_metadata(self, metadata_path: Path) -> List[FrameData]:
        """Load metadata from a single video file."""
        with open(metadata_path, "r", encoding='utf-8') as f:
            metadata = json.load(f)
        
        video_info = metadata["video_info"]
        frames = []
        
        for frame_info in metadata["frames"]:
            # Handle both new and legacy frame formats
            video_id = frame_info.get("video_id", video_info.get("id", "default"))
            
            # Create unique frame_id that includes video_id
            if video_id == "default":
                frame_id = f"frame_{frame_info['frame_number']:04d}"
            else:
                frame_id = f"{video_id}_frame_{frame_info['frame_number']:04d}"
            
            # Handle file path - ensure it's relative to video-downloads directory
            file_path = frame_info["path"]
            if not file_path.startswith("video-downloads/"):
                # Legacy format or new format
                if video_id != "default" and not file_path.startswith(f"{video_id}_"):
                    file_path = f"video-downloads/{video_id}_screenshots/{frame_info['filename']}"
                else:
                    file_path = f"video-downloads/{file_path}"
            
            frame = FrameData(
                frame_id=frame_id,
                frame_number=frame_info["frame_number"],
                timestamp_seconds=frame_info["timestamp_seconds"],
                timestamp_formatted=frame_info["timestamp_formatted"],
                file_path=file_path,
                video_id=video_id,
                video_title=video_info.get("title", "Unknown Video"),
                video_url=video_info.get("url", config.VIDEO_URL)
            )
            frames.append(frame)
        
        return frames
    
    def get_video_list(self, video_dir: str = "video-downloads") -> List[Dict]:
        """Get list of all processed videos."""
        video_dir_path = Path(video_dir)
        videos = []
        
        # Get all metadata files
        metadata_files = list(video_dir_path.glob("*_metadata.json"))
        
        # Check for legacy metadata
        legacy_metadata = Path(config.METADATA_FILE)
        if legacy_metadata.exists():
            metadata_files.append(legacy_metadata)
        
        for metadata_file in metadata_files:
            try:
                with open(metadata_file, "r", encoding='utf-8') as f:
                    metadata = json.load(f)
                
                video_info = metadata["video_info"]
                videos.append({
                    "id": video_info.get("id", "default"),
                    "title": video_info.get("title", "Unknown Video"),
                    "url": video_info.get("url", config.VIDEO_URL),
                    "duration": video_info.get("duration_seconds", 0),
                    "frames_count": len(metadata["frames"]),
                    "processed_date": video_info.get("processed_date", ""),
                    "uploader": video_info.get("uploader", ""),
                    "description": video_info.get("description", "")[:200] + "..." if video_info.get("description", "") else ""
                })
            except Exception as e:
                print(f"Error reading {metadata_file}: {e}")
                continue
        
        return sorted(videos, key=lambda x: x.get("processed_date", ""), reverse=True)
    
    def encode_image(self, image_path: str) -> np.ndarray:
        """Encode an image to a vector embedding using CLIP."""
        image = Image.open(image_path).convert("RGB")
        embedding = self.model.encode(image)
        return embedding
    
    def encode_text(self, text: str) -> np.ndarray:
        """Encode text to a vector embedding using CLIP."""
        embedding = self.model.encode(text)
        return embedding