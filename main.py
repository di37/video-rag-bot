#!/usr/bin/env python3
"""
Video RAG System - Main Entry Point

A multi-modal RAG system for searching video content using text or image queries.
"""

import argparse
import sys
from pathlib import Path

from src.indexing.indexer import VideoIndexer
from src.querying.query_engine import VideoQueryEngine
from src.downloading.youtube_downloader import YouTubeDownloader
from src.utils.helpers import parse_time, display_results
from src.core import config


def download_command(args):
    """Handle the YouTube download command."""
    print("🚀 Starting YouTube Downloader...")
    
    downloader = YouTubeDownloader(
        output_dir=args.output_dir,
        frame_interval=args.frame_interval,
        max_resolution=args.resolution
    )
    
    result = downloader.process_video(args.url)
    
    if result['success']:
        print(f"✅ {result['message']}")
        print(f"📁 Video ID: {result['video_id']}")
        if 'frames_count' in result:
            print(f"🎬 Extracted {result['frames_count']} frames")
        
        # Ask if user wants to index immediately
        if args.auto_index or input("\n🤖 Index this video now? (y/N): ").lower() == 'y':
            print("\n🔄 Starting indexing...")
            indexer = VideoIndexer()
            indexer.create_collection(recreate=False)
            
            try:
                frames = indexer._load_video_metadata(Path(result['metadata_file']))
                indexer.index_frames(frames)
                print("\n✨ Video downloaded and indexed successfully!")
            except Exception as e:
                print(f"❌ Error during indexing: {e}")
        
        return 0
    else:
        print(f"❌ {result['message']}")
        return 1


def index_command(args):
    """Handle the index command."""
    print("🚀 Starting Video Indexer...")
    
    indexer = VideoIndexer()
    indexer.create_collection(recreate=args.recreate)
    
    if args.video_id:
        # Index specific video
        try:
            indexer.index_single_video(args.video_id, args.video_dir)
        except Exception as e:
            print(f"❌ Error: {e}")
            return 1
    else:
        # Index all videos
        try:
            frames = indexer.load_all_videos_metadata(args.video_dir)
            if not frames:
                print("❌ No video metadata found! Download some videos first.")
                return 1
            indexer.index_frames(frames, batch_size=args.batch_size)
        except Exception as e:
            print(f"❌ Error: {e}")
            return 1
    
    print("\n✨ Indexing complete! View in Qdrant: http://localhost:6333/dashboard")
    return 0


def query_command(args):
    """Handle the query command."""
    engine = VideoQueryEngine()
    
    if args.text:
        results = engine.search_by_text(args.text, args.limit, args.video_id)
        display_results(results, args.text)
    
    elif args.image:
        results = engine.search_by_image(args.image, args.limit, args.video_id)
        display_results(results, f"Image: {args.image}")
    
    elif args.time_range:
        start = parse_time(args.time_range[0])
        end = parse_time(args.time_range[1])
        results = engine.search_by_time_range(start, end, args.limit, args.video_id)
        display_results(results, f"Time range: {args.time_range[0]} - {args.time_range[1]}")
    
    else:
        print("❌ Please specify a query type: --text, --image, or --time-range")
        return 1
    
    return 0


def list_command(args):
    """Handle the list command."""
    if args.type == "videos":
        indexer = VideoIndexer()
        videos = indexer.get_video_list(args.video_dir)
        
        if not videos:
            print("📭 No videos found.")
            return 0
        
        print(f"\n📚 Found {len(videos)} video(s):")
        print("-" * 80)
        
        for video in videos:
            duration_int = int(video['duration'])  # Convert float to int for formatting
            duration_str = f"{duration_int // 60}:{duration_int % 60:02d}"
            print(f"🎬 {video['title']}")
            print(f"   ID: {video['id']}")
            print(f"   Duration: {duration_str} | Frames: {video['frames_count']}")
            if video['uploader']:
                print(f"   Uploader: {video['uploader']}")
            if video['processed_date']:
                print(f"   Processed: {video['processed_date'][:10]}")
            print(f"   URL: {video['url']}")
            print()
            
    elif args.type == "stats":
        indexer = VideoIndexer()
        stats = indexer.get_collection_stats()
        
        if "error" in stats:
            print(f"❌ Error getting stats: {stats['error']}")
            return 1
        
        print("\n📊 Collection Statistics:")
        print(f"   Total frames indexed: {stats['total_points']}")
        print(f"   Total videos: {stats['total_videos']}")
        print(f"   Vector dimension: {stats['vector_size']}")
        print(f"   Distance metric: {stats['distance']}")
        
        if stats['videos']:
            print("\n🎬 Videos breakdown:")
            for video_id, info in stats['videos'].items():
                print(f"   {info['title']}: {info['frame_count']} frames")
    
    return 0


def delete_command(args):
    """Handle the delete command."""
    if not args.video_id:
        print("❌ Please specify a video ID to delete")
        return 1
    
    indexer = VideoIndexer()
    
    # Confirm deletion
    if not args.force:
        confirm = input(f"⚠️  Delete all frames for video '{args.video_id}'? (y/N): ")
        if confirm.lower() != 'y':
            print("🚫 Deletion cancelled.")
            return 0
    
    try:
        indexer.delete_video_frames(args.video_id)
        print("✅ Video frames deleted successfully!")
        return 0
    except Exception as e:
        print(f"❌ Error deleting video: {e}")
        return 1


def test_command(args):
    """Handle the test command."""
    print("🧪 Testing YouTube connectivity...")
    
    downloader = YouTubeDownloader()
    result = downloader.test_youtube_connection()
    
    if result['success']:
        print(f"✅ {result['message']}")
        print(f"🎬 Test video: {result['test_video_title']}")
        print("🎉 You can now download YouTube videos!")
        return 0
    else:
        print(f"❌ {result['message']}")
        print(f"💡 {result['suggestion']}")
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Video RAG System - Search video content with AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download a YouTube video
  python main.py download "https://www.youtube.com/watch?v=VIDEO_ID"
  
  # Index all videos
  python main.py index
  
  # Index specific video
  python main.py index --video-id VIDEO_ID
  
  # Search by text
  python main.py query --text "person explaining concept"
  
  # Search within specific video
  python main.py query --text "neural networks" --video-id VIDEO_ID
  
  # Search by image
  python main.py query --image screenshots/frame_0100.jpg
  
  # Search by time range
  python main.py query --time-range 5:00 10:00 --video-id VIDEO_ID
  
  # List all videos
  python main.py list videos
  
  # Show collection statistics
  python main.py list stats
  
  # Delete video frames
  python main.py delete --video-id VIDEO_ID
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Download command
    download_parser = subparsers.add_parser('download', help='Download YouTube video')
    download_parser.add_argument('url', help='YouTube video URL')
    download_parser.add_argument('--output-dir', default='video-downloads', help='Output directory')
    download_parser.add_argument('--frame-interval', type=int, default=5, help='Frame extraction interval (seconds)')
    download_parser.add_argument('--resolution', default='720p', help='Max video resolution')
    download_parser.add_argument('--auto-index', action='store_true', help='Automatically index after download')
    
    # Index command
    index_parser = subparsers.add_parser('index', help='Index video frames')
    index_parser.add_argument('--recreate', action='store_true', help='Recreate collection')
    index_parser.add_argument('--batch-size', type=int, default=config.BATCH_SIZE, help='Batch size')
    index_parser.add_argument('--video-id', help='Index specific video by ID')
    index_parser.add_argument('--video-dir', default='video-downloads', help='Video directory')
    
    # Query command
    query_parser = subparsers.add_parser('query', help='Query video frames')
    query_parser.add_argument('--text', help='Text query')
    query_parser.add_argument('--image', help='Image path for similarity search')
    query_parser.add_argument('--time-range', nargs=2, metavar=('START', 'END'), help='Time range (MM:SS)')
    query_parser.add_argument('--limit', type=int, default=config.DEFAULT_SEARCH_LIMIT, help='Result limit')
    query_parser.add_argument('--video-id', help='Filter by specific video ID')
    
    # List command
    list_parser = subparsers.add_parser('list', help='List videos or show stats')
    list_parser.add_argument('type', choices=['videos', 'stats'], help='What to list')
    list_parser.add_argument('--video-dir', default='video-downloads', help='Video directory')
    
    # Delete command
    delete_parser = subparsers.add_parser('delete', help='Delete video frames')
    delete_parser.add_argument('--video-id', required=True, help='Video ID to delete')
    delete_parser.add_argument('--force', action='store_true', help='Skip confirmation')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test YouTube connectivity')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == 'download':
        return download_command(args)
    elif args.command == 'index':
        return index_command(args)
    elif args.command == 'query':
        return query_command(args)
    elif args.command == 'list':
        return list_command(args)
    elif args.command == 'delete':
        return delete_command(args)
    elif args.command == 'test':
        return test_command(args)


if __name__ == "__main__":
    sys.exit(main())