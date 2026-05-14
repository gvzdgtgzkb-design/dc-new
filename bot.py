"""
NeverMiss Shop Bot — Python Discord bot
Run: python bot.py
Requires: pip install -r requirements.txt
"""
import asyncio
import sys
import os

import discord
from discord.ext import commands

import database as db
from config import DISCORD_TOKEN, GUILD_ID


# ─────────────────────────────────────────────────────────────────────────────

intents = discord.Intents.default()
intents.guilds  = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print(f"   Guilds: {[g.name for g in bot.guilds]}")

    # Sync slash commands
    try:
        if GUILD_ID:
            guild = discord.Object(id=GUILD_ID)
            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)
        else:
            synced = await bot.tree.sync()
        print(f"   Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"   ⚠️  Command sync failed: {e}")

    await bot.change_presence(
        activity=discord.Activity(
            type=discord.ActivityType.watching,
            name="🛒 Shop"
        )
    )


@bot.event
async def on_app_command_error(interaction: discord.Interaction, error: Exception):
    msg = f"<:cross_mark:1131190543339233290> Ocorreu um erro: {error}"
    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass


async def main():
    if not DISCORD_TOKEN:
        print("❌  DISCORD_BOT_TOKEN is not set.")
        print("    1. Copy .env.example to .env")
        print("    2. Paste your bot token in .env")
        sys.exit(1)

    async with bot:
        await db.init_db()
        print("✅  Database initialised")

        await bot.load_extension("cogs.admin")
        await bot.load_extension("cogs.shop")
        print("✅  Cogs loaded")

        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
