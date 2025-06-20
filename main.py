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

stored_dms = []

@bot.event
async def on_ready():
    print(f'logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel):
        print(f"got dm from {message.author}: {message.content}")
        stored_dms.append({
            "author": f"{message.author} ({message.author.id})",
            "content": message.content
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
        channel = bot.get_channel(TARGET_CHANNEL_ID)
        print(f"Target channel: {channel}")

        if not stored_dms:
            await ctx.send("no messages stored")
            print("No messages stored")
            return

        if not channel:
            await ctx.send(f"target channel not found (ID: {TARGET_CHANNEL_ID})")
            print(f"Channel {TARGET_CHANNEL_ID} not found")
            return

        # Check if bot has permissions to send messages in target channel
        if not channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.send("bot doesn't have permission to send messages in target channel")
            return

        await ctx.send(f"sending {len(stored_dms)} messages to <#{TARGET_CHANNEL_ID}>")
        print(f"Starting to send {len(stored_dms)} messages")

        sent_count = 0
        failed_count = 0

        for i, dm in enumerate(stored_dms):
            try:
                print(f"Sending message {i+1}/{len(stored_dms)}")
                
                # Handle very long messages by truncating them
                content = dm["content"] if dm["content"] else "No content"
                if len(content) > 4096:  # Discord embed description limit
                    content = content[:4093] + "..."
                
                embed = discord.Embed(
                    title="DM Message",
                    description=content,
                    color=0x2f3136
                )
                embed.set_footer(text=dm["author"])
                
                await channel.send(embed=embed)
                sent_count += 1
                print(f"Successfully sent message {i+1}")
                
                # Add a small delay to avoid rate limiting
                if i % 5 == 0 and i > 0:  # Every 5 messages
                    await asyncio.sleep(1)
                    
            except discord.HTTPException as e:
                print(f"HTTP error sending message {i+1}: {e}")
                failed_count += 1
                continue
            except Exception as e:
                print(f"Unexpected error sending message {i+1}: {e}")
                failed_count += 1
                continue

        # Send summary of results
        summary_msg = f"done! sent {sent_count}/{len(stored_dms)} messages"
        if failed_count > 0:
            summary_msg += f" ({failed_count} failed)"
        
        await ctx.send(summary_msg)
        print(summary_msg)
        
    except Exception as e:
        print(f"Error in sendpastdms command: {e}")
        await ctx.send(f"error occurred: {str(e)}")

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