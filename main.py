import discord
from discord.ext import commands
import asyncio
import logging
import os
import json
import time
from datetime import datetime, timedelta, timezone
import random

# Set up logging
logging.basicConfig(level=logging.INFO)

# Bot configuration
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Store session data
active_sessions = {}
message_templates = {}
user_preferences = {}
send_statistics = {}

@bot.event
async def on_ready():
    print(f'Bot ready: {bot.user}')
    print(f'Guilds: {len(bot.guilds)}')
    await load_message_templates()
    await load_user_preferences()
    print('System ready')

async def load_message_templates():
    """Load predefined message templates"""
    global message_templates
    message_templates = {
        'announcement': {
            'title': '📢 Important Announcement',
            'color': 0x5865F2,
            'footer': 'Official Announcement System'
        },
        'event': {
            'title': '📅 Event Notification',
            'color': 0x00D4AA,
            'footer': 'Event Management System'
        },
        'urgent': {
            'title': '🚨 Urgent Notice',
            'color': 0xFF4444,
            'footer': 'Emergency Alert System'
        },
        'reminder': {
            'title': '⏰ Reminder',
            'color': 0xFFA500,
            'footer': 'Reminder Service'
        },
        'update': {
            'title': '🔄 System Update',
            'color': 0x9932CC,
            'footer': 'Update Notification'
        }
    }
    print(f'Loaded {len(message_templates)} templates')

async def load_user_preferences():
    """Load user messaging preferences"""
    global user_preferences
    user_preferences = {
        728201873366056992: {
            'preferred_design': 'professional',
            'confirmation_required': True,
            'batch_size': 10,
            'delay_between_batches': 2
        }
    }
    print('User preferences loaded')

class MessageSession:
    def __init__(self, user_id, channel_id, guild_id):
        self.user_id = user_id
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.session_id = f"{user_id}_{int(time.time())}"
        self.stage = 'target_selection'
        self.data = {
            'targets': [],
            'message_content': '',
            'template': None,
            'design': 'standard',
            'priority': 'normal',
            'batch_size': 10,
            'delay': 2,
            'confirmation_code': None
        }
        self.created_at = datetime.now(UTC)
        self.last_activity = datetime.now(UTC)

    def update_activity(self):
        self.last_activity = datetime.now(UTC)

    def is_expired(self):
        return datetime.now(UTC) - self.last_activity > timedelta(minutes=15)

class TargetSelectionView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=900)  # 15 minutes
        self.session = session

    @discord.ui.button(label='Select by Role', style=discord.ButtonStyle.primary, emoji='👥')
    async def select_by_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('This is not your session.', ephemeral=True)
            return
        
        await interaction.response.send_message('Please enter the role ID:', ephemeral=True)
        self.session.stage = 'awaiting_role_id'
        self.session.update_activity()

    @discord.ui.button(label='Select by Mentions', style=discord.ButtonStyle.secondary, emoji='@')
    async def select_by_mentions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('This is not your session.', ephemeral=True)
            return
        
        await interaction.response.send_message('Please mention the users in your next message:', ephemeral=True)
        self.session.stage = 'awaiting_mentions'
        self.session.update_activity()

    @discord.ui.button(label='Custom User List', style=discord.ButtonStyle.success, emoji='📝')
    async def select_custom_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('This is not your session.', ephemeral=True)
            return
        
        await interaction.response.send_message('Please enter user IDs separated by commas:', ephemeral=True)
        self.session.stage = 'awaiting_custom_list'
        self.session.update_activity()

class MessageDesignView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=900)
        self.session = session

    @discord.ui.button(label='Plain Text', style=discord.ButtonStyle.secondary, emoji='📝')
    async def plain_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_design(interaction, 'plain')

    @discord.ui.button(label='Standard Embed', style=discord.ButtonStyle.primary, emoji='📋')
    async def standard_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_design(interaction, 'standard')

    @discord.ui.button(label='Professional', style=discord.ButtonStyle.success, emoji='✨')
    async def professional_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_design(interaction, 'professional')

    @discord.ui.button(label='Alert Style', style=discord.ButtonStyle.danger, emoji='🚨')
    async def alert_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_design(interaction, 'alert')

    async def set_design(self, interaction, design):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('This is not your session.', ephemeral=True)
            return
        
        self.session.data['design'] = design
        self.session.stage = 'batch_settings'
        
        batch_view = BatchSettingsView(self.session)
        await interaction.response.edit_message(
            content=f'✅ Design set to: **{design}**\n\nNow configure batch settings:',
            view=batch_view
        )
        self.session.update_activity()

class BatchSettingsView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=900)
        self.session = session

    @discord.ui.button(label='Small (5 per batch)', style=discord.ButtonStyle.secondary, emoji='🔢')
    async def small_batch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 5)

    @discord.ui.button(label='Medium (10 per batch)', style=discord.ButtonStyle.primary, emoji='🔢')
    async def medium_batch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 10)

    @discord.ui.button(label='Large (20 per batch)', style=discord.ButtonStyle.success, emoji='🔢')
    async def large_batch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 20)

    @discord.ui.button(label='All at Once', style=discord.ButtonStyle.danger, emoji='⚡')
    async def all_at_once(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 999)

    async def set_batch_size(self, interaction, size):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('This is not your session.', ephemeral=True)
            return
        
        self.session.data['batch_size'] = size
        self.session.stage = 'delay_settings'
        
        delay_view = DelaySettingsView(self.session)
        await interaction.response.edit_message(
            content=f'✅ Batch size set to: **{size}**\n\nNow set delay between batches:',
            view=delay_view
        )
        self.session.update_activity()

class DelaySettingsView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=900)
        self.session = session

    @discord.ui.button(label='No Delay', style=discord.ButtonStyle.secondary, emoji='⚡')
    async def no_delay(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_delay(interaction, 0)

    @discord.ui.button(label='1 Second', style=discord.ButtonStyle.primary, emoji='1️⃣')
    async def one_second(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_delay(interaction, 1)

    @discord.ui.button(label='3 Seconds', style=discord.ButtonStyle.primary, emoji='3️⃣')
    async def three_seconds(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_delay(interaction, 3)

    @discord.ui.button(label='5 Seconds', style=discord.ButtonStyle.success, emoji='5️⃣')
    async def five_seconds(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_delay(interaction, 5)

    async def set_delay(self, interaction, delay):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('This is not your session.', ephemeral=True)
            return
        
        self.session.data['delay'] = delay
        self.session.stage = 'confirmation'
        
        # Generate confirmation code
        code = ''.join([str(random.randint(0, 9)) for _ in range(4)])
        self.session.data['confirmation_code'] = code
        
        await interaction.response.edit_message(
            content=f'✅ Delay set to: **{delay} seconds**\n\n🔐 **Confirmation required**\nType this code to proceed: **{code}**',
            view=None
        )
        self.session.update_activity()

class FinalConfirmationView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=900)
        self.session = session

    @discord.ui.button(label='✅ Send Messages', style=discord.ButtonStyle.success, emoji='🚀')
    async def send_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('This is not your session.', ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content='🚀 **Sending messages...**\nThis may take a while depending on the number of targets.',
            view=None
        )
        
        # Execute message sending
        success, failed = await execute_message_delivery(self.session)
        
        # Update statistics
        await update_send_statistics(self.session.user_id, success, failed)
        
        # Send completion message
        embed = discord.Embed(
            title='📊 Delivery Complete',
            color=0x00FF00 if failed == 0 else 0xFFA500,
            timestamp=datetime.now(UTC)
        )
        embed.add_field(name='✅ Successful', value=str(success), inline=True)
        embed.add_field(name='❌ Failed', value=str(failed), inline=True)
        embed.add_field(name='📈 Success Rate', value=f'{(success/(success+failed)*100):.1f}%' if success+failed > 0 else 'N/A', inline=True)
        
        await interaction.followup.send(embed=embed)
        
        # Clean up session
        if self.session.session_id in active_sessions:
            del active_sessions[self.session.session_id]

    @discord.ui.button(label='❌ Cancel', style=discord.ButtonStyle.danger, emoji='🛑')
    async def cancel_send(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('This is not your session.', ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content='❌ **Message delivery cancelled.**',
            view=None
        )
        
        # Clean up session
        if self.session.session_id in active_sessions:
            del active_sessions[self.session.session_id]

async def create_message_from_session(session):
    """Create the final message based on session data"""
    content = session.data['message_content']
    design = session.data['design']
    
    if design == 'plain':
        return {'type': 'text', 'content': content}
    
    elif design == 'standard':
        embed = discord.Embed(
            description=content,
            color=0x5865F2,
            timestamp=datetime.now(UTC)
        )
        return {'type': 'embed', 'embed': embed}
    
    elif design == 'professional':
        embed = discord.Embed(
            title='📢 Message',
            description=content,
            color=0x00D4AA,
            timestamp=datetime.now(UTC)
        )
        embed.set_footer(text='Professional Message System')
        return {'type': 'embed', 'embed': embed}
    
    elif design == 'alert':
        embed = discord.Embed(
            title='🚨 Important Alert',
            description=content,
            color=0xFF4444,
            timestamp=datetime.now(UTC)
        )
        embed.set_footer(text='Alert System')
        return {'type': 'embed', 'embed': embed}
    
    # Default fallback
    return {'type': 'text', 'content': content}

async def execute_message_delivery(session):
    """Execute the actual message delivery"""
    targets = session.data['targets']
    batch_size = session.data['batch_size']
    delay = session.data['delay']
    
    success_count = 0
    fail_count = 0
    
    print(f'Starting delivery for session {session.session_id}')
    print(f'Targets: {len(targets)}, Batch size: {batch_size}, Delay: {delay}s')
    
    # Create message
    message_data = await create_message_from_session(session)
    
    # Process in batches
    for i in range(0, len(targets), batch_size):
        batch = targets[i:i + batch_size]
        print(f'Processing batch {i//batch_size + 1}: {len(batch)} targets')
        
        for target in batch:
            try:
                if message_data['type'] == 'text':
                    await target.send(message_data['content'])
                else:
                    await target.send(embed=message_data['embed'])
                
                print(f'✅ Sent to {target.display_name}')
                success_count += 1
                await asyncio.sleep(0.5)  # Small delay between individual messages
                
            except discord.Forbidden:
                print(f'❌ DMs disabled: {target.display_name}')
                fail_count += 1
            except discord.HTTPException as e:
                print(f'❌ HTTP error for {target.display_name}: {e}')
                fail_count += 1
            except Exception as e:
                print(f'❌ Unexpected error for {target.display_name}: {e}')
                fail_count += 1
        
        # Delay between batches
        if i + batch_size < len(targets) and delay > 0:
            print(f'Waiting {delay}s before next batch...')
            await asyncio.sleep(delay)
    
    print(f'Delivery complete: {success_count} sent, {fail_count} failed')
    return success_count, fail_count

async def update_send_statistics(user_id, success, fail):
    """Update user sending statistics"""
    if user_id not in send_statistics:
        send_statistics[user_id] = {
            'total_sent': 0,
            'total_failed': 0,
            'sessions_completed': 0,
            'last_send': None
        }
    
    stats = send_statistics[user_id]
    stats['total_sent'] += success
    stats['total_failed'] += fail
    stats['sessions_completed'] += 1
    stats['last_send'] = datetime.now(UTC)

@bot.command(name='send')
async def send_message(ctx):
    """Start the message sending process"""
    # Authorization check
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('❌ You are not authorized to use this command.')
        return
    
    # Clean up expired sessions first
    await cleanup_expired_sessions()
    
    # Check for existing active session
    existing_session = None
    for session_id, session in active_sessions.items():
        if session.user_id == ctx.author.id:
            existing_session = session
            break
    
    if existing_session:
        embed = discord.Embed(
            title='⚠️ Active Session Found',
            description=f'You already have an active session: `{existing_session.session_id}`\n'
                       f'Stage: {existing_session.stage}\n'
                       f'Created: {existing_session.created_at.strftime("%H:%M:%S")}',
            color=0xFFA500
        )
        await ctx.send(embed=embed)
        return
    
    # Create new session
    session = MessageSession(ctx.author.id, ctx.channel.id, ctx.guild.id)
    active_sessions[session.session_id] = session
    
    # Create initial embed
    embed = discord.Embed(
        title='📨 Message Delivery System',
        description=f'Welcome to the advanced message delivery system!\n\n'
                   f'**Session ID:** `{session.session_id}`\n'
                   f'**Step 1:** Choose how to select message recipients',
        color=0x5865F2,
        timestamp=datetime.now(UTC)
    )
    
    embed.set_footer(text='Session will expire in 15 minutes of inactivity')
    
    # Start with target selection
    view = TargetSelectionView(session)
    await ctx.send(embed=embed, view=view)

@bot.event
async def on_message(message):
    """Handle text input during sessions"""
    if message.author.bot:
        return
    
    # Check if user has an active session
    user_session = None
    for session in active_sessions.values():
        if session.user_id == message.author.id and session.channel_id == message.channel.id:
            user_session = session
            break
    
    if not user_session:
        await bot.process_commands(message)
        return
    
    # Handle session input
    await handle_session_input(message, user_session)

async def handle_session_input(message, session):
    """Handle different types of session input"""
    stage = session.stage
    content = message.content.strip()
    
    try:
        if stage == 'awaiting_role_id':
            await handle_role_id_input(message, session, content)
        elif stage == 'awaiting_mentions':
            await handle_mentions_input(message, session)
        elif stage == 'awaiting_custom_list':
            await handle_custom_list_input(message, session, content)
        elif stage == 'awaiting_message_content':
            await handle_message_content_input(message, session, content)
        elif stage == 'confirmation':
            await handle_confirmation_code_input(message, session, content)
        else:
            await bot.process_commands(message)
    
    except Exception as e:
        await message.channel.send(f'❌ Error processing input: {str(e)}')
        print(f'Session error: {e}')

async def handle_role_id_input(message, session, role_id_str):
    """Handle role ID input"""
    try:
        role_id = int(role_id_str)
        role = message.guild.get_role(role_id)
        
        if not role:
            await message.reply('❌ Role not found. Please try again with a valid role ID.')
            return
        
        # Get role members (exclude bots)
        members = [member for member in role.members if not member.bot]
        
        if not members:
            await message.reply('❌ No valid members found in this role. Please try again.')
            return
        
        session.data['targets'] = members
        session.stage = 'awaiting_message_content'
        
        embed = discord.Embed(
            title='✅ Targets Selected',
            description=f'**Role:** {role.name}\n**Members:** {len(members)} users',
            color=0x00FF00
        )
        
        await message.reply(embed=embed)
        await message.channel.send('📝 **Step 2:** Please enter your message content:')
        session.update_activity()
        
    except ValueError:
        await message.reply('❌ Invalid role ID. Please enter numbers only.')

async def handle_mentions_input(message, session):
    """Handle mentioned users input"""
    mentioned_users = [user for user in message.mentions if not user.bot]
    
    if not mentioned_users:
        await message.reply('❌ No valid users mentioned. Please try again.')
        return
    
    session.data['targets'] = mentioned_users
    session.stage = 'awaiting_message_content'
    
    embed = discord.Embed(
        title='✅ Targets Selected',
        description=f'**Mentioned Users:** {len(mentioned_users)} users',
        color=0x00FF00
    )
    
    # Show first few users
    user_list = ', '.join([user.display_name for user in mentioned_users[:5]])
    if len(mentioned_users) > 5:
        user_list += f' and {len(mentioned_users) - 5} more...'
    embed.add_field(name='Users', value=user_list, inline=False)
    
    await message.reply(embed=embed)
    await message.channel.send('📝 **Step 2:** Please enter your message content:')
    session.update_activity()

async def handle_custom_list_input(message, session, user_ids_str):
    """Handle custom user ID list input"""
    try:
        user_ids = [int(uid.strip()) for uid in user_ids_str.split(',') if uid.strip()]
        users = []
        
        for user_id in user_ids:
            try:
                user = await bot.fetch_user(user_id)
                if user and not user.bot:
                    users.append(user)
            except:
                continue
        
        if not users:
            await message.reply('❌ No valid users found. Please check the user IDs and try again.')
            return
        
        session.data['targets'] = users
        session.stage = 'awaiting_message_content'
        
        embed = discord.Embed(
            title='✅ Targets Selected',
            description=f'**Custom List:** {len(users)} users found',
            color=0x00FF00
        )
        
        await message.reply(embed=embed)
        await message.channel.send('📝 **Step 2:** Please enter your message content:')
        session.update_activity()
        
    except ValueError:
        await message.reply('❌ Invalid format. Please use: `123456789, 987654321, 555666777`')

async def handle_message_content_input(message, session, content):
    """Handle message content input"""
    if len(content) > 2000:
        await message.reply('❌ Message too long (max 2000 characters). Please shorten your message.')
        return
    
    if not content:
        await message.reply('❌ Message cannot be empty. Please enter your message.')
        return
    
    session.data['message_content'] = content
    session.stage = 'design_selection'
    
    embed = discord.Embed(
        title='✅ Message Content Set',
        description=f'**Length:** {len(content)} characters',
        color=0x00FF00
    )
    
    # Show preview
    preview = content[:200] + '...' if len(content) > 200 else content
    embed.add_field(name='Preview', value=f'```{preview}```', inline=False)
    
    await message.reply(embed=embed)
    
    # Move to design selection
    design_view = MessageDesignView(session)
    await message.channel.send('🎨 **Step 3:** Choose your message design:', view=design_view)
    session.update_activity()

async def handle_confirmation_code_input(message, session, code):
    """Handle confirmation code input"""
    expected_code = session.data.get('confirmation_code')
    
    if code != expected_code:
        await message.reply(f'❌ Incorrect code. Expected: **{expected_code}**')
        return
    
    session.stage = 'final_confirmation'
    
    # Create summary
    targets_count = len(session.data['targets'])
    content_length = len(session.data['message_content'])
    design = session.data['design']
    batch_size = session.data['batch_size']
    delay = session.data['delay']
    
    embed = discord.Embed(
        title='📋 Final Summary',
        description='Please review your message settings before sending:',
        color=0x5865F2,
        timestamp=datetime.now(UTC)
    )
    
    embed.add_field(name='👥 Targets', value=str(targets_count), inline=True)
    embed.add_field(name='📝 Message Length', value=f'{content_length} chars', inline=True)
    embed.add_field(name='🎨 Design', value=design.title(), inline=True)
    embed.add_field(name='📦 Batch Size', value=str(batch_size), inline=True)
    embed.add_field(name='⏱️ Delay', value=f'{delay}s', inline=True)
    embed.add_field(name='📊 Est. Time', value=f'{(targets_count/batch_size)*delay:.1f}s', inline=True)
    
    # Show message preview
    message_data = await create_message_from_session(session)
    
    view = FinalConfirmationView(session)
    
    if message_data['type'] == 'embed':
        await message.reply(embed=embed)
        await message.channel.send('**Message Preview:**', embed=message_data['embed'], view=view)
    else:
        await message.reply(embed=embed)
        await message.channel.send(f'**Message Preview:**\n```{message_data["content"]}```', view=view)
    
    session.update_activity()

async def cleanup_expired_sessions():
    """Clean up expired sessions"""
    current_time = datetime.now(UTC)
    expired_sessions = []
    
    for session_id, session in list(active_sessions.items()):
        if session.is_expired():
            expired_sessions.append(session_id)
            del active_sessions[session_id]
    
    if expired_sessions:
        print(f'Cleaned up {len(expired_sessions)} expired sessions')

@bot.command(name='sessions')
async def list_sessions(ctx):
    """List active sessions"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('❌ You are not authorized to use this command.')
        return
    
    await cleanup_expired_sessions()
    
    if not active_sessions:
        await ctx.send('📭 No active sessions.')
        return
    
    embed = discord.Embed(
        title='📊 Active Sessions',
        color=0x5865F2,
        timestamp=datetime.now(UTC)
    )
    
    for session_id, session in active_sessions.items():
        user = bot.get_user(session.user_id)
        username = user.display_name if user else 'Unknown User'
        
        embed.add_field(
            name=f'Session: {session_id}',
            value=f'**User:** {username}\n'
                  f'**Stage:** {session.stage}\n'
                  f'**Targets:** {len(session.data.get("targets", []))}\n'
                  f'**Created:** {session.created_at.strftime("%H:%M:%S")}',
            inline=True
        )
    
    await ctx.send(embed=embed)

@bot.command(name='stats')
async def show_stats(ctx):
    """Show user statistics"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('❌ You are not authorized to use this command.')
        return
    
    user_id = ctx.author.id
    
    if user_id not in send_statistics:
        await ctx.send('📊 No statistics available yet.')
        return
    
    stats = send_statistics[user_id]
    
    embed = discord.Embed(
        title='📈 Your Statistics',
        color=0x00D4AA,
        timestamp=datetime.now(UTC)
    )
    
    total_attempts = stats['total_sent'] + stats['total_failed']
    success_rate = (stats['total_sent'] / total_attempts * 100) if total_attempts > 0 else 0
    
    embed.add_field(name='✅ Messages Sent', value=str(stats['total_sent']), inline=True)
    embed.add_field(name='❌ Failed Deliveries', value=str(stats['total_failed']), inline=True)
    embed.add_field(name='📊 Success Rate', value=f'{success_rate:.1f}%', inline=True)
    embed.add_field(name='🎯 Sessions Completed', value=str(stats['sessions_completed']), inline=True)
    
    if stats['last_send']:
        embed.add_field(name='🕒 Last Activity', value=stats['last_send'].strftime('%Y-%m-%d %H:%M:%S UTC'), inline=True)
    
    embed.add_field(name='📈 Total Attempts', value=str(total_attempts), inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='cancel')
async def cancel_session(ctx):
    """Cancel active session"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('❌ You are not authorized to use this command.')
        return
    
    # Find user's active session
    user_session = None
    for session_id, session in list(active_sessions.items()):
        if session.user_id == ctx.author.id:
            user_session = session
            del active_sessions[session_id]
            break
    
    if user_session:
        embed = discord.Embed(
            title='✅ Session Cancelled',
            description=f'Session `{user_session.session_id}` has been cancelled.',
            color=0xFF4444
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send('❌ No active session found to cancel.')

@bot.command(name='help_send')
async def help_command(ctx):
    """Show help information"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('❌ You are not authorized to use this command.')
        return
    
    embed = discord.Embed(
        title='🤖 Message Delivery System - Help',
        description='Advanced Discord message delivery system with batch processing and rate limiting.',
        color=0x5865F2,
        timestamp=datetime.now(UTC)
    )
    
    embed.add_field(
        name='📨 Commands',
        value='`!send` - Start message delivery process\n'
              '`!sessions` - List active sessions\n'
              '`!stats` - Show your statistics\n'
              '`!cancel` - Cancel active session\n'
              '`!help_send` - Show this help',
        inline=False
    )
    
    embed.add_field(
        name='🎯 Target Selection',
        value='• **By Role** - Select all members of a role\n'
              '• **By Mentions** - Mention users directly\n'
              '• **Custom List** - Provide user IDs',
        inline=False
    )
    
    embed.add_field(
        name='🎨 Message Designs',
        value='• **Plain Text** - Simple text message\n'
              '• **Standard Embed** - Basic embed format\n'
              '• **Professional** - Polished embed with branding\n'
              '• **Alert Style** - Red alert embed for urgent messages',
        inline=False
    )
    
    embed.add_field(
        name='📦 Batch Processing',
        value='• **Small** - 5 messages per batch\n'
              '• **Medium** - 10 messages per batch\n'
              '• **Large** - 20 messages per batch\n'
              '• **All at Once** - No batching (use carefully)',
        inline=False
    )
    
    embed.add_field(
        name='⚠️ Important Notes',
        value='• Sessions expire after 15 minutes of inactivity\n'
              '• Confirmation code required before sending\n'
              '• Failed deliveries are tracked (usually DMs disabled)\n'
              '• Rate limiting prevents Discord API abuse',
        inline=False
    )
    
    embed.set_footer(text='Professional Message Delivery System')
    
    await ctx.send(embed=embed)

@bot.command(name='template')
async def create_template(ctx, template_name: str = None, *, template_content: str = None):
    """Create or list message templates"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('❌ You are not authorized to use this command.')
        return
    
    if not template_name:
        # List existing templates
        embed = discord.Embed(
            title='📋 Message Templates',
            description='Available message templates:',
            color=0x9932CC
        )
        
        for name, template in message_templates.items():
            embed.add_field(
                name=f'🏷️ {name}',
                value=f"**Title:** {template['title']}\n**Footer:** {template['footer']}",
                inline=True
            )
        
        embed.set_footer(text='Use !template <name> <content> to create new template')
        await ctx.send(embed=embed)
        return
    
    if not template_content:
        await ctx.send('❌ Please provide template content. Usage: `!template <name> <content>`')
        return
    
    # Create new template
    message_templates[template_name.lower()] = {
        'title': f'📢 {template_name.title()}',
        'color': 0x5865F2,
        'footer': f'{template_name.title()} Template',
        'content': template_content
    }
    
    embed = discord.Embed(
        title='✅ Template Created',
        description=f'Template `{template_name}` has been created successfully.',
        color=0x00FF00
    )
    embed.add_field(name='Content Preview', value=template_content[:100] + '...' if len(template_content) > 100 else template_content, inline=False)
    
    await ctx.send(embed=embed)

@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f'❌ Missing required argument: `{error.param.name}`')
    
    elif isinstance(error, commands.BadArgument):
        await ctx.send(f'❌ Invalid argument provided: {str(error)}')
    
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f'❌ Command is on cooldown. Try again in {error.retry_after:.1f} seconds.')
    
    else:
        print(f'Command error: {error}')
        await ctx.send('❌ An unexpected error occurred. Please try again.')

# Background task to clean up expired sessions
@bot.event
async def setup_background_tasks():
    """Set up background maintenance tasks"""
    while not bot.is_closed():
        try:
            await cleanup_expired_sessions()
            await asyncio.sleep(300)  # Clean up every 5 minutes
        except Exception as e:
            print(f'Background task error: {e}')
            await asyncio.sleep(60)

# Start background tasks when bot is ready
@bot.event
async def on_ready():
    print(f'Bot ready: {bot.user}')
    print(f'Guilds: {len(bot.guilds)}')
    await load_message_templates()
    await load_user_preferences()
    print('System ready')
    
    # Start background tasks
    bot.loop.create_task(setup_background_tasks())

# Enhanced error handling for message sending
async def safe_send_message(target, message_data):
    """Safely send message with comprehensive error handling"""
    try:
        if message_data['type'] == 'text':
            await target.send(message_data['content'])
        else:
            await target.send(embed=message_data['embed'])
        return True, None
    
    except discord.Forbidden:
        return False, 'DMs disabled'
    except discord.HTTPException as e:
        return False, f'HTTP error: {e.code}'
    except discord.NotFound:
        return False, 'User not found'
    except Exception as e:
        return False, f'Unexpected error: {str(e)}'

# Data persistence functions
async def save_user_data():
    """Save user preferences and statistics to file"""
    try:
        data = {
            'user_preferences': user_preferences,
            'send_statistics': send_statistics,
            'message_templates': message_templates
        }
        
        # Convert datetime objects to strings for JSON serialization
        for user_id, stats in data['send_statistics'].items():
            if stats.get('last_send'):
                stats['last_send'] = stats['last_send'].isoformat()
        
        with open('bot_data.json', 'w') as f:
            json.dump(data, f, indent=2)
        
        print('User data saved successfully')
        
    except Exception as e:
        print(f'Error saving user data: {e}')

async def load_user_data():
    """Load user preferences and statistics from file"""
    try:
        if os.path.exists('bot_data.json'):
            with open('bot_data.json', 'r') as f:
                data = json.load(f)
            
            global user_preferences, send_statistics, message_templates
            
            user_preferences.update(data.get('user_preferences', {}))
            send_statistics.update(data.get('send_statistics', {}))
            message_templates.update(data.get('message_templates', {}))
            
            # Convert datetime strings back to datetime objects
            for user_id, stats in send_statistics.items():
                if stats.get('last_send'):
                    stats['last_send'] = datetime.fromisoformat(stats['last_send'])
            
            print('User data loaded successfully')
        else:
            print('No existing data file found')
            
    except Exception as e:
        print(f'Error loading user data: {e}')

# Graceful shutdown
@bot.event
async def on_disconnect():
    """Handle bot disconnect"""
    print('Bot disconnected, saving data...')
    await save_user_data()

# Run the bot
async def main():
    """Main function to run the bot"""
    # Load existing data on startup
    await load_user_data()
    
    # Get bot token from environment variable
    bot_token = os.getenv('DISCORD_TOKEN')
    
    if not bot_token:
        print('Error: DISCORD_BOT_TOKEN environment variable not set')
        return
    
    try:
        await bot.start(bot_token)
    except discord.LoginFailure:
        print('Error: Invalid bot token')
    except Exception as e:
        print(f'Error starting bot: {e}')
    finally:
        # Save data on exit
        await save_user_data()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('\nBot stopped by user')
    except Exception as e:
        print(f'Fatal error: {e}')
