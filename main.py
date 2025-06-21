import discord
from discord.ext import commands
import asyncio
import logging
import os
import re

# Set up logging
logging.basicConfig(level=logging.INFO)

# Bot configuration
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Store pending messages
pending_messages = {}

@bot.event
async def on_ready():
    print(f'bot ready: {bot.user}')
    print(f'guilds: {len(bot.guilds)}')

class DesignView(discord.ui.View):
    def __init__(self, user_id, targets, message_content):
        super().__init__(timeout=300)  # 5 minute timeout
        self.user_id = user_id
        self.targets = targets
        self.message_content = message_content
        self.selected_design = None

    @discord.ui.button(label='Simple Text', style=discord.ButtonStyle.secondary, emoji='📝')
    async def simple_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('not your command', ephemeral=True)
            return
        
        self.selected_design = 'simple'
        await self.show_preview(interaction)

    @discord.ui.button(label='Basic Embed', style=discord.ButtonStyle.primary, emoji='📋')
    async def basic_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('not your command', ephemeral=True)
            return
        
        self.selected_design = 'basic'
        await self.show_preview(interaction)

    @discord.ui.button(label='Fancy Embed', style=discord.ButtonStyle.success, emoji='✨')
    async def fancy_embed(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('not your command', ephemeral=True)
            return
        
        self.selected_design = 'fancy'
        await self.show_preview(interaction)

    @discord.ui.button(label='Alert Style', style=discord.ButtonStyle.danger, emoji='🚨')
    async def alert_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('not your command', ephemeral=True)
            return
        
        self.selected_design = 'alert'
        await self.show_preview(interaction)

    async def show_preview(self, interaction):
        # Create the message based on selected design
        message_data = self.create_message(self.selected_design, self.message_content)
        
        # Create confirmation view
        confirm_view = ConfirmView(self.user_id, self.targets, message_data, self.selected_design)
        
        if message_data['type'] == 'text':
            await interaction.response.edit_message(
                content=f"preview ({self.selected_design}):\n\n{message_data['content']}\n\nsend this?",
                embed=None,
                view=confirm_view
            )
        else:
            await interaction.response.edit_message(
                content=f"preview ({self.selected_design}):\n\nsend this?",
                embed=message_data['embed'],
                view=confirm_view
            )

    def create_message(self, design, content):
        if design == 'simple':
            return {'type': 'text', 'content': content}
        
        elif design == 'basic':
            embed = discord.Embed(
                description=content,
                color=0x5865F2
            )
            return {'type': 'embed', 'embed': embed}
        
        elif design == 'fancy':
            embed = discord.Embed(
                title='📢 Message',
                description=content,
                color=0x00D4AA,
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text='Message System')
            return {'type': 'embed', 'embed': embed}
        
        elif design == 'alert':
            embed = discord.Embed(
                title='🚨 Important Notice',
                description=content,
                color=0xFF4444,
                timestamp=discord.utils.utcnow()
            )
            embed.set_footer(text='Alert System')
            return {'type': 'embed', 'embed': embed}

class ConfirmView(discord.ui.View):
    def __init__(self, user_id, targets, message_data, design):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.targets = targets
        self.message_data = message_data
        self.design = design

    @discord.ui.button(label='Send', style=discord.ButtonStyle.success, emoji='✅')
    async def confirm_send(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('not your command', ephemeral=True)
            return
        
        await interaction.response.edit_message(content='sending messages...', embed=None, view=None)
        
        success, fail = await self.send_messages()
        
        await interaction.followup.send(f'done. sent: {success} failed: {fail}')

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger, emoji='❌')
    async def cancel_send(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('not your command', ephemeral=True)
            return
        
        await interaction.response.edit_message(content='cancelled', embed=None, view=None)

    @discord.ui.button(label='Change Design', style=discord.ButtonStyle.secondary, emoji='🎨')
    async def change_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message('not your command', ephemeral=True)
            return
        
        # Extract original message content
        if self.message_data['type'] == 'text':
            original_content = self.message_data['content']
        else:
            original_content = self.message_data['embed'].description
        
        design_view = DesignView(self.user_id, self.targets, original_content)
        await interaction.response.edit_message(
            content='choose design:',
            embed=None,
            view=design_view
        )

    async def send_messages(self):
        success_count = 0
        fail_count = 0
        
        for target in self.targets:
            try:
                if self.message_data['type'] == 'text':
                    await target.send(self.message_data['content'])
                else:
                    await target.send(embed=self.message_data['embed'])
                
                print(f'sent message to {target.display_name}')
                success_count += 1
                await asyncio.sleep(1)  # Rate limiting
                
            except discord.Forbidden:
                print(f'dms disabled: {target.display_name}')
                fail_count += 1
            except Exception as e:
                print(f'error {target.display_name}: {e}')
                fail_count += 1
        
        print(f'summary: sent {success_count} failed {fail_count} total {len(self.targets)}')
        return success_count, fail_count

@bot.command(name='send')
async def send_message(ctx, *, args):
    """Send a message to role members or mentioned users"""
    # Authorization check
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    # Parse the command arguments
    parts = args.split(' ', 1)
    if len(parts) < 2:
        await ctx.send('usage: !send <role_id/mentions> <message>')
        return
    
    target_arg, message_content = parts
    
    # Find targets (role members or mentioned users)
    targets = []
    
    # Check if it's a role ID
    if target_arg.isdigit():
        role_id = int(target_arg)
        role = ctx.guild.get_role(role_id)
        if role:
            targets = list(role.members)
            print(f'found role: {role.name} with {len(targets)} members')
        else:
            await ctx.send('role not found')
            return
    
    # Check for mentions in the original message
    elif ctx.message.mentions:
        targets = ctx.message.mentions
        print(f'found {len(targets)} mentioned users')
    
    else:
        await ctx.send('no valid targets found. use role id or mention users')
        return
    
    if not targets:
        await ctx.send('no targets found')
        return
    
    # Show design selection
    design_view = DesignView(ctx.author.id, targets, message_content)
    await ctx.send('choose design:', view=design_view)

@bot.command(name='testsend')
async def test_send(ctx, *, message_content):
    """Test send message to yourself only"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    # Target yourself
    targets = [ctx.author]
    
    # Show design selection
    design_view = DesignView(ctx.author.id, targets, message_content)
    await ctx.send('choose design:', view=design_view)

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    print(f'command error: {error}')

if __name__ == '__main__':
    bot.run(os.getenv('DISCORD_TOKEN'))
