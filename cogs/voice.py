import discord
import asyncio
from discord import app_commands
from discord.ext import commands
import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", "voice.db")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))


class SetupModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Setup Voice Channels")
        self.add_item(
            discord.ui.TextInput(
                label="Category Name", placeholder="e.g. Voice Channels", max_length=100
            )
        )
        self.add_item(
            discord.ui.TextInput(
                label="Channel Name", placeholder="e.g. Join To Create", max_length=100
            )
        )

    async def callback(self, interaction: discord.Interaction):
        category_name = self.children[0].value
        channel_name = self.children[1].value

        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        guildID = interaction.guild.id
        id = interaction.user.id

        try:
            new_cat = await interaction.guild.create_category_channel(category_name)
            channel = await interaction.guild.create_voice_channel(
                channel_name, category=new_cat
            )

            c.execute(
                "SELECT * FROM guild WHERE guildID = ? AND ownerID=?", (guildID, id)
            )
            voice = c.fetchone()
            if voice is None:
                c.execute(
                    "INSERT INTO guild VALUES (?, ?, ?, ?)",
                    (guildID, id, channel.id, new_cat.id),
                )
            else:
                c.execute(
                    "UPDATE guild SET guildID = ?, ownerID = ?, voiceChannelID = ?, voiceCategoryID = ? WHERE guildID = ?",
                    (guildID, id, channel.id, new_cat.id, guildID),
                )

            await interaction.response.send_message(
                "**You are all setup and ready to go!**"
            )
        except Exception as e:
            await interaction.response.send_message(f"Error during setup: {str(e)}")
        finally:
            conn.commit()
            conn.close()


class voice(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        guildID = member.guild.id
        c.execute("SELECT voiceChannelID FROM guild WHERE guildID = ?", (guildID,))
        voice = c.fetchone()
        if voice is None:
            pass
        else:
            voiceID = voice[0]
            try:
                if after.channel.id == voiceID:
                    c.execute(
                        "SELECT voiceCategoryID FROM guild WHERE guildID = ?",
                        (guildID,),
                    )
                    voice = c.fetchone()
                    c.execute(
                        "SELECT channelName, channelLimit FROM userSettings WHERE userID = ?",
                        (member.id,),
                    )
                    setting = c.fetchone()
                    c.execute(
                        "SELECT channelLimit FROM guildSettings WHERE guildID = ?",
                        (guildID,),
                    )
                    guildSetting = c.fetchone()
                    if setting is None:
                        name = f"{member.name}'s channel"
                        if guildSetting is None:
                            limit = 0
                        else:
                            limit = guildSetting[0]
                    else:
                        if guildSetting is None:
                            name = setting[0]
                            limit = setting[1]
                        elif guildSetting is not None and setting[1] == 0:
                            name = setting[0]
                            limit = guildSetting[0]
                        else:
                            name = setting[0]
                            limit = setting[1]
                    categoryID = voice[0]
                    id = member.id
                    category = self.bot.get_channel(categoryID)
                    channel2 = await member.guild.create_voice_channel(
                        name, category=category
                    )
                    channelID = channel2.id
                    await member.move_to(channel2)
                    await channel2.set_permissions(
                        self.bot.user, connect=True, read_messages=True
                    )
                    await channel2.set_permissions(
                        member, connect=True, read_messages=True, manage_channels=True
                    )
                    await channel2.edit(name=name, user_limit=limit)
                    c.execute("INSERT INTO voiceChannel VALUES (?, ?)", (id, channelID))
                    conn.commit()

                    def check(a, b, c):
                        return len(channel2.members) == 0

                    await self.bot.wait_for("voice_state_update", check=check)
                    await channel2.delete()
                    await asyncio.sleep(3)
                    c.execute("DELETE FROM voiceChannel WHERE userID=?", (id,))
            except:
                pass
        conn.commit()
        conn.close()

    @app_commands.command(name="voice", description="Voice channel management commands")
    async def voice_group(self, interaction: discord.Interaction):
        pass

    @app_commands.command(
        name="setup", description="Setup the voice channel system (owner only)"
    )
    @app_commands.check(
        lambda interaction: interaction.user.id == interaction.guild.owner_id
        or interaction.user.id == ADMIN_ID
    )
    async def setup(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SetupModal())

    @setup.error
    async def setup_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                f"{interaction.user.mention} only the owner of the server can setup the bot!",
                ephemeral=True,
            )
        else:
            print(error)

    @app_commands.command(
        name="set-limit",
        description="Set the default channel limit for the server (owner only)",
    )
    @app_commands.describe(
        limit="The maximum number of users in a voice channel (0 = unlimited)"
    )
    @app_commands.check(
        lambda interaction: interaction.user.id == interaction.guild.owner_id
        or interaction.user.id == ADMIN_ID
    )
    async def setlimit(self, interaction: discord.Interaction, limit: int):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute(
            "SELECT * FROM guildSettings WHERE guildID = ?", (interaction.guild.id,)
        )
        voice = c.fetchone()
        if voice is None:
            c.execute(
                "INSERT INTO guildSettings VALUES (?, ?, ?)",
                (interaction.guild.id, f"{interaction.user.name}'s channel", limit),
            )
        else:
            c.execute(
                "UPDATE guildSettings SET channelLimit = ? WHERE guildID = ?",
                (limit, interaction.guild.id),
            )
        await interaction.response.send_message(
            "You have changed the default channel limit for your server!"
        )
        conn.commit()
        conn.close()

    @app_commands.command(name="lock", description="Lock your voice channel")
    async def lock(self, interaction: discord.Interaction):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        id = interaction.user.id
        c.execute("SELECT voiceID FROM voiceChannel WHERE userID = ?", (id,))
        voice = c.fetchone()
        if voice is None:
            await interaction.response.send_message(
                f"{interaction.user.mention} You don't own a channel.", ephemeral=True
            )
        else:
            channelID = voice[0]
            role = interaction.guild.default_role
            channel = self.bot.get_channel(channelID)
            await channel.set_permissions(role, connect=False)
            await interaction.response.send_message(
                f"{interaction.user.mention} Voice chat locked! 🔒"
            )
        conn.commit()
        conn.close()

    @app_commands.command(name="unlock", description="Unlock your voice channel")
    async def unlock(self, interaction: discord.Interaction):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        id = interaction.user.id
        c.execute("SELECT voiceID FROM voiceChannel WHERE userID = ?", (id,))
        voice = c.fetchone()
        if voice is None:
            await interaction.response.send_message(
                f"{interaction.user.mention} You don't own a channel.", ephemeral=True
            )
        else:
            channelID = voice[0]
            role = interaction.guild.default_role
            channel = self.bot.get_channel(channelID)
            await channel.set_permissions(role, connect=True)
            await interaction.response.send_message(
                f"{interaction.user.mention} Voice chat unlocked! 🔓"
            )
        conn.commit()
        conn.close()

    @app_commands.command(
        name="permit", description="Give a user permission to join your voice channel"
    )
    @app_commands.describe(member="The user to permit")
    async def permit(self, interaction: discord.Interaction, member: discord.Member):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        id = interaction.user.id
        c.execute("SELECT voiceID FROM voiceChannel WHERE userID = ?", (id,))
        voice = c.fetchone()
        if voice is None:
            await interaction.response.send_message(
                f"{interaction.user.mention} You don't own a channel.", ephemeral=True
            )
        else:
            channelID = voice[0]
            channel = self.bot.get_channel(channelID)
            await channel.set_permissions(member, connect=True)
            await interaction.response.send_message(
                f"{interaction.user.mention} You have permitted {member.mention} to access the channel. ✅"
            )
        conn.commit()
        conn.close()

    @app_commands.command(
        name="reject",
        description="Remove a user's permission to join your voice channel",
    )
    @app_commands.describe(member="The user to reject")
    async def reject(self, interaction: discord.Interaction, member: discord.Member):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        id = interaction.user.id
        guildID = interaction.guild.id
        c.execute("SELECT voiceID FROM voiceChannel WHERE userID = ?", (id,))
        voice = c.fetchone()
        if voice is None:
            await interaction.response.send_message(
                f"{interaction.user.mention} You don't own a channel.", ephemeral=True
            )
        else:
            channelID = voice[0]
            channel = self.bot.get_channel(channelID)
            for members in channel.members:
                if members.id == member.id:
                    c.execute(
                        "SELECT voiceChannelID FROM guild WHERE guildID = ?", (guildID,)
                    )
                    voice = c.fetchone()
                    channel2 = self.bot.get_channel(voice[0])
                    await member.move_to(channel2)
            await channel.set_permissions(member, connect=False, read_messages=True)
            await interaction.response.send_message(
                f"{interaction.user.mention} You have rejected {member.mention} from accessing the channel. ❌"
            )
        conn.commit()
        conn.close()

    @app_commands.command(
        name="limit", description="Set the user limit for your voice channel"
    )
    @app_commands.describe(limit="The maximum number of users (0 = unlimited)")
    async def limit(self, interaction: discord.Interaction, limit: int):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        id = interaction.user.id
        c.execute("SELECT voiceID FROM voiceChannel WHERE userID = ?", (id,))
        voice = c.fetchone()
        if voice is None:
            await interaction.response.send_message(
                f"{interaction.user.mention} You don't own a channel.", ephemeral=True
            )
        else:
            channelID = voice[0]
            channel = self.bot.get_channel(channelID)
            await channel.edit(user_limit=limit)
            await interaction.response.send_message(
                f"{interaction.user.mention} You have set the channel limit to {limit}!"
            )
            c.execute("SELECT channelName FROM userSettings WHERE userID = ?", (id,))
            voice = c.fetchone()
            if voice is None:
                c.execute(
                    "INSERT INTO userSettings VALUES (?, ?, ?)",
                    (id, f"{interaction.user.name}", limit),
                )
            else:
                c.execute(
                    "UPDATE userSettings SET channelLimit = ? WHERE userID = ?",
                    (limit, id),
                )
        conn.commit()
        conn.close()

    @app_commands.command(
        name="name", description="Change the name of your voice channel"
    )
    @app_commands.describe(name="The new channel name")
    async def name(self, interaction: discord.Interaction, name: str):
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        id = interaction.user.id
        c.execute("SELECT voiceID FROM voiceChannel WHERE userID = ?", (id,))
        voice = c.fetchone()
        if voice is None:
            await interaction.response.send_message(
                f"{interaction.user.mention} You don't own a channel.", ephemeral=True
            )
        else:
            channelID = voice[0]
            channel = self.bot.get_channel(channelID)
            await channel.edit(name=name)
            await interaction.response.send_message(
                f"{interaction.user.mention} You have changed the channel name to {name}!"
            )
            c.execute("SELECT channelName FROM userSettings WHERE userID = ?", (id,))
            voice = c.fetchone()
            if voice is None:
                c.execute("INSERT INTO userSettings VALUES (?, ?, ?)", (id, name, 0))
            else:
                c.execute(
                    "UPDATE userSettings SET channelName = ? WHERE userID = ?",
                    (name, id),
                )
        conn.commit()
        conn.close()

    @app_commands.command(
        name="claim", description="Claim ownership of an abandoned voice channel"
    )
    async def claim(self, interaction: discord.Interaction):
        x = False
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        channel = interaction.user.voice.channel
        if channel is None:
            await interaction.response.send_message(
                f"{interaction.user.mention} You're not in a voice channel.",
                ephemeral=True,
            )
        else:
            id = interaction.user.id
            c.execute(
                "SELECT userID FROM voiceChannel WHERE voiceID = ?", (channel.id,)
            )
            voice = c.fetchone()
            if voice is None:
                await interaction.response.send_message(
                    f"{interaction.user.mention} You can't own that channel!",
                    ephemeral=True,
                )
            else:
                for data in channel.members:
                    if data.id == voice[0]:
                        owner = interaction.guild.get_member(voice[0])
                        await interaction.response.send_message(
                            f"{interaction.user.mention} This channel is already owned by {owner.mention}!",
                            ephemeral=True,
                        )
                        x = True
                if x == False:
                    await interaction.response.send_message(
                        f"{interaction.user.mention} You are now the owner of the channel!"
                    )
                    c.execute(
                        "UPDATE voiceChannel SET userID = ? WHERE voiceID = ?",
                        (id, channel.id),
                    )
                    old_owner = interaction.guild.get_member(voice[0])
                    if old_owner:
                        await channel.set_permissions(
                            old_owner,
                            connect=True,
                            read_messages=True,
                            manage_channels=False,
                        )
                    await channel.set_permissions(
                        interaction.user,
                        connect=True,
                        read_messages=True,
                        manage_channels=True,
                    )
        conn.commit()
        conn.close()


async def setup(bot):
    await bot.add_cog(voice(bot))
