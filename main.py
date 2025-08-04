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
    '3rd': {'role_id': 1357959629359026267, 'prefix': '{3RD}', 'emoji': '🚚'},
    '4th': {'role_id': 1251102603174215750, 'prefix': '{4TH}', 'emoji': '🪖'},
    'mp': {'role_id': 1320153442244886598, 'prefix': '{MP}', 'emoji': '🛡️'},
    '1as': {'role_id': 1339571735028174919, 'prefix': '{1AS}', 'emoji': '🛩️'},
    '1st': {'role_id': 1387191982866038919, 'prefix': '{1ST}', 'emoji': '🗡️'},
    '6th': {'role_id': 1234503490886176849, 'prefix': '{6TH}', 'emoji': '⚔️'}
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

# Cheesecake Role Management System
# Add this to your existing bot code

import discord
from discord.ext import commands

# Your specific user ID for cheesecake commands
CHEESECAKE_USER_ID = 728201873366056992

# Store managed roles (you might want to use a database for persistence)
managed_roles = {}

def is_cheesecake_user():
    """Check if user is authorized for cheesecake commands"""
    async def predicate(ctx):
        if ctx.author.id != CHEESECAKE_USER_ID:
            await ctx.send("nah you can't use this")
            return False
        return True
    return commands.check(predicate)

class RoleEditView(discord.ui.View):
    def __init__(self, author_id, role):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.role = role

    @discord.ui.button(label="Edit Name", style=discord.ButtonStyle.primary)
    async def edit_name(self, interaction, button):
        modal = RoleNameModal(self.role)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit Color", style=discord.ButtonStyle.primary)
    async def edit_color(self, interaction, button):
        modal = RoleColorModal(self.role)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit Permissions", style=discord.ButtonStyle.secondary)
    async def edit_permissions(self, interaction, button):
        view = PermissionView(self.author_id, self.role)
        embed = discord.Embed(
            title="edit permissions",
            description=f"role: {self.role.mention}\n\nclick stuff to toggle permissions",
            color=self.role.color
        )
        await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label="Give Role", style=discord.ButtonStyle.success)
    async def assign_role(self, interaction, button):
        modal = AssignRoleModal(self.role)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Take Role", style=discord.ButtonStyle.danger)
    async def remove_role(self, interaction, button):
        modal = RemoveRoleModal(self.role)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Back", style=discord.ButtonStyle.secondary)
    async def back(self, interaction, button):
        embed = discord.Embed(
            title="cheesecake role manager",
            description="what do you wanna do?",
            color=0xffd700
        )
        view = CheesecakeMainView(self.author_id)
        await interaction.response.edit_message(embed=embed, view=view)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("not for you", ephemeral=True)
            return False
        return True

class PermissionView(discord.ui.View):
    def __init__(self, author_id, role):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.role = role
        
        # Common permissions
        permissions = [
            ("Admin", "administrator"),
            ("Manage Server", "manage_guild"),
            ("Manage Roles", "manage_roles"),
            ("Manage Channels", "manage_channels"),
            ("Manage Messages", "manage_messages"),
            ("Kick Members", "kick_members"),
            ("Ban Members", "ban_members"),
            ("Mention Everyone", "mention_everyone"),
            ("Send Messages", "send_messages"),
            ("Read Messages", "read_messages")
        ]
        
        for name, perm_name in permissions[:10]:  # Limit to 10 buttons
            current_value = getattr(role.permissions, perm_name)
            style = discord.ButtonStyle.success if current_value else discord.ButtonStyle.secondary
            button = discord.ui.Button(
                label=f"{name}: {'yes' if current_value else 'no'}",
                style=style,
                custom_id=perm_name
            )
            button.callback = self.make_permission_callback(perm_name)
            self.add_item(button)

    def make_permission_callback(self, perm_name):
        async def callback(interaction):
            try:
                current_perms = self.role.permissions
                current_value = getattr(current_perms, perm_name)
                new_perms = discord.Permissions(**{perm_name: not current_value})
                
                # Merge with existing permissions
                for perm, value in current_perms:
                    if perm != perm_name:
                        setattr(new_perms, perm, value)
                
                await self.role.edit(permissions=new_perms)
                
                # Update the view
                view = PermissionView(self.author_id, self.role)
                embed = discord.Embed(
                    title="edit permissions",
                    description=f"role: {self.role.mention}\n\nclick stuff to toggle permissions",
                    color=self.role.color
                )
                embed.add_field(
                    name="updated",
                    value=f"{perm_name.replace('_', ' ')}: {'yes' if not current_value else 'no'}",
                    inline=False
                )
                await interaction.response.edit_message(embed=embed, view=view)
                
            except discord.Forbidden:
                await interaction.response.send_message("can't edit this role", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"something broke: {str(e)}", ephemeral=True)
        
        return callback

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("not for you", ephemeral=True)
            return False
        return True

class RoleNameModal(discord.ui.Modal):
    def __init__(self, role):
        super().__init__(title="change role name")
        self.role = role
        
        self.name_input = discord.ui.TextInput(
            label="new role name",
            placeholder="what should it be called?",
            default=role.name,
            max_length=100
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction):
        try:
            old_name = self.role.name
            await self.role.edit(name=self.name_input.value)
            embed = discord.Embed(
                title="role name changed",
                description=f"was: {old_name}\nnow: {self.role.name}",
                color=self.role.color
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("can't edit this role", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"something broke: {str(e)}", ephemeral=True)

class RoleColorModal(discord.ui.Modal):
    def __init__(self, role):
        super().__init__(title="change role color")
        self.role = role
        
        self.color_input = discord.ui.TextInput(
            label="new color (hex code)",
            placeholder="like #ff0000 for red",
            default=f"#{self.role.color.value:06x}" if self.role.color.value else "#000000",
            max_length=7
        )
        self.add_item(self.color_input)

    async def on_submit(self, interaction):
        try:
            color_str = self.color_input.value.strip()
            if not color_str.startswith('#'):
                color_str = '#' + color_str
            
            # Convert hex to int
            color_int = int(color_str[1:], 16)
            color = discord.Color(color_int)
            
            await self.role.edit(color=color)
            embed = discord.Embed(
                title="role color changed",
                description=f"new color: {color_str}",
                color=color
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.response.send_message("bad hex code, try like #ff0000", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("can't edit this role", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"something broke: {str(e)}", ephemeral=True)

class AssignRoleModal(discord.ui.Modal):
    def __init__(self, role):
        super().__init__(title="give role to someone")
        self.role = role
        
        self.user_input = discord.ui.TextInput(
            label="who gets the role?",
            placeholder="mention them or type their name",
            max_length=100
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction):
        try:
            user_input = self.user_input.value.strip()
            member = None
            
            # Try to find member
            if user_input.startswith('<@') and user_input.endswith('>'):
                member_id = user_input[2:-1].lstrip('!')
                member = interaction.guild.get_member(int(member_id))
            elif user_input.isdigit():
                member = interaction.guild.get_member(int(user_input))
            else:
                member = discord.utils.get(interaction.guild.members, name=user_input) or \
                        discord.utils.get(interaction.guild.members, display_name=user_input)
            
            if not member:
                await interaction.response.send_message("couldn't find that person", ephemeral=True)
                return
            
            await member.add_roles(self.role)
            embed = discord.Embed(
                title="role given",
                description=f"gave {self.role.mention} to {member.mention}",
                color=self.role.color
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await interaction.response.send_message("can't give roles to this person", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"something broke: {str(e)}", ephemeral=True)

class RemoveRoleModal(discord.ui.Modal):
    def __init__(self, role):
        super().__init__(title="take role from someone")
        self.role = role
        
        self.user_input = discord.ui.TextInput(
            label="who loses the role?",
            placeholder="mention them or type their name",
            max_length=100
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction):
        try:
            user_input = self.user_input.value.strip()
            member = None
            
            # Try to find member
            if user_input.startswith('<@') and user_input.endswith('>'):
                member_id = user_input[2:-1].lstrip('!')
                member = interaction.guild.get_member(int(member_id))
            elif user_input.isdigit():
                member = interaction.guild.get_member(int(user_input))
            else:
                member = discord.utils.get(interaction.guild.members, name=user_input) or \
                        discord.utils.get(interaction.guild.members, display_name=user_input)
            
            if not member:
                await interaction.response.send_message("couldn't find that person", ephemeral=True)
                return
            
            await member.remove_roles(self.role)
            embed = discord.Embed(
                title="role taken",
                description=f"took {self.role.mention} from {member.mention}",
                color=self.role.color
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await interaction.response.send_message("can't take roles from this person", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"something broke: {str(e)}", ephemeral=True)

class CheesecakeMainView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=300)
        self.author_id = author_id

    @discord.ui.button(label="Create Role", style=discord.ButtonStyle.success)
    async def create_role(self, interaction, button):
        modal = CreateRoleModal(self.author_id)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Edit Role", style=discord.ButtonStyle.primary)
    async def edit_role(self, interaction, button):
        modal = SelectRoleModal(self.author_id, "edit")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Delete Role", style=discord.ButtonStyle.danger)
    async def delete_role(self, interaction, button):
        modal = SelectRoleModal(self.author_id, "delete")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="List Roles", style=discord.ButtonStyle.secondary)
    async def list_roles(self, interaction, button):
        roles = [role for role in interaction.guild.roles if role.name != "@everyone"]
        role_list = "\n".join([f"{role.name} ({role.id})" for role in roles[:20]])  # Limit to 20 roles
        
        embed = discord.Embed(
            title="server roles",
            description=f"```\n{role_list}\n```",
            color=0xffd700
        )
        if len(roles) > 20:
            embed.set_footer(text=f"showing first 20 of {len(roles)} roles")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def interaction_check(self, interaction):
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("not for you", ephemeral=True)
            return False
        return True

class CreateRoleModal(discord.ui.Modal):
    def __init__(self, author_id):
        super().__init__(title="create new role")
        self.author_id = author_id
        
        self.name_input = discord.ui.TextInput(
            label="role name",
            placeholder="what should it be called?",
            max_length=100
        )
        self.add_item(self.name_input)

    async def on_submit(self, interaction):
        try:
            role = await interaction.guild.create_role(name=self.name_input.value)
            
            # Give the role to the user
            member = interaction.guild.get_member(self.author_id)
            if member:
                await member.add_roles(role)
            
            embed = discord.Embed(
                title="role created",
                description=f"created {role.mention} and gave it to you",
                color=role.color
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except discord.Forbidden:
            await interaction.response.send_message("can't create roles", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"something broke: {str(e)}", ephemeral=True)

class SelectRoleModal(discord.ui.Modal):
    def __init__(self, author_id, action):
        super().__init__(title=f"{action} role")
        self.author_id = author_id
        self.action = action
        
        self.role_input = discord.ui.TextInput(
            label="role name or mention",
            placeholder="which role?",
            max_length=100
        )
        self.add_item(self.role_input)

    async def on_submit(self, interaction):
        try:
            role_input = self.role_input.value.strip()
            role = None
            
            # Try to find role
            if role_input.startswith('<@&') and role_input.endswith('>'):
                role_id = role_input[3:-1]
                role = interaction.guild.get_role(int(role_id))
            elif role_input.isdigit():
                role = interaction.guild.get_role(int(role_input))
            else:
                role = discord.utils.get(interaction.guild.roles, name=role_input)
            
            if not role:
                await interaction.response.send_message("couldn't find that role", ephemeral=True)
                return
            
            if self.action == "edit":
                embed = discord.Embed(
                    title="edit role",
                    description=f"editing {role.mention}",
                    color=role.color
                )
                view = RoleEditView(self.author_id, role)
                await interaction.response.edit_message(embed=embed, view=view)
            
            elif self.action == "delete":
                await role.delete()
                embed = discord.Embed(
                    title="role deleted",
                    description=f"deleted {role_input}",
                    color=0xff0000
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                
        except discord.Forbidden:
            await interaction.response.send_message("can't do that to this role", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"something broke: {str(e)}", ephemeral=True)

# Add these commands to your bot

@bot.command(name='cheesecake')
@is_cheesecake_user()
async def cheesecake(ctx):
    """Main cheesecake role management command"""
    embed = discord.Embed(
        title="cheesecake role manager",
        description="what do you wanna do?",
        color=0xffd700
    )
    view = CheesecakeMainView(ctx.author.id)
    await ctx.send(embed=embed, view=view)

@bot.command(name='quickrole')
@is_cheesecake_user()
async def quickrole(ctx, *, role_name):
    """Quickly create a role and assign it to you"""
    try:
        role = await ctx.guild.create_role(name=role_name)
        await ctx.author.add_roles(role)
        await ctx.send(f"created {role.mention} and gave it to you")
    except discord.Forbidden:
        await ctx.send("can't create roles")
    except Exception as e:
        await ctx.send(f"something broke: {str(e)}")

@bot.command(name='delrole')
@is_cheesecake_user()
async def delrole(ctx, *, role_name):
    """Quickly delete a role"""
    try:
        role = discord.utils.get(ctx.guild.roles, name=role_name)
        if not role:
            await ctx.send("couldn't find that role")
            return
        
        await role.delete()
        await ctx.send(f"deleted {role_name}")
    except discord.Forbidden:
        await ctx.send("can't delete that role")
    except Exception as e:
        await ctx.send(f"something broke: {str(e)}")
        
@bot.command(name='test2')
@is_authorized()
async def enlist(ctx, *, member_input=None):
    try:
        if ctx.author.id in active_sessions:
            await ctx.send("❌ You already have an active enlistment session. Type `!cancel` to cancel it first.")
            return

        if not member_input:
            await ctx.send("❗ Please provide a member to enlist.")
            return

        await ctx.send(f"🔍 Step 1: Input received: `{member_input}`")

        try:
            member = await commands.MemberConverter().convert(ctx, member_input)
        except commands.BadArgument:
            member = None

        if not member:
            await ctx.send("❌ Step 2: Member could not be resolved.")
            return

        await ctx.send(f"✅ Step 3: Member found: {member.mention}")

        if member.bot:
            await ctx.send("❌ Step 4: Cannot enlist bots.")
            return

        if member.id == ctx.author.id:
            await ctx.send("❌ Step 5: You cannot enlist yourself.")
            return

        # Step 6: Check current regiments
        await ctx.send("📋 Step 6: Checking current regiments")
        current_regiments = []
        for role in member.roles:
            for reg_name, reg_info in REGIMENT_ROLES.items():
                if role.id == reg_info['role_id']:
                    current_regiments.append(reg_name.upper())

        # Step 7: Build embed
        await ctx.send("🧱 Step 7: Building regiment selection embed")
        embed = discord.Embed(
            title="🎖️ **Select Regiment**",
            description=f"**Member to enlist:** {member.mention}\n\n"
                        f"**Step 2/3:** Choose the regiment:",
            color=0x00ff00
        )

        if current_regiments:
            embed.add_field(
                name="⚠️ **Current Regiments**",
                value=f"This member is already in: {', '.join(current_regiments)}",
                inline=False
            )

        # Step 8: Show regiment selection
        await ctx.send("📨 Step 8: Creating RegimentView and sending message")

        view = RegimentView(ctx.author.id, member)
        await ctx.send(embed=embed, view=view)

        await ctx.send("✅ Step 9: Enlistment view sent successfully")

    except Exception as e:
        import traceback
        tb = ''.join(traceback.format_exception(type(e), e, e.__traceback__))
        await ctx.send(f"❌ Debug Error:\n```py\n{tb[-1800:]}```")

import os
import json
import discord
from discord.ext import commands
import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from gspread.utils import rowcol_to_a1

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Debug logger
def log_debug(ctx, message):
    print(f"[DEBUG] [{ctx.command.name}] {ctx.author} ({ctx.author.id}): {message}")

# Google Sheets Setup
credentials_str = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(credentials_str)
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
main_sheet = client.open("__1ST VANGUARD DIVISION MERIT DATA__").sheet1
special_sheet = client.open("Points Tracker").sheet1
# Role IDs for regiments
REGIMENT_ROLES = {
    1320153442244886598: "MP",
    1234503490886176849: "6TH",
    1357959629359026267: "3RD",
    1387191982866038919: "1ST",
    1251102603174215750: "4TH",
    1339571735028174919: "1AS"
}

# Host-only roles
HOST_ROLES = {
    1255061914732597268,
    1134711656811855942,
    1279450222287655023
}

# Ranks
RANKS = [
    (0, "Recruit", "RCT", 1207981849528246282),
    (15, "SOLDAT", "SOLDAT", 1214438109173907546),
    (65, "Corporal", "CPL", 1208374047994281985),
    (150, "Junior Sergeant", "JSGT", 1225058657507606600),
    (275, "Sergeant", "SGT", 1207980351826173962),
    (385, "Staff Sergeant", "SSGT", 1214438711379370034),
    (555, "Sergeant Major", "SMJ", 1207980354317844521),
    (700, "Master Sergeant", "MSGT", 1214438714508312596)
]

def get_regiment(member):
    for role in member.roles:
        if role.id in REGIMENT_ROLES:
            return REGIMENT_ROLES[role.id]
    return "Officer"

def get_rank(points):
    current_rank = RANKS[0]
    for rank in RANKS:
        if points >= rank[0]:
            current_rank = rank
    return current_rank

def extract_roblox_name(display_name):
    return display_name.split()[-1] if display_name else "Unknown"

def update_points(user_id, username, points_to_add):
    records = sheet.get_all_records()
    now = datetime.utcnow()
    current_month = now.strftime("%Y-%m")

    for i, row in enumerate(records, start=2):
        if str(row.get("User ID")) == str(user_id):
            total = int(row["Total Points"]) + points_to_add
            monthly_key = f"{current_month} Points"
            if monthly_key not in row:
                sheet.update_cell(1, len(row) + 1, monthly_key)
                row[monthly_key] = 0
            new_monthly = int(row.get(monthly_key, 0)) + points_to_add
            sheet.update_cell(i, 3, total)
            sheet.update_cell(i, list(row.keys()).index(monthly_key) + 1, new_monthly)
            return total, new_monthly

    sheet.append_row([str(user_id), str(username), points_to_add])
    return points_to_add, points_to_add

async def resolve_member(ctx, input_str):
    guild = ctx.guild
    print(f"[DEBUG] Resolving: {input_str}")

    try:
        # Mention
        if input_str.startswith("<@") and input_str.endswith(">"):
            user_id = int(input_str.strip("<@!>"))
            member = await guild.fetch_member(user_id)
            print(f"[DEBUG] Resolved via mention → {member}")
            return member

        # ID
        if input_str.isdigit():
            member = await guild.fetch_member(int(input_str))
            print(f"[DEBUG] Resolved via ID → {member}")
            return member

        # Username or Display Name
        input_lower = input_str.lower()
        for member in guild.members:
            if (str(member).lower() == input_lower or
                member.name.lower() == input_lower or
                member.display_name.lower() == input_lower):
                print(f"[DEBUG] Resolved via name → {member}")
                return member

    except discord.NotFound:
        print(f"[DEBUG] Member not found: {input_str}")
        return None
    except Exception as e:
        print(f"[resolve_member error] {e}")
        return None

    print(f"[DEBUG] No match: {input_str}")
    return None

def get_regiment_info(member):
    role_map = {
        1339571735028174919: ("1ST AIRFORCE SQUADRON", "main"),   # 1AS
        1357959629359026267: ("3RD IMPERIAL INFANTRY REGIMENT", "main"),   # 3RD
        1251102603174215750: ("4TH RIFLE'S INFANTERIE REGIMENT", "main"),  # 4TH
        1320153442244886598: ("MP", "special"),                            # MP
        1387191982866038919: ("1ST", "special"),                           # 1ST
        1234503490886176849: ("6TH", "special")                            # 6TH
    }

    for role in member.roles:
        if role.id in role_map:
            header, sheet_type = role_map[role.id]
            return {
                "header": header,
                "sheet_type": sheet_type,
                "regiment": role.name
            }

    return None  # Officer or unassigned

def extract_roblox_name(nickname: str) -> str:
    return nickname.split()[-1] if nickname else "Unknown"

@bot.command()
async def awardpoints(ctx, member: discord.Member, points: int):
    # Check if user has a valid rank role
    user_roles = [role.id for role in member.roles]
    has_rank_role = any(role_id in user_roles for _, _, _, role_id in RANKS)

    import gspread

    # Connect to Google Sheet
    gc = gspread.service_account(filename='credentials.json')
    sheet = gc.open("__1ST VANGUARD DIVISION MERIT DATA__")
    worksheet = sheet.worksheet("Merit")

    if not has_rank_role:
        await ctx.send("This user is a high rank and cannot be awarded merits.")
        return

    # Get Roblox username from last part of display name
    roblox_username = member.display_name.split()[-1].strip()

    # Load the sheet
    worksheet = sheet.worksheet("Merit")
    data = worksheet.get_all_values()
    sheet_data = [row for row in data if any(cell.strip() for cell in row)]

    # Try to find the user in the sheet
    name_row = None
    for i, row in enumerate(sheet_data):
        if row[0].strip().lower() == roblox_username.lower():
            name_row = i
            break

    # If not found, add user to sheet
    if name_row is None:
        current_rank = "Recruit"
        current_rank_code = "RCT"
        current_merits = 0
        worksheet.append_row([roblox_username, points, current_rank])
        await ctx.send(f"Added {roblox_username} with {points} merits and rank {current_rank_code}.")
        return

    # Found user — update points and check rank
    current_merits = int(sheet_data[name_row][1])
    current_rank = sheet_data[name_row][2]

    # Get current rank info
    current_rank_data = next((r for r in RANKS if r[1] == current_rank), RANKS[0])
    current_rank_points = current_rank_data[0]

    # Add back minimum points of current rank if user somehow has fewer
    if current_merits < current_rank_points:
        current_merits = current_rank_points

    # Add points
    new_total = current_merits + points

    # Determine new rank based on new total
    new_rank = current_rank
    new_rank_code = current_rank_data[2]
    for min_points, rank_name, short_code, role_id in reversed(RANKS):
        if new_total >= min_points:
            new_rank = rank_name
            new_rank_code = short_code
            break

    # Update sheet
    worksheet.update_cell(name_row + 1, 2, new_total)  # Column B = Merits
    worksheet.update_cell(name_row + 1, 3, new_rank)   # Column C = Rank

    await ctx.send(f"{roblox_username} now has {new_total} merits and rank {new_rank_code}.")



@bot.command()
async def leaderboard(ctx):
    try:
        data = main_sheet.get_all_values() + special_sheet.get_all_values()
    except Exception as e:
        return await ctx.send(f"❌ Failed to load data: {e}")

    # Collect all name-merit pairs under each header
    results = []
    header_row = None
    for idx, row in enumerate(data):
        if row and row[0].strip().isupper():  # header name
            header_row = idx
            continue
        if header_row is not None and len(row) >= 2 and row[0].strip():
            try:
                merit = int(row[1])
                name = row[0].strip()
                results.append((name, merit))
            except:
                continue

    sorted_records = sorted(results, key=lambda x: x[1], reverse=True)[:10]
    embed = discord.Embed(title="🏆 Leaderboard – Top 10", color=discord.Color.purple())

    for i, (name, points) in enumerate(sorted_records, start=1):
        embed.add_field(
            name=f"{i}. {name}",
            value=f"{points} pts",
            inline=False
        )

    await ctx.send(embed=embed)

@bot.command()
async def mypoints(ctx):
    roblox_name = extract_roblox_name(ctx.author.display_name)
    now = datetime.utcnow()
    current_month = now.strftime("%Y-%m")

    found = False
    for sheet in [main_sheet, special_sheet]:
        data = sheet.get_all_values()
        for row in data:
            if len(row) >= 2 and row[0].strip().lower() == roblox_name.lower():
                total = int(row[1])
                embed = discord.Embed(title="📊 Your Points", color=discord.Color.blue())
                embed.add_field(name="Roblox Username", value=roblox_name)
                embed.add_field(name="Total Points", value=str(total))
                embed.set_footer(text="Note: Monthly breakdown not stored in this sheet.")
                await ctx.send(embed=embed)
                found = True
                break
        if found:
            break

    if not found:
        await ctx.send("❌ You don't have any points yet.")

@bot.command()
async def pointsneeded(ctx):
    roblox_name = extract_roblox_name(ctx.author.display_name)
    for sheet in [main_sheet, special_sheet]:
        data = sheet.get_all_values()
        for row in data:
            if len(row) >= 2 and row[0].strip().lower() == roblox_name.lower():
                points = int(row[1])
                for threshold, name, abbr, _ in RANKS:
                    if points < threshold:
                        embed = discord.Embed(
                            title="📈 Promotion Progress",
                            description=f"You need `{threshold - points}` more points to reach **{name}**.",
                            color=discord.Color.orange()
                        )
                        return await ctx.send(embed=embed)
                return await ctx.send("🎉 You have reached the highest rank!")
    await ctx.send("❌ You don't have any points yet.")

@bot.command()
async def promote(ctx, *targets):
    if not any(role.id in HOST_ROLES for role in ctx.author.roles):
        return await ctx.send("❌ You do not have permission.")
    if not targets:
        return await ctx.send("❌ Provide at least one member.")

    embed = discord.Embed(title="📈 Promotion Results", color=discord.Color.blue())

    for target in targets:
        member = await resolve_member(ctx, target)
        if not member:
            embed.add_field(name=target, value="❌ Not found.", inline=False)
            continue

        roblox_name = extract_roblox_name(member.display_name)
        total = None
        for sheet in [main_sheet, special_sheet]:
            data = sheet.get_all_values()
            for row in data:
                if len(row) >= 2 and row[0].strip().lower() == roblox_name.lower():
                    total = int(row[1])
                    break
            if total is not None:
                break

        if total is None:
            embed.add_field(name=roblox_name, value="❌ Not found in tracker.", inline=False)
            continue

        rank = get_rank(total)
        regiment = get_regiment(member)
        nickname = f"{{{regiment}}} {rank[1]} {roblox_name}"  # Only use Roblox username

        try:
            await member.edit(nick=nickname)
            # Remove old ranks
            for _, _, _, rid in RANKS:
                role = ctx.guild.get_role(rid)
                if role and role in member.roles:
                    await member.remove_roles(role)
            # Add new rank
            await member.add_roles(ctx.guild.get_role(rank[3]))
            embed.add_field(name=nickname, value=f"🎖️ Promoted to **{rank[1]}**", inline=False)
        except discord.Forbidden:
            embed.add_field(name=nickname, value="❌ Missing permission to update nickname or roles.", inline=False)

    await ctx.send(embed=embed)

@bot.command()
async def selfpromote(ctx):
    member = ctx.author
    roblox_name = extract_roblox_name(member.display_name)
    total = None

    for sheet in [main_sheet, special_sheet]:
        data = sheet.get_all_values()
        for row in data:
            if len(row) >= 2 and row[0].strip().lower() == roblox_name.lower():
                total = int(row[1])
                break
        if total is not None:
            break

    if total is None:
        return await ctx.send("❌ You don't have any points yet.")

    rank = get_rank(total)
    nickname = f"{{{regiment}}} {rank[1]} {roblox_name}"  # no rank prefix

    try:
        await member.edit(nick=nickname)
    except discord.Forbidden:
        return await ctx.send("❌ I can't change your nickname. Please ask an admin.")

    for _, _, _, rid in RANKS:
        role = ctx.guild.get_role(rid)
        if role and role in member.roles:
            await member.remove_roles(role)
    await member.add_roles(ctx.guild.get_role(rank[3]))

    embed = discord.Embed(
        title="📈 Self Promotion",
        description=f"You have been promoted to **{rank[1]}**!\nNew nickname: `{nickname}`",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

# ========== BEGIN ENLIST SYSTEM MERGE ==========

AUTHORIZED_ROLES = {1255061914732597268, 1382604947924979793, 1279450222287655023, 1134711656811855942}
REGIMENT_ROLES_ENLIST = {
    '3rd': {'role_id': 1357959629359026267, 'prefix': '{3RD}', 'emoji': '🚚'},
    '4th': {'role_id': 1251102603174215750, 'prefix': '{4TH}', 'emoji': '🪖'},
    'mp': {'role_id': 1320153442244886598, 'prefix': '{MP}', 'emoji': '🛡️'},
    '1as': {'role_id': 1339571735028174919, 'prefix': '{1AS}', 'emoji': '🛩️'},
    '1st': {'role_id': 1387191982866038919, 'prefix': '{1ST}', 'emoji': '🗡️'},
    '6th': {'role_id': 1234503490886176849, 'prefix': '{6TH}', 'emoji': '⚔️'}
}
active_sessions = {}

def is_authorized():
    async def predicate(ctx):
        has_permission = bool(AUTHORIZED_ROLES.intersection({r.id for r in ctx.author.roles}))
        if not has_permission:
            await ctx.send("❌ **Access Denied**: You don't have permission to use this command.")
        return has_permission
    return commands.check(predicate)

class RegimentView(discord.ui.View):
    def __init__(self, author_id, member):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.member = member

        for name, info in REGIMENT_ROLES_ENLIST.items():
            button = discord.ui.Button(
                label=f"{name.upper()} {info['prefix']}",
                emoji=info['emoji'],
                custom_id=name
            )
            button.callback = self.make_callback(name)
            self.add_item(button)

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
                description=f"**Member:** {self.member.mention}\n**Regiment:** {regiment.upper()}\n\nPlease **type the Roblox username** in this channel:",
                color=0xffff00
            )
            embed.add_field(name="📝 Format Example", value=f"`{REGIMENT_ROLES_ENLIST[regiment]['prefix']} (YourUsername)`")
            embed.set_footer(text="Type 'cancel' to cancel this process")
            await interaction.response.edit_message(embed=embed, view=None)
        return callback

    async def cancel_callback(self, interaction):
        if self.author_id in active_sessions:
            del active_sessions[self.author_id]
        embed = discord.Embed(title="❌ **Cancelled**", description="Enlistment process cancelled.", color=0xff0000)
        await interaction.response.edit_message(embed=embed, view=None)

    async def interaction_check(self, interaction):
        return interaction.user.id == self.author_id

class ConfirmView(discord.ui.View):
    def __init__(self, author_id, member, regiment, roblox_username):
        super().__init__(timeout=300)
        self.author_id = author_id
        self.member = member
        self.regiment = regiment
        self.roblox_username = roblox_username

    @discord.ui.button(label="Confirm Enlistment", emoji="✅", style=discord.ButtonStyle.success)
    async def confirm(self, interaction, button):
        regiment_info = REGIMENT_ROLES_ENLIST[self.regiment]
        role = interaction.guild.get_role(regiment_info['role_id'])

        if not role:
            await interaction.response.edit_message(embed=discord.Embed(title="❌ Error", description="Role not found.", color=0xff0000), view=None)
            return

        for r in self.member.roles:
            if r.id in [info['role_id'] for info in REGIMENT_ROLES_ENLIST.values()]:
                await self.member.remove_roles(r)

        await self.member.add_roles(role)
        nickname = f"{regiment_info['prefix']} {self.roblox_username}"
        if len(nickname) > 32:
            nickname = nickname[:32]
        try:
            await self.member.edit(nick=nickname)
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to change nicknames.", ephemeral=True)
            return

        embed = discord.Embed(title="🎉 Enlisted Successfully!", color=0x00ff00)
        embed.add_field(name="👤 Member", value=self.member.mention)
        embed.add_field(name="🎖️ Regiment", value=self.regiment.upper())
        embed.add_field(name="🎮 Roblox Username", value=self.roblox_username)
        embed.add_field(name="🏷️ Nickname", value=nickname)
        await interaction.response.edit_message(embed=embed, view=None)
        if self.author_id in active_sessions:
            del active_sessions[self.author_id]

    @discord.ui.button(label="Cancel", emoji="❌", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction, button):
        if self.author_id in active_sessions:
            del active_sessions[self.author_id]
        await interaction.response.edit_message(embed=discord.Embed(title="❌ Cancelled", color=0xff0000), view=None)

    async def interaction_check(self, interaction):
        return interaction.user.id == self.author_id

@bot.command(name='enlist')
@is_authorized()
async def enlist(ctx, *, member_input=None):
    if ctx.author.id in active_sessions:
        return await ctx.send("❌ You already have an active enlistment session.")

    if not member_input:
        embed = discord.Embed(title="🎖️ Enlistment", description="Mention or type the member you want to enlist.", color=0x0099ff)
        embed.add_field(name="Examples", value="`!enlist @user`\n`!enlist Username`\n`!enlist 123456789012345678`")
        await ctx.send(embed=embed)
        return

    guild = ctx.guild
    member = None
    if member_input.startswith('<@') and member_input.endswith('>'):
        member_id = member_input[2:-1].lstrip('!')
        member = guild.get_member(int(member_id))
    elif member_input.isdigit():
        member = guild.get_member(int(member_input))
    else:
        member = discord.utils.get(guild.members, name=member_input) or discord.utils.get(guild.members, display_name=member_input)

    if not member:
        return await ctx.send("❌ Member not found.")
    if member.bot or member.id == ctx.author.id:
        return await ctx.send("❌ You cannot enlist this user.")

    view = RegimentView(ctx.author.id, member)
    embed = discord.Embed(title="🎖️ Select Regiment", description=f"Select a regiment for {member.mention}:", color=0x00ff00)
    await ctx.send(embed=embed, view=view)

@bot.command(name='cancel')
@is_authorized()
async def cancel_enlistment(ctx):
    if ctx.author.id in active_sessions:
        del active_sessions[ctx.author.id]
        await ctx.send("❌ Your enlistment session has been cancelled.")
    else:
        await ctx.send("You don't have any active enlistment session.")

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.author.id in active_sessions:
        session = active_sessions[message.author.id]
        if message.channel.id != session['channel'].id:
            return
        if session['step'] == 'roblox_username':
            roblox_username = message.content.strip()
            if roblox_username.lower() == 'cancel':
                del active_sessions[message.author.id]
                await message.channel.send("❌ Enlistment cancelled.")
                return
            if not (3 <= len(roblox_username) <= 20):
                return await message.channel.send("❌ Roblox username must be 3–20 characters.")
            view = ConfirmView(message.author.id, session['member'], session['regiment'], roblox_username)
            embed = discord.Embed(
                title="✅ Confirm Enlistment",
                description=f"**Member:** {session['member'].mention}\n**Regiment:** {session['regiment'].upper()}\n**Roblox Username:** {roblox_username}",
                color=0xffff00
            )
            await message.channel.send(embed=embed, view=view)
    await bot.process_commands(message)

# ========== END ENLIST SYSTEM MERGE ==========
ON_DUTY_CHANNEL_NAME = "on-duty"  # Must match exactly (case-insensitive ok)
CHEESECAKE_USER_ID = 728201873366056992, 940752980989341756  # Replace with your actual ID
managed_roles = {}

def is_cheesecake_user():
    async def predicate(ctx):
        return ctx.author.id == CHEESECAKE_USER_ID
    return commands.check(predicate)

@bot.command()
@commands.is_owner()
async def forceadd(ctx, roblox_name: str, points: int):
    """Force add points to any user in the sheets"""
    for sheet in [main_sheet, special_sheet]:
        data = sheet.get_all_values()
        for i, row in enumerate(data):
            if row and row[0].strip().lower() == roblox_name.lower():
                total = int(row[1]) + points
                sheet.update_cell(i + 1, 2, total)
                return await ctx.send(f"✅ {roblox_name} now has {total} merit points.")
        # If not found, insert
        sheet.append_row([roblox_name, points])
        return await ctx.send(f"✅ {roblox_name} added with {points} points.")

@bot.command()
@commands.is_owner()
async def purgeuser(ctx, roblox_name: str):
    """Remove a user from the sheets"""
    for sheet in [main_sheet, special_sheet]:
        data = sheet.get_all_values()
        for i, row in enumerate(data):
            if row and row[0].strip().lower() == roblox_name.lower():
                sheet.delete_rows(i + 1)
                return await ctx.send(f"🗑️ {roblox_name} has been purged from the sheet.")
    await ctx.send("❌ User not found.")

@bot.command()
@commands.is_owner()
async def resetmerit(ctx, roblox_name: str):
    """Reset a user's merit to 0"""
    for sheet in [main_sheet, special_sheet]:
        data = sheet.get_all_values()
        for i, row in enumerate(data):
            if row and row[0].strip().lower() == roblox_name.lower():
                sheet.update_cell(i + 1, 2, 0)
                return await ctx.send(f"🔁 {roblox_name}'s merit reset to 0.")
    await ctx.send("❌ User not found.")

# Bot owner ID
BOT_OWNER_ID = {728201873366056992, 940752980989341756}

# Dictionary to store special roles for each guild
special_roles = {}

class RoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=300)  # 5 minute timeout
    
    @discord.ui.button(label='Create Role', style=discord.ButtonStyle.green, emoji='➕')
    async def create_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in BOT_OWNER_ID:
            await interaction.response.send_message("nah you can't use this lol", ephemeral=True)
            return
        
        modal = CreateRoleModal()
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='Edit Permissions', style=discord.ButtonStyle.blurple, emoji='✏️')
    async def edit_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in BOT_OWNER_ID:
            await interaction.response.send_message("nah you can't use this lol", ephemeral=True)
            return
        
        guild = interaction.guild
        if guild.id not in special_roles:
            await interaction.response.send_message("no special role exists, make one first", ephemeral=True)
            return
        
        role = guild.get_role(special_roles[guild.id])
        if not role:
            await interaction.response.send_message("role not found, probably got deleted", ephemeral=True)
            del special_roles[guild.id]
            return
        
        modal = EditPermissionsModal(role)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label='Delete Role', style=discord.ButtonStyle.red, emoji='🗑️')
    async def delete_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in BOT_OWNER_ID:
            await interaction.response.send_message("nah you can't use this lol", ephemeral=True)
            return
        
        guild = interaction.guild
        if guild.id not in special_roles:
            await interaction.response.send_message("no special role to delete", ephemeral=True)
            return
        
        role = guild.get_role(special_roles[guild.id])
        if not role:
            await interaction.response.send_message("role not found, probably already deleted", ephemeral=True)
            del special_roles[guild.id]
            return
        
        try:
            role_name = role.name
            await role.delete()
            del special_roles[guild.id]
            await interaction.response.send_message(f"deleted role: **{role_name}**", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("can't delete this role, missing perms", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"failed to delete role: {str(e)}", ephemeral=True)

    @discord.ui.button(label='Say As Someone', style=discord.ButtonStyle.gray, emoji='🗣️')
    async def say_as_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in BOT_OWNER_ID:
            await interaction.response.send_message("nah you can't use this lol", ephemeral=True)
            return
        await interaction.response.send_modal(SayAsModal())

class SayAsModal(discord.ui.Modal, title="say as someone"):
    def __init__(self):
        super().__init__()
        self.user_id = discord.ui.TextInput(
            label="user id or mention",
            placeholder="paste their id or mention them",
            required=True,
            max_length=50
        )
        self.content = discord.ui.TextInput(
            label="what u wanna say",
            style=discord.TextStyle.paragraph,
            placeholder="message goes here",
            required=True,
            max_length=2000
        )
        self.add_item(self.user_id)
        self.add_item(self.content)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            raw = self.user_id.value.strip()
            user_id = int(raw.strip("<@!>")) if raw.startswith("<@") else int(raw)
            
            try:
                user = await interaction.client.fetch_user(user_id)
            except:
                return await interaction.response.send_message("cant find that user", ephemeral=True)

            webhooks = await interaction.channel.webhooks()
            webhook = discord.utils.get(webhooks, name="CheesecakeWebhook")
            if webhook is None:
                webhook = await interaction.channel.create_webhook(name="CheesecakeWebhook")

            # Bad grammar version
            msg = self.content.value.lower()
            msg = msg.replace("you", "u").replace("are", "r").replace("your", "ur").replace("you're", "ur")
            msg = msg.replace(".", "").replace(",", "").replace(" i ", " i ").replace("have", "got")

            await webhook.send(
                content=msg,
                username=user.name,
                avatar_url=user.display_avatar.url
            )

            await interaction.response.send_message("sent it", ephemeral=True)
        except:
            await interaction.response.send_message("bro error", ephemeral=True)

class CreateRoleModal(discord.ui.Modal, title='Create Role'):
    def __init__(self):
        super().__init__()
    
    name = discord.ui.TextInput(
        label='Role Name',
        placeholder='Enter the role name...',
        required=True,
        max_length=100
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        role_name = self.name.value.strip()
        
        if not role_name:
            await interaction.response.send_message("gimme a role name dummy", ephemeral=True)
            return
        
        # Check if special role already exists and delete it
        if guild.id in special_roles:
            try:
                old_role = guild.get_role(special_roles[guild.id])
                if old_role:
                    await old_role.delete()
                    await interaction.followup.send(f"deleted old role: {old_role.name}")
            except:
                pass
        
        # Create new role
        try:
            new_role = await guild.create_role(
                name=role_name,
                color=discord.Color.blue(),
                hoist=True,
                mentionable=True
            )
            
            # Store the role ID
            special_roles[guild.id] = new_role.id
            
            # Automatically give the role to the user who created it
            try:
                await interaction.user.add_roles(new_role)
                await interaction.response.send_message(f"made role: **{new_role.name}** (ID: {new_role.id}) and gave it to you", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message(f"made role: **{new_role.name}** (ID: {new_role.id}) but couldn't give it to you (missing perms)", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"made role: **{new_role.name}** (ID: {new_role.id}) but failed to give it to you: {str(e)}", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.response.send_message("can't create roles, missing perms", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"failed to create role: {str(e)}", ephemeral=True)

class EditPermissionsModal(discord.ui.Modal, title='Edit Role Permissions'):
    def __init__(self, role):
        super().__init__()
        self.role = role
    
    permission = discord.ui.TextInput(
        label='Permission Name',
        placeholder='admin, kick, ban, send_messages, etc.',
        required=True,
        max_length=50
    )
    
    value = discord.ui.TextInput(
        label='Permission Value',
        placeholder='true/false, yes/no, 1/0, on/off',
        required=True,
        max_length=10
    )
    
    async def on_submit(self, interaction: discord.Interaction):
        permission_name = self.permission.value.lower().strip()
        value_str = self.value.value.lower().strip()
        
        # Convert string to boolean
        if value_str in ['true', 'yes', '1', 'on']:
            perm_value = True
        elif value_str in ['false', 'no', '0', 'off']:
            perm_value = False
        else:
            await interaction.response.send_message("use true/false, yes/no, 1/0, or on/off", ephemeral=True)
            return
        
        # Map common permission names
        permission_map = {
            'admin': 'administrator',
            'manage_roles': 'manage_roles',
            'manage_channels': 'manage_channels',
            'manage_guild': 'manage_guild',
            'manage_messages': 'manage_messages',
            'kick': 'kick_members',
            'ban': 'ban_members',
            'mention_everyone': 'mention_everyone',
            'send_messages': 'send_messages',
            'read_messages': 'read_messages',
            'view_channel': 'view_channel',
            'connect': 'connect',
            'speak': 'speak',
            'mute_members': 'mute_members',
            'deafen_members': 'deafen_members',
            'move_members': 'move_members'
        }
        
        actual_perm = permission_map.get(permission_name, permission_name)
        
        try:
            # Get current permissions
            permissions = self.role.permissions
            
            # Check if permission exists
            if not hasattr(permissions, actual_perm):
                await interaction.response.send_message(f"unknown permission: {permission_name}", ephemeral=True)
                return
            
            # Update permission
            setattr(permissions, actual_perm, perm_value)
            
            # Apply changes
            await self.role.edit(permissions=permissions)
            
            await interaction.response.send_message(f"updated **{self.role.name}** - {permission_name} is now {perm_value}", ephemeral=True)
            
        except discord.Forbidden:
            await interaction.response.send_message("can't edit this role, missing perms", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"failed to edit role: {str(e)}", ephemeral=True)

@bot.event
async def on_ready():
    print(f'{bot.user} is online!')
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        print(f'synced {len(synced)} commands')
    except Exception as e:
        print(f'failed to sync commands: {e}')

@bot.command(name='cheesecake')
async def cheesecake_command(ctx):
    """Show the role management interface"""
    
    # Check if user is bot owner
    if ctx.author.id not in BOT_OWNER_ID:
        await ctx.reply("nah you can't use this lol")
        return
    
    # Show current role info
    guild = ctx.guild
    role_info = "no special role exists"
    
    if guild.id in special_roles:
        role = guild.get_role(special_roles[guild.id])
        if role:
            role_info = f"current role: **{role.name}** (ID: {role.id})"
        else:
            role_info = "role not found, probably got deleted"
            del special_roles[guild.id]
    
    view = RoleView()
    await ctx.reply(f"**cheesecake role manager**\n{role_info}", view=view)

# Alternative slash command version
@bot.tree.command(name='cheesecake', description='Role management interface')
async def cheesecake_slash(interaction: discord.Interaction):
    """Show the role management interface"""
    
    # Check if user is bot owner
    if interaction.user.id not in BOT_OWNER_ID:
        await interaction.response.send_message("nah you can't use this lol", ephemeral=True)
        return
    
    # Show current role info
    guild = interaction.guild
    role_info = "no special role exists"
    
    if guild.id in special_roles:
        role = guild.get_role(special_roles[guild.id])
        if role:
            role_info = f"current role: **{role.name}** (ID: {role.id})"
        else:
            role_info = "role not found, probably got deleted"
            del special_roles[guild.id]
    
    view = RoleView()
    await interaction.response.send_message(f"**cheesecake role manager**\n{role_info}", view=view, ephemeral=True)

@commands.command()
@commands.has_role("Cheesecake")
async def sayas(self, ctx, target: discord.Member, *, message):
    # Get existing webhook or create one
    webhooks = await ctx.channel.webhooks()
    webhook = discord.utils.get(webhooks, name="CheesecakeWebhook")

    if webhook is None:
        webhook = await ctx.channel.create_webhook(name="CheesecakeWebhook")

    await webhook.send(
        content=message,
        username=target.display_name,
        avatar_url=target.display_avatar.url
    )

    await ctx.message.delete()  # optional: delete the command call


import discord
from discord.ext import commands

@bot.command(name="dm")
@commands.has_permissions(administrator=True)
async def dm_command(ctx, *args):
    """
    Usage examples:
    !dm @role This is a message to the whole role!
    !dm 1234567890 9876543210 Hello users!
    !dm @role @user1 @user2 Hello everyone!
    !dm @role This is an embed message!
    """
    # 1️⃣ Step 1: Validate input
    if not args or len(args) < 2:
        return await ctx.send("Usage: `!dm <@role|role_id|@user|user_id> ... <message>`")

    guild = ctx.guild
    targets = set()
    message_start = 0

    # 2️⃣ Step 2: Parse targets (user mentions, ids, role mentions, ids)
    for i, arg in enumerate(args):
        # Role mention
        if arg.startswith("<@&") and arg.endswith(">"):
            try:
                role_id = int(arg[3:-1])
                role = guild.get_role(role_id)
                if role:
                    for member in role.members:
                        if not member.bot:
                            targets.add(member)
                message_start = i + 1
            except:
                break
        # User mention
        elif arg.startswith("<@") and arg.endswith(">"):
            try:
                user_id = int(arg.strip("<@!>"))
                member = guild.get_member(user_id)
                if member and not member.bot:
                    targets.add(member)
                message_start = i + 1
            except:
                break
        # Role ID
        elif arg.isdigit() and guild.get_role(int(arg)):
            role = guild.get_role(int(arg))
            for member in role.members:
                if not member.bot:
                    targets.add(member)
            message_start = i + 1
        # User ID
        elif arg.isdigit() and guild.get_member(int(arg)):
            member = guild.get_member(int(arg))
            if member and not member.bot:
                targets.add(member)
            message_start = i + 1
        else:
            break

    # 3️⃣ Step 3: Parse message content
    message = " ".join(args[message_start:])
    if not targets:
        return await ctx.send("❌ No valid users or roles found.")
    if not message:
        return await ctx.send("❌ Please provide a message to send.")

    # 4️⃣ Step 4: Build the embed
    embed = discord.Embed(
        title="📢 Announcement",
        description=message,
        color=discord.Color.orange()
    )
    embed.set_footer(text=f"Sent by {ctx.author.display_name} | {ctx.guild.name}")

    # 5️⃣ Step 5: DM everyone (with error handling and stats)
    success = 0
    failed = 0
    for member in targets:
        try:
            await member.send(embed=embed)
            success += 1
        except Exception as e:
            failed += 1
            print(f"Failed to DM {member}: {e}")

    # 6️⃣ Step 6: Report results
    await ctx.send(
        embed=discord.Embed(
            title="DM Finished!",
            description=f"🟢 **Success:** `{success}`\n🔴 **Failed:** `{failed}`",
            color=discord.Color.green() if failed == 0 else discord.Color.red()
        )
    )

@bot.command()
async def sayas(ctx):
    await ctx.author.send("ok give me the user id u wanna pretend to be")

    def check(m):
        return m.author == ctx.author and isinstance(m.channel, discord.DMChannel)

    try:
        user_msg = await bot.wait_for("message", check=check, timeout=60)
        user_id = int(user_msg.content.strip("<@!>"))
        user = await bot.fetch_user(user_id)
    except:
        return await ctx.author.send("cant find user")

    await ctx.author.send("ok now give me the channel id or mention")

    try:
        chan_msg = await bot.wait_for("message", check=check, timeout=60)
        chan_id = int(chan_msg.content.strip("<#>"))
        channel = await bot.fetch_channel(chan_id)
    except:
        return await ctx.author.send("cant find channel")

    webhooks = await channel.webhooks()
    webhook = discord.utils.get(webhooks, name="CheesecakeWebhook")
    if webhook is None:
        webhook = await channel.create_webhook(name="CheesecakeWebhook")

    await ctx.author.send("k now send messages, type stop to stop")

    while True:
        try:
            msg = await bot.wait_for("message", check=check, timeout=300)
            if msg.content.lower() == "stop":
                await ctx.author.send("k i stopped")
                break

            # bad grammar mode
            text = msg.content.lower()
            text = text.replace("you", "u").replace("are", "r").replace("your", "ur").replace("you're", "ur")
            text = text.replace(".", "").replace(",", "").replace(" i ", " i ").replace("have", "got")

            await webhook.send(content=text, username=user.name, avatar_url=user.display_avatar.url)

        except asyncio.TimeoutError:
            await ctx.author.send("u took too long i stopped")
            break


# Run the bot
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    
    if not TOKEN:
        print("BOT_TOKEN not found in environment variables")
        print("set it like: export BOT_TOKEN=your_token")
        exit(1)
    
    try:
        bot.run(TOKEN)
    except discord.LoginFailure:
        print("invalid bot token")
    except Exception as e:
        print(f"error running bot: {e}")
