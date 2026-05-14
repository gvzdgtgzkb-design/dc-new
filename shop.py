import discord
from discord.ext import commands
from discord import app_commands
import database as db
from config import *


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def stock_label(product: dict) -> str:
    if product["stock_type"] == "infinite":
        return "∞"
    return str(product.get("available_keys", 0))


def fmt_price(val: float) -> str:
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def cart_embed(order: dict, settings: dict) -> discord.Embed:
    footer = settings.get("footer_text", "NeverMiss Apps © 2026")
    color  = settings.get("embed_color", COLOR_PRIMARY)

    em = discord.Embed(
        title=f"{EMOJI_CART} Bem-vindo ao seu Carrinho",
        color=color
    )
    if order.get("image_url"):
        em.set_image(url=order["image_url"])

    em.description = (
        f"{EMOJI_CONFIRM} Nossa entrega é 100% automática.\n"
        f"{EMOJI_PRODUCT} Você está comprando: **{order['product_name']}**"
    )
    em.set_footer(text=f"Todos os direitos reservados à {footer}")

    total     = order["unit_price"] * order["quantity"] - order.get("discount", 0)
    stk_type  = order.get("stock_type", "keys")
    available = "∞ unidades (Estoque Infinito)" if stk_type == "infinite" else f"{order.get('available_keys', '?')} unidades"

    em.add_field(
        name=f"Produto: **{order['product_name']}**",
        value=(
            "Confira os detalhes abaixo antes de finalizar a compra!\n\u200b\n"
            f"**Quantidade:** {order['quantity']}\n"
            f"**Preço Total:** {fmt_price(total)}\n"
            f"**Disponível:** {available}"
            + (f"\n**Cupom:** `{order['coupon_code']}` (-{fmt_price(order['discount'])})" if order.get('coupon_code') else "")
        ),
        inline=False
    )
    return em


def payment_embed(order: dict, settings: dict) -> discord.Embed:
    footer = settings.get("footer_text", "NeverMiss Apps © 2026")
    color  = settings.get("embed_color", COLOR_PRIMARY)
    total  = order["unit_price"] * order["quantity"] - order.get("discount", 0)

    em = discord.Embed(
        title=f"{EMOJI_PAYMENT} Confirmação de Compra",
        description="Verifique se os produtos estão corretos e efetue o pagamento.",
        color=color
    )
    em.add_field(
        name=f"{EMOJI_PIN} Produtos:",
        value=f"`{fmt_price(order['unit_price'])} - {order['product_name']} ({order['quantity']} unidade{'s' if order['quantity'] > 1 else ''})`",
        inline=False
    )
    em.add_field(
        name="\u200b",
        value=(
            f"{EMOJI_ARROW} **Valor Total:** {fmt_price(total)}\n"
            f"{EMOJI_ARROW} **Desconto:** {fmt_price(order.get('discount', 0))}"
        ),
        inline=False
    )
    em.set_footer(text=f"Todos os direitos reservados à {footer}")
    return em


# ─────────────────────────────────────────────────────────────────────────────
# Modals
# ─────────────────────────────────────────────────────────────────────────────

class QuantityModal(discord.ui.Modal, title="Alterar Quantidade"):
    qty = discord.ui.TextInput(
        label="Nova quantidade",
        placeholder="Ex: 2",
        min_length=1,
        max_length=3
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_qty = int(self.qty.value)
            if new_qty < 1:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                f"{EMOJI_CROSS} Quantidade inválida.", ephemeral=True
            )
            return

        order = await db.get_order_by_thread(str(interaction.channel_id))
        if not order:
            await interaction.response.send_message(f"{EMOJI_CROSS} Pedido não encontrado.", ephemeral=True)
            return

        total = order["unit_price"] * new_qty - order.get("discount", 0)
        await db.update_order(order["id"], quantity=new_qty, total_price=total)
        order = await db.get_order(order["id"])

        settings = await db.get_settings()
        await interaction.response.edit_message(
            embed=cart_embed(order, settings),
            view=CartView()
        )


class CouponModal(discord.ui.Modal, title="Adicionar Cupom"):
    code = discord.ui.TextInput(
        label="Código do cupom",
        placeholder="Ex: DESCONTO10",
        min_length=1,
        max_length=50
    )

    async def on_submit(self, interaction: discord.Interaction):
        coupon = await db.get_coupon(self.code.value.strip().upper())
        if not coupon:
            await interaction.response.send_message(
                f"{EMOJI_CROSS} Cupom inválido ou expirado.", ephemeral=True
            )
            return

        order = await db.get_order_by_thread(str(interaction.channel_id))
        if not order:
            await interaction.response.send_message(f"{EMOJI_CROSS} Pedido não encontrado.", ephemeral=True)
            return

        subtotal = order["unit_price"] * order["quantity"]
        if coupon["discount_type"] == "percent":
            discount = round(subtotal * coupon["discount_value"] / 100, 2)
        else:
            discount = min(coupon["discount_value"], subtotal)

        total = subtotal - discount
        await db.update_order(order["id"], coupon_code=coupon["code"], discount=discount, total_price=total)
        if coupon["uses_left"] > 0:
            await db.use_coupon(coupon["id"])

        order = await db.get_order(order["id"])
        settings = await db.get_settings()
        await interaction.response.edit_message(
            embed=cart_embed(order, settings),
            view=CartView()
        )
        await interaction.followup.send(
            f"{EMOJI_CONFIRM} Cupom **{coupon['code']}** aplicado! Desconto: {fmt_price(discount)}",
            ephemeral=True
        )


# ─────────────────────────────────────────────────────────────────────────────
# Views
# ─────────────────────────────────────────────────────────────────────────────

class ProductSelect(discord.ui.Select):
    def __init__(self, products: list[dict]):
        options = []
        for p in products[:25]:
            stk = "∞" if p["stock_type"] == "infinite" else str(p.get("available_keys", 0))
            options.append(discord.SelectOption(
                label=p["name"],
                value=str(p["id"]),
                description=f"Valor: {p['price_label']} | Estoque: {stk}",
                emoji=discord.PartialEmoji.from_str(EMOJI_CART)
            ))
        super().__init__(
            placeholder=f"{EMOJI_CART} Selecione um produto ou categoria",
            options=options,
            custom_id="shop:product_select"
        )

    async def callback(self, interaction: discord.Interaction):
        product_id = int(self.values[0])
        product    = await db.get_product(product_id)
        if not product or not product["active"]:
            await interaction.response.send_message(
                f"{EMOJI_CROSS} Produto não disponível.", ephemeral=True
            )
            return

        if product["stock_type"] == "keys" and product.get("available_keys", 0) == 0:
            await interaction.response.send_message(
                f"{EMOJI_CROSS} Sem estoque disponível para este produto.", ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"{EMOJI_CONFIRM} Criando / Adicionando seu produto ao tópico.",
            ephemeral=True
        )

        # Create a private thread for this purchase
        channel = interaction.channel
        thread_name = f"🛒 {interaction.user.display_name} — {product['name']}"
        thread = await channel.create_thread(
            name=thread_name[:100],
            type=discord.ChannelType.private_thread,
            invitable=False
        )
        await thread.add_user(interaction.user)

        settings  = await db.get_settings()
        order     = await db.create_order(
            user_id     = str(interaction.user.id),
            user_name   = interaction.user.display_name,
            product_id  = product_id,
            quantity    = 1,
            unit_price  = product["price"],
            price_label = product["price_label"],
            total_price = product["price"],
            thread_id   = str(thread.id)
        )

        cart_msg = await thread.send(
            content=interaction.user.mention,
            embed=cart_embed(order, settings),
            view=CartView()
        )
        await db.update_order(order["id"], message_id=str(cart_msg.id))

        # Update ephemeral with redirect button
        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            label="Redirecionar",
            emoji="↗️",
            url=cart_msg.jump_url,
            style=discord.ButtonStyle.link
        ))
        await interaction.edit_original_response(
            content=f"{EMOJI_CONFIRM} **Tópico Criado**\n"
                    "Seu tópico de compras foi criado, adicione os produtos que deseja comprar.\n"
                    "Para se redirecionar ao tópico clique no botão abaixo.",
            view=view
        )


class ShopView(discord.ui.View):
    """Persistent view for the main shop embed."""

    def __init__(self, products: list[dict]):
        super().__init__(timeout=None)
        self.add_item(ProductSelect(products))


class CartView(discord.ui.View):
    """Persistent cart view inside the purchase thread."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Alterar Quantidade", emoji="✏️",
        style=discord.ButtonStyle.secondary,
        custom_id="cart:change_qty", row=0
    )
    async def change_qty(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(QuantityModal())

    @discord.ui.button(
        label="Adicionar Cupom", emoji="🏷️",
        style=discord.ButtonStyle.secondary,
        custom_id="cart:add_coupon", row=0
    )
    async def add_coupon(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(CouponModal())

    @discord.ui.button(
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="cart:delete_item", row=0
    )
    async def delete_item(self, interaction: discord.Interaction, _: discord.ui.Button):
        order = await db.get_order_by_thread(str(interaction.channel_id))
        if not order:
            await interaction.response.send_message(f"{EMOJI_CROSS} Pedido não encontrado.", ephemeral=True)
            return
        await db.cancel_order(order["id"])
        await interaction.response.send_message(
            f"{EMOJI_CROSS} Item removido do carrinho.", ephemeral=True
        )
        # Disable buttons on cart message
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

    @discord.ui.button(
        label="Ir para Pagamento", emoji="🛒",
        style=discord.ButtonStyle.success,
        custom_id="cart:go_payment", row=1
    )
    async def go_payment(self, interaction: discord.Interaction, _: discord.ui.Button):
        order = await db.get_order_by_thread(str(interaction.channel_id))
        if not order:
            await interaction.response.send_message(f"{EMOJI_CROSS} Pedido não encontrado.", ephemeral=True)
            return

        settings = await db.get_settings()
        pix_key  = order.get("pix_key") or settings.get("global_pix_key")

        await db.update_order(order["id"], status="awaiting_payment")

        # Disable cart buttons
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)

        await interaction.response.send_message(
            embed=payment_embed(order, settings),
            view=PaymentView(order["id"], pix_key),
        )

    @discord.ui.button(
        label="Cancelar Pedido", emoji="🗑️",
        style=discord.ButtonStyle.danger,
        custom_id="cart:cancel_order", row=1
    )
    async def cancel_order(self, interaction: discord.Interaction, _: discord.ui.Button):
        order = await db.get_order_by_thread(str(interaction.channel_id))
        if not order:
            await interaction.response.send_message(f"{EMOJI_CROSS} Pedido não encontrado.", ephemeral=True)
            return
        await db.cancel_order(order["id"])
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(
            f"{EMOJI_CROSS} Pedido **#{order['id']}** cancelado.",
            ephemeral=True
        )


class PaymentView(discord.ui.View):
    """Payment confirmation view."""

    def __init__(self, order_id: int, pix_key: str | None):
        super().__init__(timeout=None)
        self.order_id = order_id
        self.pix_key  = pix_key

    @discord.ui.button(
        label="Código Copia e Cola", emoji="📋",
        style=discord.ButtonStyle.secondary,
        custom_id="payment:copy_code"
    )
    async def copy_code(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.pix_key:
            await interaction.response.send_message(
                f"{EMOJI_CROSS} Chave Pix não configurada. Contate o admin.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"{EMOJI_CLIPBOARD} **Chave Pix (Copia e Cola):**\n```\n{self.pix_key}\n```",
            ephemeral=True
        )

    @discord.ui.button(
        label="QR Code", emoji="📷",
        style=discord.ButtonStyle.secondary,
        custom_id="payment:qrcode"
    )
    async def qr_code(self, interaction: discord.Interaction, _: discord.ui.Button):
        if not self.pix_key:
            await interaction.response.send_message(
                f"{EMOJI_CROSS} Chave Pix não configurada.", ephemeral=True
            )
            return
        import urllib.parse
        encoded = urllib.parse.quote(self.pix_key)
        qr_url  = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={encoded}"
        em = discord.Embed(title="QR Code Pix", color=COLOR_PRIMARY)
        em.set_image(url=qr_url)
        await interaction.response.send_message(embed=em, ephemeral=True)

    @discord.ui.button(
        label="Termos e Condições", emoji="📁",
        style=discord.ButtonStyle.secondary,
        custom_id="payment:terms"
    )
    async def terms(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_message(
            f"{EMOJI_FOLDER} **Termos e Condições**\n\n"
            "• Todas as compras são finais e não reembolsáveis.\n"
            "• As chaves são entregues automaticamente após confirmação do pagamento.\n"
            "• Em caso de problemas, contate o suporte.\n"
            "• O uso do produto é de responsabilidade do comprador.",
            ephemeral=True
        )

    @discord.ui.button(
        label="Cancelar", emoji="❌",
        style=discord.ButtonStyle.danger,
        custom_id="payment:cancel"
    )
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        order = await db.get_order_by_thread(str(interaction.channel_id))
        if order:
            await db.cancel_order(order["id"])
        for child in self.children:
            child.disabled = True
        await interaction.message.edit(view=self)
        await interaction.response.send_message(
            f"{EMOJI_CROSS} Pagamento cancelado.", ephemeral=True
        )


# ─────────────────────────────────────────────────────────────────────────────
# Cog
# ─────────────────────────────────────────────────────────────────────────────

class ShopCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Register persistent views so they survive restarts
        bot.add_view(CartView())

    @commands.Cog.listener()
    async def on_ready(self):
        # Re-register PaymentView for all pending payment orders
        orders = await db._fetch(
            "SELECT o.*, p.pix_key FROM orders o "
            "LEFT JOIN products p ON o.product_id = p.id "
            "WHERE o.status = 'awaiting_payment'"
        )
        settings = await db.get_settings()
        for order in orders:
            pix = order.get("pix_key") or (settings.get("global_pix_key") if settings else None)
            self.bot.add_view(PaymentView(order["id"], pix))

    # ── /post ─────────────────────────────────────────────────────────────────

    @app_commands.command(name="post", description="Post the shop product listing")
    @app_commands.describe(channel="Channel to post in (defaults to current)")
    @app_commands.default_permissions(administrator=True)
    async def post(self, interaction: discord.Interaction,
                   channel: discord.TextChannel | None = None):
        target = channel or interaction.channel
        products = await db.get_products(active_only=True)
        if not products:
            await interaction.response.send_message(
                f"{EMOJI_CROSS} Nenhum produto ativo cadastrado.", ephemeral=True
            )
            return

        settings = await db.get_settings()
        footer   = settings.get("footer_text", "NeverMiss Apps © 2026") if settings else "NeverMiss Apps © 2026"
        color    = settings.get("embed_color", COLOR_PRIMARY) if settings else COLOR_PRIMARY

        # Build listing embed
        lines = []
        for p in products:
            stk   = "∞" if p["stock_type"] == "infinite" else str(p.get("available_keys", 0))
            lines.append(
                f"{EMOJI_CART} **{p['name']}**\n"
                f"Valor: {p['price_label']} | Estoque: {stk}"
            )

        em = discord.Embed(
            description="\n\n".join(lines),
            color=color
        )
        # Use first product's image as the main image
        for p in products:
            if p.get("image_url"):
                em.set_image(url=p["image_url"])
                break

        em.set_footer(text=footer)

        await target.send(embed=em, view=ShopView(products))
        await interaction.response.send_message(
            f"{EMOJI_CONFIRM} Listagem postada em {target.mention}!", ephemeral=True
        )
        await db.log_activity("shop_post", f"Product listing posted in #{target.name}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ShopCog(bot))
