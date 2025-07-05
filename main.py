import discord
from discord.ext import commands
import asyncio
import logging
import os
import json
import time
from datetime import datetime, timedelta, timezone
UTC = timezone.utc
import random

# Set up logging
logging.basicConfig(level=logging.INFO)

# Bot configuration
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='-', intents=intents)

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
    bot.loop.create_task(cleanup_task())  # ADD THIS LINE
    print('System ready')

async def load_message_templates():
    """Load predefined message templates"""
    global message_templates
    message_templates = {
        'announcement': {
            'title': 'announcement',
            'color': 0x5865F2,
            'footer': 'announcement system'
        },
        'event': {
            'title': 'event notification',
            'color': 0x00D4AA,
            'footer': 'event system'
        },
        'urgent': {
            'title': 'urgent notice',
            'color': 0xFF4444,
            'footer': 'emergency system'
        },
        'reminder': {
            'title': 'reminder',
            'color': 0xFFA500,
            'footer': 'reminder service'
        },
        'update': {
            'title': 'system update',
            'color': 0x9932CC,
            'footer': 'update notification'
        }
    }
    print(f'loaded {len(message_templates)} templates')

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
    print('user preferences loaded')

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

    @discord.ui.button(label='select by role', style=discord.ButtonStyle.primary)
    async def select_by_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        await interaction.response.send_message('enter role id:', ephemeral=True)
        self.session.stage = 'awaiting_role_id'
        self.session.update_activity()

    @discord.ui.button(label='select by mentions', style=discord.ButtonStyle.secondary)
    async def select_by_mentions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        await interaction.response.send_message('mention users in next message:', ephemeral=True)
        self.session.stage = 'awaiting_mentions'
        self.session.update_activity()

    @discord.ui.button(label='custom user list', style=discord.ButtonStyle.success)
    async def select_custom_list(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        await interaction.response.send_message('enter user ids separated by commas:', ephemeral=True)
        self.session.stage = 'awaiting_custom_list'
        self.session.update_activity()

class MessageDesignView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=900)
        self.session = session

    @discord.ui.button(label='plain text', style=discord.ButtonStyle.secondary)
    async def plain_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_design(interaction, 'plain')

    @discord.ui.button(label='standard embed', style=discord.ButtonStyle.primary)
    async def standard_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_design(interaction, 'standard')

    @discord.ui.button(label='professional', style=discord.ButtonStyle.success)
    async def professional_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_design(interaction, 'professional')

    @discord.ui.button(label='alert style', style=discord.ButtonStyle.danger)
    async def alert_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_design(interaction, 'alert')

    async def set_design(self, interaction, design):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        self.session.data['design'] = design
        self.session.stage = 'batch_settings'
        
        batch_view = BatchSettingsView(self.session)
        await interaction.response.edit_message(
            content=f'design set to: {design}\n\nconfigure batch settings:',
            view=batch_view
        )
        self.session.update_activity()

class BatchSettingsView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=900)
        self.session = session

    @discord.ui.button(label='small (5 per batch)', style=discord.ButtonStyle.secondary)
    async def small_batch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 5)

    @discord.ui.button(label='medium (10 per batch)', style=discord.ButtonStyle.primary)
    async def medium_batch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 10)

    @discord.ui.button(label='large (20 per batch)', style=discord.ButtonStyle.success)
    async def large_batch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 20)

    @discord.ui.button(label='all at once', style=discord.ButtonStyle.danger)
    async def all_at_once(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 999)

    async def set_batch_size(self, interaction, size):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        self.session.data['batch_size'] = size
        self.session.stage = 'delay_settings'
        
        delay_view = DelaySettingsView(self.session)
        await interaction.response.edit_message(
            content=f'batch size set to: {size}\n\nset delay between batches:',
            view=delay_view
        )
        self.session.update_activity()

class DelaySettingsView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=900)
        self.session = session

    @discord.ui.button(label='no delay', style=discord.ButtonStyle.secondary)
    async def no_delay(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_delay(interaction, 0)

    @discord.ui.button(label='1 second', style=discord.ButtonStyle.primary)
    async def one_second(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_delay(interaction, 1)

    @discord.ui.button(label='3 seconds', style=discord.ButtonStyle.primary)
    async def three_seconds(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_delay(interaction, 3)

    @discord.ui.button(label='5 seconds', style=discord.ButtonStyle.success)
    async def five_seconds(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_delay(interaction, 5)

    async def set_delay(self, interaction, delay):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        self.session.data['delay'] = delay
        self.session.stage = 'confirmation'
        
        # Generate confirmation code
        code = ''.join([str(random.randint(0, 9)) for _ in range(4)])
        self.session.data['confirmation_code'] = code
        
        await interaction.response.edit_message(
            content=f'delay set to: {delay} seconds\n\nconfirmation required\ntype this code to proceed: {code}',
            view=None
        )
        self.session.update_activity()

class FinalConfirmationView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=900)
        self.session = session

    @discord.ui.button(label='send messages', style=discord.ButtonStyle.success)
    async def send_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content='sending messages...\nthis may take a while',
            view=None
        )
        
        # Execute message sending
        success, failed = await execute_message_delivery(self.session)
        
        # Update statistics
        await update_send_statistics(self.session.user_id, success, failed)
        
        # Send completion message
        embed = discord.Embed(
            title='delivery complete',
            color=0x00FF00 if failed == 0 else 0xFFA500,
            timestamp=datetime.now(UTC)
        )
        embed.add_field(name='successful', value=str(success), inline=True)
        embed.add_field(name='failed', value=str(failed), inline=True)
        embed.add_field(name='success rate', value=f'{(success/(success+failed)*100):.1f}%' if success+failed > 0 else 'n/a', inline=True)
        
        await interaction.followup.send(embed=embed)
        
        # Clean up session
        if self.session.session_id in active_sessions:
            del active_sessions[self.session.session_id]

    @discord.ui.button(label='cancel', style=discord.ButtonStyle.danger)
    async def cancel_send(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content='message delivery cancelled',
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
            title='message',
            description=content,
            color=0x00D4AA,
            timestamp=datetime.now(UTC)
        )
        embed.set_footer(text='professional message system')
        return {'type': 'embed', 'embed': embed}
    
    elif design == 'alert':
        embed = discord.Embed(
            title='important alert',
            description=content,
            color=0xFF4444,
            timestamp=datetime.now(UTC)
        )
        embed.set_footer(text='alert system')
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
    
    print(f'starting delivery for session {session.session_id}')
    print(f'targets: {len(targets)}, batch size: {batch_size}, delay: {delay}s')
    
    # Create message
    message_data = await create_message_from_session(session)
    
    # Process in batches
    for i in range(0, len(targets), batch_size):
        batch = targets[i:i + batch_size]
        print(f'processing batch {i//batch_size + 1}: {len(batch)} targets')
        
        for target in batch:
            try:
                if message_data['type'] == 'text':
                    await target.send(message_data['content'])
                else:
                    await target.send(embed=message_data['embed'])
                
                print(f'sent to {target.display_name}')
                success_count += 1
                await asyncio.sleep(0.5)  # Small delay between individual messages
                
            except discord.Forbidden:
                print(f'dms disabled: {target.display_name}')
                fail_count += 1
            except discord.HTTPException as e:
                print(f'http error for {target.display_name}: {e}')
                fail_count += 1
            except Exception as e:
                print(f'unexpected error for {target.display_name}: {e}')
                fail_count += 1
        
        # Delay between batches
        if i + batch_size < len(targets) and delay > 0:
            print(f'waiting {delay}s before next batch...')
            await asyncio.sleep(delay)
    
    print(f'delivery complete: {success_count} sent, {fail_count} failed')
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
        await ctx.send('not authorized')
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
            title='active session found',
            description=f'session: {existing_session.session_id}\n'
                       f'stage: {existing_session.stage}\n'
                       f'created: {existing_session.created_at.strftime("%H:%M:%S")}',
            color=0xFFA500
        )
        await ctx.send(embed=embed)
        return
    
    # Create new session
    session = MessageSession(ctx.author.id, ctx.channel.id, ctx.guild.id)
    active_sessions[session.session_id] = session
    
    # Create initial embed
    embed = discord.Embed(
        title='message delivery system',
        description=f'session id: {session.session_id}\n\nchoose how to select recipients',
        color=0x5865F2,
        timestamp=datetime.now(UTC)
    )
    
    embed.set_footer(text='session expires in 15 minutes')
    
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
        await message.channel.send(f'error processing input: {str(e)}')
        print(f'session error: {e}')

async def handle_role_id_input(message, session, role_id_str):
    """Handle role ID input"""
    try:
        role_id = int(role_id_str)
        role = message.guild.get_role(role_id)
        
        if not role:
            await message.reply('role not found. try again with valid role id')
            return
        
        # Get role members (exclude bots)
        members = [member for member in role.members if not member.bot]
        
        if not members:
            await message.reply('no valid members found in role. try again')
            return
        
        session.data['targets'] = members
        session.stage = 'awaiting_message_content'
        
        embed = discord.Embed(
            title='targets selected',
            description=f'role: {role.name}\nmembers: {len(members)} users',
            color=0x00FF00
        )
        
        await message.reply(embed=embed)
        await message.channel.send('enter your message content:')
        session.update_activity()
        
    except ValueError:
        await message.reply('invalid role id. numbers only')

async def handle_mentions_input(message, session):
    """Handle mentioned users input"""
    mentioned_users = [user for user in message.mentions if not user.bot]
    
    if not mentioned_users:
        await message.reply('no valid users mentioned. try again')
        return
    
    session.data['targets'] = mentioned_users
    session.stage = 'awaiting_message_content'
    
    embed = discord.Embed(
        title='targets selected',
        description=f'mentioned users: {len(mentioned_users)} users',
        color=0x00FF00
    )
    
    # Show first few users
    user_list = ', '.join([user.display_name for user in mentioned_users[:5]])
    if len(mentioned_users) > 5:
        user_list += f' and {len(mentioned_users) - 5} more'
    embed.add_field(name='users', value=user_list, inline=False)
    
    await message.reply(embed=embed)
    await message.channel.send('enter your message content:')
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
            await message.reply('no valid users found. check user ids and try again')
            return
        
        session.data['targets'] = users
        session.stage = 'awaiting_message_content'
        
        embed = discord.Embed(
            title='targets selected',
            description=f'custom list: {len(users)} users found',
            color=0x00FF00
        )
        
        await message.reply(embed=embed)
        await message.channel.send('enter your message content:')
        session.update_activity()
        
    except ValueError:
        await message.reply('invalid format. use: 123456789, 987654321, 555666777')

async def handle_message_content_input(message, session, content):
    """Handle message content input"""
    if len(content) > 2000:
        await message.reply('message too long (max 2000 characters). shorten your message')
        return
    
    if not content:
        await message.reply('message cannot be empty. enter your message')
        return
    
    session.data['message_content'] = content
    session.stage = 'design_selection'
    
    embed = discord.Embed(
        title='message content set',
        description=f'length: {len(content)} characters',
        color=0x00FF00
    )
    
    # Show preview
    preview = content[:200] + '...' if len(content) > 200 else content
    embed.add_field(name='preview', value=f'```{preview}```', inline=False)
    
    await message.reply(embed=embed)
    
    # Move to design selection
    design_view = MessageDesignView(session)
    await message.channel.send('choose your message design:', view=design_view)
    session.update_activity()

async def handle_confirmation_code_input(message, session, code):
    """Handle confirmation code input"""
    expected_code = session.data.get('confirmation_code')
    
    if code != expected_code:
        await message.reply(f'incorrect code. expected: {expected_code}')
        return
    
    session.stage = 'final_confirmation'
    
    # Create summary
    targets_count = len(session.data['targets'])
    content_length = len(session.data['message_content'])
    design = session.data['design']
    batch_size = session.data['batch_size']
    delay = session.data['delay']
    
    embed = discord.Embed(
        title='final summary',
        description='review your message settings before sending:',
        color=0x5865F2,
        timestamp=datetime.now(UTC)
    )
    
    embed.add_field(name='targets', value=str(targets_count), inline=True)
    embed.add_field(name='message length', value=f'{content_length} chars', inline=True)
    embed.add_field(name='design', value=design, inline=True)
    embed.add_field(name='batch size', value=str(batch_size), inline=True)
    embed.add_field(name='delay', value=f'{delay}s', inline=True)
    embed.add_field(name='est time', value=f'{(targets_count/batch_size)*delay:.1f}s', inline=True)
    
    # Show message preview
    message_data = await create_message_from_session(session)
    
    view = FinalConfirmationView(session)
    
    if message_data['type'] == 'embed':
        await message.reply(embed=embed)
        await message.channel.send('message preview:', embed=message_data['embed'], view=view)
    else:
        await message.reply(embed=embed)
        await message.channel.send(f'message preview:\n```{message_data["content"]}```', view=view)
    
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
        print(f'cleaned up {len(expired_sessions)} expired sessions')

@bot.command(name='sessions')
async def list_sessions(ctx):
    """List active sessions"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    await cleanup_expired_sessions()
    
    if not active_sessions:
        await ctx.send('no active sessions')
        return
    
    embed = discord.Embed(
        title='active sessions',
        color=0x5865F2,
        timestamp=datetime.now(UTC)
    )
    
    for session_id, session in active_sessions.items():
        user = bot.get_user(session.user_id)
        username = user.display_name if user else 'unknown user'
        
        embed.add_field(
            name=f'session: {session_id}',
            value=f'user: {username}\n'
                  f'stage: {session.stage}\n'
                  f'targets: {len(session.data.get("targets", []))}\n'
                  f'created: {session.created_at.strftime("%H:%M:%S")}',
            inline=True
        )
    
    await ctx.send(embed=embed)

@bot.command(name='stats')
async def show_stats(ctx):
    """Show user statistics"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    user_id = ctx.author.id
    
    if user_id not in send_statistics:
        await ctx.send('no statistics available yet')
        return
    
    stats = send_statistics[user_id]
    
    embed = discord.Embed(
        title='your statistics',
        color=0x00D4AA,
        timestamp=datetime.now(UTC)
    )
    
    total_attempts = stats['total_sent'] + stats['total_failed']
    success_rate = (stats['total_sent'] / total_attempts * 100) if total_attempts > 0 else 0
    
    embed.add_field(name='messages sent', value=str(stats['total_sent']), inline=True)
    embed.add_field(name='failed deliveries', value=str(stats['total_failed']), inline=True)
    embed.add_field(name='success rate', value=f'{success_rate:.1f}%', inline=True)
    embed.add_field(name='sessions completed', value=str(stats['sessions_completed']), inline=True)
    
    if stats['last_send']:
        embed.add_field(name='last activity', value=stats['last_send'].strftime('%Y-%m-%d %H:%M:%S UTC'), inline=True)
    
    embed.add_field(name='total attempts', value=str(total_attempts), inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='cancel')
async def cancel_session(ctx):
    """Cancel active session"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
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
            title='session cancelled',
            description=f'session {user_session.session_id} has been cancelled',
            color=0xFF4444
        )
        await ctx.send(embed=embed)
    else:
        await ctx.send('no active session found to cancel')

@bot.command(name='help_send')
async def help_command(ctx):
    """Show help information"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    embed = discord.Embed(
        title='message delivery system help',
        description='discord message delivery system with batch processing',
        color=0x5865F2,
        timestamp=datetime.now(UTC)
    )
    
    embed.add_field(
        name='commands',
        value='!send - start message delivery\n'
              '!sessions - list active sessions\n'
              '!stats - show your statistics\n'
              '!cancel - cancel active session\n'
              '!help_send - show this help',
        inline=False
    )
    
    embed.add_field(
        name='process flow',
        value='1. select recipients (role/mentions/custom)\n'
              '2. enter message content\n'
              '3. choose design style\n'
              '4. configure batch settings\n'
              '5. set delivery delay\n'
              '6. confirm with code\n'
              '7. final confirmation & send',
        inline=False
    )
    
    embed.add_field(
        name='features',
        value='• role-based targeting\n'
              '• mention-based targeting\n'
              '• custom user lists\n'
              '• batch processing\n'
              '• delivery delays\n'
              '• multiple design styles\n'
              '• confirmation system\n'
              '• statistics tracking',
        inline=False
    )
    
    embed.add_field(
        name='design styles',
        value='• plain text\n'
              '• standard embed\n'
              '• professional\n'
              '• alert style',
        inline=True
    )
    
    embed.add_field(
        name='batch sizes',
        value='• small (5 per batch)\n'
              '• medium (10 per batch)\n'
              '• large (20 per batch)\n'
              '• all at once (999)',
        inline=True
    )
    
    embed.add_field(
        name='safety features',
        value='• session timeouts (15 min)\n'
              '• confirmation codes\n'
              '• user authorization\n'
              '• bot filtering\n'
              '• error handling',
        inline=True
    )
    
    embed.set_footer(text='message delivery system v1.0')
    
    await ctx.send(embed=embed)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    """Handle command errors"""
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    
    if isinstance(error, commands.MissingPermissions):
        await ctx.send('insufficient permissions')
        return
    
    if isinstance(error, commands.BotMissingPermissions):
        await ctx.send('bot missing required permissions')
        return
    
    # Log other errors
    print(f'command error: {error}')
    await ctx.send('an error occurred processing your command')

# Cleanup task
@bot.event
async def cleanup_task():
    """Periodic cleanup of expired sessions"""
    while True:
        await asyncio.sleep(300)  # Every 5 minutes
        await cleanup_expired_sessions()

# Start cleanup task when bot is ready
@bot.event
async def on_ready():
    print(f'Bot ready: {bot.user}')
    print(f'Guilds: {len(bot.guilds)}')
    await load_message_templates()
    await load_user_preferences()
    
    # Start cleanup task
    bot.loop.create_task(cleanup_task())
    
    print('System ready')

# Additional utility commands
@bot.command(name='clear_stats')
async def clear_stats(ctx):
    """Clear user statistics"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    user_id = ctx.author.id
    
    if user_id in send_statistics:
        del send_statistics[user_id]
        await ctx.send('statistics cleared')
    else:
        await ctx.send('no statistics to clear')

@bot.command(name='force_cleanup')
async def force_cleanup(ctx):
    """Force cleanup of all sessions"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    session_count = len(active_sessions)
    active_sessions.clear()
    
    embed = discord.Embed(
        title='cleanup complete',
        description=f'cleared {session_count} active sessions',
        color=0x00FF00
    )
    await ctx.send(embed=embed)

@bot.command(name='system_info')
async def system_info(ctx):
    """Show system information"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    embed = discord.Embed(
        title='system information',
        color=0x5865F2,
        timestamp=datetime.now(UTC)
    )
    
    embed.add_field(name='active sessions', value=str(len(active_sessions)), inline=True)
    embed.add_field(name='message templates', value=str(len(message_templates)), inline=True)
    embed.add_field(name='user preferences', value=str(len(user_preferences)), inline=True)
    embed.add_field(name='statistics tracked', value=str(len(send_statistics)), inline=True)
    embed.add_field(name='connected guilds', value=str(len(bot.guilds)), inline=True)
    embed.add_field(name='bot latency', value=f'{bot.latency*1000:.1f}ms', inline=True)
    
    await ctx.send(embed=embed)

# test command
@bot.command(name='t')
async def test_command(ctx):
    """test if bot is working"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('nah ur not allowed lol')
        return
    
    embed = discord.Embed(
        title='yo the bot is working',
        description='checking if everything is good...',
        color=0x00FF00,
        timestamp=datetime.now(UTC)
    )
    
    embed.add_field(name='bot online', value='yeah its working', inline=False)
    embed.add_field(name='templates', value=f'{len(message_templates)} loaded', inline=True)
    embed.add_field(name='active stuff', value=f'{len(active_sessions)} sessions running', inline=True)
    embed.add_field(name='ur authorized', value='yep ur good', inline=True)
    embed.add_field(name='servers', value=f'connected to {len(bot.guilds)} servers', inline=True)
    embed.add_field(name='ping', value=f'{bot.latency*1000:.1f}ms', inline=True)
    embed.add_field(name='stats', value=f'{len(send_statistics)} users tracked', inline=True)
    
    embed.set_footer(text='everything looks good')
    
    await ctx.send(embed=embed)

# ping command
@bot.command(name='ping')
async def ping_command(ctx):
    """simple ping"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('nope')
        return
    
    latency = bot.latency * 1000
    await ctx.send(f'pong! {latency:.1f}ms')

@bot.command(name='serverinfo')
async def server_info(ctx, server_id: int = None):
    """Send detailed server information to user's DM"""
    
    # If used in a server without server_id, use current server
    if ctx.guild and not server_id:
        guild = ctx.guild
    # If server_id is provided, get that server
    elif server_id:
        guild = bot.get_guild(server_id)
        if not guild:
            await ctx.send("❌ I couldn't find a server with that ID, or I'm not in that server!")
            return
    else:
        await ctx.send("❌ Please provide a server ID when using this command in DMs!\nUsage: `!serverinfo <server_id>`")
        return
    
    # Check if user is in the server (for security)
    if not guild.get_member(ctx.author.id):
        await ctx.send("❌ You must be a member of that server to get its information!")
        return
    
    try:
        # Create embed for server info
        embed = discord.Embed(
            title=f"📊 Server Information: {guild.name}",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        
        # Basic server info
        embed.add_field(
            name="🏷️ Basic Info",
            value=f"**Name:** {guild.name}\n"
                  f"**ID:** {guild.id}\n"
                  f"**Owner:** {guild.owner.mention if guild.owner else 'Unknown'}\n"
                  f"**Created:** {guild.created_at.strftime('%B %d, %Y')}\n"
                  f"**Members:** {guild.member_count}\n"
                  f"**Verification Level:** {guild.verification_level}",
            inline=False
        )
        
        # Channel information
        text_channels = [ch.name for ch in guild.text_channels]
        voice_channels = [ch.name for ch in guild.voice_channels]
        categories = [cat.name for cat in guild.categories]
        
        # Send multiple messages if content is too long
        messages_to_send = []
        
        # Basic info embed
        embed.add_field(
            name="📝 Text Channels",
            value=", ".join(text_channels) if text_channels else "None",
            inline=False
        )
        
        embed.add_field(
            name="🔊 Voice Channels", 
            value=", ".join(voice_channels) if voice_channels else "None",
            inline=False
        )
        
        if categories:
            embed.add_field(
                name="📂 Categories",
                value=", ".join(categories),
                inline=False
            )
        
        # Role information
        roles = [role.name for role in guild.roles if role.name != "@everyone"]
        if roles:
            # Split roles into chunks if too long for one field
            roles_text = ", ".join(roles)
            if len(roles_text) > 1024:
                # Split into multiple embeds
                role_chunks = []
                current_chunk = ""
                for role in roles:
                    if len(current_chunk + role + ", ") > 1024:
                        role_chunks.append(current_chunk.rstrip(", "))
                        current_chunk = role + ", "
                    else:
                        current_chunk += role + ", "
                if current_chunk:
                    role_chunks.append(current_chunk.rstrip(", "))
                
                # Add first chunk to main embed
                embed.add_field(
                    name=f"🎭 Roles ({len(roles)}) - Part 1",
                    value=role_chunks[0],
                    inline=False
                )
                
                # Create additional embeds for remaining roles
                for i, chunk in enumerate(role_chunks[1:], 2):
                    role_embed = discord.Embed(
                        title=f"🎭 Roles - Part {i}",
                        description=chunk,
                        color=discord.Color.blue()
                    )
                    messages_to_send.append(role_embed)
            else:
                embed.add_field(
                    name=f"🎭 Roles ({len(roles)})",
                    value=roles_text,
                    inline=False
                )
        
        # Emojis
        emojis = [str(emoji) for emoji in guild.emojis]
        if emojis:
            emoji_text = "".join(emojis)
            if len(emoji_text) > 1024:
                # Split emojis into chunks
                emoji_chunks = []
                current_chunk = ""
                for emoji in emojis:
                    if len(current_chunk + str(emoji)) > 1024:
                        emoji_chunks.append(current_chunk)
                        current_chunk = str(emoji)
                    else:
                        current_chunk += str(emoji)
                if current_chunk:
                    emoji_chunks.append(current_chunk)
                
                # Add first chunk to main embed
                embed.add_field(
                    name=f"😀 Custom Emojis ({len(emojis)}) - Part 1",
                    value=emoji_chunks[0],
                    inline=False
                )
                
                # Create additional embeds for remaining emojis
                for i, chunk in enumerate(emoji_chunks[1:], 2):
                    emoji_embed = discord.Embed(
                        title=f"😀 Custom Emojis - Part {i}",
                        description=chunk,
                        color=discord.Color.blue()
                    )
                    messages_to_send.append(emoji_embed)
            else:
                embed.add_field(
                    name=f"😀 Custom Emojis ({len(emojis)})",
                    value=emoji_text,
                    inline=False
                )
        
        # Features
        features = guild.features
        if features:
            feature_list = ", ".join([f.replace("_", " ").title() for f in features])
            embed.add_field(
                name="✨ Server Features",
                value=feature_list[:1024],
                inline=False
            )
        
        # Set server icon as thumbnail
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        # Send DM
        try:
            # Send main embed first
            await ctx.author.send(embed=embed)
            
            # Send additional embeds if any
            for additional_embed in messages_to_send:
                await ctx.author.send(embed=additional_embed)
            
            if ctx.guild:
                await ctx.send("📬 Server information sent to your DM!")
        except discord.Forbidden:
            if ctx.guild:
                await ctx.send("❌ I couldn't send you a DM. Please check your privacy settings.")
            else:
                await ctx.send("❌ I couldn't send you a DM. Please check your privacy settings.")
    
    except Exception as e:
        await ctx.send(f"❌ An error occurred: {str(e)}")

# In-memory storage for backups (you should use a database for production)
server_backups = {}

# Auto-backup system
@bot.event
async def on_ready():
    print(f'{bot.user} is ready!')
    # Start auto-backup task
    bot.loop.create_task(auto_backup_loop())

async def auto_backup_loop():
    """Automatically backup servers every 6 hours"""
    while True:
        try:
            for guild in bot.guilds:
                await create_backup(guild)
            print(f"Auto-backup completed for {len(bot.guilds)} servers")
        except Exception as e:
            print(f"Auto-backup error: {e}")
        
        # Wait 6 hours before next backup
        await asyncio.sleep(21600)

async def create_backup(guild):
    """Create a comprehensive backup of a server"""
    backup_data = {
        'guild_id': guild.id,
        'guild_name': guild.name,
        'backup_time': datetime.utcnow().isoformat(),
        'categories': [],
        'channels': [],
        'roles': [],
        'emojis': [],
        'guild_settings': {}
    }
    
    # Backup guild settings
    backup_data['guild_settings'] = {
        'name': guild.name,
        'description': guild.description,
        'verification_level': str(guild.verification_level),
        'default_notifications': str(guild.default_notifications),
        'explicit_content_filter': str(guild.explicit_content_filter),
        'afk_timeout': guild.afk_timeout,
        'afk_channel_id': guild.afk_channel.id if guild.afk_channel else None,
        'system_channel_id': guild.system_channel.id if guild.system_channel else None,
        'icon_url': str(guild.icon.url) if guild.icon else None,
        'banner_url': str(guild.banner.url) if guild.banner else None
    }
    
    # Backup categories
    for category in guild.categories:
        cat_data = {
            'id': category.id,
            'name': category.name,
            'position': category.position,
            'overwrites': []
        }
        
        # Backup permission overwrites
        for target, overwrite in category.overwrites.items():
            cat_data['overwrites'].append({
                'id': target.id,
                'type': 'role' if isinstance(target, discord.Role) else 'member',
                'allow': overwrite.pair()[0].value,
                'deny': overwrite.pair()[1].value
            })
        
        backup_data['categories'].append(cat_data)
    
    # Backup channels
    for channel in guild.channels:
        if isinstance(channel, discord.CategoryChannel):
            continue
            
        channel_data = {
            'id': channel.id,
            'name': channel.name,
            'type': str(channel.type),
            'position': channel.position,
            'category_id': channel.category.id if channel.category else None,
            'overwrites': []
        }
        
        # Channel-specific data
        if isinstance(channel, discord.TextChannel):
            channel_data.update({
                'topic': channel.topic,
                'slowmode_delay': channel.slowmode_delay,
                'nsfw': channel.nsfw,
                'news': channel.is_news()
            })
        elif isinstance(channel, discord.VoiceChannel):
            channel_data.update({
                'bitrate': channel.bitrate,
                'user_limit': channel.user_limit,
                'rtc_region': channel.rtc_region
            })
        
        # Backup permission overwrites
        for target, overwrite in channel.overwrites.items():
            channel_data['overwrites'].append({
                'id': target.id,
                'type': 'role' if isinstance(target, discord.Role) else 'member',
                'allow': overwrite.pair()[0].value,
                'deny': overwrite.pair()[1].value
            })
        
        backup_data['channels'].append(channel_data)
    
    # Backup roles
    for role in guild.roles:
        if role.name == "@everyone":
            continue
            
        role_data = {
            'id': role.id,
            'name': role.name,
            'color': role.color.value,
            'hoist': role.hoist,
            'mentionable': role.mentionable,
            'permissions': role.permissions.value,
            'position': role.position
        }
        backup_data['roles'].append(role_data)
    
    # Backup emojis
    for emoji in guild.emojis:
        emoji_data = {
            'id': emoji.id,
            'name': emoji.name,
            'url': str(emoji.url),
            'animated': emoji.animated,
            'roles': [role.id for role in emoji.roles]
        }
        backup_data['emojis'].append(emoji_data)
    
    # Store backup
    server_backups[guild.id] = backup_data
    
    # Save to file as well (optional)
    if not os.path.exists('backups'):
        os.makedirs('backups')
    
    with open(f'backups/{guild.id}_backup.json', 'w') as f:
        json.dump(backup_data, f, indent=2)

@bot.command(name='backup')
@commands.has_permissions(administrator=True)
async def manual_backup(ctx):
    """Manually create a backup of the server"""
    try:
        await create_backup(ctx.guild)
        embed = discord.Embed(
            title="✅ Backup Created",
            description=f"Successfully created backup for **{ctx.guild.name}**",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"❌ Error creating backup: {str(e)}")

@bot.command(name='restore')
@commands.has_permissions(administrator=True)
async def restore_server(ctx, backup_id: str = None):
    """Restore server from backup"""
    guild_id = ctx.guild.id
    
    if guild_id not in server_backups:
        await ctx.send("❌ No backup found for this server!")
        return
    
    # Confirmation
    embed = discord.Embed(
        title="⚠️ Server Restore Confirmation",
        description="**WARNING:** This will restore the server to a previous state.\n\n"
                   "This action will:\n"
                   "• Delete all current channels and categories\n"
                   "• Delete all current roles (except @everyone)\n"
                   "• Recreate channels, categories, and roles from backup\n"
                   "• Restore permissions and settings\n\n"
                   "**This cannot be undone!**\n\n"
                   "React with ✅ to confirm or ❌ to cancel.",
        color=discord.Color.red()
    )
    
    msg = await ctx.send(embed=embed)
    await msg.add_reaction('✅')
    await msg.add_reaction('❌')
    
    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == msg.id
    
    try:
        reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except asyncio.TimeoutError:
        await ctx.send("❌ Restore cancelled - timeout")
        return
    
    if str(reaction.emoji) == '❌':
        await ctx.send("❌ Restore cancelled")
        return
    
    # Start restoration
    await ctx.send("🔄 Starting server restoration... This may take a while.")
    
    try:
        await restore_from_backup(ctx.guild, server_backups[guild_id])
        
        embed = discord.Embed(
            title="✅ Server Restored",
            description=f"Successfully restored **{ctx.guild.name}** from backup",
            color=discord.Color.green(),
            timestamp=datetime.utcnow()
        )
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error during restoration: {str(e)}")

async def restore_from_backup(guild, backup_data):
    """Restore server from backup data"""
    
    # Step 1: Delete existing channels (except the one we're using)
    for channel in guild.channels:
        if channel.id != guild.channels[0].id:  # Keep first channel for communication
            try:
                await channel.delete(reason="Server restoration")
            except:
                pass
    
    # Step 2: Delete existing roles (except @everyone and bot roles)
    for role in guild.roles:
        if role.name != "@everyone" and not role.managed:
            try:
                await role.delete(reason="Server restoration")
            except:
                pass
    
    # Step 3: Recreate roles
    role_mapping = {}
    for role_data in sorted(backup_data['roles'], key=lambda x: x['position']):
        try:
            new_role = await guild.create_role(
                name=role_data['name'],
                color=discord.Color(role_data['color']),
                hoist=role_data['hoist'],
                mentionable=role_data['mentionable'],
                permissions=discord.Permissions(role_data['permissions']),
                reason="Server restoration"
            )
            role_mapping[role_data['id']] = new_role
        except Exception as e:
            print(f"Error creating role {role_data['name']}: {e}")
    
    # Step 4: Recreate categories
    category_mapping = {}
    for cat_data in sorted(backup_data['categories'], key=lambda x: x['position']):
        try:
            overwrites = {}
            for ow in cat_data['overwrites']:
                target = None
                if ow['type'] == 'role':
                    target = role_mapping.get(ow['id']) or guild.get_role(ow['id'])
                else:
                    target = guild.get_member(ow['id'])
                
                if target:
                    overwrites[target] = discord.PermissionOverwrite.from_pair(
                        discord.Permissions(ow['allow']),
                        discord.Permissions(ow['deny'])
                    )
            
            category = await guild.create_category(
                name=cat_data['name'],
                overwrites=overwrites,
                reason="Server restoration"
            )
            category_mapping[cat_data['id']] = category
        except Exception as e:
            print(f"Error creating category {cat_data['name']}: {e}")
    
    # Step 5: Recreate channels
    for channel_data in sorted(backup_data['channels'], key=lambda x: x['position']):
        try:
            overwrites = {}
            for ow in channel_data['overwrites']:
                target = None
                if ow['type'] == 'role':
                    target = role_mapping.get(ow['id']) or guild.get_role(ow['id'])
                else:
                    target = guild.get_member(ow['id'])
                
                if target:
                    overwrites[target] = discord.PermissionOverwrite.from_pair(
                        discord.Permissions(ow['allow']),
                        discord.Permissions(ow['deny'])
                    )
            
            category = category_mapping.get(channel_data['category_id'])
            
            if channel_data['type'] == 'ChannelType.text':
                await guild.create_text_channel(
                    name=channel_data['name'],
                    category=category,
                    overwrites=overwrites,
                    topic=channel_data.get('topic'),
                    slowmode_delay=channel_data.get('slowmode_delay', 0),
                    nsfw=channel_data.get('nsfw', False),
                    news=channel_data.get('news', False),
                    reason="Server restoration"
                )
            elif channel_data['type'] == 'ChannelType.voice':
                await guild.create_voice_channel(
                    name=channel_data['name'],
                    category=category,
                    overwrites=overwrites,
                    bitrate=channel_data.get('bitrate', 64000),
                    user_limit=channel_data.get('user_limit', 0),
                    rtc_region=channel_data.get('rtc_region'),
                    reason="Server restoration"
                )
        except Exception as e:
            print(f"Error creating channel {channel_data['name']}: {e}")

@bot.command(name='backupinfo')
@commands.has_permissions(administrator=True)
async def backup_info(ctx):
    """Show backup information"""
    guild_id = ctx.guild.id
    
    if guild_id not in server_backups:
        await ctx.send("❌ No backup found for this server!")
        return
    
    backup = server_backups[guild_id]
    
    embed = discord.Embed(
        title="📋 Backup Information",
        color=discord.Color.blue(),
        timestamp=datetime.fromisoformat(backup['backup_time'])
    )
    
    embed.add_field(
        name="📊 Server Stats",
        value=f"**Categories:** {len(backup['categories'])}\n"
              f"**Channels:** {len(backup['channels'])}\n"
              f"**Roles:** {len(backup['roles'])}\n"
              f"**Emojis:** {len(backup['emojis'])}",
        inline=True
    )
    
    embed.add_field(
        name="🕒 Backup Time",
        value=f"<t:{int(datetime.fromisoformat(backup['backup_time']).timestamp())}:R>",
        inline=True
    )
    
    embed.set_footer(text="Use !restore to restore from this backup")
    
    await ctx.send(embed=embed)


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
    await load_user_preferences()
    
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
