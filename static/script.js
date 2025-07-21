// Video RAG Bot - Enhanced Multi-Video Interface

let currentProcessingVideoId = null;
let statusCheckInterval = null;

// Initialize the app
document.addEventListener('DOMContentLoaded', function() {
    loadStats();
    loadVideoList();
    setupTabHandlers();
    setupSearchHandlers();
});

// Tab handling for main tabs
function setupTabHandlers() {
    // Main tabs
    document.querySelectorAll('.main-tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const tabName = this.dataset.tab;
            switchMainTab(tabName);
        });
    });

    // Search sub-tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const tabName = this.dataset.tab;
            switchSearchTab(tabName);
        });
    });
}

function switchMainTab(tabName) {
    // Update button states
    document.querySelectorAll('.main-tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Update content visibility
    document.querySelectorAll('.main-tab-content').forEach(content => {
        content.classList.remove('active');
    });
    document.getElementById(`${tabName}-tab`).classList.add('active');

    // Load data when switching to manage tab
    if (tabName === 'manage') {
        loadVideoList();
    }
}

function switchSearchTab(tabName) {
    // Update button states
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active');
    });
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Update panel visibility
    document.querySelectorAll('.search-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    document.getElementById(`${tabName}-search`).classList.add('active');
}

// Search handlers
function setupSearchHandlers() {
    // Enter key handlers
    document.getElementById('text-query').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            performSearch('text');
        }
    });

    document.getElementById('start-time').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            performSearch('time');
        }
    });

    document.getElementById('end-time').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            performSearch('time');
        }
    });

    document.getElementById('youtube-url').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            downloadVideo();
        }
    });
}

// Search functionality
async function performSearch(type) {
    const loadingDiv = document.getElementById('loading');
    const resultsDiv = document.getElementById('results');
    
    loadingDiv.classList.remove('hidden');
    resultsDiv.innerHTML = '';

    let searchData = {
        search_type: type,
        limit: parseInt(document.getElementById('limit').value),
        video_id: document.getElementById('video-filter').value || null
    };

    if (type === 'text') {
        const query = document.getElementById('text-query').value.trim();
        if (!query) {
            loadingDiv.classList.add('hidden');
            alert('Please enter a search query');
            return;
        }
        searchData.query = query;
    } else if (type === 'time') {
        const startTime = document.getElementById('start-time').value.trim();
        const endTime = document.getElementById('end-time').value.trim();
        
        if (!startTime || !endTime) {
            loadingDiv.classList.add('hidden');
            alert('Please enter both start and end times');
            return;
        }
        
        searchData.query = 'time_range_search';
        searchData.start_time = startTime;
        searchData.end_time = endTime;
    }

    try {
        const response = await fetch('/api/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(searchData)
        });

        const results = await response.json();
        
        loadingDiv.classList.add('hidden');
        
        if (results.length === 0) {
            resultsDiv.innerHTML = '<p class="no-results">No results found. Try different keywords or check if videos are indexed.</p>';
            return;
        }

        displayResults(results, searchData);
        
    } catch (error) {
        loadingDiv.classList.add('hidden');
        console.error('Search error:', error);
        resultsDiv.innerHTML = '<p class="error">Search failed. Please try again.</p>';
    }
}

function displayResults(results, searchData) {
    const resultsDiv = document.getElementById('results');
    
    let html = `<h2>📋 Search Results (${results.length})</h2>`;
    
    // Group results by video if searching across all videos
    if (!searchData.video_id && results.length > 0) {
        const groupedResults = groupResultsByVideo(results);
        
        for (const [videoTitle, videoResults] of Object.entries(groupedResults)) {
            html += `<div class="video-group">
                <h3 class="video-group-title">🎬 ${videoTitle} (${videoResults.length} results)</h3>
                <div class="video-group-results">`;
            
            videoResults.forEach(result => {
                html += createResultCard(result);
            });
            
            html += '</div></div>';
        }
    } else {
        // Regular display for single video or time search
        results.forEach(result => {
            html += createResultCard(result);
        });
    }
    
    resultsDiv.innerHTML = html;
}

function groupResultsByVideo(results) {
    const grouped = {};
    results.forEach(result => {
        const videoTitle = result.video_title;
        if (!grouped[videoTitle]) {
            grouped[videoTitle] = [];
        }
        grouped[videoTitle].push(result);
    });
    return grouped;
}

function createResultCard(result) {
    const scoreText = result.score ? 
        `<div class="result-score">${(result.score * 100).toFixed(1)}% match</div>` : '';
    
    return `
        <div class="result-item">
            <img src="${result.thumbnail}" alt="Frame ${result.frame_id}" class="result-thumbnail" 
                 onerror="this.src='data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEyMCIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB3aWR0aD0iMjAwIiBoZWlnaHQ9IjEyMCIgZmlsbD0iI2Y1ZjVmNSIvPjx0ZXh0IHg9IjUwJSIgeT0iNTAlIiBkb21pbmFudC1iYXNlbGluZT0ibWlkZGxlIiB0ZXh0LWFuY2hvcj0ibWlkZGxlIiBmb250LWZhbWlseT0iQXJpYWwsIHNhbnMtc2VyaWYiIGZvbnQtc2l6ZT0iMTRweCIgZmlsbD0iIzk5OSI+SW1hZ2UgTm90IEZvdW5kPC90ZXh0Pjwvc3ZnPg=='">
            <div class="result-details">
                <div class="result-header">
                    <div class="result-time">⏱️ ${result.timestamp}</div>
                    ${scoreText}
                </div>
                <p class="result-video">🎬 ${result.video_title}</p>
                <p class="result-id">Frame ID: ${result.frame_id}</p>
                <a href="${result.youtube_url}" target="_blank" class="watch-link">
                    🎬 Watch on YouTube
                </a>
            </div>
        </div>
    `;
}

// YouTube Download functionality
async function downloadVideo() {
    const url = document.getElementById('youtube-url').value.trim();
    const frameInterval = parseInt(document.getElementById('frame-interval').value);
    const autoIndex = document.getElementById('auto-index').checked;
    const keepVideo = document.getElementById('keep-video').checked;

    if (!url) {
        alert('Please enter a YouTube URL');
        return;
    }

    // Validate URL
    if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
        alert('Please enter a valid YouTube URL');
        return;
    }

    const downloadData = {
        url: url,
        frame_interval: frameInterval,
        auto_index: autoIndex,
        keep_video_file: keepVideo
    };

    try {
        const response = await fetch('/api/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(downloadData)
        });

        const result = await response.json();

        if (result.success) {
            currentProcessingVideoId = result.video_id;
            showDownloadStatus();
            
            if (result.message === "Video already processed") {
                document.getElementById('status-message').textContent = 'Video already exists in library!';
                document.getElementById('progress-fill').style.width = '100%';
                setTimeout(() => {
                    hideDownloadStatus();
                    switchMainTab('manage');
                    loadVideoList();
                }, 2000);
            } else {
                startStatusPolling();
            }
        } else {
            alert(`Download failed: ${result.message}`);
        }
    } catch (error) {
        console.error('Download error:', error);
        alert('Download failed. Please try again.');
    }
}

function showDownloadStatus() {
    document.getElementById('download-status').classList.remove('hidden');
}

function hideDownloadStatus() {
    document.getElementById('download-status').classList.add('hidden');
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
        statusCheckInterval = null;
    }
}

function startStatusPolling() {
    if (statusCheckInterval) {
        clearInterval(statusCheckInterval);
    }

    statusCheckInterval = setInterval(async () => {
        try {
            const response = await fetch(`/api/download/status/${currentProcessingVideoId}`);
            const status = await response.json();

            document.getElementById('status-message').textContent = status.message;
            document.getElementById('progress-fill').style.width = `${status.progress}%`;

            if (status.status === 'completed' || status.status === 'error' || status.status === 'indexed_error') {
                clearInterval(statusCheckInterval);
                statusCheckInterval = null;
                
                setTimeout(() => {
                    hideDownloadStatus();
                    loadStats();
                    loadVideoList();
                    loadVideoFilter();
                    if (status.status === 'completed') {
                        switchMainTab('manage');
                    }
                }, 2000);
            }
        } catch (error) {
            console.error('Status check error:', error);
        }
    }, 2000);
}

// Video management
async function loadVideoList() {
    try {
        const response = await fetch('/api/videos');
        const videos = await response.json();
        
        const videoListDiv = document.getElementById('video-list');
        
        if (videos.length === 0) {
            videoListDiv.innerHTML = '<p class="no-videos">No videos found. Download some YouTube videos to get started!</p>';
            return;
        }

        let html = '';
        videos.forEach(video => {
            const duration = formatDuration(video.duration);
            const processedDate = video.processed_date ? 
                new Date(video.processed_date).toLocaleDateString() : 'Unknown';
            
            html += `
                <div class="video-card" data-video-id="${video.id}">
                    <div class="video-header">
                        <h3 class="video-title">${video.title}</h3>
                        <button onclick="deleteVideo('${video.id}')" class="delete-btn" title="Delete video">🗑️</button>
                    </div>
                    <div class="video-info">
                        <p><strong>ID:</strong> ${video.id}</p>
                        <p><strong>Duration:</strong> ${duration}</p>
                        <p><strong>Frames:</strong> ${video.frames_count}</p>
                        <p><strong>Uploader:</strong> ${video.uploader || 'Unknown'}</p>
                        <p><strong>Processed:</strong> ${processedDate}</p>
                        ${video.description ? `<p><strong>Description:</strong> ${video.description}</p>` : ''}
                    </div>
                    <div class="video-actions">
                        <a href="${video.url}" target="_blank" class="video-link">🎬 Watch on YouTube</a>
                        <button onclick="searchInVideo('${video.id}')" class="search-in-video-btn">🔍 Search in this video</button>
                    </div>
                </div>
            `;
        });
        
        videoListDiv.innerHTML = html;
        
        // Update video filter dropdown
        loadVideoFilter();
        
    } catch (error) {
        console.error('Error loading video list:', error);
        document.getElementById('video-list').innerHTML = '<p class="error">Failed to load videos</p>';
    }
}

async function loadVideoFilter() {
    try {
        const response = await fetch('/api/videos');
        const videos = await response.json();
        
        const filterSelect = document.getElementById('video-filter');
        filterSelect.innerHTML = '<option value="">All Videos</option>';
        
        videos.forEach(video => {
            const option = document.createElement('option');
            option.value = video.id;
            option.textContent = `${video.title} (${video.frames_count} frames)`;
            filterSelect.appendChild(option);
        });
        
    } catch (error) {
        console.error('Error loading video filter:', error);
    }
}

function searchInVideo(videoId) {
    // Switch to search tab and set video filter
    switchMainTab('search');
    document.getElementById('video-filter').value = videoId;
}

async function deleteVideo(videoId) {
    if (!confirm('Are you sure you want to delete this video? This will remove all its frames from the search index.')) {
        return;
    }

    try {
        const response = await fetch(`/api/videos/${videoId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            loadVideoList();
            loadStats();
            loadVideoFilter();
            alert('Video deleted successfully');
        } else {
            alert(`Failed to delete video: ${result.message}`);
        }
    } catch (error) {
        console.error('Delete error:', error);
        alert('Failed to delete video');
    }
}

// Statistics
async function loadStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();

        document.getElementById('total-frames').textContent = stats.total_frames || '0';
        document.getElementById('total-videos').textContent = stats.total_videos || '0';
        document.getElementById('model').textContent = stats.embedding_model || 'Unknown';
        document.getElementById('vector-size').textContent = stats.vector_size || 'Unknown';

    } catch (error) {
        console.error('Error loading stats:', error);
        document.getElementById('total-frames').textContent = 'Error';
        document.getElementById('total-videos').textContent = 'Error';
        document.getElementById('model').textContent = 'Error';
        document.getElementById('vector-size').textContent = 'Error';
    }
}

// Utility functions
function formatDuration(seconds) {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;
    
    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
    }
}