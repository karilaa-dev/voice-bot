import discord
from discord.ext import commands
import traceback
import sys
import os

intents = discord.Intents.default()
#Message content intent needs to be enabled in the developer portal for your chosen bot.
intents.message_content = True

bot = commands.Bot(command_prefix=os.getenv('COMMAND_PREFIX', '.'), intents=intents)

bot.remove_command("help")

DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
if not DISCORD_TOKEN:
    raise ValueError("No DISCORD_TOKEN found in environment variables.")

initial_extensions = ['cogs.voice']

@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')

    for extension in initial_extensions:
        try:
            await bot.load_extension(extension)
            print(f'Loaded {extension}')
        except Exception as e:
            print(f'Failed to load extension {extension}.', file=sys.stderr)
            traceback.print_exc()

bot.run(DISCORD_TOKEN)
