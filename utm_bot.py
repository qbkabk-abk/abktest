"""
Higgsfield UTM Link Builder — Telegram Bot (YouTube only)
Compatible with python-telegram-bot==22.6
"""

import os
import re
import logging
import hashlib
import time

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

ALLOWED_USERS = {
    246710857, 146713495, 936971773, 7098425646, 402977320, 6202313386,
}

def is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USERS

async def access_denied(update: Update) -> int:
    user_id = update.effective_user.id
    text = (
        f"🚫 Access denied.\n\n"
        f"Your Telegram ID: `{user_id}`\n\n"
        f"Send this ID to your admin to get access."
    )
    if update.message:
        await update.message.reply_text(text, parse_mode="Markdown")
    return ConversationHandler.END

(
    INPUT_PAGE_URL,
    SELECT_CHANNEL_TYPE,
    SELECT_EARN_VISIBILITY,
    SELECT_HANDLE_MODE,
    INPUT_HANDLE,
    INPUT_BULK_HANDLES,
    SELECT_CAMPAIGN,
    ENTER_CUSTOM_CAMPAIGN,
    SELECT_CONTENT_TYPE,
    CONFIRM,
) = range(10)

BASE_URL = "https://higgsfield.ai"

CAMPAIGNS = {
    "cinema_studio":  {"label": "🎥 Cinema Studio",  "slug": "cinema_studio"},
    "soul_2":         {"label": "🖼 Soul 2.0",        "slug": "soul_2"},
    "kling_3":        {"label": "🎬 Kling 3.0",       "slug": "kling_3"},
    "seedance_2":     {"label": "🌱 Seedance 2.0",    "slug": "seedance_2"},
    "nano_banana_2":  {"label": "🍌 Nano Banana 2",   "slug": "nano_banana_2"},
    "higgsfield_audio":  {"label": "🎧 Higgsfield Audio ",   "slug": "higgsfield_audio"},
    "soul_cinematic":  {"label": "👻 Soul Cinematic ",   "slug": "soul_cinematic"},
    "general":        {"label": "🌐 General",          "slug": "general"},
}

CONTENT_TYPES = {
    "dedicated":  "de",
    "integrated": "in",
    "shorts":     "sh",
}

def nav_row(back_callback: str) -> list:
    return [
        InlineKeyboardButton("⬅️ Back", callback_data=back_callback),
        InlineKeyboardButton("❌ Cancel", callback_data="nav_cancel"),
    ]

def sanitize(text: str) -> str:
    text = text.lower().strip()
    text = text.replace("-", "_").replace(" ", "_")
    text = re.sub(r"[^a-z0-9_]", "", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")

def extract_yt_handle(raw: str) -> str:
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
    channel_type = data.get("channel_type", "")
    if channel_type == "earn":
        vis = data.get("earn_visibility", "pu")
        return f"youtube_e_{vis}"
    elif channel_type == "main":
        return "youtube_m"
    else:
        return "youtube_s"

def generate_id(handle="", campaign="", content_type="", length=5):
    seed = f"{handle}_{campaign}_{content_type}_{time.time_ns()}"
    h = hashlib.sha256(seed.encode()).hexdigest()
    return h[:length]

def build_utm_url(data: dict, handle_override: str = None) -> str:
    page = data.get("page", "")
    source = build_source(data)
    medium = handle_override or data.get("handle", "")
    campaign = data["campaign_slug"]
    content_type = data.get("content_type", "")
    uid = generate_id(handle=medium, campaign=campaign, content_type=content_type)
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

def build_bulk_summary(data: dict, handles: list) -> str:
    source = build_source(data)
    campaign = data.get("campaign_slug", "—")
    content_type = data.get("content_type", "—")
    lines = [
        f"📋 *Bulk UTM Links* — {len(handles)} creators\n",
        f"🌐 *Source:* `{source}`",
        f"🎯 *Campaign:* `{campaign}`",
        f"📝 *Content type:* `{content_type}`\n",
        "───────────────\n",
    ]
    for handle in handles:
        url = build_utm_url(data, handle_override=handle)
        lines.append(f"*@{handle}*")
        lines.append(f"`{url}`\n")
    return "\n".join(lines)

async def nav_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ Cancelled. Send /start to begin again.")
    return ConversationHandler.END

async def nav_back_to_page(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await start(update, context)

async def nav_back_to_channel_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await _show_channel_type(query, context, edit=True)

async def nav_back_to_visibility(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔓 Public",  callback_data="visibility_pu"),
            InlineKeyboardButton("🔒 Private", callback_data="visibility_pr"),
        ],
        nav_row("back_to_channel_type"),
    ])
    await query.edit_message_text("✅ *Earn*\n\nPublic or Private?", reply_markup=keyboard, parse_mode="Markdown")
    return SELECT_EARN_VISIBILITY

async def nav_back_to_handle_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await _show_handle_mode(query, context, edit=True)

async def nav_back_to_handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    source = build_source(context.user_data)
    await query.edit_message_text(
        f"✅ Source: `{source}`\n\nSend the creator handle.\n\n• `@handle`\n• YouTube channel URL\n• Or just the name",
        parse_mode="Markdown",
    )
    return INPUT_HANDLE

async def nav_back_to_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    source = build_source(context.user_data)
    await query.edit_message_text(
        f"✅ Source: `{source}`\n\nSend creator handles — *one per line*.\n\nYou can mix formats:\n• `@handle`\n• YouTube channel URLs\n• Plain names\n\nExample:\n`@mkbhd`\n`https://youtube.com/@LinusTech`\n`unbox_therapy`",
        parse_mode="Markdown",
    )
    return INPUT_BULK_HANDLES

async def nav_back_to_campaign(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chtype = context.user_data.get("channel_type", "")
    mode = context.user_data.get("handle_mode", "single")
    if chtype == "main":
        back_target = "back_to_channel_type"
    elif mode == "bulk":
        back_target = "back_to_bulk"
    else:
        back_target = "back_to_handle"
    keyboard = []
    for key, camp in CAMPAIGNS.items():
        keyboard.append([InlineKeyboardButton(camp["label"], callback_data=f"campaign_{key}")])
    keyboard.append([InlineKeyboardButton("✏️ Custom campaign", callback_data="campaign_custom")])
    keyboard.append(nav_row(back_target))
    handle = context.user_data.get("handle", "")
    bulk_handles = context.user_data.get("bulk_handles", [])
    handle_text = f"✅ Handles: *{len(bulk_handles)} creators*" if bulk_handles else f"✅ Handle: `{handle}`"
    await query.edit_message_text(
        f"{handle_text}\n\nPick the campaign.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return SELECT_CAMPAIGN

async def nav_back_to_content(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await _show_content_type(query, context)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    if not is_allowed(user_id):
        return await access_denied(update)
    context.user_data.clear()
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="nav_cancel")]])
    text = (
        "👋 *Higgsfield UTM Builder*\n\n"
        "Paste the page link or type the path.\n\n"
        "Examples:\n"
        "• `https://higgsfield.ai/cinema-studio`\n"
        "• `/kling-3`\n"
        "• `/image/soul-v2`"
    )
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return INPUT_PAGE_URL

async def page_url_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    raw = re.sub(r"^https?://(www\.)?higgsfield\.ai", "", raw)
    if not raw.startswith("/"):
        raw = "/" + raw
    context.user_data["page"] = raw
    return await _show_channel_type(update, context, edit=False)

async def _show_channel_type(source, context: ContextTypes.DEFAULT_TYPE, edit: bool) -> int:
    page = context.user_data["page"]
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🌍 Earn",         callback_data="chtype_earn"),
            InlineKeyboardButton("🎯 Selected",     callback_data="chtype_selected"),
        ],
        [InlineKeyboardButton("📺 Main Channel", callback_data="chtype_main")],
        nav_row("back_to_page"),
    ])
    text = f"✅ Page: `{page}`\n\n▶️ YouTube — Earn, Selected, or Main Channel?"
    if edit:
        await source.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await source.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return SELECT_CHANNEL_TYPE

async def channel_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    chtype = query.data.replace("chtype_", "")
    context.user_data["channel_type"] = chtype
    if chtype == "earn":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔓 Public",  callback_data="visibility_pu"),
                InlineKeyboardButton("🔒 Private", callback_data="visibility_pr"),
            ],
            nav_row("back_to_channel_type"),
        ])
        await query.edit_message_text("✅ *Earn*\n\nPublic or Private?", reply_markup=keyboard, parse_mode="Markdown")
        return SELECT_EARN_VISIBILITY
    elif chtype == "main":
        context.user_data["handle"] = "higgsfieldai"
        context.user_data["handle_mode"] = "single"
        keyboard = []
        for key, camp in CAMPAIGNS.items():
            keyboard.append([InlineKeyboardButton(camp["label"], callback_data=f"campaign_{key}")])
        keyboard.append([InlineKeyboardButton("✏️ Custom campaign", callback_data="campaign_custom")])
        keyboard.append(nav_row("back_to_channel_type"))
        await query.edit_message_text(
            f"✅ Source: `youtube_m`\n✅ Medium: `higgsfieldai`\n\nPick the campaign.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return SELECT_CAMPAIGN
    else:
        return await _show_handle_mode(query, context, edit=True)

async def earn_visibility_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    vis = query.data.replace("visibility_", "")
    context.user_data["earn_visibility"] = vis
    return await _show_handle_mode(query, context, edit=True)

async def _show_handle_mode(source, context: ContextTypes.DEFAULT_TYPE, edit: bool) -> int:
    src = build_source(context.user_data)
    chtype = context.user_data.get("channel_type", "")
    back_target = "back_to_visibility" if chtype == "earn" else "back_to_channel_type"
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("👤 Single creator", callback_data="hmode_single"),
            InlineKeyboardButton("👥 Bulk (multiple)", callback_data="hmode_bulk"),
        ],
        nav_row(back_target),
    ])
    text = f"✅ Source: `{src}`\n\nOne creator or multiple?"
    if edit:
        await source.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await source.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return SELECT_HANDLE_MODE

async def handle_mode_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    mode = query.data.replace("hmode_", "")
    context.user_data["handle_mode"] = mode
    source = build_source(context.user_data)
    if mode == "single":
        await query.edit_message_text(
            f"✅ Source: `{source}`\n\nSend the creator handle.\n\n• `@handle`\n• YouTube channel URL\n• Or just the name",
            parse_mode="Markdown",
        )
        return INPUT_HANDLE
    else:
        await query.edit_message_text(
            f"✅ Source: `{source}`\n\nSend creator handles — *one per line*.\n\nYou can mix formats:\n• `@handle`\n• YouTube channel URLs\n• Plain names\n\nExample:\n`@mkbhd`\n`https://youtube.com/@LinusTech`\n`unbox_therapy`",
            parse_mode="Markdown",
        )
        return INPUT_BULK_HANDLES

async def handle_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    handle = extract_yt_handle(raw)
    if not handle:
        await update.message.reply_text("⚠️ Couldn't parse that. Try `@handle` or a YouTube URL.", parse_mode="Markdown")
        return INPUT_HANDLE
    context.user_data["handle"] = handle
    keyboard = []
    for key, camp in CAMPAIGNS.items():
        keyboard.append([InlineKeyboardButton(camp["label"], callback_data=f"campaign_{key}")])
    keyboard.append([InlineKeyboardButton("✏️ Custom campaign", callback_data="campaign_custom")])
    keyboard.append(nav_row("back_to_handle"))
    await update.message.reply_text(
        f"✅ Handle: `{handle}`\n\nPick the campaign.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return SELECT_CAMPAIGN

async def bulk_handles_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw = update.message.text.strip()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    if not lines:
        await update.message.reply_text("⚠️ No handles detected. Send one per line.")
        return INPUT_BULK_HANDLES
    parsed = []
    failed = []
    for line in lines:
        h = extract_yt_handle(line)
        if h:
            parsed.append(h)
        else:
            failed.append(line)
    seen = set()
    unique = []
    for h in parsed:
        if h not in seen:
            seen.add(h)
            unique.append(h)
    if not unique:
        await update.message.reply_text("⚠️ Couldn't parse any handles. Check the format and try again.", parse_mode="Markdown")
        return INPUT_BULK_HANDLES
    context.user_data["bulk_handles"] = unique
    context.user_data["handle"] = ""
    preview = "\n".join([f"  `{h}`" for h in unique[:15]])
    extra = f"\n  _...and {len(unique) - 15} more_" if len(unique) > 15 else ""
    fail_text = f"\n\n⚠️ Skipped {len(failed)}: " + ", ".join([f"`{f}`" for f in failed[:5]]) if failed else ""
    keyboard = []
    for key, camp in CAMPAIGNS.items():
        keyboard.append([InlineKeyboardButton(camp["label"], callback_data=f"campaign_{key}")])
    keyboard.append([InlineKeyboardButton("✏️ Custom campaign", callback_data="campaign_custom")])
    keyboard.append(nav_row("back_to_handle_mode"))
    await update.message.reply_text(
        f"✅ *{len(unique)} creators parsed:*\n{preview}{extra}{fail_text}\n\nPick the campaign.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return SELECT_CAMPAIGN

async def campaign_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    campaign_key = query.data.replace("campaign_", "")
    if campaign_key == "custom":
        await query.edit_message_text(
            "Type your custom campaign name.\nAuto-formatted to snake\\_case.\n\nExample: `soul_launch`",
            parse_mode="Markdown",
        )
        return ENTER_CUSTOM_CAMPAIGN
    camp = CAMPAIGNS[campaign_key]
    context.user_data["campaign_slug"]  = camp["slug"]
    context.user_data["campaign_label"] = camp["label"]
    return await _show_content_type(query, context)

async def custom_campaign_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    raw  = update.message.text.strip()
    slug = sanitize(raw)
    if not slug:
        await update.message.reply_text("⚠️ Invalid name. Try again.")
        return ENTER_CUSTOM_CAMPAIGN
    context.user_data["campaign_slug"]  = slug
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
    buttons = [
        InlineKeyboardButton(f"{emoji_map[key]} {key.title()}", callback_data=f"content_{key}")
        for key in CONTENT_TYPES
    ]
    return [buttons, nav_row("back_to_campaign")]

async def _show_content_type(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = _build_content_keyboard()
    await query.edit_message_text("Pick the content type.", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    return SELECT_CONTENT_TYPE

async def content_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    content_key = query.data.replace("content_", "")
    context.user_data["content_type"] = CONTENT_TYPES[content_key]
    bulk_handles = context.user_data.get("bulk_handles", [])
    if bulk_handles:
        return await _show_bulk_confirm(query, context)
    else:
        context.user_data["uid"] = generate_id(
            handle=context.user_data.get("handle", ""),
            campaign=context.user_data.get("campaign_slug", ""),
            content_type=context.user_data.get("content_type", ""),
        )
        return await _show_confirm(query, context, edit=True)

async def _show_confirm(source, context: ContextTypes.DEFAULT_TYPE, edit: bool) -> int:
    data = context.user_data
    url     = build_utm_url(data)
    summary = build_summary(data)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Copy as plain text", callback_data="copy_link")],
        [
            InlineKeyboardButton("⬅️ Back",       callback_data="back_to_content"),
            InlineKeyboardButton("🔄 Start over", callback_data="restart"),
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
        await source.edit_message_text(text, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await source.message.reply_text(text, reply_markup=keyboard, parse_mode="Markdown")
    return CONFIRM

async def _show_bulk_confirm(query, context: ContextTypes.DEFAULT_TYPE) -> int:
    data = context.user_data
    handles = data.get("bulk_handles", [])
    summary = build_bulk_summary(data, handles)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Copy all links", callback_data="copy_bulk")],
        [
            InlineKeyboardButton("⬅️ Back",       callback_data="back_to_content"),
            InlineKeyboardButton("🔄 Start over", callback_data="restart"),
        ],
    ])
    if len(summary) > 3800:
        short = (
            f"📋 *Bulk UTM Links* — {len(handles)} creators\n\n"
            f"🌐 *Source:* `{build_source(data)}`\n"
            f"🎯 *Campaign:* `{data.get('campaign_slug', '—')}`\n"
            f"📝 *Content type:* `{data.get('content_type', '—')}`\n\n"
            f"✅ Links generated for all {len(handles)} creators.\n"
            f"Tap *Copy all links* to get the full list."
        )
        await query.edit_message_text(short, reply_markup=keyboard, parse_mode="Markdown")
    else:
        await query.edit_message_text(summary, reply_markup=keyboard, parse_mode="Markdown")
    return CONFIRM

async def copy_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    url = build_utm_url(context.user_data)
    await query.message.reply_text(url)
    return CONFIRM

async def copy_bulk(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    data = context.user_data
    handles = data.get("bulk_handles", [])
    lines = []
    for handle in handles:
        url = build_utm_url(data, handle_override=handle)
        lines.append(f"@{handle}\n{url}")
    full_text = "\n\n".join(lines)
    if len(full_text) > 4000:
        chunks = []
        current_chunk = []
        current_len = 0
        for block in lines:
            if current_len + len(block) + 2 > 4000:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [block]
                current_len = len(block)
            else:
                current_chunk.append(block)
                current_len += len(block) + 2
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
        for i, chunk in enumerate(chunks):
            await query.message.reply_text(f"📋 Part {i+1}/{len(chunks)}\n\n{chunk}")
    else:
        await query.message.reply_text(full_text)
    return CONFIRM

async def restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    return await start(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ Cancelled. /start to begin again.")
    context.user_data.clear()
    return ConversationHandler.END

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    await update.message.reply_text(f"Your Telegram ID: `{user_id}`", parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        "*Higgsfield UTM Builder* 🔗\n\n"
        "*Flow:*\n"
        "Page → Earn/Selected/Main → Single/Bulk → Handle(s) → Campaign → Content → Link(s)\n\n"
        "*Handle modes:*\n"
        "👤 *Single* — one handle, one link\n"
        "👥 *Bulk* — paste many handles (one per line), get individual link per creator\n\n"
        "*Source codes:*\n"
        "`youtube_e_pu` — Earn Public\n"
        "`youtube_e_pr` — Earn Private\n"
        "`youtube_s` — Selected\n"
        "`youtube_m` — Main Channel\n\n"
        "*Commands:*\n"
        "/start — New UTM link\n"
        "/myid — Show your Telegram ID\n"
        "/help — This message\n"
        "/cancel — Cancel\n"
    )
    await update.message.reply_text(text, parse_mode="Markdown")

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("❌ Set TELEGRAM_BOT_TOKEN first:")
        print("   export TELEGRAM_BOT_TOKEN='your_token_here'")
        return

    print(f"✅ Allow list: {ALLOWED_USERS}")
    app = Application.builder().token(token).build()

    nav_handlers = [
        CallbackQueryHandler(nav_cancel,               pattern=r"^nav_cancel$"),
        CallbackQueryHandler(nav_back_to_page,         pattern=r"^back_to_page$"),
        CallbackQueryHandler(nav_back_to_channel_type, pattern=r"^back_to_channel_type$"),
        CallbackQueryHandler(nav_back_to_visibility,   pattern=r"^back_to_visibility$"),
        CallbackQueryHandler(nav_back_to_handle_mode,  pattern=r"^back_to_handle_mode$"),
        CallbackQueryHandler(nav_back_to_handle,       pattern=r"^back_to_handle$"),
        CallbackQueryHandler(nav_back_to_bulk,         pattern=r"^back_to_bulk$"),
        CallbackQueryHandler(nav_back_to_campaign,     pattern=r"^back_to_campaign$"),
        CallbackQueryHandler(nav_back_to_content,      pattern=r"^back_to_content$"),
    ]

    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            INPUT_PAGE_URL:         [MessageHandler(filters.TEXT & ~filters.COMMAND, page_url_text)] + nav_handlers,
            SELECT_CHANNEL_TYPE:    [CallbackQueryHandler(channel_type_selected, pattern=r"^chtype_")] + nav_handlers,
            SELECT_EARN_VISIBILITY: [CallbackQueryHandler(earn_visibility_selected, pattern=r"^visibility_")] + nav_handlers,
            SELECT_HANDLE_MODE:     [CallbackQueryHandler(handle_mode_selected, pattern=r"^hmode_")] + nav_handlers,
            INPUT_HANDLE:           [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_received)] + nav_handlers,
            INPUT_BULK_HANDLES:     [MessageHandler(filters.TEXT & ~filters.COMMAND, bulk_handles_received)] + nav_handlers,
            SELECT_CAMPAIGN:        [CallbackQueryHandler(campaign_selected, pattern=r"^campaign_")] + nav_handlers,
            ENTER_CUSTOM_CAMPAIGN:  [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_campaign_received)] + nav_handlers,
            SELECT_CONTENT_TYPE:    [CallbackQueryHandler(content_selected, pattern=r"^content_")] + nav_handlers,
            CONFIRM: [
                CallbackQueryHandler(copy_link, pattern=r"^copy_link$"),
                CallbackQueryHandler(copy_bulk, pattern=r"^copy_bulk$"),
                CallbackQueryHandler(restart,   pattern=r"^restart$"),
            ] + nav_handlers,
        },
        fallbacks=[CommandHandler("cancel", cancel), CommandHandler("start", start)],
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("myid", myid))

    print("🚀 UTM Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
