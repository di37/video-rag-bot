"""
FastAPI Video RAG Bot

A web interface for searching video content using natural language.
"""

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
from pathlib import Path
import asyncio
import re

from src.querying.query_engine import VideoQueryEngine
from src.downloading.youtube_downloader import YouTubeDownloader
from src.indexing.indexer import VideoIndexer
from src.utils.helpers import parse_time
from src.core import config


app = FastAPI(title="Video RAG Bot", version="2.0.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

# Initialize components
query_engine = VideoQueryEngine()
downloader = YouTubeDownloader()
indexer = VideoIndexer()

# Global variable to track processing status
processing_status = {}


class SearchRequest(BaseModel):
    query: str
    search_type: str = "text"  # text, image, time
    limit: int = 5
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    video_id: Optional[str] = None


class SearchResult(BaseModel):
    frame_id: str
    video_id: str
    video_title: str
    timestamp: str
    timestamp_seconds: int
    score: Optional[float]
    youtube_url: str
    thumbnail: str


class VideoDownloadRequest(BaseModel):
    url: str
    frame_interval: int = 5
    auto_index: bool = True
    keep_video_file: bool = False  # Default to deleting video files to save space


class VideoInfo(BaseModel):
    id: str
    title: str
    url: str
    duration: float  # Changed from int to float to handle precise durations
    frames_count: int
    processed_date: str
    uploader: str
    description: str


@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the main HTML page."""
    with open("static/index.html", "r") as f:
        return f.read()


@app.post("/api/search", response_model=List[SearchResult])
async def search(request: SearchRequest):
    """Perform search on video frames."""
    try:
        if request.search_type == "text":
            results = query_engine.search_by_text(
                request.query, request.limit, request.video_id
            )
        
        elif request.search_type == "time":
            if not request.start_time or not request.end_time:
                raise HTTPException(400, "Start and end times required for time search")
            
            start_seconds = parse_time(request.start_time)
            end_seconds = parse_time(request.end_time)
            results = query_engine.search_by_time_range(
                start_seconds, end_seconds, request.limit, request.video_id
            )
        
        else:
            raise HTTPException(400, f"Invalid search type: {request.search_type}")
        
        # Convert results to response format
        response = []
        for result in results:
            response.append(SearchResult(
                frame_id=result["frame_id"],
                video_id=result["video_id"],
                video_title=result["video_title"],
                timestamp=result["timestamp"],
                timestamp_seconds=result["timestamp_seconds"],
                score=result.get("score"),
                youtube_url=result["youtube_url"],
                thumbnail=f"/frame/{result['frame_id']}"
            ))
        
        return response
    
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/stats")
async def get_stats():
    """Get collection statistics."""
    try:
        stats = indexer.get_collection_stats()
        if "error" in stats:
            return {
                "total_frames": 0,
                "total_videos": 0,
                "videos": {},
                "embedding_model": config.MODEL_NAME
            }
        
        return {
            "total_frames": stats["total_points"],
            "total_videos": stats["total_videos"],
            "videos": stats["videos"],
            "embedding_model": config.MODEL_NAME,
            "vector_size": stats.get("vector_size", config.EMBEDDING_DIM),
            "distance": stats.get("distance", "COSINE")
        }
    except Exception as e:
        return {
            "total_frames": 0,
            "total_videos": 0,
            "videos": {},
            "embedding_model": config.MODEL_NAME,
            "error": str(e)
        }


@app.get("/api/videos", response_model=List[VideoInfo])
async def list_videos():
    """Get list of all processed videos."""
    try:
        videos = indexer.get_video_list()
        return videos
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/download")
async def download_video(request: VideoDownloadRequest, background_tasks: BackgroundTasks):
    """Download and process a YouTube video."""
    try:
        # Validate YouTube URL
        if not re.search(r'(?:youtube\.com|youtu\.be)', request.url):
            raise HTTPException(400, "Invalid YouTube URL")
        
        # Get video info first
        video_info = downloader.get_video_info(request.url)
        video_id = video_info['id']
        
        # Check if already processing
        if video_id in processing_status:
            return {
                "success": False,
                "message": "Video is already being processed",
                "video_id": video_id,
                "status": processing_status[video_id]["status"]
            }
        
        # Check if already exists
        existing_metadata = downloader.get_video_metadata(video_id)
        if existing_metadata:
            return {
                "success": True,
                "message": "Video already processed",
                "video_id": video_id,
                "video_info": video_info
            }
        
        # Start background processing
        processing_status[video_id] = {
            "status": "downloading",
            "message": "Starting download...",
            "progress": 0,
            "video_info": video_info
        }
        
        background_tasks.add_task(
            process_video_background,
            request.url,
            video_id,
            request.frame_interval,
            request.auto_index,
            not request.keep_video_file  # Convert keep_video_file to delete_video_after_processing
        )
        
        return {
            "success": True,
            "message": "Video processing started",
            "video_id": video_id,
            "video_info": video_info
        }
        
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/api/download/status/{video_id}")
async def get_download_status(video_id: str):
    """Get the status of video processing."""
    if video_id not in processing_status:
        # Check if video exists
        metadata = downloader.get_video_metadata(video_id)
        if metadata:
            return {
                "status": "completed",
                "message": "Video processing completed",
                "progress": 100
            }
        else:
            return {
                "status": "not_found",
                "message": "Video not found",
                "progress": 0
            }
    
    return processing_status[video_id]


@app.delete("/api/videos/{video_id}")
async def delete_video(video_id: str):
    """Delete a video and its frames completely (database + files)."""
    import os
    import shutil
    import glob
    
    try:
        # Delete from vector database first
        indexer.delete_video_frames(video_id)
        
        # Delete physical files
        video_dir = Path("video-downloads")
        files_deleted = []
        
        # Delete metadata file
        metadata_file = video_dir / f"{video_id}_metadata.json"
        if metadata_file.exists():
            os.remove(metadata_file)
            files_deleted.append(str(metadata_file))
        
        # Delete screenshots directory
        screenshots_dir = video_dir / f"{video_id}_screenshots"
        if screenshots_dir.exists():
            shutil.rmtree(screenshots_dir)
            files_deleted.append(str(screenshots_dir))
        
        # Delete video file(s) if they exist (they're auto-deleted after processing)
        video_patterns = [
            f"{video_id}_*.mp4",
            f"{video_id}_*.webm", 
            f"{video_id}_*.mkv",
            f"{video_id}_*.avi"
        ]
        
        for pattern in video_patterns:
            for video_file in glob.glob(str(video_dir / pattern)):
                if os.path.exists(video_file):
                    file_size_mb = os.path.getsize(video_file) / (1024 * 1024)
                    os.remove(video_file)
                    files_deleted.append(f"{video_file} ({file_size_mb:.1f} MB)")
        
        # Remove from processing status if exists
        if video_id in processing_status:
            del processing_status[video_id]
        
        message = f"Video {video_id} deleted successfully"
        if files_deleted:
            message += f" (removed {len(files_deleted)} files/directories)"
        
        return {"success": True, "message": message, "files_deleted": files_deleted}
        
    except Exception as e:
        raise HTTPException(500, f"Error deleting video: {str(e)}")


@app.get("/api/videos/{video_id}/frames")
async def get_video_frames(video_id: str, limit: int = 50):
    """Get all frames from a specific video."""
    try:
        results = query_engine.search_by_video(video_id, limit)
        return results
    except Exception as e:
        raise HTTPException(500, str(e))


@app.get("/frame/{frame_id}")
async def get_frame(frame_id: str):
    """Serve a video frame image."""
    # Handle both old and new frame ID formats
    if frame_id.startswith("frame_"):
        # Legacy format
        frame_path = Path(config.SCREENSHOTS_DIR) / f"{frame_id}.jpg"
    else:
        # New format: video_id_frame_XXXX
        parts = frame_id.split("_frame_")
        if len(parts) == 2:
            video_id, frame_num = parts
            frame_path = Path("video-downloads") / f"{video_id}_screenshots" / f"{video_id}_frame_{frame_num}.jpg"
        else:
            frame_path = Path(config.SCREENSHOTS_DIR) / f"{frame_id}.jpg"
    
    if not frame_path.exists():
        raise HTTPException(404, "Frame not found")
    
    return FileResponse(frame_path, media_type="image/jpeg")


async def process_video_background(url: str, video_id: str, frame_interval: int, auto_index: bool, delete_video_after_processing: bool = True):
    """Background task to process video."""
    try:
        processing_status[video_id]["status"] = "downloading"
        processing_status[video_id]["message"] = "Downloading video..."
        processing_status[video_id]["progress"] = 10
        
        # Set up downloader with custom settings
        downloader.frame_interval = frame_interval
        downloader.delete_video_after_processing = delete_video_after_processing
        
        # Process video
        result = downloader.process_video(url)
        
        if not result['success']:
            processing_status[video_id]["status"] = "error"
            processing_status[video_id]["message"] = result['message']
            return
        
        processing_status[video_id]["status"] = "processing"
        processing_status[video_id]["message"] = "Extracting frames..."
        processing_status[video_id]["progress"] = 60
        
        # Auto-index if requested
        if auto_index:
            processing_status[video_id]["message"] = "Indexing frames..."
            processing_status[video_id]["progress"] = 80
            
            try:
                frames = indexer._load_video_metadata(Path(result['metadata_file']))
                indexer.index_frames(frames)
                processing_status[video_id]["progress"] = 100
                processing_status[video_id]["status"] = "completed"
                processing_status[video_id]["message"] = f"Successfully processed {len(frames)} frames"
            except Exception as e:
                processing_status[video_id]["status"] = "indexed_error"
                processing_status[video_id]["message"] = f"Downloaded but indexing failed: {str(e)}"
                processing_status[video_id]["progress"] = 90
        else:
            processing_status[video_id]["progress"] = 100
            processing_status[video_id]["status"] = "completed"
            processing_status[video_id]["message"] = "Video downloaded successfully (not indexed)"
        
        # Clean up status after some time
        await asyncio.sleep(300)  # Keep status for 5 minutes
        if video_id in processing_status:
            del processing_status[video_id]
            
    except Exception as e:
        processing_status[video_id]["status"] = "error"
        processing_status[video_id]["message"] = f"Error: {str(e)}"


# Create static directory
Path("static").mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


if __name__ == "__main__":
    print("🚀 Starting Video RAG Bot with YouTube Download Support...")
    print("📍 Open http://localhost:7777 in your browser")
    uvicorn.run("app:app", host="0.0.0.0", port=7777, reload=True)