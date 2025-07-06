import discord
from discord.ext import commands
import os
import logging
from datetime import datetime
import asyncio

# Configure logging for security monitoring
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_security.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Security: Authorized role IDs (users with these roles can use commands)
AUTHORIZED_ROLES = {
    1255061914732597268,
    1382604947924979793,
    1279450222287655023,
    1134711656811855942
}

# Regiment role IDs and their corresponding prefixes
REGIMENT_ROLES = {
    '3rd': {'role_id': 1357959629359026267, 'prefix': '{3RD}', 'emoji': '🔵'},
    '4th': {'role_id': 1251102603174215750, 'prefix': '{4TH}', 'emoji': '🔴'},
    'mp': {'role_id': 1320153442244886598, 'prefix': '{MP}', 'emoji': '🟡'},
    '1as': {'role_id': 1339571735028174919, 'prefix': '{1AS}', 'emoji': '🟢'},
    '1st': {'role_id': 1387191982866038919, 'prefix': '{1ST}', 'emoji': '🟠'},
    '6th': {'role_id': 1234503490886176849, 'prefix': '{6TH}', 'emoji': '🟣'}
}

# Bot setup with strict intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Store ongoing enlistment processes
enlistment_sessions = {}

def is_authorized():
    """Security check: Verify user has authorized roles"""
    async def predicate(ctx):
        user_role_ids = {role.id for role in ctx.author.roles}
        has_permission = bool(AUTHORIZED_ROLES.intersection(user_role_ids))
        
        # Log all command attempts for security monitoring
        logger.info(f"Command attempt by {ctx.author} (ID: {ctx.author.id}) - "
                   f"Authorized: {has_permission} - Command: {ctx.command}")
        
        if not has_permission:
            logger.warning(f"UNAUTHORIZED ACCESS ATTEMPT by {ctx.author} (ID: {ctx.author.id}) "
                          f"in guild {ctx.guild.name} (ID: {ctx.guild.id})")
            await ctx.send("❌ **Access Denied**: You don't have permission to use this command.")
        
        return has_permission
    
    return commands.check(predicate)

class MemberSelectView(discord.ui.View):
    def __init__(self, author_id, timeout=300):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.selected_member = None
        self.message = None
    
    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command user can interact with this.", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self):
        if self.message:
            embed = discord.Embed(
                title="⏰ **Session Timeout**",
                description="The enlistment session has timed out.",
                color=discord.Color.red()
            )
            await self.message.edit(embed=embed, view=None)
        
        # Clean up session data
        if self.author_id in enlistment_sessions:
            del enlistment_sessions[self.author_id]

class MemberSelectModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title="Select Member to Enlist")
        self.view = view
        
        self.member_input = discord.ui.TextInput(
            label="Member",
            placeholder="@username or User ID",
            max_length=100,
            required=True
        )
        self.add_item(self.member_input)
    
    async def on_submit(self, interaction):
        member_input = self.member_input.value.strip()
        
        # Try to find the member
        member = None
        guild = interaction.guild
        
        # Check if it's a mention
        if member_input.startswith('<@') and member_input.endswith('>'):
            member_id = member_input[2:-1]
            if member_id.startswith('!'):
                member_id = member_id[1:]
            try:
                member = guild.get_member(int(member_id))
            except ValueError:
                pass
        
        # Check if it's a user ID
        if not member:
            try:
                member = guild.get_member(int(member_input))
            except ValueError:
                pass
        
        # Check if it's a username
        if not member:
            member = discord.utils.get(guild.members, name=member_input)
        
        # Check if it's a display name
        if not member:
            member = discord.utils.get(guild.members, display_name=member_input)
        
        if not member:
            embed = discord.Embed(
                title="❌ **Member Not Found**",
                description="Could not find the specified member. Please try again.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=self.view)
            return
        
        # Security checks
        if member.bot:
            embed = discord.Embed(
                title="❌ **Invalid Target**",
                description="Cannot enlist bots.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=self.view)
            return
        
        if member.id == interaction.user.id:
            embed = discord.Embed(
                title="❌ **Security Error**",
                description="You cannot enlist yourself.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=self.view)
            return
        
        # Store the selected member
        self.view.selected_member = member
        enlistment_sessions[interaction.user.id] = {
            'member': member,
            'step': 'regiment_selection'
        }
        
        # Move to regiment selection
        await self.show_regiment_selection(interaction)
    
    async def show_regiment_selection(self, interaction):
        embed = discord.Embed(
            title="👤 **Member Selected**",
            description=f"**Selected Member:** {self.view.selected_member.mention}\n\n"
                       f"**Step 2/4:** Select the regiment to enlist them in:",
            color=discord.Color.blue()
        )
        
        # Check if member has existing regiment roles
        current_regiments = []
        for role in self.view.selected_member.roles:
            for reg_name, reg_info in REGIMENT_ROLES.items():
                if role.id == reg_info['role_id']:
                    current_regiments.append(reg_name.upper())
        
        if current_regiments:
            embed.add_field(
                name="⚠️ **Current Regiments**",
                value=f"This member is already in: {', '.join(current_regiments)}",
                inline=False
            )
        
        view = RegimentSelectView(interaction.user.id, self.view.selected_member)
        await interaction.response.edit_message(embed=embed, view=view)

class RegimentSelectView(discord.ui.View):
    def __init__(self, author_id, member, timeout=300):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.member = member
        self.message = None
        
        # Create buttons for each regiment
        for reg_name, reg_info in REGIMENT_ROLES.items():
            button = discord.ui.Button(
                label=f"{reg_name.upper()} {reg_info['prefix']}",
                emoji=reg_info['emoji'],
                style=discord.ButtonStyle.primary,
                custom_id=f"regiment_{reg_name}"
            )
            button.callback = self.create_regiment_callback(reg_name)
            self.add_item(button)
        
        # Add cancel button
        cancel_button = discord.ui.Button(
            label="Cancel",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            custom_id="cancel"
        )
        cancel_button.callback = self.cancel_callback
        self.add_item(cancel_button)
    
    def create_regiment_callback(self, regiment_name):
        async def callback(interaction):
            await self.regiment_selected(interaction, regiment_name)
        return callback
    
    async def regiment_selected(self, interaction, regiment_name):
        # Update session data
        enlistment_sessions[interaction.user.id]['regiment'] = regiment_name
        enlistment_sessions[interaction.user.id]['step'] = 'roblox_username'
        
        # Show Roblox username input
        await self.show_roblox_input(interaction, regiment_name)
    
    async def show_roblox_input(self, interaction, regiment_name):
        embed = discord.Embed(
            title="🎮 **Roblox Username Required**",
            description=f"**Step 3/4:** Enter the Roblox username for {self.member.mention}",
            color=discord.Color.green()
        )
        
        embed.add_field(name="👤 **Member**", value=self.member.mention, inline=True)
        embed.add_field(name="🎖️ **Regiment**", value=regiment_name.upper(), inline=True)
        embed.add_field(name="📝 **Format**", value=f"`{REGIMENT_ROLES[regiment_name]['prefix']} (RobloxUsername)`", inline=False)
        
        view = RobloxUsernameView(interaction.user.id, self.member, regiment_name)
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def show_confirmation(self, interaction, regiment_name):
        regiment_info = REGIMENT_ROLES[regiment_name]
        
        embed = discord.Embed(
            title="✅ **Confirm Enlistment**",
            description=f"**Step 3/3:** Please confirm the enlistment details:",
            color=discord.Color.orange()
        )
        
        embed.add_field(name="👤 **Member**", value=self.member.mention, inline=True)
        embed.add_field(name="🎖️ **Regiment**", value=f"{regiment_name.upper()}", inline=True)
        embed.add_field(name="🏷️ **New Prefix**", value=regiment_info['prefix'], inline=True)
        
        # Check for existing regiment roles
        current_regiments = []
        for role in self.member.roles:
            for reg_name, reg_info in REGIMENT_ROLES.items():
                if role.id == reg_info['role_id']:
                    current_regiments.append(reg_name.upper())
        
        if current_regiments:
            embed.add_field(
                name="⚠️ **Note**",
                value=f"This will remove existing regiment roles: {', '.join(current_regiments)}",
                inline=False
            )
        
        embed.set_footer(text="Click 'Confirm' to proceed or 'Cancel' to abort.")
        
        view = ConfirmationView(interaction.user.id, self.member, regiment_name)
        await interaction.response.edit_message(embed=embed, view=view)
    
    async def cancel_callback(self, interaction):
        embed = discord.Embed(
            title="❌ **Cancelled**",
            description="Enlistment process cancelled.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Clean up session
        if interaction.user.id in enlistment_sessions:
            del enlistment_sessions[interaction.user.id]
    
    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command user can interact with this.", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self):
        if self.message:
            embed = discord.Embed(
                title="⏰ **Session Timeout**",
                description="The enlistment session has timed out.",
                color=discord.Color.red()
            )
            await self.message.edit(embed=embed, view=None)
        
        # Clean up session data
        if self.author_id in enlistment_sessions:
            del enlistment_sessions[self.author_id]

class RobloxUsernameView(discord.ui.View):
    def __init__(self, author_id, member, regiment_name, timeout=300):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.member = member
        self.regiment_name = regiment_name
        self.message = None
    
    @discord.ui.button(label="Enter Roblox Username", emoji="🎮", style=discord.ButtonStyle.primary)
    async def enter_roblox_button(self, interaction, button):
        modal = RobloxUsernameModal(self)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction, button):
        embed = discord.Embed(
            title="❌ **Cancelled**",
            description="Enlistment process cancelled.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Clean up session
        if interaction.user.id in enlistment_sessions:
            del enlistment_sessions[interaction.user.id]
    
    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command user can interact with this.", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self):
        if self.message:
            embed = discord.Embed(
                title="⏰ **Session Timeout**",
                description="The enlistment session has timed out.",
                color=discord.Color.red()
            )
            await self.message.edit(embed=embed, view=None)
        
        # Clean up session data
        if self.author_id in enlistment_sessions:
            del enlistment_sessions[self.author_id]

class RobloxUsernameModal(discord.ui.Modal):
    def __init__(self, view):
        super().__init__(title="Enter Roblox Username")
        self.view = view
        
        self.roblox_input = discord.ui.TextInput(
            label="Roblox Username",
            placeholder="Enter the exact Roblox username",
            max_length=50,
            required=True
        )
        self.add_item(self.roblox_input)
    
    async def on_submit(self, interaction):
        roblox_username = self.roblox_input.value.strip()
        
        # Basic validation
        if not roblox_username:
            embed = discord.Embed(
                title="❌ **Invalid Username**",
                description="Please enter a valid Roblox username.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=self.view)
            return
        
        # Check for invalid characters (basic validation)
        if len(roblox_username) < 3 or len(roblox_username) > 20:
            embed = discord.Embed(
                title="❌ **Invalid Username**",
                description="Roblox usernames must be between 3-20 characters.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=self.view)
            return
        
        # Store the Roblox username
        enlistment_sessions[interaction.user.id]['roblox_username'] = roblox_username
        enlistment_sessions[interaction.user.id]['step'] = 'confirmation'
        
        # Show confirmation
        await self.show_confirmation(interaction, roblox_username)
    
    async def show_confirmation(self, interaction, roblox_username):
        regiment_info = REGIMENT_ROLES[self.view.regiment_name]
        new_nickname = f"{regiment_info['prefix']} ({roblox_username})"
        
        embed = discord.Embed(
            title="✅ **Confirm Enlistment**",
            description=f"**Step 4/4:** Please confirm the enlistment details:",
            color=discord.Color.orange()
        )
        
        embed.add_field(name="👤 **Member**", value=self.view.member.mention, inline=True)
        embed.add_field(name="🎖️ **Regiment**", value=f"{self.view.regiment_name.upper()}", inline=True)
        embed.add_field(name="🎮 **Roblox Username**", value=roblox_username, inline=True)
        embed.add_field(name="🏷️ **New Nickname**", value=new_nickname, inline=False)
        
        # Check for existing regiment roles
        current_regiments = []
        for role in self.view.member.roles:
            for reg_name, reg_info in REGIMENT_ROLES.items():
                if role.id == reg_info['role_id']:
                    current_regiments.append(reg_name.upper())
        
        if current_regiments:
            embed.add_field(
                name="⚠️ **Note**",
                value=f"This will remove existing regiment roles: {', '.join(current_regiments)}",
                inline=False
            )
        
        # Check nickname length
        if len(new_nickname) > 32:
            embed.add_field(
                name="⚠️ **Warning**",
                value=f"Nickname will be truncated to 32 characters: `{new_nickname[:32]}`",
                inline=False
            )
        
        embed.set_footer(text="Click 'Confirm' to proceed or 'Cancel' to abort.")
        
        view = ConfirmationView(interaction.user.id, self.view.member, self.view.regiment_name, roblox_username)
        await interaction.response.edit_message(embed=embed, view=view)
    def __init__(self, author_id, member, regiment_name, timeout=300):
        super().__init__(timeout=timeout)
        self.author_id = author_id
        self.member = member
        self.regiment_name = regiment_name
        self.message = None
    
    @discord.ui.button(label="Confirm Enlistment", emoji="✅", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction, button):
        await self.process_enlistment(interaction)
    
    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction, button):
        embed = discord.Embed(
            title="❌ **Cancelled**",
            description="Enlistment process cancelled.",
            color=discord.Color.red()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Clean up session
        if interaction.user.id in enlistment_sessions:
            del enlistment_sessions[interaction.user.id]
    
    async def process_enlistment(self, interaction):
        try:
            # Security checks
            if not interaction.guild.me.guild_permissions.manage_roles:
                embed = discord.Embed(
                    title="❌ **Error**",
                    description="Bot lacks permission to manage roles.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                return
            
            if not interaction.guild.me.guild_permissions.manage_nicknames:
                embed = discord.Embed(
                    title="❌ **Error**",
                    description="Bot lacks permission to manage nicknames.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                return
            
            # Get regiment info
            regiment_info = REGIMENT_ROLES[self.regiment_name]
            regiment_role = interaction.guild.get_role(regiment_info['role_id'])
            
            if not regiment_role:
                embed = discord.Embed(
                    title="❌ **Error**",
                    description="Regiment role not found. Please contact an administrator.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                return
            
            # Check role hierarchy
            if regiment_role >= interaction.guild.me.top_role:
                embed = discord.Embed(
                    title="❌ **Error**",
                    description="Cannot assign role due to role hierarchy.",
                    color=discord.Color.red()
                )
                await interaction.response.edit_message(embed=embed, view=None)
                return
            
            # Show processing message
            embed = discord.Embed(
                title="⏳ **Processing Enlistment**",
                description="Please wait while the enlistment is being processed...",
                color=discord.Color.yellow()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            
            # Remove existing regiment roles
            roles_removed = []
            for role in self.member.roles:
                for reg_name, reg_info in REGIMENT_ROLES.items():
                    if role.id == reg_info['role_id']:
                        await self.member.remove_roles(role, reason=f"Regiment transfer by {interaction.user}")
                        roles_removed.append(reg_name.upper())
            
            # Add new regiment role
            await self.member.add_roles(regiment_role, reason=f"Enlisted by {interaction.user}")
            
            # Update nickname
            new_prefix = regiment_info['prefix']
            new_nickname = f"{new_prefix} ({self.roblox_username})"
            
            # Discord nickname length limit
            if len(new_nickname) > 32:
                new_nickname = new_nickname[:32]
            
            await self.member.edit(nick=new_nickname, reason=f"Enlisted to {self.regiment_name.upper()} by {interaction.user}")
            
            # Success message
            embed = discord.Embed(
                title="🎉 **Enlistment Successful!**",
                description=f"{self.member.mention} has been successfully enlisted!",
                color=discord.Color.green(),
                timestamp=datetime.utcnow()
            )
            
            embed.add_field(name="🎖️ **Regiment**", value=self.regiment_name.upper(), inline=True)
            embed.add_field(name="📝 **Role Assigned**", value=regiment_role.mention, inline=True)
            embed.add_field(name="🎮 **Roblox Username**", value=self.roblox_username, inline=True)
            embed.add_field(name="🏷️ **New Nickname**", value=new_nickname, inline=True)
            embed.add_field(name="👤 **Enlisted By**", value=interaction.user.mention, inline=True)
            
            if roles_removed:
                embed.add_field(name="🔄 **Roles Removed**", value=", ".join(roles_removed), inline=False)
            
            embed.set_thumbnail(url=self.member.display_avatar.url)
            embed.set_footer(text=f"Enlistment completed at")
            
            await interaction.edit_original_response(embed=embed)
            
            # Security logging
            logger.info(f"SUCCESSFUL ENLISTMENT: {self.member} (ID: {self.member.id}) enlisted to {self.regiment_name.upper()} "
                       f"by {interaction.user} (ID: {interaction.user.id}) in guild {interaction.guild.name}")
            
        except discord.Forbidden:
            embed = discord.Embed(
                title="❌ **Error**",
                description="Insufficient permissions to modify this member.",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed)
            logger.error(f"Forbidden error when enlisting {self.member} by {interaction.user}")
            
        except discord.HTTPException as e:
            embed = discord.Embed(
                title="❌ **Error**",
                description="Failed to complete enlistment due to Discord API error.",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed)
            logger.error(f"HTTP error when enlisting {self.member} by {interaction.user}: {e}")
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ **Error**",
                description="An unexpected error occurred during enlistment.",
                color=discord.Color.red()
            )
            await interaction.edit_original_response(embed=embed)
            logger.error(f"Unexpected error when enlisting {self.member} by {interaction.user}: {e}")
        
        finally:
            # Clean up session
            if interaction.user.id in enlistment_sessions:
                del enlistment_sessions[interaction.user.id]
    
    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("❌ Only the command user can interact with this.", ephemeral=True)
            return False
        return True
    
    async def on_timeout(self):
        if self.message:
            embed = discord.Embed(
                title="⏰ **Session Timeout**",
                description="The enlistment session has timed out.",
                color=discord.Color.red()
            )
            await self.message.edit(embed=embed, view=None)
        
        # Clean up session data
        if self.author_id in enlistment_sessions:
            del enlistment_sessions[self.author_id]

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    logger.info(f'Bot is in {len(bot.guilds)} guilds')
    
    # Security: Log all guilds the bot is in
    for guild in bot.guilds:
        logger.info(f'Guild: {guild.name} (ID: {guild.id})')

@bot.command(name='enlist')
@is_authorized()
async def enlist_member(ctx):
    """
    Start the interactive enlistment process
    """
    
    # Security: Additional validation
    if not ctx.guild:
        logger.warning(f"Command attempted outside of guild by {ctx.author}")
        await ctx.send("❌ This command can only be used in a server.")
        return
    
    # Check if user already has an active session
    if ctx.author.id in enlistment_sessions:
        await ctx.send("❌ You already have an active enlistment session. Please complete or cancel it first.")
        return
    
    # Start the enlistment process
    embed = discord.Embed(
        title="🎖️ **Regiment Enlistment System**",
        description="**Step 1/4:** Select the member you want to enlist.\n\n"
                   "Click the button below to specify the member.",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📋 **Process Overview**",
        value="1️⃣ Select Member\n2️⃣ Choose Regiment\n3️⃣ Enter Roblox Username\n4️⃣ Confirm Details",
        inline=True
    )
    
    embed.add_field(
        name="📋 **Available Regiments**",
        value="\n".join([f"{info['emoji']} **{name.upper()}** - {info['prefix']}" 
                        for name, info in REGIMENT_ROLES.items()]),
        inline=False
    )
    
    embed.add_field(
        name="🏷️ **Nickname Format**",
        value="`{REGIMENT} (RobloxUsername)`\nExample: `{3RD} (PlayerName123)`",
        inline=False
    )
    
    embed.set_footer(text="This session will timeout after 5 minutes.")
    
    view = MemberSelectView(ctx.author.id)
    message = await ctx.send(embed=embed, view=view)
    view.message = message
    
    # Initialize session
    enlistment_sessions[ctx.author.id] = {
        'step': 'member_selection',
        'message': message
    }

class MemberSelectView(discord.ui.View):
    def __init__(self):
    super().__init__()


@discord.ui.select(placeholder="Choose a member to enlist...")
  async def member_select(self, interaction: discord.Interaction, self: discord.ui.Select):
      selected_value = select.values[0]
      await
ineraction.response.send_messags(f"You selected: {selected_value}")

# Add a button to the MemberSelectView to open the modal
@discord.ui.button(label="Select Member", emoji="👤", style=discord.ButtonStyle.primary)
async def select_member_button(self, interaction, button):
    modal = MemberSelectModal(self)
    await interaction.response.send_modal(modal)

# Add the button to the MemberSelectView
MemberSelectView.select_member_button = select_member_button

@bot.command(name='regiments')
@is_authorized()
async def list_regiments(ctx):
    """Display all available regiments with their information"""
    
    embed = discord.Embed(
        title="📋 **Available Regiments**",
        description="Here are all the available regiments for enlistment:",
        color=discord.Color.blue()
    )
    
    for reg_name, reg_info in REGIMENT_ROLES.items():
        role = ctx.guild.get_role(reg_info['role_id'])
        role_mention = role.mention if role else "⚠️ Role not found"
        
        embed.add_field(
            name=f"{reg_info['emoji']} **{reg_name.upper()}**",
            value=f"**Prefix:** {reg_info['prefix']}\n**Role:** {role_mention}",
            inline=True
        )
    
    embed.set_footer(text="Use !enlist to start the enlistment process")
    await ctx.send(embed=embed)

@bot.command(name='status')
@is_authorized()
async def enlistment_status(ctx):
    """Check active enlistment sessions"""
    
    active_sessions = len(enlistment_sessions)
    
    embed = discord.Embed(
        title="📊 **Enlistment System Status**",
        color=discord.Color.green()
    )
    
    embed.add_field(name="🔄 **Active Sessions**", value=str(active_sessions), inline=True)
    embed.add_field(name="🎖️ **Available Regiments**", value=str(len(REGIMENT_ROLES)), inline=True)
    embed.add_field(name="🤖 **Bot Status**", value="✅ Online", inline=True)
    
    if active_sessions > 0:
        session_info = []
        for user_id, session in enlistment_sessions.items():
            user = ctx.guild.get_member(user_id)
            user_name = user.display_name if user else f"Unknown User ({user_id})"
            session_info.append(f"• {user_name} - {session['step']}")
        
        embed.add_field(
            name="🔄 **Active Sessions Details**",
            value="\n".join(session_info[:10]),  # Limit to 10 entries
            inline=False
        )
    
    await ctx.send(embed=embed)

@bot.command(name='cancel')
@is_authorized()
async def cancel_enlistment(ctx):
    """Cancel your active enlistment session"""
    
    if ctx.author.id not in enlistment_sessions:
        await ctx.send("❌ You don't have an active enlistment session.")
        return
    
    # Clean up session
    del enlistment_sessions[ctx.author.id]
    
    embed = discord.Embed(
        title="❌ **Session Cancelled**",
        description="Your enlistment session has been cancelled.",
        color=discord.Color.red()
    )
    
    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    """Enhanced error handling with security logging"""
    if isinstance(error, commands.CheckFailure):
        # Already handled in the check function
        return
    elif isinstance(error, commands.MemberNotFound):
        await ctx.send("❌ **Error**: Member not found. Please use the interactive enlistment system.")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("❌ **Error**: Invalid argument provided.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ **Error**: Use `!enlist` to start the interactive enlistment process.")
    else:
        logger.error(f"Unexpected error in command {ctx.command}: {error}")
        await ctx.send("❌ **Error**: An unexpected error occurred. Please contact an administrator.")

# Additional security: Monitor for suspicious activity
@bot.event
async def on_member_update(before, after):
    """Monitor member updates for security purposes"""
    if before.roles != after.roles:
        added_roles = set(after.roles) - set(before.roles)
        removed_roles = set(before.roles) - set(after.roles)
        
        for role in added_roles:
            if role.id in [info['role_id'] for info in REGIMENT_ROLES.values()]:
                logger.info(f"Regiment role {role.name} added to {after} (ID: {after.id})")
        
        for role in removed_roles:
            if role.id in [info['role_id'] for info in REGIMENT_ROLES.values()]:
                logger.info(f"Regiment role {role.name} removed from {after} (ID: {after.id})")

# Run the bot
if __name__ == "__main__":
    discord_token = os.getenv('DISCORD_TOKEN')
    
    if not discord_token:
        logger.error("DISCORD_TOKEN environment variable not found!")
        print("Error: Please set the DISCORD_TOKEN environment variable.")
        exit(1)
    
    try:
        bot.run(discord_token)
    except discord.LoginFailure:
        logger.error("Invalid Discord token provided!")
        print("Error: Invalid Discord token. Please check your DISCORD_TOKEN environment variable.")
    except Exception as e:
        logger.error(f"Fatal error starting bot: {e}")
        print(f"Fatal error: {e}")
       
