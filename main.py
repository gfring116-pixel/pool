import discord
from discord.ext import commands
import os
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
AUTHORIZED_ROLES = {1255061914732597268, 1382604947924979793, 1279450222287655023, 1134711656811855942}
REGIMENT_ROLES = {
    '3rd': {'role_id': 1357959629359026267, 'prefix': '{3RD}', 'emoji': '🔵'},
    '4th': {'role_id': 1251102603174215750, 'prefix': '{4TH}', 'emoji': '🔴'},
    'mp': {'role_id': 1320153442244886598, 'prefix': '{MP}', 'emoji': '🟡'},
    '1as': {'role_id': 1339571735028174919, 'prefix': '{1AS}', 'emoji': '🟢'},
    '1st': {'role_id': 1387191982866038919, 'prefix': '{1ST}', 'emoji': '🟠'},
    '6th': {'role_id': 1234503490886176849, 'prefix': '{6TH}', 'emoji': '🟣'}
}

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Authorization check
def is_authorized():
    async def predicate(ctx):
        has_permission = bool(AUTHORIZED_ROLES.intersection({r.id for r in ctx.author.roles}))
        if not has_permission:
            await ctx.send("❌ **Access Denied**: You don't have permission to use this command.")
            logger.warning(f"Unauthorized access attempt by {ctx.author}")
        return has_permission
    return commands.check(predicate)

# Main enlistment view
class EnlistmentView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.member = None
        self.regiment = None
        self.roblox_username = None

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command user can interact with this.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Select Member", emoji="👤", style=discord.ButtonStyle.primary)
    async def select_member(self, interaction, button):
        modal = MemberModal(self)
        await interaction.response.send_modal(modal)

    async def show_regiments(self, interaction):
        embed = discord.Embed(title="Select Regiment", description=f"Enlisting: {self.member.mention}", color=0x00ff00)
        view = RegimentView(self)
        await interaction.edit_original_response(embed=embed, view=view)

    async def show_roblox_input(self, interaction):
        embed = discord.Embed(title="Enter Roblox Username", 
                            description=f"Member: {self.member.mention}\nRegiment: {self.regiment.upper()}", 
                            color=0xffff00)
        view = RobloxView(self)
        await interaction.edit_original_response(embed=embed, view=view)

    async def show_confirmation(self, interaction):
        regiment_info = REGIMENT_ROLES[self.regiment]
        nickname = f"{regiment_info['prefix']} ({self.roblox_username})"
        embed = discord.Embed(title="Confirm Enlistment", color=0xff9900)
        embed.add_field(name="Member", value=self.member.mention)
        embed.add_field(name="Regiment", value=self.regiment.upper())
        embed.add_field(name="Nickname", value=nickname[:32])
        view = ConfirmView(self)
        await interaction.edit_original_response(embed=embed, view=view)

    async def process_enlistment(self, interaction):
        try:
            regiment_info = REGIMENT_ROLES[self.regiment]
            role = interaction.guild.get_role(regiment_info['role_id'])
            
            # Remove existing regiment roles
            for r in self.member.roles:
                if r.id in [info['role_id'] for info in REGIMENT_ROLES.values()]:
                    await self.member.remove_roles(r)
            
            # Add new role and set nickname
            await self.member.add_roles(role)
            nickname = f"{regiment_info['prefix']} ({self.roblox_username})"
            await self.member.edit(nick=nickname[:32])
            
            embed = discord.Embed(title="🎉 Enlistment Successful!", color=0x00ff00)
            embed.add_field(name="Member", value=self.member.mention)
            embed.add_field(name="Regiment", value=self.regiment.upper())
            embed.add_field(name="Nickname", value=nickname[:32])
            await interaction.edit_original_response(embed=embed, view=None)
            
            logger.info(f"Enlisted {self.member} to {self.regiment.upper()} by {interaction.user}")
            
        except Exception as e:
            embed = discord.Embed(title="❌ Error", description="Enlistment failed", color=0xff0000)
            await interaction.edit_original_response(embed=embed, view=None)
            logger.error(f"Enlistment error: {e}")

class MemberModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title="Select Member")
        self.view = view
        self.member_input = discord.ui.TextInput(label="Member", placeholder="@username or User ID")
        self.add_item(self.member_input)

    async def on_submit(self, interaction):
        member_input = self.member_input.value.strip()
        guild = interaction.guild
        
        # Try different ways to find member
        member = None
        if member_input.startswith('<@'):
            member_id = member_input[2:-1].lstrip('!')
            try:
                member = guild.get_member(int(member_id))
            except ValueError:
                pass
        
        if not member:
            try:
                member = guild.get_member(int(member_input))
            except ValueError:
                member = discord.utils.get(guild.members, name=member_input) or \
                        discord.utils.get(guild.members, display_name=member_input)
        
        if not member or member.bot:
            embed = discord.Embed(title="❌ Error", description="Member not found or invalid", color=0xff0000)
            await interaction.response.edit_message(embed=embed)
            return
        
        self.view.member = member
        await self.view.show_regiments(interaction)

class RegimentView(discord.ui.View):
    def __init__(self, parent_view):
        super().__init__(timeout=300)
        self.parent_view = parent_view
        
        for name, info in REGIMENT_ROLES.items():
            button = discord.ui.Button(
                label=f"{name.upper()} {info['prefix']}",
                emoji=info['emoji'],
                custom_id=name
            )
            button.callback = self.make_callback(name)
            self.add_item(button)

    def make_callback(self, regiment):
        async def callback(interaction):
            self.parent_view.regiment = regiment
            await self.parent_view.show_roblox_input(interaction)
        return callback

    async def interaction_check(self, interaction):
        return await self.parent_view.interaction_check(interaction)

class RobloxView(discord.ui.View):
    def __init__(self, parent_view):
        super().__init__(timeout=300)
        self.parent_view = parent_view

    @discord.ui.button(label="Enter Roblox Username", emoji="🎮", style=discord.ButtonStyle.primary)
    async def enter_roblox(self, interaction, button):
        modal = RobloxModal(self.parent_view)
        await interaction.response.send_modal(modal)

    async def interaction_check(self, interaction):
        return await self.parent_view.interaction_check(interaction)

class RobloxModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title="Enter Roblox Username")
        self.view = view
        self.roblox_input = discord.ui.TextInput(label="Roblox Username", max_length=20)
        self.add_item(self.roblox_input)

    async def on_submit(self, interaction):
        username = self.roblox_input.value.strip()
        if not username or len(username) < 3:
            embed = discord.Embed(title="❌ Error", description="Invalid username", color=0xff0000)
            await interaction.response.edit_message(embed=embed)
            return
        
        self.view.roblox_username = username
        await self.view.show_confirmation(interaction)

class ConfirmView(discord.ui.View):
    def __init__(self, parent_view):
        super().__init__(timeout=300)
        self.parent_view = parent_view

    @discord.ui.button(label="Confirm", emoji="✅", style=discord.ButtonStyle.success)
    async def confirm(self, interaction, button):
        await self.parent_view.process_enlistment(interaction)

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, button):
        embed = discord.Embed(title="❌ Cancelled", color=0xff0000)
        await interaction.response.edit_message(embed=embed, view=None)

    async def interaction_check(self, interaction):
        return await self.parent_view.interaction_check(interaction)

# Commands
@bot.command(name='enlist')
@is_authorized()
async def enlist(ctx):
    embed = discord.Embed(title="🎖️ Regiment Enlistment", description="Click to select a member", color=0x0099ff)
    view = EnlistmentView(ctx.author.id)
    await ctx.send(embed=embed, view=view)

@bot.command(name='regiments')
@is_authorized()
async def regiments(ctx):
    embed = discord.Embed(title="Available Regiments", color=0x0099ff)
    for name, info in REGIMENT_ROLES.items():
        role = ctx.guild.get_role(info['role_id'])
        embed.add_field(name=f"{info['emoji']} {name.upper()}", 
                       value=f"{info['prefix']}\n{role.mention if role else 'Role not found'}")
    await ctx.send(embed=embed)

@bot.event
async def on_ready():
    logger.info(f'{bot.user} connected to Discord!')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        return
    logger.error(f"Command error: {error}")
    await ctx.send("❌ An error occurred.")

# Run bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN not found!")
        exit(1)
    bot.run(token)
