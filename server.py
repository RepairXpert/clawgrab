import os
import re
import tempfile
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

def detect_platform(url):
    if re.search(r'tiktok\.com', url): return 'TikTok'
    if re.search(r'youtube\.com|youtu\.be', url): return 'YouTube'
    if re.search(r'instagram\.com', url): return 'Instagram'
    if re.search(r'twitter\.com|x\.com', url): return 'Twitter/X'
    return 'Video'

def transcribe():
    try:
        data = request.get_json()
        if not data or not data.get('url'):
            return jsonify({'error': 'Missing url'}), 400
        url = data['url'].strip()
        print('Received URL:', url)
        platform = detect_platform(url)
        print('Platform:', platform)
        with tempfile.TemporaryDirectory() as tmpdir:
            print('Starting transcript grab...')
            text = get_transcript(url, tmpdir)
            print('Transcript result:', text[:100] if text else 'None')
            if not text:
                return jsonify({'error': 'Could not grab transcript'}), 500
            return jsonify({
                'platform': platform,
                'plain': text,
                'timed': text,
                'url': url,
                'word_count': len(text.split())
            })
    except Exception as e:
        print('FATAL ERROR:', str(e))
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
    lines = vtt.splitlines()
    seen = set()
    result = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith('WEBVTT') or '-->' in line:
            continue
        clean = re.sub(r'<[^>]+>', '', line).strip()
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return ' '.join(result)

def get_transcript(url, tmpdir):
    try:
        result = subprocess.run([
            'yt-dlp',
            '--write-auto-subs',
            '--write-subs',
            '--sub-langs', 'en.*',
            '--sub-format', 'vtt/best',
            '--skip-download',
            '--no-check-certificates',
            '--output', os.path.join(tmpdir, 'caption'),
            url
        ], capture_output=True, text=True, timeout=60)
        print('yt-dlp stdout:', result.stdout[-500:])
        print('yt-dlp stderr:', result.stderr[-500:])
        for f in Path(tmpdir).glob('caption*.vtt'):
            text = clean_vtt(f.read_text(encoding='utf-8', errors='ignore'))
            if text:
                return text
    except Exception as e:
        print('Error:', e)
    return None

@app.route('/api/transcribe', methods=['POST'])
def transcribe():
    data = request.get_json()
    if not data or not data.get('url'):
        return jsonify({'error': 'Missing url'}), 400
    url = data['url'].strip()
    platform = detect_platform(url)
    with tempfile.TemporaryDirectory() as tmpdir:
        text = get_transcript(url, tmpdir)
        if not text:
            return jsonify({'error': 'Could not grab transcript'}), 500
        return jsonify({
            'platform': platform,
            'plain': text,
            'timed': text,
            'url': url,
            'word_count': len(text.split())
        })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print('ClawGrab running on port', port)
    app.run(host='0.0.0.0', port=port, debug=False)