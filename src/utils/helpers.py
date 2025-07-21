"""Helper utilities for the Video RAG system."""

from datetime import timedelta
from typing import List, Dict


def format_time(seconds: int) -> str:
    """Convert seconds to MM:SS format."""
    return str(timedelta(seconds=seconds))[2:7]


def parse_time(time_str: str) -> int:
    """Convert MM:SS format to seconds."""
    parts = time_str.split(':')
    return int(parts[0]) * 60 + int(parts[1])


def display_results(results: List[Dict], query: str = ""):
    """Display search results in a formatted way."""
    if not results:
        print(f"\n❌ No results found{f' for: {query}' if query else ''}")
        return
        
    print(f"\n🔍 Found {len(results)} results{f' for: {query}' if query else ''}")
    print("=" * 60)
    
    for i, result in enumerate(results, 1):
        print(f"\n{i}. ⏱️  {result['timestamp']}")
        if 'score' in result:
            print(f"   📊 Score: {result['score']:.3f}")
        print(f"   🔗 {result['youtube_url']}")