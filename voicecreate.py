import discord
from discord.ext import commands
import os
import shutil
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voicecreate")


class VoiceBot(commands.Bot):
    """
    Main bot class for the VoiceMaster bot.
    Handles initialization, database setup, and extension loading.
    """

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True

        # Determine command prefix
        command_prefix = os.getenv("COMMAND_PREFIX", ".")

        super().__init__(command_prefix=command_prefix, intents=intents)
        self.remove_command("help")

    async def setup_hook(self):
        """
        Hook called after the bot has logged in but before it has connected to the Websocket.
        Used for database setup and loading extensions.
        """
        # Database initialization
        DB_PATH = os.getenv("DB_PATH", "voice.db")
        if not os.path.exists(DB_PATH):
            if os.path.exists("voice.db") and DB_PATH != "voice.db":
                logger.info(f"Copying template database to {DB_PATH}...")
                directory = os.path.dirname(DB_PATH)
                if directory:
                    os.makedirs(directory, exist_ok=True)
                shutil.copy("voice.db", DB_PATH)

        initial_extensions = ["cogs.voice"]
        for extension in initial_extensions:
            try:
                await self.load_extension(extension)
                logger.info(f"Loaded {extension}")
            except Exception:
                logger.exception(f"Failed to load extension {extension}.")

        # Sync slash commands
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")

    async def on_ready(self):
        """Called when the bot is ready."""
        logger.info("Logged in as")
        if self.user:
            logger.info(self.user.name)
            logger.info(self.user.id)
        logger.info("------")


if __name__ == "__main__":
    DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
    if not DISCORD_TOKEN:
        logger.warning("Warning: DISCORD_TOKEN environment variable not set.")
        # We don't exit here to allow import for testing, but run() will fail if called with None

    bot = VoiceBot()

    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        logger.error("Error: DISCORD_TOKEN is missing.")
