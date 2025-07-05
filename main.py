import discord
from discord.ext import commands
import os
import asyncio
from datetime import datetime
import json
import re

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='-', intents=intents, help_command=None)

# Storage for user sessions
user_sessions = {}

class DMSession:
    def __init__(self, user_id, guild_id):
        self.user_id = user_id
        self.guild_id = guild_id
        self.target_type = None  # 'single_role', 'multiple_roles', 'single_user', 'multiple_users'
        self.targets = []
        self.message_type = None  # 'embed' or 'text'
        self.message_content = {}
        self.step = 'target_selection'

class TargetSelectionView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label='📝 Single Role', style=discord.ButtonStyle.primary, emoji='👥')
    async def single_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This interaction is not for you!", ephemeral=True)
            return
        
        session = user_sessions.get(self.user_id)
        if session:
            session.target_type = 'single_role'
            session.step = 'role_input'
            
            embed = discord.Embed(
                title="🎯 Role Selection",
                description="Please provide the role you want to target:\n\n" +
                           "**Options:**\n" +
                           "• Role ID: `123456789`\n" +
                           "• Role mention: `@RoleName`\n" +
                           "• Role name: `RoleName`\n\n" +
                           "⏰ You have 5 minutes to respond.",
                color=0x3498db
            )
            
            await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label='📝 Multiple Roles', style=discord.ButtonStyle.primary, emoji='👥')
    async def multiple_roles(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This interaction is not for you!", ephemeral=True)
            return
        
        session = user_sessions.get(self.user_id)
        if session:
            session.target_type = 'multiple_roles'
            session.step = 'role_input'
            
            embed = discord.Embed(
                title="🎯 Multiple Roles Selection",
                description="Please provide the roles you want to target:\n\n" +
                           "**Options:**\n" +
                           "• Role IDs: `123456789 987654321`\n" +
                           "• Role mentions: `@Role1 @Role2`\n" +
                           "• Role names: `Role1 Role2`\n" +
                           "• Mixed: `@Role1 123456789 RoleName`\n\n" +
                           "⏰ You have 5 minutes to respond.",
                color=0x3498db
            )
            
            await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label='👤 Single User', style=discord.ButtonStyle.secondary, emoji='👤')
    async def single_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This interaction is not for you!", ephemeral=True)
            return
        
        session = user_sessions.get(self.user_id)
        if session:
            session.target_type = 'single_user'
            session.step = 'user_input'
            
            embed = discord.Embed(
                title="🎯 User Selection",
                description="Please provide the user you want to target:\n\n" +
                           "**Options:**\n" +
                           "• User ID: `123456789`\n" +
                           "• User mention: `@Username`\n\n" +
                           "⏰ You have 5 minutes to respond.",
                color=0x9b59b6
            )
            
            await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label='👥 Multiple Users', style=discord.ButtonStyle.secondary, emoji='👥')
    async def multiple_users(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This interaction is not for you!", ephemeral=True)
            return
        
        session = user_sessions.get(self.user_id)
        if session:
            session.target_type = 'multiple_users'
            session.step = 'user_input'
            
            embed = discord.Embed(
                title="🎯 Multiple Users Selection",
                description="Please provide the users you want to target:\n\n" +
                           "**Options:**\n" +
                           "• User IDs: `123456789 987654321`\n" +
                           "• User mentions: `@User1 @User2`\n" +
                           "• Mixed: `@User1 123456789`\n\n" +
                           "⏰ You have 5 minutes to respond.",
                color=0x9b59b6
            )
            
            await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label='❌ Cancel', style=discord.ButtonStyle.danger, emoji='❌')
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This interaction is not for you!", ephemeral=True)
            return
        
        if self.user_id in user_sessions:
            del user_sessions[self.user_id]
        
        embed = discord.Embed(
            title="❌ Operation Cancelled",
            description="The DM operation has been cancelled.",
            color=0xe74c3c
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

class MessageTypeView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label='📋 Rich Embed', style=discord.ButtonStyle.primary, emoji='✨')
    async def embed_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This interaction is not for you!", ephemeral=True)
            return
        
        session = user_sessions.get(self.user_id)
        if session:
            session.message_type = 'embed'
            session.step = 'embed_title'
            
            embed = discord.Embed(
                title="✨ Embed Message Setup",
                description="Let's create a rich embed message!\n\n" +
                           "**Step 1: Embed Title**\n" +
                           "Please provide the title for your embed:\n\n" +
                           "⏰ You have 5 minutes to respond.",
                color=0xf39c12
            )
            
            await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label='💬 Plain Text', style=discord.ButtonStyle.secondary, emoji='📝')
    async def text_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This interaction is not for you!", ephemeral=True)
            return
        
        session = user_sessions.get(self.user_id)
        if session:
            session.message_type = 'text'
            session.step = 'text_content'
            
            embed = discord.Embed(
                title="💬 Plain Text Message",
                description="Please provide the message content you want to send:\n\n" +
                           "**Tips:**\n" +
                           "• Use `\\n` for line breaks\n" +
                           "• Maximum 2000 characters\n\n" +
                           "⏰ You have 5 minutes to respond.",
                color=0x95a5a6
            )
            
            await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label='❌ Cancel', style=discord.ButtonStyle.danger, emoji='❌')
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This interaction is not for you!", ephemeral=True)
            return
        
        if self.user_id in user_sessions:
            del user_sessions[self.user_id]
        
        embed = discord.Embed(
            title="❌ Operation Cancelled",
            description="The DM operation has been cancelled.",
            color=0xe74c3c
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

class ConfirmationView(discord.ui.View):
    def __init__(self, user_id):
        super().__init__(timeout=300)
        self.user_id = user_id

    @discord.ui.button(label='✅ Send Messages', style=discord.ButtonStyle.success, emoji='🚀')
    async def confirm_send(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This interaction is not for you!", ephemeral=True)
            return
        
        session = user_sessions.get(self.user_id)
        if not session:
            await interaction.response.send_message("❌ Session not found!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Get target users
        target_users = []
        guild = bot.get_guild(session.guild_id)
        
        if session.target_type in ['single_role', 'multiple_roles']:
            for target in session.targets:
                if isinstance(target, discord.Role):
                    target_users.extend(target.members)
        else:  # single_user or multiple_users
            target_users = [target for target in session.targets if isinstance(target, discord.Member)]
        
        # Remove duplicates
        target_users = list(set(target_users))
        
        if not target_users:
            embed = discord.Embed(
                title="❌ No Users Found",
                description="No users were found to send messages to.",
                color=0xe74c3c
            )
            await interaction.edit_original_response(embed=embed, view=None)
            return
        
        # Send messages
        success_count = 0
        failed_count = 0
        failed_users = []
        
        progress_embed = discord.Embed(
            title="🚀 Sending Messages...",
            description=f"Sending messages to {len(target_users)} users...",
            color=0xf39c12
        )
        await interaction.edit_original_response(embed=progress_embed, view=None)
        
        for user in target_users:
            try:
                if session.message_type == 'embed':
                    dm_embed = discord.Embed(
                        title=session.message_content.get('title', 'No Title'),
                        description=session.message_content.get('description', 'No Description'),
                        color=int(session.message_content.get('color', '3498db'), 16)
                    )
                    if session.message_content.get('footer'):
                        dm_embed.set_footer(text=session.message_content['footer'])
                    if session.message_content.get('thumbnail'):
                        dm_embed.set_thumbnail(url=session.message_content['thumbnail'])
                    
                    await user.send(embed=dm_embed)
                else:
                    await user.send(session.message_content['content'])
                
                success_count += 1
                await asyncio.sleep(1)  # Rate limit protection
                
            except Exception as e:
                failed_count += 1
                failed_users.append(f"{user.display_name} ({user.id})")
        
        # Final report
        result_embed = discord.Embed(
            title="📊 Message Sending Complete",
            color=0x2ecc71 if failed_count == 0 else 0xf39c12
        )
        
        result_embed.add_field(
            name="✅ Successful",
            value=f"{success_count} messages sent",
            inline=True
        )
        
        result_embed.add_field(
            name="❌ Failed",
            value=f"{failed_count} messages failed",
            inline=True
        )
        
        if failed_users:
            failed_list = "\n".join(failed_users[:10])  # Show first 10 failed users
            if len(failed_users) > 10:
                failed_list += f"\n... and {len(failed_users) - 10} more"
            
            result_embed.add_field(
                name="Failed Users",
                value=f"```{failed_list}```",
                inline=False
            )
        
        await interaction.edit_original_response(embed=result_embed, view=None)
        
        # Clean up session
        if self.user_id in user_sessions:
            del user_sessions[self.user_id]

    @discord.ui.button(label='✏️ Edit Message', style=discord.ButtonStyle.secondary, emoji='✏️')
    async def edit_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This interaction is not for you!", ephemeral=True)
            return
        
        session = user_sessions.get(self.user_id)
        if session:
            # Reset to message type selection
            session.step = 'message_type'
            session.message_content = {}
            
            embed = discord.Embed(
                title="💬 Message Configuration",
                description="Choose how you want to format your message:",
                color=0x3498db
            )
            
            view = MessageTypeView(self.user_id)
            await interaction.response.edit_message(embed=embed, view=view)

    @discord.ui.button(label='❌ Cancel', style=discord.ButtonStyle.danger, emoji='❌')
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ This interaction is not for you!", ephemeral=True)
            return
        
        if self.user_id in user_sessions:
            del user_sessions[self.user_id]
        
        embed = discord.Embed(
            title="❌ Operation Cancelled",
            description="The DM operation has been cancelled.",
            color=0xe74c3c
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

def parse_targets(content, guild, target_type):
    """Parse roles or users from message content"""
    targets = []
    parts = content.split()
    
    for part in parts:
        part = part.strip()
        
        if target_type in ['single_role', 'multiple_roles']:
            # Try to parse as role
            role = None
            
            # Check if it's a role mention
            if part.startswith('<@&') and part.endswith('>'):
                role_id = part[3:-1]
                try:
                    role = guild.get_role(int(role_id))
                except ValueError:
                    continue
            
            # Check if it's a role ID
            elif part.isdigit():
                try:
                    role = guild.get_role(int(part))
                except ValueError:
                    continue
            
            # Check if it's a role name
            else:
                role = discord.utils.get(guild.roles, name=part)
            
            if role:
                targets.append(role)
        
        else:  # single_user or multiple_users
            # Try to parse as user
            user = None
            
            # Check if it's a user mention
            if part.startswith('<@') and part.endswith('>'):
                user_id = part[2:-1]
                if user_id.startswith('!'):
                    user_id = user_id[1:]
                try:
                    user = guild.get_member(int(user_id))
                except ValueError:
                    continue
            
            # Check if it's a user ID
            elif part.isdigit():
                try:
                    user = guild.get_member(int(part))
                except ValueError:
                    continue
            
            if user:
                targets.append(user)
    
    return targets

def is_valid_hex_color(color):
    """Check if a string is a valid hex color"""
    if not color:
        return False
    if color.startswith('#'):
        color = color[1:]
    return len(color) == 6 and all(c in '0123456789abcdefABCDEF' for c in color)

def is_valid_url(url):
    """Simple URL validation"""
    return url.startswith(('http://', 'https://'))

@bot.event
async def on_ready():
    print(f'✅ {bot.user} is ready!')
    print(f'🌐 Connected to {len(bot.guilds)} guilds')

@bot.command(name='send')
async def send_command(ctx):
    """Main command to start the DM sending process"""
    if not ctx.guild:
        await ctx.send("❌ This command can only be used in a server!")
        return
    
    # Check if user has permission (you can customize this)
    if not ctx.author.guild_permissions.manage_messages:
        await ctx.send("❌ You need 'Manage Messages' permission to use this command!")
        return
    
    # Create new session
    user_sessions[ctx.author.id] = DMSession(ctx.author.id, ctx.guild.id)
    
    embed = discord.Embed(
        title="🚀 DM Sender Bot",
        description="Welcome to the DM Sender! Choose your target type:",
        color=0x3498db
    )
    
    embed.add_field(
        name="📝 Role Options",
        value="• **Single Role** - Target one role\n• **Multiple Roles** - Target multiple roles",
        inline=True
    )
    
    embed.add_field(
        name="👤 User Options",
        value="• **Single User** - Target one user\n• **Multiple Users** - Target multiple users",
        inline=True
    )
    
    embed.set_footer(text="⏰ This menu will expire in 5 minutes")
    
    view = TargetSelectionView(ctx.author.id)
    await ctx.send(embed=embed, view=view)

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Check if user has an active session
    session = user_sessions.get(message.author.id)
    if not session:
        await bot.process_commands(message)
        return
    
    # Handle different steps
    if session.step == 'role_input':
        guild = bot.get_guild(session.guild_id)
        targets = parse_targets(message.content, guild, session.target_type)
        
        if not targets:
            embed = discord.Embed(
                title="❌ No Valid Roles Found",
                description="I couldn't find any valid roles from your input. Please try again with:\n\n" +
                           "• Role ID: `123456789`\n" +
                           "• Role mention: `@RoleName`\n" +
                           "• Role name: `RoleName`",
                color=0xe74c3c
            )
            await message.reply(embed=embed)
            return
        
        session.targets = targets
        session.step = 'message_type'
        
        # Count total members
        total_members = sum(len(role.members) for role in targets)
        unique_members = len(set(member for role in targets for member in role.members))
        
        embed = discord.Embed(
            title="✅ Roles Selected",
            description=f"**Selected Roles:** {', '.join(role.name for role in targets)}\n\n" +
                       f"**Total Role Members:** {total_members}\n" +
                       f"**Unique Members:** {unique_members}\n\n" +
                       "Now choose your message type:",
            color=0x2ecc71
        )
        
        view = MessageTypeView(message.author.id)
        await message.reply(embed=embed, view=view)
    
    elif session.step == 'user_input':
        guild = bot.get_guild(session.guild_id)
        targets = parse_targets(message.content, guild, session.target_type)
        
        if not targets:
            embed = discord.Embed(
                title="❌ No Valid Users Found",
                description="I couldn't find any valid users from your input. Please try again with:\n\n" +
                           "• User ID: `123456789`\n" +
                           "• User mention: `@Username`",
                color=0xe74c3c
            )
            await message.reply(embed=embed)
            return
        
        session.targets = targets
        session.step = 'message_type'
        
        embed = discord.Embed(
            title="✅ Users Selected",
            description=f"**Selected Users:** {', '.join(user.display_name for user in targets)}\n\n" +
                       f"**Total Users:** {len(targets)}\n\n" +
                       "Now choose your message type:",
            color=0x2ecc71
        )
        
        view = MessageTypeView(message.author.id)
        await message.reply(embed=embed, view=view)
    
    elif session.step == 'embed_title':
        if len(message.content) > 256:
            embed = discord.Embed(
                title="❌ Title Too Long",
                description="Embed titles must be 256 characters or less. Please try again.",
                color=0xe74c3c
            )
            await message.reply(embed=embed)
            return
        
        session.message_content['title'] = message.content
        session.step = 'embed_description'
        
        embed = discord.Embed(
            title="✨ Embed Description",
            description="Please provide the description for your embed:\n\n" +
                       "**Tips:**\n" +
                       "• Use `\\n` for line breaks\n" +
                       "• Maximum 4096 characters\n" +
                       "• You can use markdown formatting\n\n" +
                       "⏰ You have 5 minutes to respond.",
            color=0xf39c12
        )
        
        await message.reply(embed=embed)
    
    elif session.step == 'embed_description':
        if len(message.content) > 4096:
            embed = discord.Embed(
                title="❌ Description Too Long",
                description="Embed descriptions must be 4096 characters or less. Please try again.",
                color=0xe74c3c
            )
            await message.reply(embed=embed)
            return
        
        session.message_content['description'] = message.content.replace('\\n', '\n')
        session.step = 'embed_color'
        
        embed = discord.Embed(
            title="🎨 Embed Color",
            description="Please provide the color for your embed:\n\n" +
                       "**Options:**\n" +
                       "• Hex color: `#3498db` or `3498db`\n" +
                       "• Type `skip` to use default blue\n\n" +
                       "⏰ You have 5 minutes to respond.",
            color=0xf39c12
        )
        
        await message.reply(embed=embed)
    
    elif session.step == 'embed_color':
        if message.content.lower() == 'skip':
            session.message_content['color'] = '3498db'
        else:
            color = message.content.strip()
            if not is_valid_hex_color(color):
                embed = discord.Embed(
                    title="❌ Invalid Color",
                    description="Please provide a valid hex color (e.g., `#3498db` or `3498db`) or type `skip`.",
                    color=0xe74c3c
                )
                await message.reply(embed=embed)
                return
            
            if color.startswith('#'):
                color = color[1:]
            session.message_content['color'] = color
        
        session.step = 'embed_footer'
        
        embed = discord.Embed(
            title="📝 Embed Footer",
            description="Please provide the footer text for your embed:\n\n" +
                       "**Tips:**\n" +
                       "• Maximum 2048 characters\n" +
                       "• Type `skip` to have no footer\n\n" +
                       "⏰ You have 5 minutes to respond.",
            color=0xf39c12
        )
        
        await message.reply(embed=embed)
    
    elif session.step == 'embed_footer':
        if message.content.lower() != 'skip':
            if len(message.content) > 2048:
                embed = discord.Embed(
                    title="❌ Footer Too Long",
                    description="Embed footers must be 2048 characters or less. Please try again or type `skip`.",
                    color=0xe74c3c
                )
                await message.reply(embed=embed)
                return
            session.message_content['footer'] = message.content
        
        session.step = 'embed_thumbnail'
        
        embed = discord.Embed(
            title="🖼️ Embed Thumbnail",
            description="Please provide a thumbnail URL for your embed:\n\n" +
                       "**Tips:**\n" +
                       "• Must be a valid image URL (http/https)\n" +
                       "• Type `skip` to have no thumbnail\n\n" +
                       "⏰ You have 5 minutes to respond.",
            color=0xf39c12
        )
        
        await message.reply(embed=embed)
    
    elif session.step == 'embed_thumbnail':
        if message.content.lower() != 'skip':
            if not is_valid_url(message.content):
                embed = discord.Embed(
                    title="❌ Invalid URL",
                    description="Please provide a valid image URL (starting with http:// or https://) or type `skip`.",
                    color=0xe74c3c
                )
                await message.reply(embed=embed)
                return
            session.message_content['thumbnail'] = message.content
        
        session.step = 'confirmation'
        await show_confirmation(message.author.id, message.channel)
    
    elif session.step == 'text_content':
        if len(message.content) > 2000:
            embed = discord.Embed(
                title="❌ Message Too Long",
                description="Messages must be 2000 characters or less. Please try again.",
                color=0xe74c3c
            )
            await message.reply(embed=embed)
            return
        
        session.message_content['content'] = message.content.replace('\\n', '\n')
        session.step = 'confirmation'
        await show_confirmation(message.author.id, message.channel)
    
    else:
        await bot.process_commands(message)

async def show_confirmation(user_id, channel):
    """Show confirmation message with preview"""
    session = user_sessions.get(user_id)
    if not session:
        return
    
    embed = discord.Embed(
        title="🔍 Message Preview & Confirmation",
        description="Here's how your message will look:",
        color=0x3498db
    )
    
    # Add target information
    if session.target_type in ['single_role', 'multiple_roles']:
        target_names = [role.name for role in session.targets]
        total_members = sum(len(role.members) for role in session.targets)
        unique_members = len(set(member for role in session.targets for member in role.members))
        
        embed.add_field(
            name="🎯 Target Roles",
            value=f"**Roles:** {', '.join(target_names)}\n**Recipients:** {unique_members} unique members",
            inline=False
        )
    else:
        target_names = [user.display_name for user in session.targets]
        embed.add_field(
            name="🎯 Target Users",
            value=f"**Users:** {', '.join(target_names)}\n**Recipients:** {len(session.targets)}",
            inline=False
        )
    
    # Create preview
    if session.message_type == 'embed':
        preview_embed = discord.Embed(
            title=session.message_content.get('title', 'No Title'),
            description=session.message_content.get('description', 'No Description'),
            color=int(session.message_content.get('color', '3498db'), 16)
        )
        if session.message_content.get('footer'):
            preview_embed.set_footer(text=session.message_content['footer'])
        if session.message_content.get('thumbnail'):
            preview_embed.set_thumbnail(url=session.message_content['thumbnail'])
        
        embed.add_field(
            name="📋 Message Type",
            value="Rich Embed",
            inline=True
        )
        
        await channel.send(embed=embed)
        await channel.send("**Preview:**", embed=preview_embed)
    else:
        embed.add_field(
            name="📋 Message Type",
            value="Plain Text",
            inline=True
        )
        
        embed.add_field(
            name="📝 Message Content",
            value=f"```{session.message_content['content']}```",
            inline=False
        )
        
        await channel.send(embed=embed)
    
    # Send confirmation buttons
    confirmation_embed = discord.Embed(
        title="⚠️ Confirmation Required",
        description="Are you sure you want to send this message to all selected recipients?",
        color=0xf39c12
    )
    
    view = ConfirmationView(user_id)
    await channel.send(embed=confirmation_embed, view=view)

@bot.command(name='help')
async def help_command(ctx):
    """Show help information"""
    embed = discord.Embed(
        title="🚀 DM Sender Bot - Help",
        description="A powerful bot for sending DM messages to users or role members.",
        color=0x3498db
    )
    
    embed.add_field(
        name="📋 Commands",
        value="`-send` - Start the DM sending process\n`-help` - Show this help message",
        inline=False
    )
    
    embed.add_field(
        name="🎯 Target Types",
        value="• **Single Role** - Send to all members of one role\n" +
              "• **Multiple Roles** - Send to all members of multiple roles\n" +
              "• **Single User** - Send to one specific user\n" +
              "• **Multiple Users** - Send to multiple specific users",
        inline=False
    )
    
    embed.add_field(
        name="💬 Message Types",
        value="• **Rich Embed** - Formatted message with title, description, color, etc.\n" +
              "• **Plain Text** - Simple text message",
        inline=False
    )
    
    embed.add_field(
        name="🔒 Permissions",
        value="You need the 'Manage Messages' permission to use this bot.",
        inline=False
    )
    
    embed.set_footer(text="Created with ❤️ for your server")
    
    await ctx.send(embed=embed)

# Run the bot
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print("❌ Error: DISCORD_TOKEN environment variable not set!")
        exit(1)
    
    bot.run(TOKEN)