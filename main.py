import discord
from discord.ext import commands
import asyncio
import logging
import os
import re
import json
import time
from datetime import datetime, timedelta
import random

# Set up logging
logging.basicConfig(level=logging.INFO)

# Bot configuration
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Store complex session data
active_sessions = {}
message_templates = {}
user_preferences = {}
send_statistics = {}

@bot.event
async def on_ready():
    print(f'bot ready: {bot.user}')
    print(f'guilds: {len(bot.guilds)}')
    print('loading message templates...')
    await load_message_templates()
    print('loading user preferences...')
    await load_user_preferences()
    print('system ready')

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
    print(f'loaded {len(message_templates)} templates')

async def load_user_preferences():
    """Load user messaging preferences"""
    global user_preferences
    user_preferences = {
        728201873366056992: {
            'preferred_design': 'fancy',
            'confirmation_required': True,
            'batch_size': 10,
            'delay_between_batches': 5
        }
    }
    print('preferences loaded')

class MessageSession:
    def __init__(self, user_id, channel_id, guild_id):
        self.user_id = user_id
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.session_id = f"{user_id}_{int(time.time())}"
        self.stage = 'init'
        self.data = {
            'targets': [],
            'message_content': '',
            'template': None,
            'design': None,
            'priority': 'normal',
            'schedule_time': None,
            'confirmation_code': None,
            'batch_settings': {},
            'custom_fields': {},
            'safety_checks': {},
            'delivery_options': {}
        }
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.steps_completed = 0
        self.total_steps = 12

    def update_activity(self):
        self.last_activity = datetime.utcnow()

    def progress_percentage(self):
        return int((self.steps_completed / self.total_steps) * 100)

class Step1View(discord.ui.View):
    """Target Selection Step"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Role Members', style=discord.ButtonStyle.primary, emoji='👥')
    async def select_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        await interaction.response.send_message('enter role id:', ephemeral=True)
        self.session.stage = 'awaiting_role_id'
        self.session.update_activity()

    @discord.ui.button(label='Mentioned Users', style=discord.ButtonStyle.secondary, emoji='@')
    async def select_mentions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        await interaction.response.send_message('mention users in next message:', ephemeral=True)
        self.session.stage = 'awaiting_mentions'
        self.session.update_activity()

    @discord.ui.button(label='Custom List', style=discord.ButtonStyle.success, emoji='📝')
    async def select_custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        await interaction.response.send_message('enter user ids separated by commas:', ephemeral=True)
        self.session.stage = 'awaiting_custom_list'
        self.session.update_activity()

class Step2View(discord.ui.View):
    """Message Content Type Selection"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Plain Text', style=discord.ButtonStyle.secondary, emoji='📝')
    async def plain_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(content='enter your message:', view=None)
        self.session.stage = 'awaiting_message_content'
        self.session.data['content_type'] = 'plain'
        self.session.update_activity()

    @discord.ui.button(label='Rich Text', style=discord.ButtonStyle.primary, emoji='✨')
    async def rich_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(content='enter your message with formatting:', view=None)
        self.session.stage = 'awaiting_message_content'
        self.session.data['content_type'] = 'rich'
        self.session.update_activity()

    @discord.ui.button(label='Template Based', style=discord.ButtonStyle.success, emoji='📋')
    async def template_based(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        template_view = TemplateSelectionView(self.session)
        await interaction.response.edit_message(content='choose template:', view=template_view)
        self.session.stage = 'selecting_template'
        self.session.data['content_type'] = 'template'
        self.session.update_activity()

class TemplateSelectionView(discord.ui.View):
    """Template Selection"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session
        
        # Add template buttons
        for template_name, template_data in message_templates.items():
            button = discord.ui.Button(
                label=template_name.title(),
                style=discord.ButtonStyle.secondary,
                custom_id=f"template_{template_name}"
            )
            button.callback = self.template_callback
            self.add_item(button)

    async def template_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        template_name = interaction.data['custom_id'].replace('template_', '')
        self.session.data['template'] = template_name
        
        await interaction.response.edit_message(
            content=f'selected template: {template_name}\nenter your message content:',
            view=None
        )
        self.session.stage = 'awaiting_template_content'
        self.session.update_activity()

class Step3View(discord.ui.View):
    """Priority Selection"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Low Priority', style=discord.ButtonStyle.secondary, emoji='🔵')
    async def low_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_priority(interaction, 'low')

    @discord.ui.button(label='Normal Priority', style=discord.ButtonStyle.primary, emoji='🟡')
    async def normal_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_priority(interaction, 'normal')

    @discord.ui.button(label='High Priority', style=discord.ButtonStyle.danger, emoji='🔴')
    async def high_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_priority(interaction, 'high')

    @discord.ui.button(label='Critical Priority', style=discord.ButtonStyle.danger, emoji='🚨')
    async def critical_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_priority(interaction, 'critical')

    async def set_priority(self, interaction, priority):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        self.session.data['priority'] = priority
        self.session.steps_completed = 3
        
        schedule_view = Step4View(self.session)
        await interaction.response.edit_message(
            content=f'priority set: {priority}\n\nschedule delivery:',
            view=schedule_view
        )
        self.session.stage = 'scheduling'
        self.session.update_activity()

class Step4View(discord.ui.View):
    """Delivery Scheduling"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Send Now', style=discord.ButtonStyle.success, emoji='⚡')
    async def send_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        self.session.data['schedule_time'] = 'now'
        await self.proceed_to_batch_settings(interaction)

    @discord.ui.button(label='Schedule for Later', style=discord.ButtonStyle.primary, emoji='⏰')
    async def schedule_later(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content='enter schedule time (format: YYYY-MM-DD HH:MM):',
            view=None
        )
        self.session.stage = 'awaiting_schedule_time'
        self.session.update_activity()

    async def proceed_to_batch_settings(self, interaction):
        self.session.steps_completed = 4
        batch_view = Step5View(self.session)
        await interaction.response.edit_message(
            content=f'delivery scheduled: {self.session.data["schedule_time"]}\n\nconfigure batch settings:',
            view=batch_view
        )
        self.session.stage = 'batch_settings'

class Step5View(discord.ui.View):
    """Batch Settings Configuration"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Small Batches (5)', style=discord.ButtonStyle.secondary, emoji='🔢')
    async def small_batch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 5)

    @discord.ui.button(label='Medium Batches (10)', style=discord.ButtonStyle.primary, emoji='🔢')
    async def medium_batch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 10)

    @discord.ui.button(label='Large Batches (20)', style=discord.ButtonStyle.success, emoji='🔢')
    async def large_batch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 20)

    @discord.ui.button(label='All at Once', style=discord.ButtonStyle.danger, emoji='⚡')
    async def all_at_once(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 999)

    async def set_batch_size(self, interaction, size):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        self.session.data['batch_settings']['size'] = size
        self.session.steps_completed = 5
        
        delay_view = Step6View(self.session)
        await interaction.response.edit_message(
            content=f'batch size: {size}\n\nset delay between batches:',
            view=delay_view
        )
        self.session.stage = 'delay_settings'
        self.session.update_activity()

class Step6View(discord.ui.View):
    """Delay Settings"""
    def __init__(self, session):
        super().__init__(timeout=600)
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

    @discord.ui.button(label='Custom Delay', style=discord.ButtonStyle.danger, emoji='⏱️')
    async def custom_delay(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content='enter custom delay in seconds:',
            view=None
        )
        self.session.stage = 'awaiting_custom_delay'
        self.session.update_activity()

    async def set_delay(self, interaction, delay):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        self.session.data['batch_settings']['delay'] = delay
        self.session.steps_completed = 6
        
        await self.proceed_to_safety_checks(interaction)

    async def proceed_to_safety_checks(self, interaction):
        safety_view = Step7View(self.session)
        await interaction.response.edit_message(
            content=f'delay set: {self.session.data["batch_settings"]["delay"]}s\n\nsafety verification required:',
            view=safety_view
        )
        self.session.stage = 'safety_checks'

class Step7View(discord.ui.View):
    """Safety Checks"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Verify Message Content', style=discord.ButtonStyle.primary, emoji='✅')
    async def verify_content(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        self.session.data['safety_checks']['content_verified'] = True
        await self.check_safety_progress(interaction)

    @discord.ui.button(label='Verify Target List', style=discord.ButtonStyle.primary, emoji='👥')
    async def verify_targets(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        self.session.data['safety_checks']['targets_verified'] = True
        await self.check_safety_progress(interaction)

    @discord.ui.button(label='Verify Permissions', style=discord.ButtonStyle.primary, emoji='🔒')
    async def verify_permissions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        self.session.data['safety_checks']['permissions_verified'] = True
        await self.check_safety_progress(interaction)

    async def check_safety_progress(self, interaction):
        checks = self.session.data['safety_checks']
        completed = sum(1 for check in checks.values() if check)
        total = 3
        
        if completed == total:
            self.session.steps_completed = 7
            confirmation_view = Step8View(self.session)
            await interaction.response.edit_message(
                content='all safety checks completed\n\ngenerate confirmation code:',
                view=confirmation_view
            )
            self.session.stage = 'confirmation_code'
        else:
            await interaction.response.edit_message(
                content=f'safety checks: {completed}/{total} completed\ncontinue verification:',
                view=self
            )

class Step8View(discord.ui.View):
    """Confirmation Code Generation"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Generate Code', style=discord.ButtonStyle.success, emoji='🔐')
    async def generate_code(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        # Generate random confirmation code
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.session.data['confirmation_code'] = code
        self.session.steps_completed = 8
        
        await interaction.response.edit_message(
            content=f'confirmation code: **{code}**\n\ntype this code to proceed:',
            view=None
        )
        self.session.stage = 'awaiting_confirmation_code'
        self.session.update_activity()

class Step9View(discord.ui.View):
    """Design Selection"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Minimal', style=discord.ButtonStyle.secondary, emoji='📝')
    async def minimal_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_design(interaction, 'minimal')

    @discord.ui.button(label='Standard', style=discord.ButtonStyle.primary, emoji='📋')
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
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        self.session.data['design'] = design
        self.session.steps_completed = 9
        
        preview_view = Step10View(self.session)
        await interaction.response.edit_message(
            content=f'design selected: {design}\n\npreview message:',
            view=preview_view
        )
        self.session.stage = 'preview'
        self.session.update_activity()

class Step10View(discord.ui.View):
    """Message Preview"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Show Preview', style=discord.ButtonStyle.primary, emoji='👁️')
    async def show_preview(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        # Create preview message
        message_data = await create_message_from_session(self.session)
        
        if message_data['type'] == 'text':
            preview_content = f"**PREVIEW:**\n{message_data['content']}"
        else:
            preview_content = "**PREVIEW:**"
            
        final_view = Step11View(self.session, message_data)
        
        if message_data['type'] == 'embed':
            await interaction.response.edit_message(
                content=preview_content,
                embed=message_data['embed'],
                view=final_view
            )
        else:
            await interaction.response.edit_message(
                content=preview_content,
                view=final_view
            )
        
        self.session.steps_completed = 10
        self.session.stage = 'final_confirmation'

class Step11View(discord.ui.View):
    """Final Confirmation"""
    def __init__(self, session, message_data):
        super().__init__(timeout=600)
        self.session = session
        self.message_data = message_data

    @discord.ui.button(label='Send Messages', style=discord.ButtonStyle.success, emoji='🚀')
    async def send_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content='processing delivery...',
            embed=None,
            view=None
        )
        
        # Execute the message sending
        success, fail = await execute_message_delivery(self.session, self.message_data)
        
        # Update statistics
        await update_send_statistics(self.session.user_id, success, fail)
        
        self.session.steps_completed = 12
        
        await interaction.followup.send(
            f'delivery complete\n'
            f'sent: {success}\n'
            f'failed: {fail}\n'
            f'total targets: {len(self.session.data["targets"])}\n'
            f'session: {self.session.session_id}'
        )
        
        # Clean up session
        if self.session.session_id in active_sessions:
            del active_sessions[self.session.session_id]

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger, emoji='❌')
    async def cancel_send(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content='message delivery cancelled',
            embed=None,
            view=None
        )
        
        # Clean up session
        if self.session.session_id in active_sessions:
            del active_sessions[self.session.session_id]

    @discord.ui.button(label='Modify Settings', style=discord.ButtonStyle.secondary, emoji='⚙️')
    async def modify_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        # Go back to design selection
        design_view = Step9View(self.session)
        await interaction.response.edit_message(
            content='modify settings - choose design:',
            embed=None,
            view=design_view
        )
        self.session.stage = 'design_selection'

async def create_message_from_session(session):
    """Create the final message based on session data"""
    content = session.data.get('message_content', '')
    design = session.data.get('design', 'standard')
    template = session.data.get('template')
    
    if design == 'minimal':
        return {'type': 'text', 'content': content}
    
    elif design == 'standard':
        embed = discord.Embed(
            description=content,
            color=0x5865F2,
            timestamp=datetime.utcnow()
        )
        return {'type': 'embed', 'embed': embed}
    
    elif design == 'professional':
        embed = discord.Embed(
            title='📢 Message',
            description=content,
            color=0x00D4AA,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text='Professional Message System')
        return {'type': 'embed', 'embed': embed}
    
    elif design == 'alert':
        embed = discord.Embed(
            title='🚨 Important Notice',
            description=content,
            color=0xFF4444,
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text='Alert System')
        return {'type': 'embed', 'embed': embed}
    
    # Template-based message
    if template and template in message_templates:
        template_data = message_templates[template]
        embed = discord.Embed(
            title=template_data['title'],
            description=content,
            color=template_data['color'],
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=template_data['footer'])
        return {'type': 'embed', 'embed': embed}
    
    # Default fallback
    return {'type': 'text', 'content': content}

async def execute_message_delivery(session, message_data):
    """Execute the actual message delivery"""
    targets = session.data['targets']
    batch_size = session.data['batch_settings'].get('size', 10)
    delay = session.data['batch_settings'].get('delay', 1)
    
    success_count = 0
    fail_count = 0
    
    print(f'starting delivery for session {session.session_id}')
    print(f'targets: {len(targets)}, batch_size: {batch_size}, delay: {delay}s')
    
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
            except Exception as e:
                print(f'error {target.display_name}: {e}')
                fail_count += 1
        
        # Delay between batches
        if i + batch_size < len(targets) and delay > 0:
            print(f'batch complete, waiting {delay}s before next batch...')
            await asyncio.sleep(delay)
    
    print(f'delivery complete: sent {success_count}, failed {fail_count}')
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
    stats['last_send'] = datetime.utcnow()
    
    print(f'updated stats for user {user_id}: {stats}')

@bot.command(name='send')
async def send_message(ctx, *, args=None):
    """Start the complex message sending process"""
    # Authorization check
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    # Check for existing active session
    existing_session = None
  @bot.command(name='send')
async def send_message(ctx, *, args=None):
    """Start the complex message sending process"""
    # Authorization check
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    # Check for existing active session
    existing_session = None
    for session_id, session in active_sessions.items():
        if session.user_id == ctx.author.id:
            existing_session = session
            break
    
    if existing_session:
        embed = discord.Embed(
            title='⚠️ Active Session Found',
            description=f'You have an active session: `{existing_session.session_id}`\n'
                       f'Progress: {existing_session.progress_percentage()}%\n'
                       f'Stage: {existing_session.stage}',
            color=0xFFA500
        )
        embed.add_field(name='Options', value='React to continue or start new', inline=False)
        
        view = ExistingSessionView(existing_session)
        await ctx.send(embed=embed, view=view)
        return
    
    # Create new session
    session = MessageSession(ctx.author.id, ctx.channel.id, ctx.guild.id)
    active_sessions[session.session_id] = session
    
    # Create initial embed
    embed = discord.Embed(
        title='📨 Message Delivery System',
        description='Advanced message delivery system initialized\n'
                   f'Session ID: `{session.session_id}`\n'
                   f'Progress: {session.progress_percentage()}%',
        color=0x5865F2,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(
        name='Step 1: Target Selection',
        value='Choose how to select message recipients',
        inline=False
    )
    
    embed.set_footer(text=f'Session timeout: 10 minutes')
    
    # Start with target selection
    view = Step1View(session)
    await ctx.send(embed=embed, view=view)
    session.stage = 'target_selection'

class ExistingSessionView(discord.ui.View):
    """Handle existing session options"""
    def __init__(self, session):
        super().__init__(timeout=300)
        self.session = session

    @discord.ui.button(label='Continue Session', style=discord.ButtonStyle.success, emoji='▶️')
    async def continue_session(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        # Resume from current stage
        stage = self.session.stage
        
        if stage == 'target_selection':
            view = Step1View(self.session)
            content = 'continuing session - select targets:'
        elif stage == 'content_selection':
            view = Step2View(self.session)
            content = 'continuing session - select content type:'
        elif stage == 'priority_selection':
            view = Step3View(self.session)
            content = 'continuing session - set priority:'
        else:
            view = None
            content = f'session in stage: {stage}\nplease complete current step'
        
        await interaction.response.edit_message(content=content, embed=None, view=view)

    @discord.ui.button(label='Start New Session', style=discord.ButtonStyle.danger, emoji='🔄')
    async def new_session(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('not your session', ephemeral=True)
            return
        
        # Remove existing session
        if self.session.session_id in active_sessions:
            del active_sessions[self.session.session_id]
        
        # Create new session
        new_session = MessageSession(interaction.user.id, interaction.channel.id, interaction.guild.id)
        active_sessions[new_session.session_id] = new_session
        
        embed = discord.Embed(
            title='📨 New Message Delivery Session',
            description=f'Session ID: `{new_session.session_id}`\n'
                       f'Progress: {new_session.progress_percentage()}%',
            color=0x5865F2
        )
        embed.add_field(name='Step 1', value='Select message targets', inline=False)
        
        view = Step1View(new_session)
        await interaction.response.edit_message(embed=embed, view=view)

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
    
    stage = user_session.stage
    content = message.content.strip()
    
    try:
        if stage == 'awaiting_role_id':
            await handle_role_id_input(message, user_session, content)
        elif stage == 'awaiting_mentions':
            await handle_mentions_input(message, user_session)
        elif stage == 'awaiting_custom_list':
            await handle_custom_list_input(message, user_session, content)
        elif stage == 'awaiting_message_content':
            await handle_message_content_input(message, user_session, content)
        elif stage == 'awaiting_template_content':
            await handle_template_content_input(message, user_session, content)
        elif stage == 'awaiting_schedule_time':
            await handle_schedule_time_input(message, user_session, content)
        elif stage == 'awaiting_custom_delay':
            await handle_custom_delay_input(message, user_session, content)
        elif stage == 'awaiting_confirmation_code':
            await handle_confirmation_code_input(message, user_session, content)
        else:
            await bot.process_commands(message)
    
    except Exception as e:
        await message.channel.send(f'error processing input: {e}')
        print(f'session error: {e}')

async def handle_role_id_input(message, session, role_id_str):
    """Handle role ID input"""
    try:
        role_id = int(role_id_str)
        role = message.guild.get_role(role_id)
        
        if not role:
            await message.channel.send('role not found, try again:')
            return
        
        # Get role members
        members = [member for member in role.members if not member.bot]
        
        if not members:
            await message.channel.send('no members in role, try again:')
            return
        
        session.data['targets'] = members
        session.steps_completed = 1
        
        embed = discord.Embed(
            title='✅ Targets Selected', 
            description=f'Role: {role.name}\nMembers: {len(members)}',
            color=0x00FF00
        )
        
        # Move to content selection
        view = Step2View(session)
        await message.channel.send(
            content='step 2: choose message type:',
            embed=embed,
            view=view
        )
        session.stage = 'content_selection'
        
    except ValueError:
        await message.channel.send('invalid role id, enter numbers only:')

async def handle_mentions_input(message, session):
    """Handle mentioned users input"""
    mentioned_users = [user for user in message.mentions if not user.bot]
    
    if not mentioned_users:
        await message.channel.send('no valid users mentioned, try again:')
        return
    
    session.data['targets'] = mentioned_users
    session.steps_completed = 1
    
    embed = discord.Embed(
        title='✅ Targets Selected',
        description=f'Mentioned users: {len(mentioned_users)}',
        color=0x00FF00
    )
    
    for user in mentioned_users[:10]:  # Show first 10
        embed.add_field(name=user.display_name, value=user.mention, inline=True)
    
    if len(mentioned_users) > 10:
        embed.add_field(name='...', value=f'and {len(mentioned_users) - 10} more', inline=True)
    
    view = Step2View(session)
    await message.channel.send(
        content='step 2: choose message type:',
        embed=embed,
        view=view
    )
    session.stage = 'content_selection'

async def handle_custom_list_input(message, session, user_ids_str):
    """Handle custom user ID list input"""
    try:
        user_ids = [int(uid.strip()) for uid in user_ids_str.split(',')]
        users = []
        
        for user_id in user_ids:
            try:
                user = await bot.fetch_user(user_id)
                if user and not user.bot:
                    users.append(user)
            except:
                continue
        
        if not users:
            await message.channel.send('no valid users found, try again:')
            return
        
        session.data['targets'] = users
        session.steps_completed = 1
        
        embed = discord.Embed(
            title='✅ Targets Selected',
            description=f'Custom list: {len(users)} users',
            color=0x00FF00
        )
        
        view = Step2View(session)
        await message.channel.send(
            content='step 2: choose message type:',
            embed=embed,
            view=view
        )
        session.stage = 'content_selection'
        
    except ValueError:
        await message.channel.send('invalid format, use: id1, id2, id3')

async def handle_message_content_input(message, session, content):
    """Handle message content input"""
    if len(content) > 2000:
        await message.channel.send('message too long (max 2000 characters), try again:')
        return
    
    if not content:
        await message.channel.send('message cannot be empty, try again:')
        return
    
    session.data['message_content'] = content
    session.steps_completed = 2
    
    embed = discord.Embed(
        title='✅ Message Content Set',
        description=f'Content length: {len(content)} characters',
        color=0x00FF00
    )
    
    # Show preview of content
    preview = content[:200] + '...' if len(content) > 200 else content
    embed.add_field(name='Preview', value=f'```{preview}```', inline=False)
    
    view = Step3View(session)
    await message.channel.send(
        content='step 3: set message priority:',
        embed=embed,
        view=view
    )
    session.stage = 'priority_selection'

async def handle_template_content_input(message, session, content):
    """Handle template-based content input"""
    if len(content) > 1500:  # Templates have additional formatting
        await message.channel.send('content too long for template (max 1500 characters), try again:')
        return
    
    if not content:
        await message.channel.send('content cannot be empty, try again:')
        return
    
    session.data['message_content'] = content
    session.steps_completed = 2
    
    template_name = session.data['template']
    embed = discord.Embed(
        title='✅ Template Content Set',
        description=f'Template: {template_name}\nContent length: {len(content)} characters',
        color=0x00FF00
    )
    
    view = Step3View(session)
    await message.channel.send(
        content='step 3: set message priority:',
        embed=embed,
        view=view
    )
    session.stage = 'priority_selection'

async def handle_schedule_time_input(message, session, time_str):
    """Handle schedule time input"""
    try:
        # Parse time format: YYYY-MM-DD HH:MM
        schedule_time = datetime.strptime(time_str, '%Y-%m-%d %H:%M')
        
        # Check if time is in the future
        if schedule_time <= datetime.now():
            await message.channel.send('time must be in the future, try again:')
            return
        
        # Check if time is not too far in the future (e.g., 30 days)
        if schedule_time > datetime.now() + timedelta(days=30):
            await message.channel.send('time too far in future (max 30 days), try again:')
            return
        
        session.data['schedule_time'] = schedule_time
        session.steps_completed = 4
        
        embed = discord.Embed(
            title='✅ Schedule Time Set',
            description=f'Delivery time: {schedule_time.strftime("%Y-%m-%d %H:%M")}',
            color=0x00FF00
        )
        
        view = Step5View(session)
        await message.channel.send(
            content='step 5: configure batch settings:',
            embed=embed,
            view=view
        )
        session.stage = 'batch_settings'
        
    except ValueError:
        await message.channel.send('invalid time format, use: YYYY-MM-DD HH:MM')

async def handle_custom_delay_input(message, session, delay_str):
    """Handle custom delay input"""
    try:
        delay = float(delay_str)
        
        if delay < 0:
            await message.channel.send('delay cannot be negative, try again:')
            return
        
        if delay > 300:  # Max 5 minutes
            await message.channel.send('delay too long (max 300 seconds), try again:')
            return
        
        session.data['batch_settings']['delay'] = delay
        session.steps_completed = 6
        
        embed = discord.Embed(
            title='✅ Custom Delay Set',
            description=f'Delay: {delay} seconds',
            color=0x00FF00
        )
        
        view = Step7View(session)
        await message.channel.send(
            content='step 7: safety verification required:',
            embed=embed,
            view=view
        )
        session.stage = 'safety_checks'
        
    except ValueError:
        await message.channel.send('invalid number, enter delay in seconds:')

async def handle_confirmation_code_input(message, session, code):
    """Handle confirmation code input"""
    expected_code = session.data.get('confirmation_code')
    
    if code != expected_code:
        await message.channel.send(f'incorrect code, expected: **{expected_code}**')
        return
    
    session.steps_completed = 9
    
    embed = discord.Embed(
        title='✅ Code Confirmed',
        description='Confirmation successful',
        color=0x00FF00
    )
    
    view = Step9View(session)
    await message.channel.send(
        content='step 9: choose message design:',
        embed=embed,
        view=view
    )
    session.stage = 'design_selection'

@bot.command(name='sessions')
async def list_sessions(ctx):
    """List active sessions"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    if not active_sessions:
        await ctx.send('no active sessions')
        return
    
    embed = discord.Embed(
        title='📊 Active Sessions',
        color=0x5865F2,
        timestamp=datetime.utcnow()
    )
    
    for session_id, session in active_sessions.items():
        user = bot.get_user(session.user_id)
        username = user.display_name if user else 'Unknown User'
        
        embed.add_field(
            name=f'Session: {session_id}',
            value=f'User: {username}\n'
                  f'Progress: {session.progress_percentage()}%\n'
                  f'Stage: {session.stage}\n'
                  f'Targets: {len(session.data.get("targets", []))}\n'
                  f'Created: {session.created_at.strftime("%H:%M:%S")}',
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
        await ctx.send('no statistics available')
        return
    
    stats = send_statistics[user_id]
    
    embed = discord.Embed(
        title='📈 Your Statistics',
        color=0x00D4AA,
        timestamp=datetime.utcnow()
    )
    
    embed.add_field(name='Messages Sent', value=stats['total_sent'], inline=True)
    embed.add_field(name='Failed Deliveries', value=stats['total_failed'], inline=True)
    embed.add_field(name='Success Rate', value=f"{stats['total_sent']/(stats['total_sent']+stats['total_failed'])*100:.1f}%" if stats['total_sent']+stats['total_failed'] > 0 else "0%", inline=True)
    embed.add_field(name='Sessions Completed', value=stats['sessions_completed'], inline=True)
    
    if stats['last_send']:
        embed.add_field(name='Last Send', value=stats['last_send'].strftime('%Y-%m-%d %H:%M:%S'), inline=True)
    
    await ctx.send(embed=embed)

@bot.command(name='cleanup')
async def cleanup_sessions(ctx):
    """Clean up expired sessions"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    current_time = datetime.utcnow()
    expired_sessions = []
    
    for session_id, session in list(active_sessions.items()):
        # Sessions expire after 10 minutes of inactivity
        if current_time - session.last_activity > timedelta(minutes=10):
            expired_sessions.append(session_id)
            del active_sessions[session_id]
    
    await ctx.send(f'cleaned up {len(expired_sessions)} expired sessions')

@bot.command(name='test')
async def test_command(ctx):
    """quick test command"""
    authorized_users = [728201873366056992]
    
    if ctx.author.id not in authorized_users:
        await ctx.send('nah')
        return
    
    # basic info
    await ctx.send(f'yo {ctx.author.display_name}')
    await ctx.send(f'guild: {ctx.guild.name}')
    await ctx.send(f'channel: {ctx.channel.name}')
    await ctx.send(f'members: {len(ctx.guild.members)}')
    
    # test session creation
    test_session = MessageSession(ctx.author.id, ctx.channel.id, ctx.guild.id)
    await ctx.send(f'session test: {test_session.session_id}')
    
    # test templates
    await ctx.send(f'templates loaded: {len(message_templates)}')
    
    # test stats
    if ctx.author.id in send_statistics:
        stats = send_statistics[ctx.author.id]
        await ctx.send(f'your stats: sent {stats["total_sent"]} failed {stats["total_failed"]}')
    else:
        await ctx.send('no stats yet')
    
    await ctx.send('all good')

# Run the bot
if __name__ == "__main__":
    # Get token from environment variable
    token = os.getenv('DISCORD_TOKEN') or os.getenv('BOT_TOKEN')
    
    if not token:
        print("Error: No bot token found in environment variables!")
        print("Please set DISCORD_TOKEN or BOT_TOKEN environment variable")
        exit(1)
    
    bot.run(token)
