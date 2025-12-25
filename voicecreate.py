import discord
from discord.ext import commands
import traceback
import sys
import os
import shutil

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix="\u0000", intents=intents)

bot.remove_command("help")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
if not DISCORD_TOKEN:
    print("Warning: DISCORD_TOKEN environment variable not set.")

DB_PATH = os.getenv("DB_PATH", "voice.db")
if not os.path.exists(DB_PATH):
    if os.path.exists("voice.db") and DB_PATH != "voice.db":
        print(f"Copying template database to {DB_PATH}...")
        directory = os.path.dirname(DB_PATH)
        if directory:
            os.makedirs(directory, exist_ok=True)
        shutil.copy("voice.db", DB_PATH)

initial_extensions = ["cogs.voice"]


@bot.event
async def on_ready():
    print("Logged in as")
    print(bot.user.name)
    print(bot.user.id)
    print("------")

    for extension in initial_extensions:
        try:
            await bot.load_extension(extension)
            print(f"Loaded {extension}")
        except Exception as e:
            print(f"Failed to load extension {extension}.", file=sys.stderr)
            traceback.print_exc()

    if DISCORD_TOKEN:
        print(f"Bot is in {len(bot.guilds)} guild(s)")
        for guild in bot.guilds:
            print(f"  - {guild.name} ({guild.id})")

        print("Syncing commands to all guilds...")
        try:
            synced = await bot.tree.sync()
            print(f"Synced {len(synced)} commands globally")
        except Exception as e:
            print(f"Failed to sync commands: {e}")


if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    print("Error: DISCORD_TOKEN is missing.")
