import discord
from discord.ext import commands
from discord import app_commands
import aiosqlite
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
        async with aiosqlite.connect(DB_PATH) as db:
            # Cleanup Logic
            if before.channel:
                voice_id = before.channel.id
                async with db.execute(
                    "SELECT userID FROM voiceChannel WHERE voiceID = ?", (voice_id,)
                ) as cursor:
                    result = await cursor.fetchone()

                if result:
                    # It's a dynamic channel
                    if len(before.channel.members) == 0:
                        try:
                            await before.channel.delete()
                        except discord.NotFound:
                            pass  # Already deleted
                        except Exception as e:
                            logger.error(f"Failed to delete channel {voice_id}: {e}")

                        await db.execute(
                            "DELETE FROM voiceChannel WHERE voiceID = ?", (voice_id,)
                        )
                        await db.commit()

            # Creation Logic
            if after.channel:
                guildID = member.guild.id
                async with db.execute(
                    "SELECT voiceChannelID FROM guild WHERE guildID = ?", (guildID,)
                ) as cursor:
                    voice = await cursor.fetchone()

                if voice:
                    voiceID = voice[0]
                    if after.channel.id == voiceID:
                        try:
                            async with db.execute(
                                "SELECT voiceCategoryID FROM guild WHERE guildID = ?",
                                (guildID,),
                            ) as cursor:
                                voice_cat = await cursor.fetchone()

                            async with db.execute(
                                "SELECT channelName, channelLimit FROM userSettings WHERE userID = ?",
                                (member.id,),
                            ) as cursor:
                                setting = await cursor.fetchone()

                            async with db.execute(
                                "SELECT channelLimit FROM guildSettings WHERE guildID = ?",
                                (guildID,),
                            ) as cursor:
                                guildSetting = await cursor.fetchone()

                            if setting is None:
                                name = f"{member.name}'s channel"
                                limit = 0 if guildSetting is None else guildSetting[0]
                            else:
                                name = setting[0]
                                if guildSetting is None:
                                    limit = setting[1]
                                elif setting[1] == 0:
                                    limit = guildSetting[0]
                                else:
                                    limit = setting[1]

                            categoryID = voice_cat[0]
                            category = self.bot.get_channel(categoryID)
                            if category:
                                channel2 = await member.guild.create_voice_channel(
                                    name, category=category
                                )
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

                                await db.execute(
                                    "INSERT INTO voiceChannel VALUES (?, ?)",
                                    (member.id, channel2.id),
                                )
                                await db.commit()
                        except Exception:
                            logger.exception("Error in voice state update (creation)")

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
        if not (
            interaction.user.id == interaction.guild.owner_id
            or interaction.user.id == ADMIN_ID
        ):
            await interaction.response.send_message(
                f"{interaction.user.mention} only the owner of the server can setup the bot!",
                ephemeral=True,
            )
            return

        async with aiosqlite.connect(DB_PATH) as db:
            try:
                new_cat = await interaction.guild.create_category_channel(category_name)
                channel = await interaction.guild.create_voice_channel(
                    channel_name, category=new_cat
                )

                async with db.execute(
                    "SELECT * FROM guild WHERE guildID = ? AND ownerID=?",
                    (interaction.guild.id, interaction.user.id),
                ) as cursor:
                    voice = await cursor.fetchone()

                if voice is None:
                    await db.execute(
                        "INSERT INTO guild VALUES (?, ?, ?, ?)",
                        (
                            interaction.guild.id,
                            interaction.user.id,
                            channel.id,
                            new_cat.id,
                        ),
                    )
                else:
                    await db.execute(
                        "UPDATE guild SET guildID = ?, ownerID = ?, voiceChannelID = ?, voiceCategoryID = ? WHERE guildID = ?",
                        (
                            interaction.guild.id,
                            interaction.user.id,
                            channel.id,
                            new_cat.id,
                            interaction.guild.id,
                        ),
                    )
                await db.commit()

                await interaction.response.send_message(
                    "**You are all setup and ready to go!**", ephemeral=True
                )
            except Exception as e:
                await interaction.response.send_message(
                    f"An error occurred: {e}", ephemeral=True
                )
                logger.exception("Error in setup")

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

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT * FROM guildSettings WHERE guildID = ?", (interaction.guild.id,)
            ) as cursor:
                voice = await cursor.fetchone()

            if voice is None:
                await db.execute(
                    "INSERT INTO guildSettings VALUES (?, ?, ?)",
                    (interaction.guild.id, f"{interaction.user.name}'s channel", limit),
                )
            else:
                await db.execute(
                    "UPDATE guildSettings SET channelLimit = ? WHERE guildID = ?",
                    (limit, interaction.guild.id),
                )
            await db.commit()

        await interaction.response.send_message(
            "You have changed the default channel limit for your server!",
            ephemeral=True,
        )

    @voice_group.command(name="lock", description="Lock your voice channel")
    async def lock(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT voiceID FROM voiceChannel WHERE userID = ?",
                (interaction.user.id,),
            ) as cursor:
                voice = await cursor.fetchone()

            if voice is None:
                await interaction.response.send_message(
                    f"{interaction.user.mention} You don't own a channel.",
                    ephemeral=True,
                )
            else:
                channelID = voice[0]
                role = interaction.guild.default_role
                channel = self.bot.get_channel(channelID)
                await channel.set_permissions(role, connect=False)
                await interaction.response.send_message(
                    f"{interaction.user.mention} Voice chat locked! 🔒", ephemeral=True
                )

    @voice_group.command(name="unlock", description="Unlock your voice channel")
    async def unlock(self, interaction: discord.Interaction):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT voiceID FROM voiceChannel WHERE userID = ?",
                (interaction.user.id,),
            ) as cursor:
                voice = await cursor.fetchone()

            if voice is None:
                await interaction.response.send_message(
                    f"{interaction.user.mention} You don't own a channel.",
                    ephemeral=True,
                )
            else:
                channelID = voice[0]
                role = interaction.guild.default_role
                channel = self.bot.get_channel(channelID)
                await channel.set_permissions(role, connect=True)
                await interaction.response.send_message(
                    f"{interaction.user.mention} Voice chat unlocked! 🔓",
                    ephemeral=True,
                )

    @voice_group.command(
        name="permit", description="Permit a user to join your channel"
    )
    async def permit(self, interaction: discord.Interaction, member: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT voiceID FROM voiceChannel WHERE userID = ?",
                (interaction.user.id,),
            ) as cursor:
                voice = await cursor.fetchone()

            if voice is None:
                await interaction.response.send_message(
                    f"{interaction.user.mention} You don't own a channel.",
                    ephemeral=True,
                )
            else:
                channelID = voice[0]
                channel = self.bot.get_channel(channelID)
                await channel.set_permissions(member, connect=True)
                await interaction.response.send_message(
                    f"{interaction.user.mention} You have permitted {member.name} to have access to the channel. ✅",
                    ephemeral=True,
                )

    @voice_group.command(
        name="reject", description="Reject/Remove a user from your channel"
    )
    async def reject(self, interaction: discord.Interaction, member: discord.Member):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT voiceID FROM voiceChannel WHERE userID = ?",
                (interaction.user.id,),
            ) as cursor:
                voice = await cursor.fetchone()

            if voice is None:
                await interaction.response.send_message(
                    f"{interaction.user.mention} You don't own a channel.",
                    ephemeral=True,
                )
            else:
                channelID = voice[0]
                channel = self.bot.get_channel(channelID)
                for members in channel.members:
                    if members.id == member.id:
                        async with db.execute(
                            "SELECT voiceChannelID FROM guild WHERE guildID = ?",
                            (interaction.guild.id,),
                        ) as cursor:
                            voice_setup = await cursor.fetchone()

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

    @voice_group.command(
        name="limit", description="Set the user limit for your channel"
    )
    async def limit(self, interaction: discord.Interaction, limit: int):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT voiceID FROM voiceChannel WHERE userID = ?",
                (interaction.user.id,),
            ) as cursor:
                voice = await cursor.fetchone()

            if voice is None:
                await interaction.response.send_message(
                    f"{interaction.user.mention} You don't own a channel.",
                    ephemeral=True,
                )
            else:
                channelID = voice[0]
                channel = self.bot.get_channel(channelID)
                await channel.edit(user_limit=limit)
                await interaction.response.send_message(
                    f"{interaction.user.mention} You have set the channel limit to be {limit}!",
                    ephemeral=True,
                )
                async with db.execute(
                    "SELECT channelName FROM userSettings WHERE userID = ?",
                    (interaction.user.id,),
                ) as cursor:
                    voice_setting = await cursor.fetchone()

                if voice_setting is None:
                    await db.execute(
                        "INSERT INTO userSettings VALUES (?, ?, ?)",
                        (interaction.user.id, f"{interaction.user.name}", limit),
                    )
                else:
                    await db.execute(
                        "UPDATE userSettings SET channelLimit = ? WHERE userID = ?",
                        (limit, interaction.user.id),
                    )
                await db.commit()

    @voice_group.command(name="name", description="Change the name of your channel")
    async def name(self, interaction: discord.Interaction, name: str):
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT voiceID FROM voiceChannel WHERE userID = ?",
                (interaction.user.id,),
            ) as cursor:
                voice = await cursor.fetchone()

            if voice is None:
                await interaction.response.send_message(
                    f"{interaction.user.mention} You don't own a channel.",
                    ephemeral=True,
                )
            else:
                channelID = voice[0]
                channel = self.bot.get_channel(channelID)
                await channel.edit(name=name)
                await interaction.response.send_message(
                    f"{interaction.user.mention} You have changed the channel name to {name}!",
                    ephemeral=True,
                )
                async with db.execute(
                    "SELECT channelName FROM userSettings WHERE userID = ?",
                    (interaction.user.id,),
                ) as cursor:
                    voice_setting = await cursor.fetchone()

                if voice_setting is None:
                    await db.execute(
                        "INSERT INTO userSettings VALUES (?, ?, ?)",
                        (interaction.user.id, name, 0),
                    )
                else:
                    await db.execute(
                        "UPDATE userSettings SET channelName = ? WHERE userID = ?",
                        (name, interaction.user.id),
                    )
                await db.commit()

    @voice_group.command(
        name="claim", description="Claim ownership of the channel if the owner left"
    )
    async def claim(self, interaction: discord.Interaction):
        channel = interaction.user.voice.channel if interaction.user.voice else None
        if channel is None:
            await interaction.response.send_message(
                f"{interaction.user.mention} you're not in a voice channel.",
                ephemeral=True,
            )
            return

        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT userID FROM voiceChannel WHERE voiceID = ?", (channel.id,)
            ) as cursor:
                voice = await cursor.fetchone()

            if voice is None:
                await interaction.response.send_message(
                    f"{interaction.user.mention} You can't own that channel!",
                    ephemeral=True,
                )
            else:
                # Check if current owner is still in the channel
                owner_found = False
                for data in channel.members:
                    if data.id == voice[0]:
                        owner = interaction.guild.get_member(voice[0])
                        await interaction.response.send_message(
                            f"{interaction.user.mention} This channel is already owned by {owner.mention}!",
                            ephemeral=True,
                        )
                        owner_found = True
                        break

                if not owner_found:
                    await interaction.response.send_message(
                        f"{interaction.user.mention} You are now the owner of the channel!",
                        ephemeral=True,
                    )
                    await db.execute(
                        "UPDATE voiceChannel SET userID = ? WHERE voiceID = ?",
                        (interaction.user.id, channel.id),
                    )
                    await db.commit()

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


async def setup(bot):
    await bot.add_cog(voice(bot))
