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
