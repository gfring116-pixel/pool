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

# Store active enlistment sessions
active_sessions = {}

# Authorization check
def is_authorized():
    async def predicate(ctx):
        has_permission = bool(AUTHORIZED_ROLES.intersection({r.id for r in ctx.author.roles}))
        if not has_permission:
            await ctx.send("❌ **Access Denied**: You don't have permission to use this command.")
            logger.warning(f"Unauthorized access attempt by {ctx.author}")
        return has_permission
    return commands.check(predicate)

# Regiment selection view
class RegimentView(discord.ui.View):
    def __init__(self, author_id, member):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.member = member
        
        for name, info in REGIMENT_ROLES.items():
            button = discord.ui.Button(
                label=f"{name.upper()} {info['prefix']}",
                emoji=info['emoji'],
                custom_id=name
            )
            button.callback = self.make_callback(name)
            self.add_item(button)
        
        # Add cancel button
        cancel_button = discord.ui.Button(label="Cancel", emoji="❌", style=discord.ButtonStyle.danger)
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)

    def make_callback(self, regiment):
        async def callback(interaction):
            active_sessions[self.author_id] = {
                'step': 'roblox_username',
                'member': self.member,
                'regiment': regiment,
                'channel': interaction.channel
            }
            
            embed = discord.Embed(
                title="🎮 **Enter Roblox Username**",
                description=f"**Member:** {self.member.mention}\n"
                           f"**Regiment:** {regiment.upper()}\n\n"
                           f"Please **type the Roblox username** in this channel:",
                color=0xffff00
            )
            embed.add_field(name="📝 Format Example", value=f"`{REGIMENT_ROLES[regiment]['prefix']} (YourUsername)`")
            embed.set_footer(text="Type 'cancel' to cancel this process")
            
            await interaction.response.edit_message(embed=embed, view=None)
        return callback

    async def cancel_callback(self, interaction):
        if self.author_id in active_sessions:
            del active_sessions[self.author_id]
        embed = discord.Embed(title="❌ **Cancelled**", description="Enlistment process cancelled.", color=0xff0000)
        await interaction.response.edit_message(embed=embed, view=None)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command user can interact with this.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.author_id in active_sessions:
            del active_sessions[self.author_id]

# Confirmation view
class ConfirmView(discord.ui.View):
    def __init__(self, author_id, member, regiment, roblox_username):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.member = member
        self.regiment = regiment
        self.roblox_username = roblox_username

    @discord.ui.button(label="Confirm Enlistment", emoji="✅", style=discord.ButtonStyle.success)
    async def confirm(self, interaction, button):
        await self.process_enlistment(interaction)

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, button):
        if self.author_id in active_sessions:
            del active_sessions[self.author_id]
        embed = discord.Embed(title="❌ **Cancelled**", description="Enlistment process cancelled.", color=0xff0000)
        await interaction.response.edit_message(embed=embed, view=None)

    async def process_enlistment(self, interaction):
        try:
            regiment_info = REGIMENT_ROLES[self.regiment]
            role = interaction.guild.get_role(regiment_info['role_id'])
            
            if not role:
                embed = discord.Embed(title="❌ **Error**", description="Regiment role not found.", color=0xff0000)
                await interaction.response.edit_message(embed=embed, view=None)
                return
            
            # Remove existing regiment roles
            roles_removed = []
            for r in self.member.roles:
                if r.id in [info['role_id'] for info in REGIMENT_ROLES.values()]:
                    await self.member.remove_roles(r)
                    roles_removed.append(r.name)
            
            # Add new role and set nickname
            await self.member.add_roles(role)
            nickname = f"{regiment_info['prefix']} ({self.roblox_username})"
            if len(nickname) > 32:
                nickname = nickname[:32]
            await self.member.edit(nick=nickname)
            
            embed = discord.Embed(title="🎉 **Enlistment Successful!**", color=0x00ff00)
            embed.add_field(name="👤 **Member**", value=self.member.mention, inline=True)
            embed.add_field(name="🎖️ **Regiment**", value=self.regiment.upper(), inline=True)
            embed.add_field(name="🎮 **Roblox Username**", value=self.roblox_username, inline=True)
            embed.add_field(name="🏷️ **New Nickname**", value=nickname, inline=True)
            embed.add_field(name="👤 **Enlisted By**", value=interaction.user.mention, inline=True)
            
            if roles_removed:
                embed.add_field(name="🔄 **Roles Removed**", value=", ".join(roles_removed), inline=False)
            
            embed.set_thumbnail(url=self.member.display_avatar.url)
            embed.timestamp = datetime.utcnow()
            
            await interaction.response.edit_message(embed=embed, view=None)
            
            if self.author_id in active_sessions:
                del active_sessions[self.author_id]
            
            logger.info(f"Enlisted {self.member} to {self.regiment.upper()} by {interaction.user}")
            
        except discord.Forbidden:
            embed = discord.Embed(title="❌ **Error**", description="Insufficient permissions to modify this member.", color=0xff0000)
            await interaction.response.edit_message(embed=embed, view=None)
            logger.error(f"Forbidden error when enlisting {self.member} by {interaction.user}")
        except Exception as e:
            embed = discord.Embed(title="❌ **Error**", description="An unexpected error occurred during enlistment.", color=0xff0000)
            await interaction.response.edit_message(embed=embed, view=None)
            logger.error(f"Enlistment error: {e}")

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command user can interact with this.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if self.author_id in active_sessions:
            del active_sessions[self.author_id]

# Commands
@bot.command(name='enlist')
@is_authorized()
async def enlist(ctx, *, member_input=None):
    if ctx.author.id in active_sessions:
        await ctx.send("❌ You already have an active enlistment session. Type `!cancel` to cancel it first.")
        return
    
    if not member_input:
        embed = discord.Embed(
            title="🎖️ **Regiment Enlistment**",
            description="Please **mention or type the member** you want to enlist.\n\n"
                       "**Examples:**\n"
                       "• `!enlist @JohnDoe`\n"
                       "• `!enlist JohnDoe`\n"
                       "• `!enlist 123456789012345678` (User ID)",
            color=0x0099ff
        )
        embed.add_field(
            name="📋 **Available Regiments**",
            value="\n".join([f"{info['emoji']} **{name.upper()}** - {info['prefix']}" 
                           for name, info in REGIMENT_ROLES.items()]),
            inline=False
        )
        await ctx.send(embed=embed)
        return
    
    # Try to find the member
    member = None
    guild = ctx.guild
    
    # Try mention format
    if member_input.startswith('<@') and member_input.endswith('>'):
        member_id = member_input[2:-1].lstrip('!')
        try:
            member = guild.get_member(int(member_id))
        except ValueError:
            pass
    
    # Try user ID
    if not member and member_input.isdigit():
        try:
            member = guild.get_member(int(member_input))
        except ValueError:
            pass
    
    # Try username or display name
    if not member:
        member = discord.utils.get(guild.members, name=member_input) or \
                discord.utils.get(guild.members, display_name=member_input)
    
    if not member:
        embed = discord.Embed(
            title="❌ **Member Not Found**",
            description=f"Could not find member: `{member_input}`\n\n"
                       "**Try:**\n"
                       "• Mentioning them: `@username`\n"
                       "• Their exact username\n"
                       "• Their user ID",
            color=0xff0000
        )
        await ctx.send(embed=embed)
        return
    
    if member.bot:
        await ctx.send("❌ **Error**: Cannot enlist bots.")
        return
    
    if member.id == ctx.author.id:
        await ctx.send("❌ **Error**: You cannot enlist yourself.")
        return
    
    # Show regiment selection
    embed = discord.Embed(
        title="🎖️ **Select Regiment**",
        description=f"**Member to enlist:** {member.mention}\n\n"
                   f"**Step 2/3:** Choose the regiment:",
        color=0x00ff00
    )
    
    # Show current regiments if any
    current_regiments = []
    for role in member.roles:
        for reg_name, reg_info in REGIMENT_ROLES.items():
            if role.id == reg_info['role_id']:
                current_regiments.append(reg_name.upper())
    
    if current_regiments:
        embed.add_field(
            name="⚠️ **Current Regiments**",
            value=f"This member is already in: {', '.join(current_regiments)}",
            inline=False
        )
    
    view = RegimentView(ctx.author.id, member)
    await ctx.send(embed=embed, view=view)

@bot.command(name='regiments')
@is_authorized()
async def regiments(ctx):
    embed = discord.Embed(title="📋 **Available Regiments**", color=0x0099ff)
    for name, info in REGIMENT_ROLES.items():
        role = ctx.guild.get_role(info['role_id'])
        embed.add_field(
            name=f"{info['emoji']} **{name.upper()}**",
            value=f"**Prefix:** {info['prefix']}\n**Role:** {role.mention if role else '⚠️ Role not found'}",
            inline=True
        )
    embed.set_footer(text="Use !enlist @member to start enlistment")
    await ctx.send(embed=embed)

@bot.command(name='cancel')
@is_authorized()
async def cancel_enlistment(ctx):
    if ctx.author.id not in active_sessions:
        await ctx.send("❌ You don't have an active enlistment session.")
        return
    
    del active_sessions[ctx.author.id]
    embed = discord.Embed(title="❌ **Session Cancelled**", description="Your enlistment session has been cancelled.", color=0xff0000)
    await ctx.send(embed=embed)

# Message listener for active sessions
@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Check if user has active session
    if message.author.id in active_sessions:
        session = active_sessions[message.author.id]
        
        # Check if message is in the correct channel
        if message.channel.id != session['channel'].id:
            return
        
        if session['step'] == 'roblox_username':
            # Handle cancel
            if message.content.lower() == 'cancel':
                del active_sessions[message.author.id]
                embed = discord.Embed(title="❌ **Cancelled**", description="Enlistment process cancelled.", color=0xff0000)
                await message.channel.send(embed=embed)
                return
            
            # Validate Roblox username
            roblox_username = message.content.strip()
            if not roblox_username or len(roblox_username) < 3 or len(roblox_username) > 20:
                embed = discord.Embed(
                    title="❌ **Invalid Username**",
                    description="Roblox usernames must be between 3-20 characters.\n\nPlease try again or type `cancel` to cancel:",
                    color=0xff0000
                )
                await message.channel.send(embed=embed)
                return
            
            # Show confirmation
            member = session['member']
            regiment = session['regiment']
            regiment_info = REGIMENT_ROLES[regiment]
            nickname = f"{regiment_info['prefix']} ({roblox_username})"
            
            embed = discord.Embed(
                title="✅ **Confirm Enlistment**",
                description="**Step 3/3:** Please confirm the enlistment details:",
                color=0xff9900
            )
            embed.add_field(name="👤 **Member**", value=member.mention, inline=True)
            embed.add_field(name="🎖️ **Regiment**", value=regiment.upper(), inline=True)
            embed.add_field(name="🎮 **Roblox Username**", value=roblox_username, inline=True)
            embed.add_field(name="🏷️ **New Nickname**", value=nickname[:32], inline=False)
            
            if len(nickname) > 32:
                embed.add_field(name="⚠️ **Note**", value="Nickname will be truncated to 32 characters", inline=False)
            
            view = ConfirmView(message.author.id, member, regiment, roblox_username)
            await message.channel.send(embed=embed, view=view)
            
            # Clean up session - confirmation view will handle it
            del active_sessions[message.author.id]
    
    # Process commands
    await bot.process_commands(message)

@bot.event
async def on_ready():
    logger.info(f'{bot.user} connected to Discord!')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CheckFailure):
        return
    logger.error(f"Command error: {error}")
    await ctx.send("❌ An error occurred. Please try again.")

# Run bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN not found!")
        exit(1)
    bot.run(token)
