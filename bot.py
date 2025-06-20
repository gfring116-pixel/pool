import discord
from discord.ext import commands
from dotenv import load_dotenv
import os

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
        await message.channel.send("message received")

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

    for dm in stored_dms:
        embed = discord.Embed(
            title="dm",
            description=dm["content"],
            color=0x2f3136
        )
        embed.set_footer(text=dm["author"])
        await channel.send(embed=embed)

    await ctx.send("done")