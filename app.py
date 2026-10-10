import os
import random
import string
from flask import Flask, request, jsonify, redirect, render_template_string
from upstash_redis import Redis

app = Flask(__name__)

# Upstash Redis কানেকশন
redis = Redis(
    url=os.environ.get("UPSTASH_REDIS_REST_URL"),
    token=os.environ.get("UPSTASH_REDIS_REST_TOKEN")
)

# ফ্রন্টএন্ড UI টেমপ্লেট
HTML_PAGE = """
<!DOCTYPE html>
<html lang="bn">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Smart URL Shortener</title>
  <style>
    body { font-family: sans-serif; background: #0f172a; color: #fff; display: flex; justify-content: center; align-items: center; min-height: 100vh; margin: 0; padding: 20px; box-sizing: border-box; }
    .card { background: #1e293b; padding: 24px; border-radius: 12px; width: 100%; max-width: 440px; box-shadow: 0 10px 25px rgba(0,0,0,0.4); }
    h2 { margin-top: 0; text-align: center; color: #38bdf8; }
    label { font-size: 13px; color: #94a3b8; display: block; margin-top: 12px; margin-bottom: 4px; }
    input { width: 100%; padding: 10px; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: #fff; box-sizing: border-box; }
    button { width: 100%; padding: 12px; margin-top: 20px; background: #0284c7; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; }
    button:hover { background: #0369a1; }
    #result { margin-top: 18px; padding: 12px; background: #0f172a; border-radius: 6px; word-break: break-all; display: none; }
    #result a { color: #38bdf8; text-decoration: none; }
  </style>
</head>
<body>
  <div class="card">
    <h2>Smart URL Shortener</h2>
    <label>টার্গেট লিংক (Destination URL)</label>
    <input type="url" id="targetUrl" placeholder="https://example.com" required>

    <label>কাস্টম প্রিভিউ টাইটেল (Title)</label>
    <input type="text" id="linkTitle" placeholder="Exclusive Video / Post Title">

    <label>কাস্টম থাম্বনেইল/ছবি (Direct Image URL)</label>
    <input type="url" id="linkImage" placeholder="https://i.ibb.co/example.jpg">

    <button onclick="createShortLink()">Generate Short Link</button>

    <div id="result">
      শর্ট লিংক: <br>
      <a id="shortUrl" target="_blank"></a>
    </div>
  </div>

  <script>
    async function createShortLink() {
      const url = document.getElementById('targetUrl').value.trim();
      const title = document.getElementById('linkTitle').value.trim();
      const image = document.getElementById('linkImage').value.trim();

      if (!url) return alert('অনুগ্রহ করে মূল লিংকটি দিন!');

      const res = await fetch('/api/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, title, image })
      });

      const data = await res.json();
      if (data.code) {
        const fullShortUrl = `${window.location.origin}/r/${data.code}`;
        const resultDiv = document.getElementById('result');
        const linkTag = document.getElementById('shortUrl');
        linkTag.href = fullShortUrl;
        linkTag.innerText = fullShortUrl;
        resultDiv.style.display = 'block';
      } else {
        alert('ত্রুটি: ' + (data.error || 'কিছু ভুল হয়েছে'));
      }
    }
  </script>
</body>
</html>
"""

# মেটা ট্যাগ প্রিভিউ টেমপ্লেট (Facebook, Telegram বটের জন্য)
BOT_PREVIEW_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>{{ data.title }}</title>
  <meta property="og:title" content="{{ data.title }}">
  <meta property="og:image" content="{{ data.image }}">
  <meta property="og:url" content="{{ data.url }}">
  <meta property="og:type" content="website">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="{{ data.title }}">
  <meta name="twitter:image" content="{{ data.image }}">
</head>
<body></body>
</html>"""

@app.route("/")
def home():
    return render_template_string(HTML_PAGE)

@app.route("/api/create", methods=["POST"])
def create_link():
    payload = request.get_json() or {}
    url = payload.get("url")
    title = payload.get("title") or "Shared Link"
    image = payload.get("image") or ""

    if not url:
        return jsonify({"error": "URL is required"}), 400

    # ৫ অক্ষরের ইউনিক কোড তৈরি
    code = ''.join(random.choices(string.ascii_letters + string.digits, k=5))

    # Upstash-এ ডেটা রাখা
    redis.set(code, {"url": url, "title": title, "image": image})

    return jsonify({"code": code})

@app.route("/r/<code>")
def handle_redirect(code):
    data = redis.get(code)
    if not data:
        return "Link not found or expired", 404

    # ডেটা ডিকশনারি ফরম্যাটে নিশ্চিত করা
    if isinstance(data, str):
        import json
        data = json.loads(data)

    user_agent = request.headers.get("User-Agent", "").lower()
    bot_keywords = ["facebookexternalhit", "facebot", "twitterbot", "telegrambot", "whatsapp", "slackbot", "discordbot"]

    # সোশ্যাল মিডিয়া বট আসলে মেটা ট্যাগ পেজ পাঠানো
    if any(bot in user_agent for bot in bot_keywords):
        return render_template_string(BOT_PREVIEW_TEMPLATE, data=data)

    # আসল ইউজার হলে সোজা টার্গেট লিংকে পাঠানো
    return redirect(data.get("url"), code=302)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)