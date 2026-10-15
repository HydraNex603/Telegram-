import telebot
import instaloader
import re
import time
import io
import requests

BOT_TOKEN = "8893348654:AAHWy4If_wFPRozLKXunPNm2IKSwjyuzqWg"
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# ---------- Instaloader ----------
L = instaloader.Instaloader(
    save_metadata=False,
    download_comments=False,
    post_metadata_txt_pattern="",
    quiet=True,
)

# ---------- Cache ----------
CACHE = {}
CACHE_LIMIT = 20


def extract_shortcode(url):
    m = re.search(r"/(?:reel|reels|p|tv)/([^/?]+)", url)
    return m.group(1) if m else None


def get_best_video_url(post):
    """
    Highest quality video URL nikaalta hai.
    Priority: video_url → DASH highest → sidecar best
    """
    # 1) Default best (Instaloader already picks highest)
    if post.video_url:
        return post.video_url

    # 2) Carousel — best video node
    if post.typename == "GraphSidecar":
        best = None
        best_score = -1
        for node in post.get_sidecar_nodes():
            if node.is_video and node.video_url:
                # resolution ke hisaab se best chuno (agar available ho)
                try:
                    score = (node.video_duration or 0) + (node.video_view_count or 0) * 0
                except Exception:
                    score = 1
                if score > best_score:
                    best_score = score
                    best = node.video_url
        return best

    return None


def fetch_reel_bytes(url):
    """Reel ko memory me fetch karta hai — disk pe kuch save nahi."""
    shortcode = extract_shortcode(url)
    if not shortcode:
        return None

    if shortcode in CACHE:
        return io.BytesIO(CACHE[shortcode])

    try:
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        video_url = get_best_video_url(post)

        if not video_url:
            return None

        headers = {
            "User-Agent": L.context.user_agent,
            "Accept": "*/*",
        }

        # Best quality stream → RAM
        r = requests.get(video_url, headers=headers, stream=True, timeout=90)
        r.raise_for_status()
        data = r.content

        # Cache only if < 50 MB
        if len(data) < 50 * 1024 * 1024:
            if len(CACHE) >= CACHE_LIMIT:
                CACHE.pop(next(iter(CACHE)))
            CACHE[shortcode] = data

        return io.BytesIO(data)

    except Exception as e:
        print(f"❌ Fetch error: {e}")
        return None


# ---------- /start & /help ----------
@bot.message_handler(commands=["start", "help"])
def cmd_start(msg):
    text = (
        "🎬 <b>『 𝙉𝙚𝙭𝙤𝙍𝙚𝙚𝙡𝙨 』 𝘿𝙤𝙬𝙣𝙡𝙤𝙖𝙙𝙚𝙧</b> ⚡\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "✨ <b>Welcome!</b>\n\n"
        "📥 Send me any <b>Instagram Reel</b> link and I'll "
        "fetch the video instantly in <b>HD quality</b>.\n\n"
        "🚀 <b>Features:</b>\n"
        "  ✅ HD Quality Video\n"
        "  ⚡ Super Fast Delivery\n"
        "  🎯 Direct To You\n"
        "  🆓 100% Free Service\n\n"
        "📌 <b>Example:</b>\n"
        "<code>https://www.instagram.com/reel/xxxxx/</code>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━"
    )
    bot.send_message(msg.chat.id, text)


# ---------- Main handler ----------
@bot.message_handler(func=lambda m: True)
def handle_link(msg):
    url = (msg.text or "").strip()

    if "instagram.com" not in url:
        bot.reply_to(
            msg,
            "❌ <b>Invalid Link</b>\n\n"
            "💡 Please send a valid Instagram Reel URL.\n"
            "📌 Example: <code>https://www.instagram.com/reel/xxxxx/</code>",
        )
        return

    t0 = time.time()
    status = bot.reply_to(
        msg,
        "⏳ <b>Processing...</b>\n\n🔍 Fetching reel data...",
    )

    try:
        bot.edit_message_text(
            "📥 <b>Downloading...</b>\n\n⚡ Please wait...",
            msg.chat.id, status.message_id,
        )
    except Exception:
        pass

    video_io = fetch_reel_bytes(url)

    if video_io:
        try:
            bot.edit_message_text(
                "📤 <b>Uploading...</b>\n\n🚀 Almost done...",
                msg.chat.id, status.message_id,
            )
        except Exception:
            pass

        try:
            speed = time.time() - t0
            caption = (
                "✅ <b>Download Complete!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "🎬 <b>Your Reel is Ready</b>\n"
                "💎 Quality: <b>HD</b>\n"
                f"⚡ Speed: <b>{speed:.1f}s</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                "💫 Enjoy! 🎉"
            )
            bot.send_video(
                msg.chat.id,
                video_io,
                caption=caption,
                supports_streaming=True,
            )
            try:
                bot.delete_message(msg.chat.id, status.message_id)
            except Exception:
                pass
        except Exception as e:
            print(f"Upload error: {e}")
            try:
                bot.edit_message_text(
                    "❌ <b>Upload Failed</b>\n\n😕 Please try again.",
                    msg.chat.id, status.message_id,
                )
            except Exception:
                pass
    else:
        err = (
            "❌ <b>Download Failed</b>\n\n"
            "📋 <b>Possible reasons:</b>\n"
            "  • Private account / reel\n"
            "  • Invalid URL\n"
            "  • Instagram rate limit\n\n"
            "💡 Try again in a few minutes."
        )
        try:
            bot.edit_message_text(err, msg.chat.id, status.message_id)
        except Exception:
            pass


# ---------- Startup banner ----------
print("================================")
print("  🤖 『 𝙉𝙚𝙭𝙤𝙍𝙚𝙚𝙡𝙨 』 𝘿𝙤𝙬𝙣𝙡𝙤𝙖𝙙𝙚𝙧 ONLINE")
print("================================")
print("  ✅ Bot is running successfully")
print("  📡 Waiting for messages...")
print("  🟢 Service Active")
print("================================")

# ---------- Infinity polling ----------
while True:
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=30, skip_pending=True)
    except Exception as e:
        print(f"⚠️ Connection error: {e}")
        print("🔄 Restarting bot in 3 seconds...")
        time.sleep(3)