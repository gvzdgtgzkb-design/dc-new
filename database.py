import aiosqlite
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "shop.db")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS products (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                name         TEXT    NOT NULL,
                description  TEXT    NOT NULL DEFAULT '',
                price        REAL    NOT NULL DEFAULT 0,
                price_label  TEXT    NOT NULL DEFAULT '',
                image_url    TEXT,
                pix_key      TEXT,
                stock_type   TEXT    NOT NULL DEFAULT 'keys',
                active       INTEGER NOT NULL DEFAULT 1,
                created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS keys (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  INTEGER NOT NULL,
                key_value   TEXT    NOT NULL UNIQUE,
                status      TEXT    NOT NULL DEFAULT 'available',
                used_by     TEXT,
                used_at     TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     TEXT    NOT NULL,
                user_name   TEXT    NOT NULL,
                product_id  INTEGER NOT NULL,
                quantity    INTEGER NOT NULL DEFAULT 1,
                unit_price  REAL    NOT NULL,
                price_label TEXT    NOT NULL DEFAULT '',
                total_price REAL    NOT NULL,
                coupon_code TEXT,
                discount    REAL    NOT NULL DEFAULT 0,
                status      TEXT    NOT NULL DEFAULT 'pending',
                thread_id   TEXT,
                message_id  TEXT,
                created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (product_id) REFERENCES products(id)
            );

            CREATE TABLE IF NOT EXISTS coupons (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                code           TEXT    NOT NULL UNIQUE COLLATE NOCASE,
                discount_type  TEXT    NOT NULL DEFAULT 'percent',
                discount_value REAL    NOT NULL,
                uses_left      INTEGER DEFAULT -1,
                active         INTEGER NOT NULL DEFAULT 1,
                created_at     TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS settings (
                id              INTEGER PRIMARY KEY DEFAULT 1,
                shop_channel_id TEXT,
                admin_role_ids  TEXT,
                log_channel_id  TEXT,
                global_pix_key  TEXT,
                footer_text     TEXT    NOT NULL DEFAULT 'NeverMiss Apps © 2026',
                embed_color     INTEGER NOT NULL DEFAULT 1843227,
                bot_name        TEXT    NOT NULL DEFAULT 'Shop Bot'
            );

            CREATE TABLE IF NOT EXISTS activity (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                type       TEXT    NOT NULL,
                message    TEXT    NOT NULL,
                created_at TEXT    NOT NULL DEFAULT (datetime('now'))
            );

            INSERT OR IGNORE INTO settings (id) VALUES (1);
        """)
        await db.commit()


# ── helpers ──────────────────────────────────────────────────────────────────

def _row(row) -> Optional[dict]:
    return dict(row) if row else None


async def _fetch(query, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            return [dict(r) for r in await cur.fetchall()]


async def _fetchone(query, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cur:
            row = await cur.fetchone()
            return _row(row)


async def _execute(query, params=()):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(query, params)
        await db.commit()
        return cur.lastrowid


# ── products ─────────────────────────────────────────────────────────────────

async def get_products(active_only=True):
    where = "WHERE p.active = 1" if active_only else ""
    rows = await _fetch(f"""
        SELECT p.*,
               (SELECT COUNT(*) FROM keys k WHERE k.product_id = p.id AND k.status = 'available') AS available_keys,
               (SELECT COUNT(*) FROM keys k WHERE k.product_id = p.id) AS total_keys
        FROM products p {where}
        ORDER BY p.id
    """)
    return rows


async def get_product(product_id: int):
    rows = await _fetch("""
        SELECT p.*,
               (SELECT COUNT(*) FROM keys k WHERE k.product_id = p.id AND k.status = 'available') AS available_keys,
               (SELECT COUNT(*) FROM keys k WHERE k.product_id = p.id) AS total_keys
        FROM products p WHERE p.id = ?
    """, (product_id,))
    return rows[0] if rows else None


async def create_product(name, description, price, price_label, image_url=None,
                         pix_key=None, stock_type="keys"):
    pid = await _execute(
        "INSERT INTO products (name, description, price, price_label, image_url, pix_key, stock_type) VALUES (?,?,?,?,?,?,?)",
        (name, description, price, price_label, image_url, pix_key, stock_type)
    )
    await log_activity("product_add", f'Product "{name}" added (ID: {pid})')
    return await get_product(pid)


async def update_product(product_id: int, **kwargs):
    allowed = {"name", "description", "price", "price_label", "image_url", "pix_key", "stock_type", "active"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    await _execute(f"UPDATE products SET {sets} WHERE id = ?", (*fields.values(), product_id))
    return await get_product(product_id)


async def delete_product(product_id: int):
    p = await get_product(product_id)
    if p:
        await _execute("DELETE FROM products WHERE id = ?", (product_id,))
        await log_activity("product_remove", f'Product "{p["name"]}" deleted')
    return p


# ── keys ─────────────────────────────────────────────────────────────────────

async def get_keys(product_id=None, status=None):
    clauses, params = [], []
    if product_id is not None:
        clauses.append("k.product_id = ?"); params.append(product_id)
    if status:
        clauses.append("k.status = ?"); params.append(status)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return await _fetch(f"""
        SELECT k.*, p.name AS product_name
        FROM keys k LEFT JOIN products p ON k.product_id = p.id
        {where} ORDER BY k.id
    """, params)


async def add_key(product_id: int, key_value: str):
    try:
        kid = await _execute(
            "INSERT INTO keys (product_id, key_value) VALUES (?, ?)",
            (product_id, key_value)
        )
        await log_activity("key_add", f"Key added for product #{product_id}")
        return await _fetchone("SELECT * FROM keys WHERE id = ?", (kid,))
    except Exception:
        return None  # duplicate


async def bulk_add_keys(product_id: int, key_list: list[str]):
    added, skipped = 0, 0
    for kv in key_list:
        result = await add_key(product_id, kv.strip())
        if result:
            added += 1
        else:
            skipped += 1
    if added:
        await log_activity("bulk_key_add", f"{added} keys added for product #{product_id}")
    return added, skipped


async def delete_key(key_id: int):
    k = await _fetchone("SELECT * FROM keys WHERE id = ?", (key_id,))
    if k:
        await _execute("DELETE FROM keys WHERE id = ?", (key_id,))
        await log_activity("key_remove", f"Key #{key_id} deleted")
    return k


async def pop_available_key(product_id: int):
    """Claim the next available key and mark it as used."""
    k = await _fetchone(
        "SELECT * FROM keys WHERE product_id = ? AND status = 'available' ORDER BY id LIMIT 1",
        (product_id,)
    )
    if k:
        await _execute(
            "UPDATE keys SET status = 'used', used_at = datetime('now') WHERE id = ?",
            (k["id"],)
        )
    return k


# ── orders ───────────────────────────────────────────────────────────────────

async def create_order(user_id, user_name, product_id, quantity,
                       unit_price, price_label, total_price, thread_id=None):
    oid = await _execute(
        """INSERT INTO orders
           (user_id, user_name, product_id, quantity, unit_price, price_label, total_price, thread_id)
           VALUES (?,?,?,?,?,?,?,?)""",
        (user_id, user_name, product_id, quantity, unit_price, price_label, total_price, thread_id)
    )
    await log_activity("order_create", f"Order #{oid} created by {user_name}")
    return await get_order(oid)


async def get_order(order_id: int):
    return await _fetchone("""
        SELECT o.*, p.name AS product_name, p.image_url, p.pix_key, p.stock_type
        FROM orders o LEFT JOIN products p ON o.product_id = p.id
        WHERE o.id = ?
    """, (order_id,))


async def get_order_by_thread(thread_id: str):
    return await _fetchone("""
        SELECT o.*, p.name AS product_name, p.image_url, p.pix_key, p.stock_type
        FROM orders o LEFT JOIN products p ON o.product_id = p.id
        WHERE o.thread_id = ? AND o.status IN ('pending','awaiting_payment')
        ORDER BY o.id DESC LIMIT 1
    """, (thread_id,))


async def update_order(order_id: int, **kwargs):
    allowed = {"quantity", "total_price", "coupon_code", "discount", "status", "message_id"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    await _execute(f"UPDATE orders SET {sets} WHERE id = ?", (*fields.values(), order_id))
    return await get_order(order_id)


async def cancel_order(order_id: int):
    await _execute("UPDATE orders SET status = 'cancelled' WHERE id = ?", (order_id,))
    await log_activity("order_cancel", f"Order #{order_id} cancelled")


# ── coupons ──────────────────────────────────────────────────────────────────

async def get_coupon(code: str):
    return await _fetchone(
        "SELECT * FROM coupons WHERE code = ? AND active = 1",
        (code,)
    )


async def use_coupon(coupon_id: int):
    await _execute(
        "UPDATE coupons SET uses_left = MAX(uses_left - 1, -1) WHERE id = ? AND uses_left > 0",
        (coupon_id,)
    )


async def create_coupon(code, discount_type, discount_value, uses_left=-1):
    cid = await _execute(
        "INSERT INTO coupons (code, discount_type, discount_value, uses_left) VALUES (?,?,?,?)",
        (code, discount_type, discount_value, uses_left)
    )
    return await _fetchone("SELECT * FROM coupons WHERE id = ?", (cid,))


async def delete_coupon(code: str):
    await _execute("DELETE FROM coupons WHERE code = ?", (code,))


# ── settings ─────────────────────────────────────────────────────────────────

async def get_settings():
    return await _fetchone("SELECT * FROM settings WHERE id = 1")


async def update_settings(**kwargs):
    allowed = {"shop_channel_id", "admin_role_ids", "log_channel_id",
               "global_pix_key", "footer_text", "embed_color", "bot_name"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    await _execute(f"UPDATE settings SET {sets} WHERE id = 1", (*fields.values(),))
    return await get_settings()


# ── stats / activity ──────────────────────────────────────────────────────────

async def log_activity(type_: str, message: str):
    await _execute("INSERT INTO activity (type, message) VALUES (?,?)", (type_, message))


async def get_stats():
    s = await _fetchone("""
        SELECT
            (SELECT COUNT(*) FROM products)                                  AS total_products,
            (SELECT COUNT(*) FROM products WHERE active = 1)                 AS active_products,
            (SELECT COUNT(*) FROM keys)                                      AS total_keys,
            (SELECT COUNT(*) FROM keys WHERE status = 'available')           AS available_keys,
            (SELECT COUNT(*) FROM keys WHERE status = 'used')                AS used_keys,
            (SELECT COUNT(*) FROM orders)                                    AS total_orders,
            (SELECT COUNT(*) FROM orders WHERE status = 'completed')         AS completed_orders,
            (SELECT COUNT(*) FROM orders WHERE status = 'pending')           AS pending_orders
    """)
    return s
