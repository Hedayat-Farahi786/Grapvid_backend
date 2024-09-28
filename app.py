from flask import Flask, request, jsonify
import yt_dlp
from flask_cors import CORS
from collections import defaultdict
import logging

app = Flask(__name__)
CORS(app)  # Enable CORS to allow requests from your frontend

# Set up logging for better visibility
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def format_size(size):
    """Handle None and pre-formatted size strings."""
    if isinstance(size, str) and " " in size:
        return size

    if size is None:
        return 'Unknown size'

    size = int(size)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} TB"

def convert_filesize_to_int(size):
    """Convert human-readable filesize (e.g., '26.36 MB') to integer bytes."""
    if size == 'Unknown size':
        return -1

    if isinstance(size, int):
        return size

    size_str, unit = size.split()
    size_value = float(size_str)

    units = {'B': 1, 'KB': 1024, 'MB': 1024 ** 2, 'GB': 1024 ** 3, 'TB': 1024 ** 4}

    return int(size_value * units[unit])

@app.route('/api/video-info', methods=['POST'])
def video_info():
    try:
        url = request.json.get('url')
        if not url:
            return jsonify({'error': 'Missing YouTube URL'}), 400

        logger.debug(f"Fetching video info for URL: {url}")

        # Use yt-dlp to fetch video info
        ydl_opts = {
            'cookiefile': 'cookies.txt',  # Path to your cookies file
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3',
            # Add any other options you need...
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

        # Get all formats
        formats = [{
            'itag': f['format_id'],
            'quality': f.get('format_note', 'Unknown quality'),
            'mimeType': f['ext'],
            'resolution': f.get('resolution', 'Unknown resolution'),
            'filesize': format_size(f.get('filesize')),
            'has_audio': f.get('acodec') != 'none',
            'has_video': f.get('vcodec') != 'none'
        } for f in info['formats']]

        logger.debug(f"Fetched {len(formats)} formats")

        video_info = {
            'title': info['title'],
            'description': info.get('description', ''),
            'thumbnailUrl': info['thumbnail'],
            'duration': info['duration'],
            'formats': formats
        }

        return jsonify(video_info)

    except Exception as e:
        logger.error(f"Error in video_info: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/download', methods=['GET'])
def download_video():
    url = request.args.get('url')
    video_itag = request.args.get('videoItag')
    audio_itag = request.args.get('audioItag')

    if not url or not video_itag or not audio_itag:
        return jsonify({'error': 'Missing URL or format (itag)'}), 400

    try:
        logger.debug(f"Preparing download for URL: {url} with video itag: {video_itag} and audio itag: {audio_itag}")

        # Set yt-dlp options to fetch the video and audio URLs
        ydl_opts = {
            'format': f'{video_itag}+{audio_itag}',
            'noplaylist': True,
            'skip_download': True,  # Skip actual file download, just get the info
            'no_warnings': True,  # Suppress warnings
            'merge_output_format': 'mp4'  # Ensure the output format is mp4
        }

        # Extract video info to get the streaming URLs
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            logger.debug("Video info extracted successfully")

            # Attempt to get the video URL from the info
            video_url = None
            for f in info['formats']:
                if f['format_id'] == video_itag or f['format_id'] == audio_itag:
                    video_url = f['url']
                    break

            if not video_url:
                logger.error("Video URL not found or invalid format selected")
                return jsonify({'error': 'Video URL not found'}), 404

            video_title = info.get('title', 'video').replace(" ", "_")
            logger.debug(f"Video title: {video_title}")

        return jsonify({
            'video_url': video_url,
            'video_title': f'{video_title}.mp4'
        })

    except Exception as e:
        logger.error(f"Error in download_video: {str(e)}")  # Log the error
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(port=5001, debug=True)
