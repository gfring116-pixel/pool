import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import asyncio

# Load environment variables
load_dotenv()

# Configuration
TARGET_ROLE_ID = 1382280238842515587
TARGET_CHANNEL_ID = 1383802708024365238
BOT_TOKEN = os.getenv('BOT_TOKEN')

# Set up intents
intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
intents.guilds = True
intents.members = True  # Added to access member list

# Create bot instance
bot = commands.Bot(command_prefix='!', intents=intents)

# Track users who have already messaged in the target channel
users_who_messaged = set()

@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user}')
    
    # Load existing messages from the target channel to populate the set
    try:
        channel = bot.get_channel(TARGET_CHANNEL_ID)
        if channel:
            print('Loading existing messages from target channel...')
            async for message in channel.history(limit=100):
                if not message.author.bot:
                    users_who_messaged.add(message.author.id)
            print(f'Loaded {len(users_who_messaged)} users who have already messaged in the channel.')
    except Exception as error:
        print(f'Error loading existing messages: {error}')

@bot.event
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return
    
    # Check if message is in the target channel
    if message.channel.id == TARGET_CHANNEL_ID:
        # Add user to the set of users who have messaged
        users_who_messaged.add(message.author.id)
        print(f'User {message.author} has now messaged in the target channel.')
    
    # Process commands
    await bot.process_commands(message)

@bot.command(name='dm_users')
async def dm_users_command(ctx):
    """Main command to DM all users with the target role who haven't messaged in the channel"""
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.reply("no dm commands")
        return
    
    await ctx.reply("starting dm process")
    
    users_to_dm = []
    total_with_role = 0
    successful_dms = 0
    failed_dms = 0
    
    # Go through all guilds the bot is in
    for guild in bot.guilds:
        print(f'Checking guild: {guild.name}')
        try:
            # Find the target role in this guild
            target_role = guild.get_role(TARGET_ROLE_ID)
            if not target_role:
                print(f'Target role not found in guild {guild.name}')
                continue
            
            # Get all members with the target role
            for member in target_role.members:
                total_with_role += 1
                # Check if they haven't messaged in the target channel
                if member.id not in users_who_messaged:
                    users_to_dm.append(member)
                    print(f'Added {member} to DM list')
                else:
                    print(f'Skipping {member} - already messaged in channel')
                    
        except Exception as error:
            print(f'Error checking guild {guild.name}: {error}')
            continue
    
    print(f'Found {len(users_to_dm)} users to DM out of {total_with_role} total users with the role')
    
    # Send DMs to all qualifying users
    for member in users_to_dm:
        try:
            await send_redirect_message(member)
            successful_dms += 1
            print(f'Successfully sent DM to {member}')
            # Small delay to avoid rate limiting
            await asyncio.sleep(1)
        except Exception as error:
            failed_dms += 1
            print(f'Failed to send DM to {member}: {error}')
    
    # Send summary
    summary = f"""complete
role users: {total_with_role}
already messaged: {total_with_role - len(users_to_dm)}
dm sent: {successful_dms}
failed: {failed_dms}"""
    
    await ctx.followup.send(summary)

async def send_redirect_message(user):
    """Send redirect message to user"""
    try:
        redirect_message = f"""Hello! The DM the bot feature doesn't work, so if you haven't sent a message to <#{TARGET_CHANNEL_ID}> already, you should.

Please choose one of these options:

**Option 1:** Visit <#{TARGET_CHANNEL_ID}> and type your message there.

**Option 2:** If you're very busy as the instructions mentioned, don't leave! Instead, add the user ".iloh." and tell them your concern.

Thank you for understanding!"""

        await user.send(redirect_message)
    except discord.Forbidden:
        print(f'Could not send DM to {user} - DMs might be disabled')
        raise
    except Exception as error:
        print(f'Error sending DM to {user}: {error}')
        raise

# Test command to manually trigger the DM check for the command user
@bot.command(name='test')
async def test_dm(ctx):
    if isinstance(ctx.channel, discord.DMChannel):
        return
    
    has_role = await check_user_role(ctx.author.id)
    has_messaged = ctx.author.id in users_who_messaged
    
    status_message = f"role: {has_role} messaged: {has_messaged}"
    await ctx.reply(status_message)
    
    if has_role and not has_messaged:
        await send_redirect_message(ctx.author)

async def check_user_role(user_id):
    """Check if user has the required role"""
    try:
        # Get all guilds the bot is in
        for guild in bot.guilds:
            try:
                member = guild.get_member(user_id)
                if member is None:
                    member = await guild.fetch_member(user_id)
                
                if member:
                    # Check if member has the required role
                    for role in member.roles:
                        if role.id == TARGET_ROLE_ID:
                            return True
            except discord.NotFound:
                # User might not be in this guild, continue checking other guilds
                continue
            except Exception as error:
                print(f'Error checking member in guild {guild.name}: {error}')
                continue
        
        return False
    except Exception as error:
        print(f'Error checking user role: {error}')
        return False

# Command to check stats
@bot.command(name='stat')
async def stats(ctx):
    if isinstance(ctx.channel, discord.DMChannel):
        return
    
    await ctx.reply(f'{len(users_who_messaged)}')

# Command to manually refresh the users who messaged list
@bot.command(name='refresh')
async def refresh_users(ctx):
    """Refresh the list of users who have messaged in the target channel"""
    if isinstance(ctx.channel, discord.DMChannel):
        return
    
    users_who_messaged.clear()
    
    try:
        channel = bot.get_channel(TARGET_CHANNEL_ID)
        if channel:
            async for message in channel.history(limit=100):
                if not message.author.bot:
                    users_who_messaged.add(message.author.id)
            await ctx.reply(f'refreshed {len(users_who_messaged)} users')
        else:
            await ctx.reply('target channel not found')
    except Exception as error:
        await ctx.reply(f'refresh error: {error}')

# Error handling
@bot.event
async def on_error(event, *args, **kwargs):
    print(f'Bot error in {event}: {args}, {kwargs}')

@bot.event
async def on_command_error(ctx, error):
    print(f'Command error: {error}')

# Run the bot
if __name__ == '__main__':
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("Error: BOT_TOKEN not found in environment variables!")
        print("Please create a .env file with BOT_TOKEN=your_bot_token_here")
