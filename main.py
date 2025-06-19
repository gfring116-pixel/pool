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
        # Forward DM to the specified channel
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
    
    # Process commands
    await bot.process_commands(message)

@bot.command(name='dm_role')
@commands.has_permissions(administrator=True)
async def dm_role_members(ctx):
    """DM all members with the specified role"""
    
    role_id = 1382280238842515587
    role = ctx.guild.get_role(role_id)
    
    if not role:
        await ctx.send("❌ Role not found!")
        return
    
    members_with_role = role.members
    
    if not members_with_role:
        await ctx.send("❌ No members found with this role!")
        return
    
    await ctx.send(f"📨 Starting to DM {len(members_with_role)} members with the role '{role.name}'...")
    
    dm_message = """Hello! 👋

We're checking in to see who's still active and wants to attend in server events.

**Please go to:** https://discord.com/channels/1122152849833459842/1383802708024365238

**Say anything there** if you're still here and want to participate in activities.

If you're really busy and can't participate, you may leave the server 

You can also reply to this DM and your message will be forwarded to the channel automatically."""
    
    sent_count = 0
    failed_count = 0
    
    for member in members_with_role:
        try:
            await member.send(dm_message)
            sent_count += 1
            
            # Send progress update every 10 members
            if sent_count % 10 == 0:
                await ctx.send(f"📤 Sent DMs to {sent_count} members...")
                
        except discord.Forbidden:
            # User has DMs disabled or blocked the bot
            failed_count += 1
        except discord.HTTPException:
            # Other DM sending errors
            failed_count += 1
        except Exception:
            failed_count += 1
    
    # Final summary
    summary = f"""

• Successfully sent: {sent_count} DMs
• Failed to send: {failed_count} DMs
• Total members with role: {len(members_with_role)}

All DM responses will be automatically forwarded to <#1383802708024365238>
"""
    
    await ctx.send(summary)

