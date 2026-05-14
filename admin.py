import discord
from discord.ext import commands
from discord import app_commands
import database as db
from config import *


# ─────────────────────────────────────────────────────────────────────────────
# Permission helpers
# ─────────────────────────────────────────────────────────────────────────────

def _has_owner_role(member: discord.Member) -> bool:
    """Always-admin: role IDs hardcoded in config.OWNER_ROLE_IDS."""
    member_role_ids = {str(r.id) for r in member.roles}
    return bool(member_role_ids & set(OWNER_ROLE_IDS))


def is_admin():
    """
    Allow if ANY of:
      1. Discord Administrator permission
      2. Member has one of the hardcoded OWNER_ROLE_IDS
      3. Member has any role listed in settings.admin_role_ids (comma-separated)
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user
        if member.guild_permissions.administrator:
            return True
        if _has_owner_role(member):
            return True
        settings = await db.get_settings()
        if settings and settings.get("admin_role_ids"):
            allowed_ids = {r.strip() for r in settings["admin_role_ids"].split(",")}
            member_role_ids = {str(r.id) for r in member.roles}
            if allowed_ids & member_role_ids:
                return True
        return False
    return app_commands.check(predicate)


def is_owner_only():
    """
    Stricter check for /settings — only Discord admins or OWNER_ROLE_IDS.
    Prevents admin-role users from escalating their own permissions.
    """
    async def predicate(interaction: discord.Interaction) -> bool:
        member = interaction.user
        if member.guild_permissions.administrator:
            return True
        if _has_owner_role(member):
            return True
        return False
    return app_commands.check(predicate)


def fmt_price(val: float) -> str:
    return f"R$ {val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ─────────────────────────────────────────────────────────────────────────────

class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /addproduct ───────────────────────────────────────────────────────────

    @app_commands.command(name="addproduct", description="Add a new product to the shop")
    @app_commands.describe(
        name="Product name",
        price="Price value (e.g. 60.00)",
        price_label="Display label (e.g. R$ 60,00)",
        description="Product description shown in the cart",
        image_url="Product image URL (optional)",
        pix_key="Pix key for this product (overrides global)",
        stock_type="'keys' = license keys | 'infinite' = unlimited stock"
    )
    @app_commands.choices(stock_type=[
        app_commands.Choice(name="Keys (license key delivery)", value="keys"),
        app_commands.Choice(name="Infinite (unlimited stock)", value="infinite"),
    ])
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_admin()
    async def addproduct(
        self,
        interaction: discord.Interaction,
        name: str,
        price: float,
        price_label: str,
        description: str = "",
        image_url: str | None = None,
        pix_key: str | None = None,
        stock_type: str = "keys"
    ):
        product = await db.create_product(
            name=name, description=description,
            price=price, price_label=price_label,
            image_url=image_url, pix_key=pix_key,
            stock_type=stock_type
        )
        em = discord.Embed(
            title=f"{EMOJI_PRODUCT} Produto Adicionado",
            description=f"**{product['name']}** foi cadastrado com sucesso!",
            color=COLOR_SUCCESS
        )
        em.add_field(name="ID",    value=str(product["id"]),   inline=True)
        em.add_field(name="Preço", value=price_label,           inline=True)
        em.add_field(name="Stock", value=stock_type,            inline=True)
        await interaction.response.send_message(embed=em, ephemeral=True)

    # ── /editproduct ──────────────────────────────────────────────────────────

    @app_commands.command(name="editproduct", description="Edit an existing product")
    @app_commands.describe(product_id="Product ID to edit")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_admin()
    async def editproduct(
        self,
        interaction: discord.Interaction,
        product_id: int,
        name: str | None = None,
        price: float | None = None,
        price_label: str | None = None,
        description: str | None = None,
        image_url: str | None = None,
        pix_key: str | None = None,
    ):
        kwargs = {k: v for k, v in {
            "name": name, "price": price, "price_label": price_label,
            "description": description, "image_url": image_url, "pix_key": pix_key
        }.items() if v is not None}
        if not kwargs:
            await interaction.response.send_message(f"{EMOJI_CROSS} Nenhum campo fornecido.", ephemeral=True)
            return
        product = await db.update_product(product_id, **kwargs)
        if not product:
            await interaction.response.send_message(f"{EMOJI_CROSS} Produto #{product_id} não encontrado.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"{EMOJI_CONFIRM} Produto **{product['name']}** atualizado!", ephemeral=True
        )

    # ── /removeproduct ────────────────────────────────────────────────────────

    @app_commands.command(name="removeproduct", description="Remove a product from the shop")
    @app_commands.describe(product_id="Product ID to remove")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_admin()
    async def removeproduct(self, interaction: discord.Interaction, product_id: int):
        product = await db.delete_product(product_id)
        if not product:
            await interaction.response.send_message(f"{EMOJI_CROSS} Produto #{product_id} não encontrado.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"{EMOJI_CONFIRM} Produto **{product['name']}** removido!", ephemeral=True
        )

    # ── /toggleproduct ────────────────────────────────────────────────────────

    @app_commands.command(name="toggleproduct", description="Enable or disable a product")
    @app_commands.describe(product_id="Product ID")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_admin()
    async def toggleproduct(self, interaction: discord.Interaction, product_id: int):
        product = await db.get_product(product_id)
        if not product:
            await interaction.response.send_message(f"{EMOJI_CROSS} Produto #{product_id} não encontrado.", ephemeral=True)
            return
        new_state = 0 if product["active"] else 1
        await db.update_product(product_id, active=new_state)
        state_label = "ativado" if new_state else "desativado"
        await interaction.response.send_message(
            f"{EMOJI_CONFIRM} Produto **{product['name']}** {state_label}!", ephemeral=True
        )

    # ── /listproducts ─────────────────────────────────────────────────────────

    @app_commands.command(name="listproducts", description="List all products")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_admin()
    async def listproducts(self, interaction: discord.Interaction):
        products = await db.get_products(active_only=False)
        if not products:
            await interaction.response.send_message(f"{EMOJI_CROSS} Nenhum produto cadastrado.", ephemeral=True)
            return
        em = discord.Embed(title=f"{EMOJI_PRODUCT} Produtos", color=COLOR_PRIMARY)
        for p in products:
            stk    = "∞" if p["stock_type"] == "infinite" else f"{p.get('available_keys', 0)} chaves"
            status = EMOJI_CONFIRM if p["active"] else EMOJI_CROSS
            em.add_field(
                name=f"[{p['id']}] {p['name']}",
                value=f"{status} | {p['price_label']} | {stk}",
                inline=False
            )
        await interaction.response.send_message(embed=em, ephemeral=True)

    # ── /addkey ───────────────────────────────────────────────────────────────

    @app_commands.command(name="addkey", description="Add a single license key")
    @app_commands.describe(product_id="Product ID", key="The license key")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_admin()
    async def addkey(self, interaction: discord.Interaction, product_id: int, key: str):
        result = await db.add_key(product_id, key)
        if not result:
            await interaction.response.send_message(
                f"{EMOJI_CROSS} Chave já existe ou produto inválido.", ephemeral=True
            )
            return
        await interaction.response.send_message(
            f"{EMOJI_CONFIRM} Chave adicionada ao produto #{product_id}! ID: `{result['id']}`",
            ephemeral=True
        )

    # ── /bulkaddkeys ──────────────────────────────────────────────────────────

    @app_commands.command(name="bulkaddkeys", description="Add multiple keys (comma or newline separated)")
    @app_commands.describe(product_id="Product ID", keys="Keys separated by commas or new lines")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_admin()
    async def bulkaddkeys(self, interaction: discord.Interaction, product_id: int, keys: str):
        await interaction.response.defer(ephemeral=True)
        key_list = [k.strip() for k in keys.replace("\n", ",").split(",") if k.strip()]
        if not key_list:
            await interaction.followup.send(f"{EMOJI_CROSS} Nenhuma chave fornecida.", ephemeral=True)
            return
        added, skipped = await db.bulk_add_keys(product_id, key_list)
        await interaction.followup.send(
            f"{EMOJI_CONFIRM} **{added}** chaves adicionadas, **{skipped}** duplicadas ignoradas.",
            ephemeral=True
        )

    # ── /removekey ────────────────────────────────────────────────────────────

    @app_commands.command(name="removekey", description="Remove a license key by ID")
    @app_commands.describe(key_id="Key ID to remove")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_admin()
    async def removekey(self, interaction: discord.Interaction, key_id: int):
        key = await db.delete_key(key_id)
        if not key:
            await interaction.response.send_message(f"{EMOJI_CROSS} Chave #{key_id} não encontrada.", ephemeral=True)
            return
        await interaction.response.send_message(
            f"{EMOJI_CONFIRM} Chave #{key_id} removida!", ephemeral=True
        )

    # ── /listkeys ─────────────────────────────────────────────────────────────

    @app_commands.command(name="listkeys", description="List keys for a product")
    @app_commands.describe(product_id="Product ID", status="Filter by status")
    @app_commands.choices(status=[
        app_commands.Choice(name="All", value="all"),
        app_commands.Choice(name="Available", value="available"),
        app_commands.Choice(name="Used", value="used"),
    ])
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_admin()
    async def listkeys(self, interaction: discord.Interaction, product_id: int, status: str = "all"):
        st = None if status == "all" else status
        keys = await db.get_keys(product_id=product_id, status=st)
        product = await db.get_product(product_id)
        if not product:
            await interaction.response.send_message(f"{EMOJI_CROSS} Produto não encontrado.", ephemeral=True)
            return

        available = sum(1 for k in keys if k["status"] == "available")
        used      = sum(1 for k in keys if k["status"] == "used")

        em = discord.Embed(
            title=f"{EMOJI_KEY} Chaves — {product['name']}",
            color=COLOR_PRIMARY
        )
        em.add_field(name=f"{EMOJI_CONFIRM} Disponíveis", value=str(available), inline=True)
        em.add_field(name=f"{EMOJI_CROSS} Usadas",        value=str(used),      inline=True)
        em.add_field(name="Total",                        value=str(len(keys)), inline=True)

        if keys:
            sample = keys[:10]
            lines  = []
            for k in sample:
                icon   = EMOJI_CONFIRM if k["status"] == "available" else EMOJI_CROSS
                masked = k["key_value"][:6] + "••••••"
                lines.append(f"`{k['id']}` {icon} `{masked}`")
            em.add_field(
                name="Chaves (primeiras 10)",
                value="\n".join(lines) + ("\n..." if len(keys) > 10 else ""),
                inline=False
            )

        await interaction.response.send_message(embed=em, ephemeral=True)

    # ── /confirmorder ─────────────────────────────────────────────────────────

    @app_commands.command(name="confirmorder", description="Manually confirm a payment and deliver key")
    @app_commands.describe(order_id="Order ID to confirm")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_admin()
    async def confirmorder(self, interaction: discord.Interaction, order_id: int):
        await interaction.response.defer(ephemeral=True)
        order = await db.get_order(order_id)
        if not order:
            await interaction.followup.send(f"{EMOJI_CROSS} Pedido #{order_id} não encontrado.", ephemeral=True)
            return
        if order["status"] == "completed":
            await interaction.followup.send(f"{EMOJI_CROSS} Pedido já confirmado.", ephemeral=True)
            return

        delivery_msg = ""
        if order["stock_type"] == "keys":
            key = await db.pop_available_key(order["product_id"])
            if not key:
                await interaction.followup.send(
                    f"{EMOJI_CROSS} Sem chaves disponíveis para este produto.", ephemeral=True
                )
                return
            try:
                user = await self.bot.fetch_user(int(order["user_id"]))
                await user.send(
                    f"{EMOJI_KEY} **Sua Chave — {order['product_name']}**\n"
                    f"```\n{key['key_value']}\n```\n"
                    f"{EMOJI_CONFIRM} Guarde esta chave. Não compartilhe com ninguém.\n"
                    f"{EMOJI_WARNING} Entre em contato com o suporte em caso de problemas."
                )
                delivery_msg = f"\n{EMOJI_CONFIRM} Chave enviada via DM para <@{order['user_id']}>."
            except Exception:
                delivery_msg = f"\n{EMOJI_CROSS} DM bloqueada. Chave: `{key['key_value']}`"

        await db.update_order(order_id, status="completed")
        await db.log_activity("order_complete", f"Order #{order_id} confirmed by {interaction.user.display_name}")

        if order.get("thread_id"):
            thread = self.bot.get_channel(int(order["thread_id"]))
            if thread:
                await thread.send(
                    f"{EMOJI_CONFIRM} **Pagamento confirmado!** Obrigado pela sua compra.{delivery_msg}"
                )

        await interaction.followup.send(
            f"{EMOJI_CONFIRM} Pedido #{order_id} confirmado!{delivery_msg}", ephemeral=True
        )

    # ── /cancelorder ─────────────────────────────────────────────────────────

    @app_commands.command(name="cancelorder", description="Cancel an order")
    @app_commands.describe(order_id="Order ID to cancel")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_admin()
    async def cancelorder(self, interaction: discord.Interaction, order_id: int):
        order = await db.get_order(order_id)
        if not order:
            await interaction.response.send_message(f"{EMOJI_CROSS} Pedido #{order_id} não encontrado.", ephemeral=True)
            return
        await db.cancel_order(order_id)
        if order.get("thread_id"):
            thread = self.bot.get_channel(int(order["thread_id"]))
            if thread:
                await thread.send(f"{EMOJI_CROSS} Pedido cancelado pelo administrador.")
        await interaction.response.send_message(
            f"{EMOJI_CONFIRM} Pedido #{order_id} cancelado!", ephemeral=True
        )

    # ── /addcoupon ────────────────────────────────────────────────────────────

    @app_commands.command(name="addcoupon", description="Create a discount coupon")
    @app_commands.describe(
        code="Coupon code",
        discount_type="percent = percentage, fixed = fixed R$ amount",
        value="Discount value (e.g. 10 for 10% or R$10)",
        uses="Max uses (-1 for unlimited)"
    )
    @app_commands.choices(discount_type=[
        app_commands.Choice(name="Percentage (%)", value="percent"),
        app_commands.Choice(name="Fixed (R$)",     value="fixed"),
    ])
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_admin()
    async def addcoupon(
        self,
        interaction: discord.Interaction,
        code: str,
        discount_type: str,
        value: float,
        uses: int = -1
    ):
        coupon = await db.create_coupon(code.upper(), discount_type, value, uses)
        if not coupon:
            await interaction.response.send_message(f"{EMOJI_CROSS} Cupom já existe.", ephemeral=True)
            return
        label = f"{value}%" if discount_type == "percent" else f"R$ {value:.2f}"
        await interaction.response.send_message(
            f"{EMOJI_CONFIRM} Cupom **{coupon['code']}** criado — {label} de desconto "
            f"({'ilimitado' if uses == -1 else str(uses)} usos).",
            ephemeral=True
        )

    # ── /removecoupon ─────────────────────────────────────────────────────────

    @app_commands.command(name="removecoupon", description="Remove a coupon")
    @app_commands.describe(code="Coupon code to remove")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_admin()
    async def removecoupon(self, interaction: discord.Interaction, code: str):
        await db.delete_coupon(code.upper())
        await interaction.response.send_message(
            f"{EMOJI_CONFIRM} Cupom **{code.upper()}** removido!", ephemeral=True
        )

    # ── /stats ────────────────────────────────────────────────────────────────

    @app_commands.command(name="stats", description="Show bot statistics")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_admin()
    async def stats(self, interaction: discord.Interaction):
        s = await db.get_stats()
        em = discord.Embed(title=f"{EMOJI_ADMIN} Estatísticas", color=COLOR_PRIMARY)
        em.add_field(name=f"{EMOJI_PRODUCT} Produtos",     value=f"{s['active_products']}/{s['total_products']} ativos", inline=True)
        em.add_field(name=f"{EMOJI_KEY} Chaves",           value=f"{s['available_keys']} disponíveis",                  inline=True)
        em.add_field(name=f"{EMOJI_CONFIRM} Concluídos",   value=str(s["completed_orders"]),                            inline=True)
        em.add_field(name="Chaves Usadas",                 value=str(s["used_keys"]),                                   inline=True)
        em.add_field(name="Pedidos Pendentes",             value=str(s["pending_orders"]),                              inline=True)
        em.add_field(name="Total de Pedidos",              value=str(s["total_orders"]),                                inline=True)
        await interaction.response.send_message(embed=em, ephemeral=True)

    # ── /addadmin ─────────────────────────────────────────────────────────────

    @app_commands.command(name="addadmin", description="Grant a role access to admin commands")
    @app_commands.describe(role="The role to grant admin access")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_owner_only()
    async def addadmin(self, interaction: discord.Interaction, role: discord.Role):
        settings = await db.get_settings()
        existing = settings.get("admin_role_ids") or ""
        ids = [r.strip() for r in existing.split(",") if r.strip()]
        if str(role.id) in ids:
            await interaction.response.send_message(
                f"{EMOJI_CROSS} O cargo {role.mention} já é admin.", ephemeral=True
            )
            return
        ids.append(str(role.id))
        await db.update_settings(admin_role_ids=",".join(ids))
        await interaction.response.send_message(
            f"{EMOJI_CONFIRM} {role.mention} agora tem acesso admin!", ephemeral=True
        )

    # ── /removeadmin ─────────────────────────────────────────────────────────

    @app_commands.command(name="removeadmin", description="Revoke a role's admin access")
    @app_commands.describe(role="The role to revoke")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_owner_only()
    async def removeadmin(self, interaction: discord.Interaction, role: discord.Role):
        settings = await db.get_settings()
        existing = settings.get("admin_role_ids") or ""
        ids = [r.strip() for r in existing.split(",") if r.strip() and r.strip() != str(role.id)]
        await db.update_settings(admin_role_ids=",".join(ids))
        await interaction.response.send_message(
            f"{EMOJI_CONFIRM} Acesso admin removido de {role.mention}.", ephemeral=True
        )

    # ── /listadmins ───────────────────────────────────────────────────────────

    @app_commands.command(name="listadmins", description="List all roles with admin access")
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_owner_only()
    async def listadmins(self, interaction: discord.Interaction):
        settings = await db.get_settings()
        existing = settings.get("admin_role_ids") or ""
        ids = [r.strip() for r in existing.split(",") if r.strip()]

        em = discord.Embed(title=f"{EMOJI_ADMIN} Admin Roles", color=COLOR_PRIMARY)

        owner_lines = [f"<@&{rid}>" for rid in OWNER_ROLE_IDS]
        em.add_field(
            name=f"{EMOJI_LOCK} Owner Roles (permanentes)",
            value="\n".join(owner_lines) if owner_lines else "Nenhum",
            inline=False
        )
        em.add_field(
            name=f"{EMOJI_KEY} Admin Roles (adicionados)",
            value="\n".join(f"<@&{rid}>" for rid in ids) if ids else "Nenhum",
            inline=False
        )
        await interaction.response.send_message(embed=em, ephemeral=True)

    # ── /settings ─────────────────────────────────────────────────────────────
    # Owner-only — prevents admin roles from escalating their own permissions

    @app_commands.command(name="settings", description="View or update bot settings")
    @app_commands.describe(
        shop_channel_id="ID of the shop channel",
        global_pix_key="Global Pix key for payments",
        footer_text="Footer text shown on embeds",
        bot_name="Bot display name"
    )
    @app_commands.default_permissions(administrator=True)
    @app_commands.guild_only()
    @is_owner_only()
    async def settings(
        self,
        interaction: discord.Interaction,
        shop_channel_id: str | None = None,
        global_pix_key: str | None = None,
        footer_text: str | None = None,
        bot_name: str | None = None,
    ):
        updates = {k: v for k, v in {
            "shop_channel_id": shop_channel_id,
            "global_pix_key":  global_pix_key,
            "footer_text":     footer_text,
            "bot_name":        bot_name,
        }.items() if v is not None}

        if updates:
            await db.update_settings(**updates)
            await interaction.response.send_message(
                f"{EMOJI_CONFIRM} Configurações atualizadas!", ephemeral=True
            )
            return

        s = await db.get_settings()
        em = discord.Embed(title=f"{EMOJI_ADMIN} Configurações", color=COLOR_PRIMARY)
        em.add_field(name="Canal da Loja",    value=f"<#{s['shop_channel_id']}>"  if s.get("shop_channel_id") else "Não definido", inline=False)
        em.add_field(name="Chave Pix Global", value=f"||{s['global_pix_key']}||" if s.get("global_pix_key")  else "Não definida", inline=False)
        em.add_field(name="Footer",           value=s.get("footer_text", "—"),   inline=False)
        em.add_field(name="Nome do Bot",      value=s.get("bot_name", "—"),       inline=False)
        em.add_field(
            name="Admin Roles",
            value=s.get("admin_role_ids") or "Nenhum (use /addadmin)",
            inline=False
        )
        await interaction.response.send_message(embed=em, ephemeral=True)

    # ── Error handler ─────────────────────────────────────────────────────────

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.CheckFailure):
            msg = f"{EMOJI_CROSS} Você não tem permissão para usar este comando."
        elif isinstance(error, app_commands.MissingPermissions):
            msg = f"{EMOJI_CROSS} Permissões insuficientes."
        else:
            msg = f"{EMOJI_CROSS} Erro: {error}"
        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
