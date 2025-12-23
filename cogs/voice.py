import discord
import asyncio
from discord.ext import commands
from discord import app_commands
import sqlite3
import os
import logging

DB_PATH = os.getenv("DB_PATH", "voice.db")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

logger = logging.getLogger("cogs.voice")


class voice(commands.Cog):
    """
    Cog for managing dynamic voice channels.
    """

    def __init__(self, bot):
        self.bot = bot

    voice_group = app_commands.Group(
        name="voice", description="Voice channel management"
    )

    async def cog_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.AppCommandError
    ):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                "You don't have permission to use this command.", ephemeral=True
            )
        elif isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(
                "You can't use this command.", ephemeral=True
            )
        else:
            # Only send if not already sent
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    f"An error occurred: {error}", ephemeral=True
                )
            logger.error(f"App command error: {error}", exc_info=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """
        Listener for voice state updates to handle dynamic channel creation and cleanup.
        """
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
                if after.channel and after.channel.id == voiceID:
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
                    if category:
                        channel2 = await member.guild.create_voice_channel(
                            name, category=category
                        )
                        channelID = channel2.id
                        await member.move_to(channel2)
                        await channel2.set_permissions(
                            self.bot.user, connect=True, read_messages=True
                        )
                        await channel2.set_permissions(
                            member,
                            connect=True,
                            read_messages=True,
                            manage_channels=True,
                        )
                        await channel2.edit(name=name, user_limit=limit)
                        c.execute(
                            "INSERT INTO voiceChannel VALUES (?, ?)", (id, channelID)
                        )
                        conn.commit()

                        def check(a, b, c):
                            return len(channel2.members) == 0

                        await self.bot.wait_for("voice_state_update", check=check)
                        await channel2.delete()
                        await asyncio.sleep(3)
                        c.execute("DELETE FROM voiceChannel WHERE userID=?", (id,))
            except Exception:
                # Log error with stack trace
                logger.exception("Error in voice state update")
                pass
        conn.commit()
        conn.close()

    @voice_group.command(
        name="setup", description="Setup the join-to-create voice system (Admin only)"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup(
        self,
        interaction: discord.Interaction,
        category_name: str = "Voice Channels",
        channel_name: str = "Join To Create",
    ):
        # Check if user is owner or admin ID (fallback if permission check passes but we want strict owner/admin_id match)
        # The user's original code checked: ctx.author.id == ctx.guild.owner_id or ctx.author.id == ADMIN_ID
        # The @has_permissions(administrator=True) covers most cases, but let's stick to the specific logic if possible or enhance it.
        # However, has_permissions is standard. I'll add the manual check to match strict logic if desired,
        # but modern discord bots usually rely on permissions.
        # I'll keep the strict check for safety as per original code intent, combined with the admin perm check.

        if not (
            interaction.user.id == interaction.guild.owner_id
            or interaction.user.id == ADMIN_ID
        ):
            await interaction.response.send_message(
                f"{interaction.user.mention} only the owner of the server can setup the bot!",
                ephemeral=True,
            )
            return

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
                "**You are all setup and ready to go!**", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(
                f"An error occurred: {e}", ephemeral=True
            )

        conn.commit()
        conn.close()

    @voice_group.command(
        name="setlimit",
        description="Set the default limit for new channels (Admin only)",
    )
    async def setlimit(self, interaction: discord.Interaction, limit: int):
        if not (
            interaction.user.id == interaction.guild.owner_id
            or interaction.user.id == ADMIN_ID
        ):
            await interaction.response.send_message(
                f"{interaction.user.mention} only the owner of the server can setup the bot!",
                ephemeral=True,
            )
            return

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
            "You have changed the default channel limit for your server!",
            ephemeral=True,
        )
        conn.commit()
        conn.close()

    @voice_group.command(name="lock", description="Lock your voice channel")
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
                f"{interaction.user.mention} Voice chat locked! 🔒", ephemeral=True
            )
        conn.commit()
        conn.close()

    @voice_group.command(name="unlock", description="Unlock your voice channel")
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
                f"{interaction.user.mention} Voice chat unlocked! 🔓", ephemeral=True
            )
        conn.commit()
        conn.close()

    @voice_group.command(
        name="permit", description="Permit a user to join your channel"
    )
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
                f"{interaction.user.mention} You have permitted {member.name} to have access to the channel. ✅",
                ephemeral=True,
            )
        conn.commit()
        conn.close()

    @voice_group.command(
        name="reject", description="Reject/Remove a user from your channel"
    )
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
                    voice_setup = c.fetchone()
                    if voice_setup:
                        channel2 = self.bot.get_channel(voice_setup[0])
                        # Check if target channel exists and is accessible
                        if channel2:
                            await member.move_to(channel2)
            await channel.set_permissions(member, connect=False, read_messages=True)
            await interaction.response.send_message(
                f"{interaction.user.mention} You have rejected {member.name} from accessing the channel. ❌",
                ephemeral=True,
            )
        conn.commit()
        conn.close()

    @voice_group.command(
        name="limit", description="Set the user limit for your channel"
    )
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
                f"{interaction.user.mention} You have set the channel limit to be {limit}!",
                ephemeral=True,
            )
            c.execute("SELECT channelName FROM userSettings WHERE userID = ?", (id,))
            voice_setting = c.fetchone()
            if voice_setting is None:
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

    @voice_group.command(name="name", description="Change the name of your channel")
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
                f"{interaction.user.mention} You have changed the channel name to {name}!",
                ephemeral=True,
            )
            c.execute("SELECT channelName FROM userSettings WHERE userID = ?", (id,))
            voice_setting = c.fetchone()
            if voice_setting is None:
                c.execute("INSERT INTO userSettings VALUES (?, ?, ?)", (id, name, 0))
            else:
                c.execute(
                    "UPDATE userSettings SET channelName = ? WHERE userID = ?",
                    (name, id),
                )
        conn.commit()
        conn.close()

    @voice_group.command(
        name="claim", description="Claim ownership of the channel if the owner left"
    )
    async def claim(self, interaction: discord.Interaction):
        x = False
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if channel is None:
            await interaction.response.send_message(
                f"{interaction.user.mention} you're not in a voice channel.",
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
                # Check if current owner is still in the channel
                for data in channel.members:
                    if data.id == voice[0]:
                        owner = interaction.guild.get_member(voice[0])
                        await interaction.response.send_message(
                            f"{interaction.user.mention} This channel is already owned by {owner.mention}!",
                            ephemeral=True,
                        )
                        x = True
                        break
                if not x:
                    await interaction.response.send_message(
                        f"{interaction.user.mention} You are now the owner of the channel!",
                        ephemeral=True,
                    )
                    c.execute(
                        "UPDATE voiceChannel SET userID = ? WHERE voiceID = ?",
                        (id, channel.id),
                    )

                    old_owner_id = voice[0]
                    old_owner = interaction.guild.get_member(old_owner_id)
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
