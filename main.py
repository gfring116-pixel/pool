import discord
from discord.ext import commands
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

TARGET_CHANNEL_ID = 1383802708024365238
TARGET_ROLE_ID = 1382280238842515587
TARGET_USER_ID = 728201873366056992  # User to send the collected DMs to

stored_dms = []
channel_message_authors = set()  # Track users who already sent messages to the channel

@bot.event
async def on_ready():
    print(f'logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    # Track users who send messages to the target channel
    if message.channel.id == TARGET_CHANNEL_ID:
        channel_message_authors.add(message.author.id)
        print(f"Added {message.author} to channel message authors list")

    if isinstance(message.channel, discord.DMChannel):
        print(f"got dm from {message.author}: {message.content}")
        stored_dms.append({
            "author": f"{message.author} ({message.author.id})",
            "content": message.content,
            "user_id": message.author.id
        })
        try:
            await message.channel.send("message received")
        except Exception as e:
            print(f"failed to send confirmation to {message.author}: {e}")

    await bot.process_commands(message)

@bot.command()
async def sendpastdms(ctx):
    print(f"sendpastdms command called by {ctx.author}")
    
    try:
        # Debug: Check if command is even running
        print("Command started executing...")
        await ctx.send("🔄 Starting sendpastdms command...")
        
        # Get the target user instead of channel
        print(f"Looking for user with ID: {TARGET_USER_ID}")
        target_user = bot.get_user(TARGET_USER_ID)
        print(f"Target user found: {target_user}")
        
        if not target_user:
            print("Target user not found, trying to fetch...")
            try:
                target_user = await bot.fetch_user(TARGET_USER_ID)
                print(f"Target user fetched: {target_user}")
            except Exception as e:
                print(f"Failed to fetch user: {e}")
                await ctx.send(f"❌ target user not found (ID: {TARGET_USER_ID})")
                return

        if not stored_dms:
            await ctx.send("❌ no messages stored")
            print("No messages stored")
            return

        await ctx.send(f"📤 Found {len(stored_dms)} messages. Sending to {target_user}...")
        print(f"Starting to send {len(stored_dms)} messages to {target_user}")

        sent_count = 0
        failed_count = 0

        for i, dm in enumerate(stored_dms):
            try:
                print(f"Processing message {i+1}/{len(stored_dms)}")
                
                # Handle very long messages by truncating them
                content = dm["content"] if dm["content"] else "No content"
                if len(content) > 4096:  # Discord embed description limit
                    content = content[:4093] + "..."
                
                embed = discord.Embed(
                    title=f"DM Message #{i+1}",
                    description=content,
                    color=0x2f3136
                )
                embed.set_footer(text=f"From: {dm['author']}")
                
                print(f"Attempting to send message {i+1} to {target_user}")
                # Send to the target user via DM
                await target_user.send(embed=embed)
                sent_count += 1
                print(f"✅ Successfully sent message {i+1}")
                
                # Add a small delay to avoid rate limiting
                if i % 5 == 0 and i > 0:  # Every 5 messages
                    print("Rate limiting pause...")
                    await asyncio.sleep(1)
                    
            except discord.HTTPException as e:
                print(f"❌ HTTP error sending message {i+1}: {e}")
                failed_count += 1
                continue
            except discord.Forbidden as e:
                print(f"❌ Forbidden error sending message {i+1}: {e}")
                await ctx.send(f"❌ Cannot send DMs to {target_user} - they may have DMs disabled or blocked the bot")
                return
            except Exception as e:
                print(f"❌ Unexpected error sending message {i+1}: {e}")
                failed_count += 1
                continue

        # Send summary of results
        summary_msg = f"✅ Done! Sent {sent_count}/{len(stored_dms)} messages to {target_user}"
        if failed_count > 0:
            summary_msg += f" ({failed_count} failed)"
        
        await ctx.send(summary_msg)
        print(summary_msg)
        
    except Exception as e:
        print(f"❌ Critical error in sendpastdms command: {e}")
        import traceback
        traceback.print_exc()
        await ctx.send(f"❌ Critical error occurred: {str(e)}")

# Add a simple debug command to test basic functionality
@bot.command()
async def debug(ctx):
    """Debug command to test basic bot functionality"""
    print(f"Debug command called by {ctx.author}")
    
    embed = discord.Embed(title="Debug Info", color=0x00ff00)
    embed.add_field(name="Bot User", value=str(bot.user), inline=False)
    embed.add_field(name="Stored DMs", value=str(len(stored_dms)), inline=False)
    embed.add_field(name="Target User ID", value=str(TARGET_USER_ID), inline=False)
    
    # Try to get target user
    target_user = bot.get_user(TARGET_USER_ID)
    if target_user:
        embed.add_field(name="Target User Found", value=f"✅ {target_user}", inline=False)
    else:
        embed.add_field(name="Target User Found", value="❌ Not found", inline=False)
    
    await ctx.send(embed=embed)
    print("Debug command completed")

# Command to manually add a test DM
@bot.command()
async def addtestdm(ctx):
    """Add a test DM to the stored messages"""
    stored_dms.append({
        "author": f"Test User (123456789)",
        "content": "This is a test message",
        "user_id": 123456789
    })
    await ctx.send(f"✅ Added test DM. Total stored: {len(stored_dms)}")
    print(f"Test DM added. Total stored: {len(stored_dms)}")

# Add a simple test command to verify bot is responding
@bot.command()
async def test(ctx):
    await ctx.send("bot is working!")
    print(f"Test command called by {ctx.author}")

# Add a command to check stored DMs without sending
@bot.command()
async def checkdms(ctx):
    if not stored_dms:
        await ctx.send("no messages stored")
        return
    
    dm_list = []
    for i, dm in enumerate(stored_dms[:5]):  # Show first 5
        content_preview = dm["content"][:50] + "..." if len(dm["content"]) > 50 else dm["content"]
        dm_list.append(f"{i+1}. {dm['author']}: {content_preview}")
    
    message = f"stored {len(stored_dms)} messages:\n" + "\n".join(dm_list)
    if len(stored_dms) > 5:
        message += f"\n... and {len(stored_dms) - 5} more"
    
    await ctx.send(f"```{message}```")

@bot.command()
async def dmrole(ctx):
    """DM users with the target role asking them to message the bot again"""
    print(f"dmrole command called by {ctx.author}")
    
    try:
        # Get all members with the specified role across all guilds
        role_members = []
        for guild in bot.guilds:
            role = guild.get_role(TARGET_ROLE_ID)
            if role:
                print(f"Found role '{role.name}' in guild '{guild.name}' with {len(role.members)} members")
                role_members.extend(role.members)
        
        if not role_members:
            await ctx.send(f"no members found with role ID {TARGET_ROLE_ID}")
            return
        
        # Remove duplicates (in case user is in multiple servers with the role)
        unique_members = {member.id: member for member in role_members}
        role_members = list(unique_members.values())
        
        await ctx.send(f"found {len(role_members)} unique members with the target role")
        
        # Filter out users who already sent messages to the target channel
        users_who_sent_dm = {dm.get("user_id") for dm in stored_dms if dm.get("user_id")}
        
        members_to_dm = []
        skipped_channel = 0
        skipped_dm = 0
        
        for member in role_members:
            if member.id in channel_message_authors:
                skipped_channel += 1
                print(f"Skipping {member} - already sent message to target channel")
            elif member.id in users_who_sent_dm:
                skipped_dm += 1
                print(f"Skipping {member} - already sent DM to bot")
            else:
                members_to_dm.append(member)
        
        if not members_to_dm:
            await ctx.send(f"no members need to be DMed (skipped {skipped_channel} who messaged channel, {skipped_dm} who already DMed bot)")
            return
        
        await ctx.send(f"sending DMs to {len(members_to_dm)} members (skipped {skipped_channel + skipped_dm} who don't need it)")
        
        sent_count = 0
        failed_count = 0
        
        dm_message = """Hello! 

I'm reaching out because you have a specific role. If you previously sent me a message, could you please message me again? 

Just send me any message and I'll confirm I received it.

Thank you!"""
        
        for i, member in enumerate(members_to_dm):
            try:
                print(f"Sending DM to {member} ({i+1}/{len(members_to_dm)})")
                await member.send(dm_message)
                sent_count += 1
                
                # Rate limiting - Discord allows 10 DMs per 10 seconds to different users
                if i % 8 == 0 and i > 0:
                    print("Rate limiting pause...")
                    await asyncio.sleep(2)
                    
            except discord.HTTPException as e:
                print(f"Failed to DM {member}: {e}")
                failed_count += 1
                continue
            except discord.Forbidden:
                print(f"Cannot DM {member} - they have DMs disabled or blocked the bot")
                failed_count += 1
                continue
            except Exception as e:
                print(f"Unexpected error DMing {member}: {e}")
                failed_count += 1
                continue
        
        summary = f"DM campaign complete! Sent to {sent_count}/{len(members_to_dm)} members"
        if failed_count > 0:
            summary += f" ({failed_count} failed - likely have DMs disabled)"
        
        await ctx.send(summary)
        print(summary)
        
    except Exception as e:
        print(f"Error in dmrole command: {e}")
        await ctx.send(f"error occurred: {str(e)}")

@bot.command()
async def cleartracking(ctx):
    """Clear the tracking of who sent messages to the channel"""
    count = len(channel_message_authors)
    channel_message_authors.clear()
    await ctx.send(f"cleared tracking for {count} users who sent messages to the channel")

@bot.command()
async def status(ctx):
    """Show current status of stored data"""
    target_user = bot.get_user(TARGET_USER_ID)
    target_user_name = target_user.name if target_user else "User not found"
    
    embed = discord.Embed(title="Bot Status", color=0x2f3136)
    embed.add_field(name="Stored DMs", value=str(len(stored_dms)), inline=True)
    embed.add_field(name="Channel Message Authors", value=str(len(channel_message_authors)), inline=True)
    embed.add_field(name="Target Channel", value=f"<#{TARGET_CHANNEL_ID}>", inline=True)
    embed.add_field(name="Target Role ID", value=str(TARGET_ROLE_ID), inline=True)
    embed.add_field(name="Target User", value=f"{target_user_name} ({TARGET_USER_ID})", inline=True)
    await ctx.send(embed=embed)

@bot.command()
async def cleardms(ctx):
    """Clear all stored DMs"""
    count = len(stored_dms)
    stored_dms.clear()
    await ctx.send(f"cleared {count} stored messages")

@bot.command()
async def dmcount(ctx):
    """Show how many DMs are stored"""
    await ctx.send(f"currently storing {len(stored_dms)} messages")

bot.run(token)