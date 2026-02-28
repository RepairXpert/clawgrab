import os
import re
import tempfile
import subprocess
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["https://getclawgrab.com","https://www.getclawgrab.com","https://roaring-valkyrie-3bf9be.netlify.app","*"])

def detect_platform(url):
    if re.search(r'tiktok\.com', url): return 'TikTok'
    if re.search(r'youtube\.com|youtu\.be', url): return 'YouTube'
    if re.search(r'instagram\.com', url): return 'Instagram'
    if re.search(r'twitter\.com|x\.com', url): return 'Twitter/X'
    return 'Video'

def clean_vtt(vtt):
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
        cmd = [
            'yt-dlp',
            '--write-auto-subs',
            '--write-subs',
            '--sub-langs', 'en.*',
            '--sub-format', 'vtt/best',
            '--skip-download',
            '--no-check-certificates',
            '--no-playlist',
            '--force-ipv4',
            '--socket-timeout', '30',
            '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            '--output', os.path.join(tmpdir, 'caption'),
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
        print('yt-dlp exit code:', result.returncode)
        print('yt-dlp stderr:', result.stderr[-300:])
        for f in Path(tmpdir).glob('caption*.vtt'):
            text = clean_vtt(f.read_text(encoding='utf-8', errors='ignore'))
            if text and len(text) > 20:
                return text
    except subprocess.TimeoutExpired:
        print('yt-dlp timeout')
    except Exception as e:
        print('Error:', e)
    return None

@app.route('/api/transcribe', methods=['POST'])
def transcribe():
    try:
        data = request.get_json()
        if not data or not data.get('url'):
            return jsonify({'error': 'Missing url'}), 400
        url = data['url'].strip()
        print('URL:', url)
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
    except Exception as e:
        print('FATAL ERROR:', str(e))
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    import hmac
    import hashlib
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature', '')
    secret = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    
    try:
        # Verify signature
        elements = dict(item.split('=', 1) for item in sig_header.split(','))
        timestamp = elements.get('t', '')
        signature = elements.get('v1', '')
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return jsonify({'error': 'Invalid signature'}), 400
    except Exception as e:
        print('Webhook signature error:', e)
        return jsonify({'error': 'Signature verification failed'}), 400

    event = request.get_json()
    print('Stripe event:', event.get('type'))

    if event.get('type') in ['checkout.session.completed', 'customer.subscription.created']:
        customer_email = event.get('data', {}).get('object', {}).get('customer_email') or \
                        event.get('data', {}).get('object', {}).get('customer_details', {}).get('email')
        if customer_email:
            print(f'Upgrading {customer_email} to Pro')
            upgrade_user_to_pro(customer_email)

    return jsonify({'status': 'ok'})

def upgrade_user_to_pro(email):
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print('Supabase not configured')
        return
    try:
        import urllib.request
        import json
        # Find user by email and update their plan
        req = urllib.request.Request(
            f'{SUPABASE_URL}/auth/v1/admin/users?email={email}',
            headers={
                'apikey': SUPABASE_SERVICE_KEY,
                'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}'
            }
        )
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read())
            users = data.get('users', [])
            if users:
                user_id = users[0]['id']
                update_req = urllib.request.Request(
                    f'{SUPABASE_URL}/auth/v1/admin/users/{user_id}',
                    data=json.dumps({'user_metadata': {'plan': 'pro'}}).encode(),
                    method='PUT',
                    headers={
                        'apikey': SUPABASE_SERVICE_KEY,
                        'Authorization': f'Bearer {SUPABASE_SERVICE_KEY}',
                        'Content-Type': 'application/json'
                    }
                )
                urllib.request.urlopen(update_req)
                print(f'✓ Upgraded {email} to Pro')
    except Exception as e:
        print(f'Error upgrading user: {e}')
@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    print('ClawGrab running on port', port)
    app.run(host='0.0.0.0', port=port, debug=False)
