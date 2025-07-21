"""Video frame querying functionality."""

from typing import List, Dict, Optional
from qdrant_client.models import Filter, FieldCondition, Range, MatchValue

from ..core.base import VideoRAGBase
from ..core import config


class VideoQueryEngine(VideoRAGBase):
    """Handles querying of video frames from Qdrant."""
    
    def search_by_text(self, query_text: str, limit: int = config.DEFAULT_SEARCH_LIMIT, 
                      video_id: Optional[str] = None) -> List[Dict]:
        """Search for frames using a text query."""
        query_embedding = self.encode_text(query_text)
        
        search_filter = None
        if video_id:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="video_id",
                        match=MatchValue(value=video_id)
                    )
                ]
            )
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding.tolist(),
            query_filter=search_filter,
            limit=limit
        )
        
        return self._format_results(results)
    
    def search_by_image(self, image_path: str, limit: int = config.DEFAULT_SEARCH_LIMIT,
                       video_id: Optional[str] = None) -> List[Dict]:
        """Search for similar frames using an image query."""
        try:
            query_embedding = self.encode_image(image_path)
            
            search_filter = None
            if video_id:
                search_filter = Filter(
                    must=[
                        FieldCondition(
                            key="video_id",
                            match=MatchValue(value=video_id)
                        )
                    ]
                )
            
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding.tolist(),
                query_filter=search_filter,
                limit=limit
            )
            
            return self._format_results(results)
        except Exception as e:
            print(f"❌ Error: {e}")
            return []
    
    def search_by_time_range(self, start_seconds: int, end_seconds: int, limit: int = 100,
                            video_id: Optional[str] = None) -> List[Dict]:
        """Search for frames within a specific time range."""
        filter_conditions = [
            FieldCondition(
                key="timestamp_seconds",
                range=Range(gte=start_seconds, lte=end_seconds)
            )
        ]
        
        if video_id:
            filter_conditions.append(
                FieldCondition(
                    key="video_id",
                    match=MatchValue(value=video_id)
                )
            )
        
        results = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(must=filter_conditions),
            limit=limit
        )
        
        frames = []
        for point in results[0]:
            frames.append({
                "frame_id": point.payload["frame_id"],
                "video_id": point.payload["video_id"],
                "video_title": point.payload["video_title"],
                "timestamp": point.payload["timestamp_formatted"],
                "timestamp_seconds": point.payload["timestamp_seconds"],
                "file_path": point.payload["file_path"],
                "youtube_url": f"{point.payload['video_url']}?t={point.payload['timestamp_seconds']}"
            })
            
        return sorted(frames, key=lambda x: x["timestamp_seconds"])
    
    def search_by_video(self, video_id: str, limit: int = 100) -> List[Dict]:
        """Get all frames from a specific video."""
        results = self.client.scroll(
            collection_name=self.collection_name,
            scroll_filter=Filter(
                must=[
                    FieldCondition(
                        key="video_id",
                        match=MatchValue(value=video_id)
                    )
                ]
            ),
            limit=limit
        )
        
        frames = []
        for point in results[0]:
            frames.append({
                "frame_id": point.payload["frame_id"],
                "video_id": point.payload["video_id"],
                "video_title": point.payload["video_title"],
                "timestamp": point.payload["timestamp_formatted"],
                "timestamp_seconds": point.payload["timestamp_seconds"],
                "file_path": point.payload["file_path"],
                "youtube_url": f"{point.payload['video_url']}?t={point.payload['timestamp_seconds']}"
            })
        
        return sorted(frames, key=lambda x: x["timestamp_seconds"])
    
    def get_random_frames(self, limit: int = 10, video_id: Optional[str] = None) -> List[Dict]:
        """Get random frames for exploration."""
        search_filter = None
        if video_id:
            search_filter = Filter(
                must=[
                    FieldCondition(
                        key="video_id",
                        match=MatchValue(value=video_id)
                    )
                ]
            )
        
        # Use a random vector for random sampling
        import numpy as np
        random_vector = np.random.random(config.EMBEDDING_DIM).tolist()
        
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=random_vector,
            query_filter=search_filter,
            limit=limit
        )
        
        return self._format_results(results, include_score=False)
    
    def _format_results(self, results, include_score: bool = True) -> List[Dict]:
        """Format search results."""
        formatted_results = []
        for result in results:
            frame_data = {
                "frame_id": result.payload["frame_id"],
                "video_id": result.payload["video_id"],
                "video_title": result.payload["video_title"],
                "timestamp": result.payload["timestamp_formatted"],
                "timestamp_seconds": result.payload["timestamp_seconds"],
                "file_path": result.payload["file_path"],
                "youtube_url": f"{result.payload['video_url']}?t={result.payload['timestamp_seconds']}"
            }
            
            if include_score:
                frame_data["score"] = result.score
            
            formatted_results.append(frame_data)
        
        return formatted_results