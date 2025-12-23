import discord
from discord.ext import commands
import sys
import os
import shutil


class VoiceBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True

        # Determine command prefix
        command_prefix = os.getenv("COMMAND_PREFIX", ".")

        super().__init__(command_prefix=command_prefix, intents=intents)
        self.remove_command("help")

    async def setup_hook(self):
        # Database initialization
        DB_PATH = os.getenv("DB_PATH", "voice.db")
        if not os.path.exists(DB_PATH):
            if os.path.exists("voice.db") and DB_PATH != "voice.db":
                print(f"Copying template database to {DB_PATH}...")
                directory = os.path.dirname(DB_PATH)
                if directory:
                    os.makedirs(directory, exist_ok=True)
                shutil.copy("voice.db", DB_PATH)

        initial_extensions = ["cogs.voice"]
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                print(f"Loaded {extension}")
            except Exception:
                print(f"Failed to load extension {extension}.", file=sys.stderr)
                import traceback

                traceback.print_exc()

        # Sync slash commands
        try:
            synced = await self.tree.sync()
            print(f"Synced {len(synced)} command(s)")
        except Exception as e:
            print(e)

    async def on_ready(self):
        print("Logged in as")
        if self.user:
            print(self.user.name)
            print(self.user.id)
        print("------")


if __name__ == "__main__":
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if not DISCORD_TOKEN:
        print("Warning: DISCORD_TOKEN environment variable not set.")
        # We don't exit here to allow import for testing, but run() will fail if called with None

    bot = VoiceBot()

    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("Error: DISCORD_TOKEN is missing.")
