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
    channel = bot.get_channel(TARGET_CHANNEL_ID)

    if not stored_dms:
        await ctx.send("no messages stored")
        return

    if not channel:
        await ctx.send("target channel not found")
        return

    await ctx.send(f"sending {len(stored_dms)} messages to <#{TARGET_CHANNEL_ID}>")

    sent_count = 0
    failed_count = 0

    for i, dm in enumerate(stored_dms):
        try:
            # Handle very long messages by truncating them
            content = dm["content"]
            if len(content) > 4096:  # Discord embed description limit
                content = content[:4093] + "..."
            
            embed = discord.Embed(
                title="dm",
                description=content,
                color=0x2f3136
            )
            embed.set_footer(text=dm["author"])
            
            await channel.send(embed=embed)
            sent_count += 1
            
            # Add a small delay to avoid rate limiting
            if i % 5 == 0 and i > 0:  # Every 5 messages
                await asyncio.sleep(1)
                
        except discord.HTTPException as e:
            print(f"failed to send message {i+1}: {e}")
            failed_count += 1
            # Continue to next message instead of stopping
            continue
        except Exception as e:
            print(f"unexpected error sending message {i+1}: {e}")
            failed_count += 1
            continue

    # Send summary of results
    summary_msg = f"done! sent {sent_count}/{len(stored_dms)} messages"
    if failed_count > 0:
        summary_msg += f" ({failed_count} failed)"
    
    await ctx.send(summary_msg)

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