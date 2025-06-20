import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

OWNER_ID = 728201873366056992
TARGET_CHANNEL_ID = 1383802708024365238

# Store DMs while the bot is running
stored_dms = []

@bot.event
async def on_ready():
    print(f'logged in as {bot.user}')

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if isinstance(message.channel, discord.DMChannel):
        stored_dms.append({
            "author": f"{message.author} ({message.author.id})",
            "content": message.content
        })
        await message.channel.send("message received")

    await bot.process_commands(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def sendpastdms(ctx):
    channel = bot.get_channel(TARGET_CHANNEL_ID)

    if not stored_dms:
        await ctx.send("no messages stored")
        return

    if not channel:
        await ctx.send("target channel not found")
        return

    await ctx.send(f"sending {len(stored_dms)} messages to <#{TARGET_CHANNEL_ID}>")

    for dm in stored_dms:
        embed = discord.Embed(
            title="dm",
            description=dm["content"],
            color=0x2f3136
        )
        embed.set_footer(text=dm["author"])
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"error sending dm: {e}")

    await ctx.send("done")