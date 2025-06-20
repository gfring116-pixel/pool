import discord
from discord.ext import commands
import asyncio
import os
from dotenv import load_dotenv

# Load token from .env
load_dotenv()
BOT_TOKEN = os.getenv("DISCORD_TOKEN")

# Configuration
TARGET_ROLE_ID = 1382280238842515587
TARGET_CHANNEL_ID = 1383802708024365238

# Set up intents
intents = discord.Intents.default()
intents.message_content = True
intents.dm_messages = True
intents.guilds = True
intents.members = True

# Create bot instance
bot = commands.Bot(command_prefix='!', intents=intents)
users_who_messaged = set()

@bot.event
async def on_ready():
    print(f'Bot is ready! Logged in as {bot.user}')
    try:
        channel = bot.get_channel(TARGET_CHANNEL_ID)
        if channel:
            async for message in channel.history(limit=100):
                if not message.author.bot:
                    users_who_messaged.add(message.author.id)
            print(f'loaded {len(users_who_messaged)} users')
    except Exception as error:
        print(f'load error: {error}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    if message.channel.id == TARGET_CHANNEL_ID:
        users_who_messaged.add(message.author.id)
    await bot.process_commands(message)

@bot.command(name='dm_users')
async def dm_users_command(ctx):
    print(f"dm_users command called by {ctx.author} in {ctx.channel}")
    
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.reply("no dm commands")
        return

    # Add permission check - only allow certain users or roles to use this command
    # Uncomment and modify as needed:
    # if not ctx.author.guild_permissions.administrator:
    #     await ctx.reply("You don't have permission to use this command")
    #     return

    try:
        await ctx.reply("starting")
        print("Sent 'starting' message")
    except Exception as e:
        print(f"Failed to send 'starting' message: {e}")
        return

    users_to_dm = []
    total_with_role = 0
    successful_dms = 0
    failed_dms = 0

    print(f"Checking {len(bot.guilds)} guilds for role {TARGET_ROLE_ID}")
    
    for guild in bot.guilds:
        try:
            target_role = guild.get_role(TARGET_ROLE_ID)
            if not target_role:
                print(f"Role {TARGET_ROLE_ID} not found in guild {guild.name}")
                continue
            
            print(f"Found role {target_role.name} with {len(target_role.members)} members")
            
            for member in target_role.members:
                total_with_role += 1
                if member.id not in users_who_messaged:
                    users_to_dm.append(member)
                    print(f"Will DM {member.display_name} ({member.id})")
                else:
                    print(f"Skipping {member.display_name} - already messaged")
                    
        except Exception as error:
            print(f'guild check error: {error}')
            continue

    print(f"Found {len(users_to_dm)} users to DM")

    for member in users_to_dm:
        try:
            await send_redirect_message(member)
            successful_dms += 1
            print(f"Successfully DMed {member.display_name}")
            await asyncio.sleep(1)  # Rate limiting
        except Exception as error:
            failed_dms += 1
            print(f'dm fail for {member.display_name}: {error}')

    summary = f"""complete
role users: {total_with_role}
already messaged: {total_with_role - len(users_to_dm)}
dm sent: {successful_dms}
failed: {failed_dms}"""
    
    try:
        await ctx.send(summary)  # Changed from followup.send to send
        print("Sent summary message")
    except Exception as e:
        print(f"Failed to send summary: {e}")

async def send_redirect_message(user):
    try:
        redirect_message = f"""Hello! The DM the bot feature doesn't work, so if you haven't sent a message to <#{TARGET_CHANNEL_ID}> already, you should.

Please choose one of these options:

**Option 1:** Visit <#{TARGET_CHANNEL_ID}> and type your message there.

**Option 2:** If you're very busy as the instructions mentioned, don't leave! Instead, add the user ".iloh." and tell them your concern.

Thank you for understanding!"""
        await user.send(redirect_message)
    except discord.Forbidden:
        print(f'dm blocked for {user}')
        raise
    except Exception as error:
        print(f'dm error for {user}: {error}')
        raise

@bot.command(name='test')
async def test_dm(ctx):
    print(f"test command called by {ctx.author}")
    
    if isinstance(ctx.channel, discord.DMChannel):
        return
    
    has_role = await check_user_role(ctx.author.id)
    has_messaged = ctx.author.id in users_who_messaged
    status_message = f"role {has_role} msg {has_messaged}"
    
    try:
        await ctx.reply(status_message)
        print(f"Sent test response: {status_message}")
        
        if has_role and not has_messaged:
            await send_redirect_message(ctx.author)
            print(f"Sent redirect message to {ctx.author}")
    except Exception as e:
        print(f"Error in test command: {e}")

async def check_user_role(user_id):
    try:
        for guild in bot.guilds:
            try:
                member = guild.get_member(user_id)
                if member is None:
                    member = await guild.fetch_member(user_id)
                if member:
                    for role in member.roles:
                        if role.id == TARGET_ROLE_ID:
                            return True
            except discord.NotFound:
                continue
            except Exception as error:
                print(f'check role error: {error}')
                continue
        return False
    except Exception as error:
        print(f'role check fail: {error}')
        return False

@bot.command(name='stat')
async def stats(ctx):
    print(f"stat command called by {ctx.author}")
    
    if isinstance(ctx.channel, discord.DMChannel):
        return
    
    try:
        await ctx.reply(f'{len(users_who_messaged)} users have messaged')
        print(f"Sent stats: {len(users_who_messaged)} users")
    except Exception as e:
        print(f"Error in stats command: {e}")

@bot.command(name='refresh')
async def refresh_users(ctx):
    print(f"refresh command called by {ctx.author}")
    
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
            print(f"Refreshed: {len(users_who_messaged)} users")
        else:
            await ctx.reply('channel not found')
            print("Target channel not found")
    except Exception as error:
        await ctx.reply(f'refresh failed: {error}')
        print(f"Refresh error: {error}")

@bot.event
async def on_error(event, *args, **kwargs):
    print(f'error in {event}: {args}, {kwargs}')

@bot.event
async def on_command_error(ctx, error):
    print(f'cmd error in {ctx.command}: {error}')
    if isinstance(error, commands.CommandNotFound):
        print(f"Command not found: {ctx.message.content}")
    elif isinstance(error, commands.MissingPermissions):
        await ctx.reply("You don't have permission to use this command")
    elif isinstance(error, commands.BotMissingPermissions):
        await ctx.reply("I don't have the required permissions")
    else:
        await ctx.reply(f"An error occurred: {error}")

# Start bot
if __name__ == '__main__':
    print("checking token...")
    if BOT_TOKEN:
        print(f"token found: {BOT_TOKEN[:10]}...")
        try:
            bot.run(BOT_TOKEN)
        except discord.LoginFailure:
            print("invalid token")
        except discord.HTTPException as e:
            print(f"http error: {e}")
        except Exception as e:
            print(f'bot error: {e}')
    else:
        print("token not found in .env")
