import discord
from discord.ext import commands
import asyncio
import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO)

# Bot configuration
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Configuration
TARGET_ROLE_ID = 1382280238842515587
GUILD_ID = 1122152849833459842  # Your server ID
EVENT_LINK = 'https://discord.com/events/1122152849833459842/1384531945312227389'
GAME_LINK = 'https://www.roblox.com/games/13550599465/Trenches'
BATTLE_TIMESTAMP = '<t:1750507200:t>'  # This will show in user's timezone

async def send_battle_notifications():
    """Send battle notifications to all users with the target role"""
    try:
        print('starting notifications')
        
        # Get the guild
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            print('guild not found')
            return
        
        # Fetch all members to ensure we have complete member data
        await guild.chunk()
        
        # Find the target role
        target_role = guild.get_role(TARGET_ROLE_ID)
        if not target_role:
            print('role not found')
            return
        
        print(f'found role: {target_role.name} with {len(target_role.members)} members')
        
        # Create the embed message
        embed = discord.Embed(
            title='🔥 Battle Alert!',
            description=f"There's a battle happening today at {BATTLE_TIMESTAMP}! (this time is converted to your own time)",
            color=0xFF4444,
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name='🎮 Game Location',
            value=f'[Trenches]({GAME_LINK})',
            inline=False
        )
        
        embed.add_field(
            name='✅ Can Attend?',
            value=f'Press "Interested" on [this event]({EVENT_LINK}) and ping <@.iloh>',
            inline=False
        )
        
        embed.add_field(
            name='❌ Cannot Attend?',
            value='Ping <@.iloh> and let them know you cannot attend (no reason needed)',
            inline=False
        )
        
        embed.set_footer(text='Battle Notification System')
        
        success_count = 0
        fail_count = 0
        
        # Send DM to each member with the role
        for member in target_role.members:
            try:
                await member.send(embed=embed)
                print(f'sent dm to {member.display_name}')
                success_count += 1
                
                # Add a small delay to avoid rate limiting
                await asyncio.sleep(1)
                
            except discord.Forbidden:
                print(f'dms disabled: {member.display_name}')
                fail_count += 1
            except discord.HTTPException as e:
                print(f'http error {member.display_name}: {e}')
                fail_count += 1
            except Exception as e:
                print(f'error {member.display_name}: {e}')
                fail_count += 1
        
        print(f'summary: sent {success_count} failed {fail_count} total {len(target_role.members)}')
        
        return success_count, fail_count
        
    except Exception as e:
        print(f'error in notifications: {e}')
        return 0, 0

@bot.command(name='sendi')
async def send_battle_command(ctx):
    """Command to trigger battle notifications"""
    # Add your user ID here for permission check
    authorized_users = [728201873366056992]  # Your Discord user ID
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    await ctx.send('sending notifications')
    
    success, fail = await send_battle_notifications()
    
    await ctx.send(f'done. sent: {success} failed: {fail}')

@bot.command(name='testicle')
async def test_battle_command(ctx):
    """Test command to send battle notification to yourself only"""
    # Add your user ID here for permission check
    authorized_users = [728201873366056992]  # Your Discord user ID
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    # Get your user object
    try:
        user = await bot.fetch_user(728201873366056992)
    except:
        await ctx.send('user not found')
        return
    
    # Create the embed message
    embed = discord.Embed(
        title='🔥 Battle Alert! (TEST)',
        description=f"There's a battle happening today at {BATTLE_TIMESTAMP}! (this time is converted to your own time)",
        color=0xFF4444,
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(
        name='🎮 Game Location',
        value=f'[Trenches]({GAME_LINK})',
        inline=False
    )
    
    embed.add_field(
        name='✅ Can Attend?',
        value=f'Press "Interested" on [this event]({EVENT_LINK}) and ping <@.iloh>',
        inline=False
    )
    
    embed.add_field(
        name='❌ Cannot Attend?',
        value='Ping <@.iloh> and let them know you cannot attend (no reason needed)',
        inline=False
    )
    
    embed.set_footer(text='Battle Notification System - TEST MESSAGE')
    
    try:
        await user.send(embed=embed)
        await ctx.send('test sent')
        print(f'test dm sent to {user.name}')
    except discord.Forbidden:
        await ctx.send('dms disabled')
        print('test dm failed: dms disabled')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    print(f'command error: {error}')

# Alternative: Auto-run when bot starts (uncomment if needed)
"""
@bot.event
async def on_ready():
    print(f'✅ Bot is ready! Logged in as {bot.user}')
    
    # Wait a bit for everything to load, then send notifications
    await asyncio.sleep(5)
    await send_battle_notifications()
"""

if __name__ == '__main__':
    # Get bot token from environment variable
    bot.run(os.getenv('DISCORD_TOKEN'))
