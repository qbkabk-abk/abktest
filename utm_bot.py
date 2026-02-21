"""
Higgsfield UTM Link Builder — Telegram Bot (YouTube only)

Source logic:
  youtube + earn + public  → youtube_e_pu
  youtube + earn + private → youtube_e_pr
  youtube + selected       → youtube_s

Setup:
  1. pip install python-telegram-bot
  2. Get a bot token from @BotFather on Telegram
  3. export TELEGRAM_BOT_TOKEN="your_token_here"
  4. python utm_bot.py
"""

import os
import re
import random
import string
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ── Conversation states ──────────────────────────────────────────────────────
(
    INPUT_PAGE_URL,
    SELECT_CHANNEL_TYPE,
    SELECT_EARN_VISIBILITY,
    INPUT_HANDLE,
    SELECT_CAMPAIGN,
    ENTER_CUSTOM_CAMPAIGN,
    SELECT_CONTENT_TYPE,
    CONFIRM,
) = range(8)

# ── Constants ────────────────────────────────────────────────────────────────
BASE_URL = "https://higgsfield.ai"
MEDIUM = "influencer"

CAMPAIGNS = {
    "cinema_studio": {
        "label": "🎥 Cinema Studio",
        "slug": "cinema_studio",
    },
    "soul_2": {
        "label": "🖼 Soul 2.0",
        "slug": "soul_2",
    },
    "kling_3": {
        "label": "🎬 Kling 3.0",
        "slug": "kling_3",
    },
    "seedance_2": {
        "label": "🌱 Seedance 2.0",
        "slug": "seedance_2",
    },
    "general": {
        "label": "🌐 General",
        "slug": "general",
    },
}

CONTENT_TYPES = {
    "dedicated":  "de",
    "integrated": "in",
    "shorts":     "sh",
}

MONTH_TAG = datetime.now().strftime("%Y%m")


# ── Helpers ───────────────────────────────────────────────────────────────────

def sanitize(text: str) -> str:
    """Lowercase, strip, replace spaces/hyphens → underscore, remove special chars."""
    text = text.lower().strip()
    text = text.replace("-", "_").replace(" ", "_")
    text = re.sub(r"[^a-z0-9_]", "", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def extract_yt_handle(raw: str) -> str:
    """
    Parse YouTube handle from various formats:
      @aifilmmaster                          → aifilmmaster
      https://youtube.com/@aifilmmaster      → aifilmmaster
      https://youtube.com/c/Film-Riot        → film_riot
      https://youtube.com/channel/UCxxxx     → ucxxxx
      plain text                             → sanitized
    """
    raw = raw.strip()

    for pattern in [
        r"(?:https?://)?(?:www\.)?youtube\.com/@([a-zA-Z0-9_\-\.]+)",
        r"(?:https?://)?(?:www\.)?youtube\.com/c/([a-zA-Z0-9_\-\.]+)",
        r"(?:https?://)?(?:www\.)?youtube\.com/channel/([a-zA-Z0-9_\-]+)",
        r"(?:https?://)?(?:www\.)?youtube\.com/user/([a-zA-Z0-9_\-\.]+)",
    ]:
        m = re.search(pattern, raw)
        if m:
            return sanitize(m.group(1))

    if raw.startswith("@"):
        return sanitize(raw[1:])

    return sanitize(raw)


def build_source(data: dict) -> str:
    """
    youtube + earn + public  → youtube_e_pu
    youtube + earn + private → youtube_e_pr
    youtube + selected       → youtube_s
    youtube + main           → youtube_m
    """
    channel_type = data.get("channel_type", "")
    if channel_type == "earn":
        vis = data.get("earn_visibility", "pu")
        return f"youtube_e_{vis}"
    elif channel_type == "main":
        return "youtube_m"
    else:
        return "youtube_s"


import hashlib
import time


def generate_id(handle: str = "", campaign: str = "", content_type: str = "", length: int = 5) -> str:
    """Generate a unique 5-char ID seeded by handle + campaign + content + timestamp.
    Different creators will never collide because the handle is part of the seed."""
    seed = f"{handle}_{campaign}_{content_type}_{time.time_ns()}"
    h = hashlib.sha256(seed.encode()).hexdigest()
    # Convert hex to alphanumeric (a-z, 0-9)
    result = ""
    for char in h:
        if len(result) >= length:
            break
        result += char
    return result[:length]


def build_utm_url(data: dict) -> str:
    page = data.get("page", "")
    source = build_source(data)
    medium = data.get("handle", "")
    
    campaign = data["campaign_slug"]

    content_type = data.get("content_type", "")
    uid = data.get("uid", generate_id())
    content = f"{content_type}_{uid}"

    return (
        f"{BASE_URL}{page}"
        f"?utm_source={source}"
        f"&utm_medium={medium}"
        f"&utm_campaign={campaign}"
        f"&utm_content={content}"
    )


def build_summary(data: dict) -> str:
    source = build_source(data)
    handle = data.get("handle", "—")
    campaign = data.get("campaign_slug", "—")
    content_type = data.get("content_type", "—")
    uid = data.get("uid", "—")

    return "\n".join([
        "📋 *UTM Link Summary*\n",
        f"🌐 *Source:* `{source}`",
        f"📡 *Medium:* `{handle}`",
        f"🎯 *Campaign:* `{campaign}`",
        f"📝 *Content:* `{content_type}_{uid}`",
    ])


def chunked(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


# ── Handlers ──────────────────────────────────────────────────────────────────

async def start(update: Update, context) -> int:
    """Entry point — ask for page URL."""
    context.user_data.clear()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🎥 Cinema Studio", callback_data="qpage_/cinema-studio"),
            InlineKeyboardButton("🖼 Soul v2", callback_data="qpage_/image/soul-v2"),
        ],
        [
            InlineKeyboardButton("🎬 Kling 3.0", callback_data="qpage_/kling-3"),
            InlineKeyboardButton("🌱 Seedance (add link)", callback_data="qpage_custom_seedance"),
        ],
        [
            InlineKeyboardButton("✏️ Custom page", callback_data="qpage_custom"),
        ],
    ])

    text = (
        "👋 *Higgsfield UTM Builder*\n\n"
        "Which page should this link go to?\n\n"
        "Pick one or type a custom path."
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            text, reply_markup=keyboard, parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text, reply_markup=keyboard, parse_mode="Markdown"
        )
    return INPUT_PAGE_URL


async def page_url_button(update: Update, context) -> int:
    """Page picked via button."""
    query = update.callback_query
    await query.answer()

    val = query.data.replace("qpage_", "")

    if val == "custom":
        await query.edit_message_text(
            "Type the page path or full URL.\n\n"
            "Examples:\n"
            "• `/seedance`\n"
            "• `https://higgsfield.ai/contests/my-contest`",
            parse_mode="Markdown",
        )
        return INPUT_PAGE_URL

    if val == "custom_seedance":
        await query.edit_message_text(
            "🌱 *Seedance*\n\n"
            "Paste the Seedance page link.",
            parse_mode="Markdown",
        )
        return INPUT_PAGE_URL

    context.user_data["page"] = val
    return await _show_channel_type(query, context, edit=True)


async def page_url_text(update: Update, context) -> int:
    """Page typed manually — accept path or full URL."""
    raw = update.message.text.strip()

    # Strip base URL if pasted full link
    raw = re.sub(r"^https?://(www\.)?higgsfield\.ai", "", raw)

    if not raw.startswith("/"):
        raw = "/" + raw

    context.user_data["page"] = raw
    return await _show_channel_type(update, context, edit=False)


async def _show_channel_type(source, context, edit: bool) -> int:
    """Show Earn / Selected / Main Channel buttons."""
    page = context.user_data["page"]
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌍 Earn", callback_data="chtype_earn"),
            InlineKeyboardButton("🎯 Selected", callback_data="chtype_selected"),
        ],
        [
            InlineKeyboardButton("📺 Main Channel", callback_data="chtype_main"),
        ],
    ])

    text = f"✅ Page: `{page}`\n\n▶️ YouTube — Earn, Selected, or Main Channel?"

    if edit:
        await source.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await source.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return SELECT_CHANNEL_TYPE


async def channel_type_selected(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()

    chtype = query.data.replace("chtype_", "")
    context.user_data["channel_type"] = chtype

    if chtype == "earn":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔓 Public", callback_data="visibility_pu"),
                InlineKeyboardButton("🔒 Private", callback_data="visibility_pr"),
            ]
        ])
        await query.edit_message_text(
            "✅ *Earn*\n\nPublic or Private?",
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
        return SELECT_EARN_VISIBILITY

    elif chtype == "main":
        # Main channel — auto-set handle, skip to campaign
        context.user_data["handle"] = "higgsfieldai"

        keyboard = []
        for key, camp in CAMPAIGNS.items():
            keyboard.append(
                [InlineKeyboardButton(camp["label"], callback_data=f"campaign_{key}")]
            )
        keyboard.append(
            [InlineKeyboardButton("✏️ Custom campaign", callback_data="campaign_custom")]
        )

        await query.edit_message_text(
            f"✅ Source: `youtube_m`\n"
            f"✅ Medium: `higgsfieldai`\n\n"
            f"Pick the campaign.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return SELECT_CAMPAIGN

    else:
        # Selected
        await query.edit_message_text(
            f"✅ Source: `youtube_s`\n\n"
            f"Send the creator handle.\n\n"
            f"• `@handle`\n"
            f"• YouTube channel URL\n"
            f"• Or just the name",
            parse_mode="Markdown",
        )
        return INPUT_HANDLE


async def earn_visibility_selected(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()

    vis = query.data.replace("visibility_", "")
    context.user_data["earn_visibility"] = vis

    source = build_source(context.user_data)

    await query.edit_message_text(
        f"✅ Source: `{source}`\n\n"
        f"Send the creator handle.\n\n"
        f"• `@handle`\n"
        f"• YouTube channel URL\n"
        f"• Or just the name",
        parse_mode="Markdown",
    )
    return INPUT_HANDLE


async def handle_received(update: Update, context) -> int:
    raw = update.message.text.strip()
    handle = extract_yt_handle(raw)

    if not handle:
        await update.message.reply_text(
            "⚠️ Couldn't parse that. Try `@handle` or a YouTube URL.",
            parse_mode="Markdown",
        )
        return INPUT_HANDLE

    context.user_data["handle"] = handle

    keyboard = []
    for key, camp in CAMPAIGNS.items():
        keyboard.append(
            [InlineKeyboardButton(camp["label"], callback_data=f"campaign_{key}")]
        )
    keyboard.append(
        [InlineKeyboardButton("✏️ Custom campaign", callback_data="campaign_custom")]
    )

    await update.message.reply_text(
        f"✅ Handle: `{handle}`\n\nPick the campaign.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return SELECT_CAMPAIGN


async def campaign_selected(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()

    campaign_key = query.data.replace("campaign_", "")

    if campaign_key == "custom":
        await query.edit_message_text(
            "Type your custom campaign name.\n"
            "Auto-formatted to snake\\_case.\n\n"
            "Example: `soul_launch_feb`",
            parse_mode="Markdown",
        )
        return ENTER_CUSTOM_CAMPAIGN

    camp = CAMPAIGNS[campaign_key]
    context.user_data["campaign_slug"] = camp["slug"]
    context.user_data["campaign_label"] = camp["label"]

    return await _show_content_type(query, context)


async def custom_campaign_received(update: Update, context) -> int:
    raw = update.message.text.strip()
    slug = sanitize(raw)

    if not slug:
        await update.message.reply_text("⚠️ Invalid name. Try again.")
        return ENTER_CUSTOM_CAMPAIGN

    context.user_data["campaign_slug"] = slug
    context.user_data["campaign_label"] = raw

    keyboard = _build_content_keyboard()
    await update.message.reply_text(
        f"✅ Campaign: `{slug}`\n\nPick the content type.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return SELECT_CONTENT_TYPE


def _build_content_keyboard():
    emoji_map = {"dedicated": "🎬", "integrated": "🔗", "shorts": "📱"}
    buttons = []
    for key in CONTENT_TYPES:
        emoji = emoji_map.get(key, "📝")
        buttons.append(
            InlineKeyboardButton(f"{emoji} {key.title()}", callback_data=f"content_{key}")
        )
    return [buttons]


async def _show_content_type(query, context) -> int:
    keyboard = _build_content_keyboard()
    await query.edit_message_text(
        "Pick the content type.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return SELECT_CONTENT_TYPE


async def content_selected(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()

    content_key = query.data.replace("content_", "")
    context.user_data["content_type"] = CONTENT_TYPES[content_key]
    context.user_data["uid"] = generate_id(
        handle=context.user_data.get("handle", ""),
        campaign=context.user_data.get("campaign_slug", ""),
        content_type=context.user_data.get("content_type", ""),
    )

    return await _show_confirm(query, context, edit=True)


async def regenerate_id(update: Update, context) -> int:
    """Generate a new random ID and show updated link."""
    query = update.callback_query
    await query.answer()

    context.user_data["uid"] = generate_id(
        handle=context.user_data.get("handle", ""),
        campaign=context.user_data.get("campaign_slug", ""),
        content_type=context.user_data.get("content_type", ""),
    )
    return await _show_confirm(query, context, edit=True)


async def _show_confirm(source, context, edit: bool) -> int:
    data = context.user_data
    url = build_utm_url(data)
    summary = build_summary(data)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Copy as plain text", callback_data="copy_link"),
            InlineKeyboardButton("🔄 Start over", callback_data="restart"),
        ],
        [
            InlineKeyboardButton("🔀 New ID", callback_data="regen_id"),
        ],
    ])

    text = (
        f"{summary}\n\n"
        f"───────────────\n"
        f"🔗 *Your UTM link:*\n\n"
        f"`{url}`\n\n"
        f"───────────────\n"
        f"Tap the link above to copy."
    )

    if edit:
        await source.edit_message_text(
            text, reply_markup=keyboard, parse_mode="Markdown"
        )
    else:
        await source.message.reply_text(
            text, reply_markup=keyboard, parse_mode="Markdown"
        )
    return CONFIRM


async def copy_link(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    url = build_utm_url(context.user_data)
    await query.message.reply_text(url)
    return CONFIRM


async def restart(update: Update, context) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    return await start(update, context)


async def cancel(update: Update, context) -> int:
    await update.message.reply_text("Cancelled. /start to begin again.")
    context.user_data.clear()
    return ConversationHandler.END


async def help_command(update: Update, context) -> None:
    text = (
        "*Higgsfield UTM Builder* 🔗\n\n"
        "*Flow:*\n"
        "Earn/Selected → (Public/Private) → Handle → Campaign → Content → Version → Link\n\n"
        "*Source codes:*\n"
        "`youtube_e_pu` — Earn Public\n"
        "`youtube_e_pr` — Earn Private\n"
        "`youtube_s` — Selected\n\n"
        "*Commands:*\n"
        "/start — New UTM link\n"
        "/help — This message\n"
        "/cancel — Cancel\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ Set TELEGRAM_BOT_TOKEN first:")
        print("   export TELEGRAM_BOT_TOKEN='your_token_here'")
        return

    app = Application.builder().token(token).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            INPUT_PAGE_URL: [
                CallbackQueryHandler(page_url_button, pattern=r"^qpage_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, page_url_text),
            ],
            SELECT_CHANNEL_TYPE: [
                CallbackQueryHandler(channel_type_selected, pattern=r"^chtype_"),
            ],
            SELECT_EARN_VISIBILITY: [
                CallbackQueryHandler(earn_visibility_selected, pattern=r"^visibility_"),
            ],
            INPUT_HANDLE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_received),
            ],
            SELECT_CAMPAIGN: [
                CallbackQueryHandler(campaign_selected, pattern=r"^campaign_"),
            ],
            ENTER_CUSTOM_CAMPAIGN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_campaign_received),
            ],
            SELECT_CONTENT_TYPE: [
                CallbackQueryHandler(content_selected, pattern=r"^content_"),
            ],
            CONFIRM: [
                CallbackQueryHandler(copy_link, pattern=r"^copy_link$"),
                CallbackQueryHandler(restart, pattern=r"^restart$"),
                CallbackQueryHandler(regenerate_id, pattern=r"^regen_id$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("help", help_command))

    print("🚀 UTM Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
