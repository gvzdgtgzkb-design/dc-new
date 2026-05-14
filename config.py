import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
GUILD_ID = int(os.getenv("GUILD_ID")) if os.getenv("GUILD_ID") else None

# ── Permanent owner role — always has admin access no matter what ─────────────
# Add more IDs separated by commas in OWNER_ROLE_IDS env var, or hardcode below
OWNER_ROLE_IDS: list[str] = ["1257944622689419326"]
_extra = os.getenv("OWNER_ROLE_IDS", "")
if _extra:
    OWNER_ROLE_IDS += [r.strip() for r in _extra.split(",") if r.strip()]

# ── Custom Discord emojis (your codes) ──────────────────────────────────────
EMOJI_CART    = "<:carrinho:1466466067743244431>"
EMOJI_CONFIRM = "<a:confirmar:1466466203341029396>"
EMOJI_CROSS   = "<:cross_mark:1131190543339233290>"
EMOJI_PRODUCT = "<:1455376139169173565:1484006620466909254>"

# ── Standard emojis ──────────────────────────────────────────────────────────
EMOJI_KEY       = "🔑"
EMOJI_LOCK      = "🔒"
EMOJI_WARNING   = "⚠️"
EMOJI_ADMIN     = "⚙️"
EMOJI_PAYMENT   = "💳"
EMOJI_PENCIL    = "✏️"
EMOJI_TAG       = "🏷️"
EMOJI_TRASH     = "🗑️"
EMOJI_CLIPBOARD = "📋"
EMOJI_QR        = "📷"
EMOJI_FOLDER    = "📁"
EMOJI_ARROW     = "→"
EMOJI_PIN       = "📌"
EMOJI_GIFT      = "🎁"

# ── Embed colours ─────────────────────────────────────────────────────────────
COLOR_PRIMARY = 0x1B1F3B
COLOR_SUCCESS = 0x57F287
COLOR_ERROR   = 0xED4245
COLOR_WARNING = 0xFEE75C
COLOR_PURPLE  = 0x5865F2
