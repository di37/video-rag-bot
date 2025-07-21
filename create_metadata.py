import os
import json

def create_frame_metadata():
    screenshots_dir = "screenshots"
    frames = sorted([f for f in os.listdir(screenshots_dir) if f.endswith('.jpg')])
    
    metadata = {
        "video_info": {
            "title": "DeepSeek Basics",
            "url": "https://youtu.be/WjhDDeZ7DvM",
            "duration_seconds": 2396.62,
            "fps_extraction": 0.2,
            "frame_interval_seconds": 5
        },
        "frames": []
    }
    
    for i, frame in enumerate(frames):
        frame_number = i + 1
        timestamp_seconds = i * 5
        timestamp_formatted = f"{timestamp_seconds // 60:02d}:{timestamp_seconds % 60:02d}"
        
        frame_info = {
            "frame_number": frame_number,
            "filename": frame,
            "path": os.path.join(screenshots_dir, frame),
            "timestamp_seconds": timestamp_seconds,
            "timestamp_formatted": timestamp_formatted
        }
        
        metadata["frames"].append(frame_info)
    
    with open("video_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Created metadata for {len(frames)} frames")
    print(f"Total video coverage: {len(frames) * 5} seconds ({(len(frames) * 5) / 60:.1f} minutes)")

if __name__ == "__main__":
    create_frame_metadata()