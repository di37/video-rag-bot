"""Configuration settings for the Video RAG system."""

# Qdrant settings
QDRANT_HOST = "localhost"
QDRANT_PORT = 6333
COLLECTION_NAME = "video_frames"

# Model settings
MODEL_NAME = "clip-ViT-B-32"
EMBEDDING_DIM = 512

# Processing settings
BATCH_SIZE = 32
DEFAULT_SEARCH_LIMIT = 5

# File paths
METADATA_FILE = "video_metadata.json"
SCREENSHOTS_DIR = "video-downloads/screenshots"

# Video info
VIDEO_URL = "https://youtu.be/WjhDDeZ7DvM"