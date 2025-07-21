"""Video frame indexing functionality."""

from typing import List
from tqdm import tqdm
from qdrant_client.models import PointStruct
import hashlib

from ..core.base import VideoRAGBase, FrameData
from ..core import config


class VideoIndexer(VideoRAGBase):
    """Handles indexing of video frames into Qdrant."""
    
    def index_frames(self, frames: List[FrameData], batch_size: int = config.BATCH_SIZE):
        """Index video frames into Qdrant."""
        print(f"\n🎬 Indexing {len(frames)} frames...")
        
        points = []
        
        for i in tqdm(range(0, len(frames), batch_size), desc="Processing"):
            batch = frames[i:i + batch_size]
            
            for frame in batch:
                try:
                    embedding = self.encode_image(frame.file_path)
                    
                    # Generate unique point ID using video_id and frame_number
                    point_id = self._generate_point_id(frame.video_id, frame.frame_number)
                    
                    point = PointStruct(
                        id=point_id,
                        vector=embedding.tolist(),
                        payload={
                            "frame_id": frame.frame_id,
                            "video_id": frame.video_id,
                            "video_title": frame.video_title,
                            "video_url": frame.video_url,
                            "timestamp_seconds": frame.timestamp_seconds,
                            "timestamp_formatted": frame.timestamp_formatted,
                            "file_path": frame.file_path,
                            "frame_number": frame.frame_number
                        }
                    )
                    points.append(point)
                except Exception as e:
                    print(f"\n❌ Error processing frame {frame.frame_id}: {e}")
                    continue
            
            if points:
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=points
                )
                points = []
        
        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
                
        print("\n✅ Indexing complete!")
    
    def index_single_video(self, video_id: str, video_dir: str = "video-downloads"):
        """Index frames from a single video."""
        metadata_file = f"{video_dir}/{video_id}_metadata.json"
        try:
            frames = self._load_video_metadata(metadata_file)
            self.index_frames(frames)
            print(f"✅ Successfully indexed {len(frames)} frames from video: {video_id}")
        except Exception as e:
            print(f"❌ Error indexing video {video_id}: {e}")
    
    def _generate_point_id(self, video_id: str, frame_number: int) -> int:
        """Generate a unique point ID for a frame."""
        # Create a unique string and hash it to get an integer ID
        unique_string = f"{video_id}_{frame_number}"
        hash_object = hashlib.md5(unique_string.encode())
        # Convert hash to integer (using first 8 bytes to avoid overflow)
        return int(hash_object.hexdigest()[:8], 16)
    
    def delete_video_frames(self, video_id: str):
        """Delete all frames for a specific video from the collection."""
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        # Delete points with matching video_id
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="video_id",
                        match=MatchValue(value=video_id)
                    )
                ]
            )
        )
        print(f"🗑️  Deleted all frames for video: {video_id}")
    
    def get_collection_stats(self) -> dict:
        """Get statistics about the indexed collection."""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            
            # Get video counts
            scroll_result = self.client.scroll(
                collection_name=self.collection_name,
                limit=10000,  # Adjust based on your collection size
                with_payload=["video_id", "video_title"]
            )
            
            video_counts = {}
            for point in scroll_result[0]:
                video_id = point.payload.get("video_id", "unknown")
                video_title = point.payload.get("video_title", "Unknown")
                if video_id not in video_counts:
                    video_counts[video_id] = {
                        "title": video_title,
                        "frame_count": 0
                    }
                video_counts[video_id]["frame_count"] += 1
            
            return {
                "total_points": collection_info.points_count,
                "total_videos": len(video_counts),
                "videos": video_counts,
                "vector_size": collection_info.config.params.vectors.size,
                "distance": collection_info.config.params.vectors.distance.name
            }
        except Exception as e:
            return {"error": str(e)}