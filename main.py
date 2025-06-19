import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Replace with your own user ID
OWNER_ID = 728201873366056992

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')

@bot.event
async def on_message(message):
    # Don't respond to bot messages
    if message.author.bot:
        return

    # Check if it's a DM to the bot
    if isinstance(message.channel, discord.DMChannel):
        target_channel_id = 1383802708024365238
        channel = bot.get_channel(target_channel_id)

        if channel:
            embed = discord.Embed(
                title="DM Received",
                description=message.content,
                color=0x00ff00
            )
            embed.set_author(name=f"{message.author.display_name} ({message.author.name})", icon_url=message.author.avatar.url if message.author.avatar else None)
            embed.set_footer(text=f"User ID: {message.author.id}")

            await channel.send(embed=embed)

        # DM owner with info about who DMed the bot
        owner = await bot.fetch_user(OWNER_ID)
        if owner:
            await owner.send(f"{message.author} this dude: {message.content}")

    # Process commands
    await bot.process_commands(message)

@bot.command(name='rawr')
@commands.has_permissions(administrator=True)
async def dm_role_members(ctx):
    """DM all members with the specified role"""

    role_id = 1382280238842515587
    role = ctx.guild.get_role(role_id)

    if not role:
        await ctx.send("failed loser")
        return

    members_with_role = role.members

    if not members_with_role:
        await ctx.send("no i don't want to")
        return

    await ctx.send(f" {len(members_with_role)} '{role.name}'...")

    dm_message = """
We're checking in to see who's still active and wants to attend in server events.

**Please go to:** https://discord.com/channels/1122152849833459842/1383802708024365238

**Say anything there** if you're still here and want to participate in activities.

If you're really busy and can't participate, you may leave the server 
https://discord.gg/pnvPBXsZ4T

You can also reply to this DM and your message will be forwarded to the channel automatically."""

    sent_count = 0
    failed_count = 0
    notified_users = []

    for member in members_with_role:
        try:
            await member.send(dm_message)
            sent_count += 1
            notified_users.append(str(member))

            if sent_count % 10 == 0:
                await ctx.send(f"Sent DMs to {sent_count} members")

        except (discord.Forbidden, discord.HTTPException, Exception):
            failed_count += 1

    summary = f"""

• Sent: {sent_count} DMs
• Failed to send: {failed_count} DMs
• Total members with role: {len(members_with_role)}

  all DM responses will be forwarded to <#1383802708024365238>
"""

    await ctx.send(summary)

    # DM the owner with the list of members who were messaged
    owner = await bot.fetch_user(OWNER_ID)
    if owner:
        users = "\n".join(notified_users)
        await owner.send(f"✅ DMed the following users:\n{users}")

bot.run(token)
