# NeverMiss Shop Bot — Setup Guide

## Quick Start

### 1. Install Python dependencies
```bash
cd discord_bot
pip install -r requirements.txt
```

### 2. Create your .env file
```bash
cp .env.example .env
```
Edit `.env` and add:
```
DISCORD_BOT_TOKEN=your_token_here
GUILD_ID=your_server_id_here
```

### 3. Run the bot
```bash
python bot.py
```

---

## How to get your Bot Token

1. Go to https://discord.com/developers/applications
2. Click **New Application** → give it a name
3. Go to **Bot** tab → click **Reset Token** → copy the token
4. Paste it in your `.env` file as `DISCORD_BOT_TOKEN`

**Bot Permissions needed:**
- Send Messages
- Create Private Threads
- Manage Threads
- Embed Links
- Read Message History
- Use Application Commands (slash commands)

**Privileged Intents needed (Bot tab → enable these):**
- Server Members Intent
- Message Content Intent

**Invite URL:**
Go to OAuth2 → URL Generator → Scopes: `bot` + `applications.commands` → Bot Permissions: the ones above.

---

## Admin Commands (slash commands)

| Command | Description |
|---|---|
| `/post [channel]` | Post the shop product listing |
| `/addproduct name price price_label ...` | Add a product |
| `/editproduct product_id ...` | Edit a product |
| `/removeproduct product_id` | Delete a product |
| `/toggleproduct product_id` | Enable/disable a product |
| `/listproducts` | List all products |
| `/addkey product_id key` | Add a single license key |
| `/bulkaddkeys product_id keys` | Add many keys (comma separated) |
| `/removekey key_id` | Delete a key |
| `/listkeys product_id` | List keys for a product |
| `/addcoupon code type value [uses]` | Create a discount coupon |
| `/removecoupon code` | Remove a coupon |
| `/confirmorder order_id` | Manually confirm payment + deliver key |
| `/cancelorder order_id` | Cancel an order |
| `/stats` | View statistics |
| `/settings ...` | View/update bot configuration |

---

## User Purchase Flow

1. User sees the product listing embed (posted with `/post`)
2. User opens the **"Selecione um produto ou categoria"** dropdown
3. Bot creates a **private thread** for that user's purchase
4. Bot posts a **cart embed** in the thread with:
   - ✏️ Change Quantity
   - 🏷️ Add Coupon
   - 🗑️ Remove item
   - 🛒 Go to Payment
   - 🗑️ Cancel Order
5. User clicks **Ir para Pagamento** → payment confirmation with Pix key + QR code
6. Admin runs `/confirmorder ID` → bot DMs the license key to the user

---

## Configure Pix Payment

You can set a global Pix key:
```
/settings global_pix_key=your_pix_key_here
```

Or per-product when adding:
```
/addproduct name:"Panel 15 Days" price:60 price_label:"R$ 60,00" pix_key:your_pix_key
```

---

## Custom Emojis Used

| Emoji | Code |
|---|---|
| 🛒 Cart | `<:carrinho:1466466067743244431>` |
| ✅ Confirm | `<a:confirmar:1466466203341029396>` |
| ❌ Cross | `<:cross_mark:1131190543339233290>` |
| 📦 Product | `<:1455376139169173565:1484006620466909254>` |

---

## Files

```
discord_bot/
├── bot.py          ← Main entry point (run this)
├── database.py     ← SQLite database (auto-created as shop.db)
├── config.py       ← Emoji codes + colour constants
├── cogs/
│   ├── admin.py    ← All admin slash commands
│   └── shop.py     ← Product listing, cart, payment views
├── requirements.txt
└── .env.example
```
