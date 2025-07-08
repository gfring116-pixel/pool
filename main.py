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

# military_points_bot.py (full debug logging enabled)

import os
import json
import discord
from discord import app_commands
from discord.ext import commands
import gspread
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

def log_debug(message):
    print(f"[DEBUG] {message}")

# Google Sheets Setup
try:
    credentials_str = os.getenv("GOOGLE_CREDENTIALS")
    creds_dict = json.loads(credentials_str)
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Points Tracker").sheet1
    log_debug("Google Sheets successfully connected.")
except Exception as e:
    log_debug(f"Google Sheets error: {e}")

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

# Rank thresholds and abbreviations
RANKS = [
    (0, "Recruit", "RCT", 1207981849528246282),
    (15, "Soldat", "SLD", 1214438109173907546),
    (65, "Corporal", "CPL", 1208374047994281985),
    (150, "Junior Sergeant", "JSGT", 1225058657507606600),
    (275, "Sergeant", "SGT", 1207980351826173962),
    (385, "Staff Sergeant", "SSGT", 1214438711379370034),
    (555, "Sergeant Major", "SMJ", 1207980354317844521),
    (700, "Master Sergeant", "MSGT", 1214438714508312596)
]

# Helper functions
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

def update_points(user_id, username, points_to_add):
    log_debug(f"Updating points for user {username} ({user_id})")
    records = sheet.get_all_records()
    now = datetime.utcnow()
    current_month = now.strftime("%Y-%m")

    for i, row in enumerate(records, start=2):
        if str(row["User ID"]) == str(user_id):
            log_debug(f"User found in sheet. Adding {points_to_add} points.")
            total = int(row["Total Points"]) + points_to_add
            monthly_key = f"{current_month} Points"
            if monthly_key not in row:
                sheet.update_cell(1, len(row) + 1, monthly_key)
                row[monthly_key] = 0
            new_monthly = int(row.get(monthly_key, 0)) + points_to_add
            sheet.update_cell(i, 3, total)
            sheet.update_cell(i, list(row.keys()).index(monthly_key) + 1, new_monthly)
            return total, new_monthly

    log_debug("User not found in sheet. Appending new row.")
    sheet.append_row([user_id, username, points_to_add])
    return points_to_add, points_to_add

# Slash Commands
@tree.command(name="awardpoints")
@app_commands.describe(user="User to award", points="Number of points")
async def awardpoints(interaction: discord.Interaction, user: discord.Member, points: int):
    log_debug(f"/awardpoints by {interaction.user} → {user} +{points}")
    try:
        if not any(role.id in HOST_ROLES for role in interaction.user.roles):
            await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
            return
        total, monthly = update_points(user.id, user.name, points)
        await interaction.response.send_message(f"{user.mention} was awarded **{points}** points. Total: **{total}**, Month: **{monthly}**")
    except Exception as e:
        log_debug(f"Error in /awardpoints: {e}")
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@tree.command(name="mypoints")
async def mypoints(interaction: discord.Interaction):
    log_debug(f"/mypoints used by {interaction.user}")
    try:
        user_id = str(interaction.user.id)
        now = datetime.utcnow()
        current_month = now.strftime("%Y-%m")
        records = sheet.get_all_records()
        for row in records:
            if str(row["User ID"]) == user_id:
                total = row["Total Points"]
                monthly = row.get(f"{current_month} Points", 0)
                await interaction.response.send_message(f"**{interaction.user.display_name}**, you have **{total}** total points and **{monthly}** this month.")
                return
        await interaction.response.send_message("You don't have any points yet.")
    except Exception as e:
        log_debug(f"Error in /mypoints: {e}")
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@tree.command(name="pointsneeded")
async def pointsneeded(interaction: discord.Interaction):
    log_debug(f"/pointsneeded used by {interaction.user}")
    try:
        user_id = str(interaction.user.id)
        records = sheet.get_all_records()
        for row in records:
            if str(row["User ID"]) == user_id:
                total_points = int(row["Total Points"])
                for threshold, name, abbr, role_id in RANKS:
                    if total_points < threshold:
                        await interaction.response.send_message(f"You need **{threshold - total_points}** more points to reach **{name}**.")
                        return
                await interaction.response.send_message("🎉 You have reached the highest rank!")
                return
        await interaction.response.send_message("You don't have any points yet.")
    except Exception as e:
        log_debug(f"Error in /pointsneeded: {e}")
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@tree.command(name="leaderboard")
async def leaderboard(interaction: discord.Interaction):
    log_debug("/leaderboard triggered")
    try:
        records = sheet.get_all_records()
        sorted_records = sorted(records, key=lambda x: int(x.get("Total Points", 0)), reverse=True)
        top = sorted_records[:10]
        msg = "**🏆 Leaderboard – Top 10**\n"
        for i, user in enumerate(top, start=1):
            msg += f"**{i}.** {user['Username']} — {user['Total Points']} pts\n"
        await interaction.response.send_message(msg)
    except Exception as e:
        log_debug(f"Error in /leaderboard: {e}")
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@tree.command(name="promote")
@app_commands.describe(user="User to promote")
async def promote(interaction: discord.Interaction, user: discord.Member):
    log_debug(f"/promote triggered by {interaction.user} for {user}")
    try:
        if not any(role.id in HOST_ROLES for role in interaction.user.roles):
            await interaction.response.send_message("❌ You do not have permission to use this command.", ephemeral=True)
            return
        user_id = str(user.id)
        records = sheet.get_all_records()
        for row in records:
            if str(row["User ID"]) == user_id:
                points = int(row["Total Points"])
                new_rank = get_rank(points)
                regiment = get_regiment(user)
                nickname = f"{regiment} {new_rank[2]} {user.name}"
                await user.edit(nick=nickname)
                for _, _, _, rid in RANKS:
                    role = interaction.guild.get_role(rid)
                    if role in user.roles:
                        await user.remove_roles(role)
                await user.add_roles(interaction.guild.get_role(new_rank[3]))
                await interaction.response.send_message(f"{user.mention} has been promoted to **{new_rank[1]}**!")
                return
        await interaction.response.send_message("User not found in points tracker.")
    except Exception as e:
        log_debug(f"Error in /promote: {e}")
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@tree.command(name="selfpromote")
async def selfpromote(interaction: discord.Interaction):
    log_debug(f"/selfpromote used by {interaction.user}")
    try:
        member = interaction.user
        user_id = str(member.id)
        records = sheet.get_all_records()
        for row in records:
            if str(row["User ID"]) == user_id:
                points = int(row["Total Points"])
                new_rank = get_rank(points)
                regiment = get_regiment(member)
                nickname = f"{regiment} {new_rank[2]} {member.name}"
                await member.edit(nick=nickname)
                for _, _, _, rid in RANKS:
                    role = interaction.guild.get_role(rid)
                    if role in member.roles:
                        await member.remove_roles(role)
                await member.add_roles(interaction.guild.get_role(new_rank[3]))
                await interaction.response.send_message(f"You have been promoted to **{new_rank[1]}**!")
                return
        await interaction.response.send_message("You don't have any points yet.")
    except Exception as e:
        log_debug(f"Error in /selfpromote: {e}")
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@tree.command(name="debug")
async def debug(interaction: discord.Interaction):
    try:
        log_debug(f"/debug triggered by {interaction.user.name} ({interaction.user.id})")
        await interaction.response.send_message("✅ Bot is alive and responding.")
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
        log_debug(f"Error in /debug: {e}")

@bot.event
async def on_ready():
    try:
        await tree.sync()
        log_debug("Slash commands synced successfully.")
        print(f"✅ Logged in as {bot.user}")
    except Exception as e:
        log_debug(f"Error syncing commands: {e}")        
    
# Run bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("DISCORD_TOKEN not found!")
        exit(1)
    bot.run(token)
