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

# Global storage for active sessions
active_sessions = {}

class MessageSession:
    """Represents an active message sending session"""
    def __init__(self, user_id, channel_id, guild_id):
        self.session_id = str(uuid.uuid4())[:8]
        self.user_id = user_id
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.created_at = datetime.utcnow()
        self.last_activity = datetime.utcnow()
        self.stage = 'initial'
        self.steps_completed = 0
        self.total_steps = 10
        self.data = {}
    
    def progress_percentage(self):
        return int((self.steps_completed / self.total_steps) * 100)
    
    def update_activity(self):
        self.last_activity = datetime.utcnow()
    
    def is_expired(self):
        return datetime.utcnow() - self.last_activity > timedelta(minutes=10)

@bot.command(name='send')
async def send_message(ctx, *, args=None):
    """Start the complex message sending process"""
    # Authorization check
    authorized_users = [728201873366056992]  # Replace with actual authorized user IDs
    
    if ctx.author.id not in authorized_users:
        await ctx.send('❌ Not authorized to use this command')
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
    session.update_activity()

class ExistingSessionView(discord.ui.View):
    """Handle existing session options"""
    def __init__(self, session):
        super().__init__(timeout=300)
        self.session = session

    @discord.ui.button(label='Continue Session', style=discord.ButtonStyle.success, emoji='▶️')
    async def continue_session(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        # Resume from current stage
        stage = self.session.stage
        self.session.update_activity()
        
        embed = discord.Embed(
            title='📨 Continuing Session',
            description=f'Session: `{self.session.session_id}`\nProgress: {self.session.progress_percentage()}%',
            color=0x5865F2
        )
        
        if stage == 'target_selection':
            view = Step1View(self.session)
            embed.add_field(name='Current Step', value='Step 1: Target Selection', inline=False)
            await interaction.response.edit_message(embed=embed, view=view)
        elif stage == 'content_selection':
            view = Step2View(self.session)
            embed.add_field(name='Current Step', value='Step 2: Message Content', inline=False)
            await interaction.response.edit_message(embed=embed, view=view)
        elif stage == 'priority_selection':
            view = Step3View(self.session)
            embed.add_field(name='Current Step', value='Step 3: Priority Selection', inline=False)
            await interaction.response.edit_message(embed=embed, view=view)
        elif stage == 'scheduling':
            view = Step4View(self.session)
            embed.add_field(name='Current Step', value='Step 4: Scheduling', inline=False)
            await interaction.response.edit_message(embed=embed, view=view)
        elif stage == 'batch_settings':
            view = Step5View(self.session)
            embed.add_field(name='Current Step', value='Step 5: Batch Settings', inline=False)
            await interaction.response.edit_message(embed=embed, view=view)
        elif stage == 'delay_settings':
            view = Step6View(self.session)
            embed.add_field(name='Current Step', value='Step 6: Delay Settings', inline=False)
            await interaction.response.edit_message(embed=embed, view=view)
        elif stage == 'safety_checks':
            view = Step7View(self.session)
            embed.add_field(name='Current Step', value='Step 7: Safety Checks', inline=False)
            await interaction.response.edit_message(embed=embed, view=view)
        elif stage == 'confirmation_code':
            view = Step8View(self.session)
            embed.add_field(name='Current Step', value='Step 8: Confirmation Code', inline=False)
            await interaction.response.edit_message(embed=embed, view=view)
        elif stage == 'design_selection':
            view = Step9View(self.session)
            embed.add_field(name='Current Step', value='Step 9: Design Selection', inline=False)
            await interaction.response.edit_message(embed=embed, view=view)
        elif stage == 'preview':
            view = Step10View(self.session)
            embed.add_field(name='Current Step', value='Step 10: Preview', inline=False)
            await interaction.response.edit_message(embed=embed, view=view)
        else:
            await interaction.response.edit_message(
                content=f'Session in stage: {stage}\nComplete current step manually',
                embed=None,
                view=None
            )

    @discord.ui.button(label='Start New Session', style=discord.ButtonStyle.danger, emoji='🔄')
    async def new_session(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
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
            color=0x5865F2,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name='Step 1', value='Select message targets', inline=False)
        embed.set_footer(text='Session timeout: 10 minutes')
        
        view = Step1View(new_session)
        await interaction.response.edit_message(embed=embed, view=view)
        new_session.stage = 'target_selection'
        new_session.update_activity()

class Step1View(discord.ui.View):
    """Target Selection Step"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Role Members', style=discord.ButtonStyle.primary, emoji='👥')
    async def select_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content=f'Session: `{self.session.session_id}`\n**Enter role ID in your next message:**',
            embed=None,
            view=None
        )
        self.session.stage = 'awaiting_role_id'
        self.session.update_activity()

    @discord.ui.button(label='Mentioned Users', style=discord.ButtonStyle.secondary, emoji='@')
    async def select_mentions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content=f'Session: `{self.session.session_id}`\n**Mention users in your next message:**',
            embed=None,
            view=None
        )
        self.session.stage = 'awaiting_mentions'
        self.session.update_activity()

    @discord.ui.button(label='Custom List', style=discord.ButtonStyle.success, emoji='📝')
    async def select_custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content=f'Session: `{self.session.session_id}`\n**Enter user IDs separated by commas:**\nExample: 123456789, 987654321, 456789123',
            embed=None,
            view=None
        )
        self.session.stage = 'awaiting_custom_list'
        self.session.update_activity()

class Step2View(discord.ui.View):
    """Content Selection Step"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Plain Text', style=discord.ButtonStyle.primary, emoji='📝')
    async def plain_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        self.session.data['content_type'] = 'plain'
        await interaction.response.edit_message(
            content=f'Session: `{self.session.session_id}`\n**Enter your message content (max 2000 characters):**',
            embed=None,
            view=None
        )
        self.session.stage = 'awaiting_message_content'
        self.session.update_activity()

    @discord.ui.button(label='Embed Template', style=discord.ButtonStyle.secondary, emoji='📋')
    async def embed_template(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        view = TemplateSelectionView(self.session)
        embed = discord.Embed(
            title='📋 Select Template Type',
            description='Choose from available embed templates:',
            color=0x5865F2
        )
        await interaction.response.edit_message(embed=embed, view=view)

class TemplateSelectionView(discord.ui.View):
    """Template Selection Sub-Step"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Announcement', style=discord.ButtonStyle.primary, emoji='📢')
    async def announcement_template(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        self.session.data['content_type'] = 'embed'
        self.session.data['template'] = 'announcement'
        await interaction.response.edit_message(
            content=f'Session: `{self.session.session_id}`\n**Enter announcement content (max 1500 characters):**\nThis will be formatted as an announcement embed.',
            embed=None,
            view=None
        )
        self.session.stage = 'awaiting_template_content'
        self.session.update_activity()

    @discord.ui.button(label='Warning', style=discord.ButtonStyle.danger, emoji='⚠️')
    async def warning_template(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        self.session.data['content_type'] = 'embed'
        self.session.data['template'] = 'warning'
        await interaction.response.edit_message(
            content=f'Session: `{self.session.session_id}`\n**Enter warning content (max 1500 characters):**\nThis will be formatted as a warning embed.',
            embed=None,
            view=None
        )
        self.session.stage = 'awaiting_template_content'
        self.session.update_activity()

    @discord.ui.button(label='Info', style=discord.ButtonStyle.success, emoji='ℹ️')
    async def info_template(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        self.session.data['content_type'] = 'embed'
        self.session.data['template'] = 'info'
        await interaction.response.edit_message(
            content=f'Session: `{self.session.session_id}`\n**Enter info content (max 1500 characters):**\nThis will be formatted as an info embed.',
            embed=None,
            view=None
        )
        self.session.stage = 'awaiting_template_content'
        self.session.update_activity()

class Step3View(discord.ui.View):
    """Priority Selection Step"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Low Priority', style=discord.ButtonStyle.secondary, emoji='🔵')
    async def low_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return await self._set_priority(interaction, 'low', '🔵')

    @discord.ui.button(label='Normal Priority', style=discord.ButtonStyle.primary, emoji='🟢')
    async def normal_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return await self._set_priority(interaction, 'normal', '🟢')

    @discord.ui.button(label='High Priority', style=discord.ButtonStyle.danger, emoji='🔴')
    async def high_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return await self._set_priority(interaction, 'high', '🔴')

    async def _set_priority(self, interaction, priority, emoji):
        self.session.data['priority'] = priority
        self.session.steps_completed = 3
        
        embed = discord.Embed(
            title=f'{emoji} Priority Set',
            description=f'Message priority: **{priority.upper()}**',
            color=0x00FF00
        )
        
        view = Step4View(self.session)
        await interaction.response.edit_message(
            embed=embed,
            view=view
        )
        self.session.stage = 'scheduling'
        self.session.update_activity()

class Step4View(discord.ui.View):
    """Scheduling Step"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Send Now', style=discord.ButtonStyle.success, emoji='⚡')
    async def send_now(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        self.session.data['schedule'] = 'now'
        self.session.steps_completed = 4
        await self._next_step(interaction)

    @discord.ui.button(label='Schedule Later', style=discord.ButtonStyle.primary, emoji='⏰')
    async def schedule_later(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content=f'Session: `{self.session.session_id}`\n**Enter delay in minutes (1-1440):**\nExample: 30 (for 30 minutes)',
            embed=None,
            view=None
        )
        self.session.stage = 'awaiting_schedule_time'
        self.session.update_activity()

    async def _next_step(self, interaction):
        embed = discord.Embed(
            title='⚡ Scheduling Set',
            description='Messages will be sent immediately',
            color=0x00FF00
        )
        
        view = Step5View(self.session)
        await interaction.response.edit_message(embed=embed, view=view)
        self.session.stage = 'batch_settings'
        self.session.update_activity()

class Step5View(discord.ui.View):
    """Batch Settings Step"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Send All at Once', style=discord.ButtonStyle.primary, emoji='📤')
    async def send_all(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        self.session.data['batch_mode'] = 'all'
        self.session.steps_completed = 5
        await self._next_step(interaction)

    @discord.ui.button(label='Send in Batches', style=discord.ButtonStyle.secondary, emoji='📦')
    async def send_batches(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content=f'Session: `{self.session.session_id}`\n**Enter batch size (1-50):**\nExample: 10 (send to 10 users at a time)',
            embed=None,
            view=None
        )
        self.session.stage = 'awaiting_batch_size'
        self.session.update_activity()

    async def _next_step(self, interaction):
        embed = discord.Embed(
            title='📤 Batch Settings Set',
            description='All messages will be sent at once',
            color=0x00FF00
        )
        
        view = Step6View(self.session)
        await interaction.response.edit_message(embed=embed, view=view)
        self.session.stage = 'delay_settings'
        self.session.update_activity()

class Step6View(discord.ui.View):
    """Delay Settings Step"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='No Delay', style=discord.ButtonStyle.success, emoji='🚀')
    async def no_delay(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        self.session.data['delay'] = 0
        self.session.steps_completed = 6
        await self._next_step(interaction)

    @discord.ui.button(label='Custom Delay', style=discord.ButtonStyle.primary, emoji='⏱️')
    async def custom_delay(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(
            content=f'Session: `{self.session.session_id}`\n**Enter delay between messages in seconds (1-60):**\nExample: 5 (5 seconds between each message)',
            embed=None,
            view=None
        )
        self.session.stage = 'awaiting_delay_time'
        self.session.update_activity()

    async def _next_step(self, interaction):
        embed = discord.Embed(
            title='🚀 Delay Settings Set',
            description='No delay between messages',
            color=0x00FF00
        )
        
        view = Step7View(self.session)
        await interaction.response.edit_message(embed=embed, view=view)
        self.session.stage = 'safety_checks'
        self.session.update_activity()

class Step7View(discord.ui.View):
    """Safety Checks Step"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Skip Safety Checks', style=discord.ButtonStyle.danger, emoji='⚠️')
    async def skip_safety(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        self.session.data['safety_checks'] = False
        self.session.steps_completed = 7
        await self._next_step(interaction)

    @discord.ui.button(label='Enable Safety Checks', style=discord.ButtonStyle.success, emoji='🛡️')
    async def enable_safety(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        self.session.data['safety_checks'] = True
        self.session.steps_completed = 7
        await self._next_step(interaction)

    async def _next_step(self, interaction):
        safety_status = "Enabled" if self.session.data['safety_checks'] else "Disabled"
        emoji = "🛡️" if self.session.data['safety_checks'] else "⚠️"
        
        embed = discord.Embed(
            title=f'{emoji} Safety Checks {safety_status}',
            description=f'Safety checks: **{safety_status}**',
            color=0x00FF00
        )
        
        view = Step8View(self.session)
        await interaction.response.edit_message(embed=embed, view=view)
        self.session.stage = 'confirmation_code'
        self.session.update_activity()

class Step8View(discord.ui.View):
    """Confirmation Code Step"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session
        self.confirmation_code = str(random.randint(1000, 9999))
        self.session.data['confirmation_code'] = self.confirmation_code

    @discord.ui.button(label='Generate Code', style=discord.ButtonStyle.primary, emoji='🔑')
    async def generate_code(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        embed = discord.Embed(
            title='🔑 Confirmation Code Generated',
            description=f'**Your confirmation code: `{self.confirmation_code}`**\n\nEnter this code in your next message to proceed.',
            color=0x5865F2
        )
        
        await interaction.response.edit_message(embed=embed, view=None)
        self.session.stage = 'awaiting_confirmation_code'
        self.session.update_activity()

class Step9View(discord.ui.View):
    """Design Selection Step"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Default Design', style=discord.ButtonStyle.primary, emoji='🎨')
    async def default_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        self.session.data['design'] = 'default'
        self.session.steps_completed = 9
        await self._next_step(interaction)

    @discord.ui.button(label='Minimal Design', style=discord.ButtonStyle.secondary, emoji='⚪')
    async def minimal_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        self.session.data['design'] = 'minimal'
        self.session.steps_completed = 9
        await self._next_step(interaction)

    @discord.ui.button(label='Colorful Design', style=discord.ButtonStyle.success, emoji='🌈')
    async def colorful_design(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        self.session.data['design'] = 'colorful'
        self.session.steps_completed = 9
        await self._next_step(interaction)

    async def _next_step(self, interaction):
        design = self.session.data['design']
        embed = discord.Embed(
            title='🎨 Design Selected',
            description=f'Message design: **{design.title()}**',
            color=0x00FF00
        )
        
        view = Step10View(self.session)
        await interaction.response.edit_message(embed=embed, view=view)
        self.session.stage = 'preview'
        self.session.update_activity()

class Step10View(discord.ui.View):
    """Preview and Final Step"""
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Preview Message', style=discord.ButtonStyle.primary, emoji='👁️')
    async def preview_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        # Create preview embed
        targets = self.session.data.get('targets', [])
        content = self.session.data.get('message_content', 'No content')
        
        preview_embed = discord.Embed(
            title='👁️ Message Preview',
            description='**This is how your message will look:**',
            color=0x5865F2
        )
        
        # Show message preview based on content type
        if self.session.data.get('content_type') == 'embed':
            template = self.session.data.get('template', 'info')
            if template == 'announcement':
                msg_embed = discord.Embed(title='📢 Announcement', description=content, color=0x5865F2)
            elif template == 'warning':
                msg_embed = discord.Embed(title='⚠️ Warning', description=content, color=0xFF0000)
            else:
                msg_embed = discord.Embed(title='ℹ️ Information', description=content, color=0x00FF00)
            
            preview_embed.add_field(name='Message Content', value='*Embed message (see below)*', inline=False)
        else:
            preview_embed.add_field(name='Message Content', value=f'```{content[:500]}{"..." if len(content) > 500 else ""}```', inline=False)
        
        preview_embed.add_field(name='Recipients', value=f'{len(targets)} users', inline=True)
        preview_embed.add_field(name='Priority', value=self.session.data.get('priority', 'normal').title(), inline=True)
        preview_embed.add_field(name='Schedule', value=self.session.data.get('schedule', 'now').title(), inline=True)
        
        if self.session.data.get('content_type') == 'embed':
            await interaction.response.edit_message(embed=preview_embed, view=self)
            await interaction.followup.send(embed=msg_embed)
        else:
            await interaction.response.edit_message(embed=preview_embed, view=self)

    @discord.ui.button(label='Send Messages', style=discord.ButtonStyle.success, emoji='✅')
    async def send_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        await interaction.response.defer()
        
        # Get all the session data
        targets = self.session.data.get('targets', [])
        content = self.session.data.get('message_content', '')
        content_type = self.session.data.get('content_type', 'plain')
        template = self.session.data.get('template', 'info')
        delay = self.session.data.get('delay', 0)
        batch_size = self.session.data.get('batch_size', len(targets))
        
        if not targets or not content:
            await interaction.followup.send('❌ Missing targets or content!', ephemeral=True)
            return
        
        # Create the message to send
        if content_type == 'embed':
            if template == 'announcement':
                message_embed = discord.Embed(title='📢 Announcement', description=content, color=0x5865F2)
            elif template == 'warning':
                message_embed = discord.Embed(title='⚠️ Warning', description=content, color=0xFF0000)
            else:
                message_embed = discord.Embed(title='ℹ️ Information', description=content, color=0x00FF00)
            message_to_send = message_embed
        else:
            message_to_send = content
        
        # Send messages
        successful_sends = 0
        failed_sends = 0
        
        status_embed = discord.Embed(
            title='📤 Sending Messages...',
            description=f'Sending to {len(targets)} recipients...',
            color=0xFFA500
        )
        status_message = await interaction.followup.send(embed=status_embed)
        
        for i, target in enumerate(targets):
            try:
                if isinstance(message_to_send, discord.Embed):
                    await target.send(embed=message_to_send)
                else:
                    await target.send(message_to_send)
                successful_sends += 1
                
                # Update status every 5 messages
                if (i + 1) % 5 == 0:
                    progress = int(((i + 1) / len(targets)) * 100)
                    status_embed.description = f'Progress: {i + 1}/{len(targets)} ({progress}%)\nSuccessful: {successful_sends} | Failed: {failed_sends}'
                    await status_message.edit(embed=status_embed)
                
                # Apply delay if specified
                if delay > 0 and i < len(targets) - 1:
                    await asyncio.sleep(delay)
                    
            except Exception as e:
                failed_sends += 1
                print(f"Failed to send message to {target}: {e}")
        
        # Final status update
        final_embed = discord.Embed(
            title='✅ Message Sending Complete!',
            description=f'**Results:**\n✅ Successful: {successful_sends}\n❌ Failed: {failed_sends}\n📊 Total: {len(targets)}',
            color=0x00FF00 if failed_sends == 0 else 0xFFA500,
            timestamp=datetime.utcnow()
        )
        
        await status_message.edit(embed=final_embed)
        
        # Clean up session
        if self.session.session_id in active_sessions:
            del active_sessions[self.session.session_id]
        
        self.session.steps_completed = 10
        self.session.stage = 'completed'

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger, emoji='❌')
    async def cancel_session(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('❌ Not your session', ephemeral=True)
            return
        
        # Clean up session
        if self.session.session_id in active_sessions:
            del active_sessions[self.session.session_id]
        
        embed = discord.Embed(
            title='❌ Session Cancelled',
            description='Message sending session has been cancelled.',
            color=0xFF0000
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

# Message event handler to process user inputs
@bot.event
async def on_message(message):
    # Ignore bot messages
    if message.author.bot:
        return
    
    # Process commands first
    await bot.process_commands(message)
    
    # Check if user has an active session waiting for input
    user_session = None
    for session_id, session in active_sessions.items():
        if session.user_id == message.author.id and session.channel_id == message.channel.id:
            user_session = session
            break
    
    if not user_session:
        return
    
    # Handle different input stages
    if user_session.stage == 'awaiting_role_id':
        await handle_role_id_input(message, user_session, message.content.strip())
    elif user_session.stage == 'awaiting_mentions':
        await handle_mentions_input(message, user_session)
    elif user_session.stage == 'awaiting_custom_list':
        await handle_custom_list_input(message, user_session, message.content.strip())
    elif user_session.stage == 'awaiting_message_content':
        await handle_message_content_input(message, user_session, message.content)
    elif user_session.stage == 'awaiting_template_content':
        await handle_template_content_input(message, user_session, message.content)
    elif user_session.stage == 'awaiting_schedule_time':
        await handle_schedule_time_input(message, user_session, message.content.strip())
    elif user_session.stage == 'awaiting_batch_size':
        await handle_batch_size_input(message, user_session, message.content.strip())
    elif user_session.stage == 'awaiting_delay_time':
        await handle_delay_time_input(message, user_session, message.content.strip())
    elif user_session.stage == 'awaiting_confirmation_code':
        await handle_confirmation_code_input(message, user_session, message.content.strip())

# Input handling functions
async def handle_role_id_input(message, session, role_id_str):
    """Handle role ID input"""
    try:
        role_id = int(role_id_str)
        role = message.guild.get_role(role_id)
        
        if not role:
            await message.channel.send('❌ Role not found, try again:')
            return
        
        # Get role members
        members = [member for member in role.members if not member.bot]
        
        if not members:
            await message.channel.send('❌ No members in role, try again:')
            return
        
        session.data['targets'] = members
        session.steps_completed = 1
        
        embed = discord.Embed(
            title='✅ Targets Selected', 
            description=f'**Role:** {role.name}\n**Members:** {len(members)}',
            color=0x00FF00
        )
        
        # Show some members
        member_list = []
        for member in members[:10]:
            member_list.append(f'• {member.display_name}')
        
        if member_list:
            embed.add_field(
                name='Members Preview', 
                value='\n'.join(member_list) + (f'\n... and {len(members) - 10} more' if len(members) > 10 else ''),
                inline=False
            )
        
        # Move to content selection
        view = Step2View(session)
        await message.channel.send(embed=embed, view=view)
        session.stage = 'content_selection'
        session.update_activity()
        
    except ValueError:
        await message.channel.send('❌ Invalid role ID, enter numbers only:')

async def handle_mentions_input(message, session):
    """Handle mentioned users input"""
    mentioned_users = [user for user in message.mentions if not user.bot]
    
    if not mentioned_users:
        await message.channel.send('❌ No valid users mentioned, try again:')
        return
    
    session.data['targets'] = mentioned_users
    session.steps_completed = 1
    
    embed = discord.Embed(
        title='✅ Targets Selected',
        description=f'**Mentioned users:** {len(mentioned_users)}',
        color=0x00FF00
    )
    
    for i, user in enumerate(mentioned_users[:10]):  # Show first 10
        embed.add_field(name=f'User {i+1}', value=user.mention, inline=True)
    
    if len(mentioned_users) > 10:
        embed.add_field(name='...', value=f'and {len(mentioned_users) - 10} more', inline=True)
    
    view = Step2View(session)
    await message.channel.send(embed=embed, view=view)
    session.stage = 'content_selection'
    session.update_activity()

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
            await message.channel.send('❌ No valid users found, try again:')
            return
        
        session.data['targets'] = users
        session.steps_completed = 1
        
        embed = discord.Embed(
            title='✅ Targets Selected',
            description=f'**Custom list:** {len(users)} users',
            color=0x00FF00
        )
        
        # Show user preview
        user_list = []
        for user in users[:10]:
            user_list.append(f'• {user.display_name} ({user.id})')
        
        if user_list:
            embed.add_field(
                name='Users Preview',
                value='\n'.join(user_list) + (f'\n... and {len(users) - 10} more' if len(users) > 10 else ''),
                inline=False
            )
        
        view = Step2View(session)
        await message.channel.send(embed=embed, view=view)
        session.stage = 'content_selection'
        session.update_activity()
        
    except ValueError:
        await message.channel.send('❌ Invalid format, use: `id1, id2, id3`')

async def handle_message_content_input(message, session, content):
    """Handle message content input"""
    if len(content) > 2000:
        await message.channel.send('❌ Message too long (max 2000 characters), try again:')
        return
    
    if not content:
        await message.channel.send('❌ Message cannot be empty, try again:')
        return
    
    session.data['message_content'] = content
    session.steps_completed = 2
    
    embed = discord.Embed(
        title='✅ Message Content Set',
        description=f'**Content length:** {len(content)} characters',
        color=0x00FF00
    )
    
    # Show preview of content
    preview = content[:300] + '...' if len(content) > 300 else content
    embed.add_field(name='Preview', value=f'```{preview}```', inline=False)
    
    view = Step3View(session)
    await message.channel.send(embed=embed, view=view)
    session.stage = 'priority_selection'
    session.update_activity()

async def handle_template_content_input(message, session, content):
    """Handle template-based content input"""
    if len(content) > 1500:  # Templates have additional formatting
        await message.channel.send('❌ Content too long for template (max 1500 characters), try again:')
        return
    
    if not content:
        await message.channel.send('❌ Content cannot be empty, try again:')
        return
    
    session.data['message_content'] = content
    session.steps_completed = 2
    
    template_name = session.data['template']
    embed = discord.Embed(
        title='✅ Template Content Set',
        description=f'**Template:** {template_name.title()}\n**Content length:** {len(content)} characters',
        color=0x00FF00
    )
    
    # Show template preview
    if template_name == 'announcement':
        preview_embed = discord.Embed(title='📢 Announcement', description=content[:200] + '...' if len(content) > 200 else content, color=0x5865F2)
    elif template_name == 'warning':
        preview_embed = discord.Embed(title='⚠️ Warning', description=content[:200] + '...' if len(content) > 200 else content, color=0xFF0000)
    else:
        preview_embed = discord.Embed(title='ℹ️ Information', description=content[:200] + '...' if len(content) > 200 else content, color=0x00FF00)
    
    await message.channel.send(embed=embed)
    await message.channel.send("**Template Preview:**", embed=preview_embed)
    
    view = Step3View(session)
    await message.channel.send("**Continue to next step:**", view=view)
    session.stage = 'priority_selection'
    session.update_activity()

async def handle_schedule_time_input(message, session, time_str):
    """Handle schedule time input"""
    try:
        minutes = int(time_str)
        if minutes < 1 or minutes > 1440:
            await message.channel.send('❌ Invalid time. Enter minutes between 1-1440:')
            return
        
        session.data['schedule'] = f'{minutes} minutes'
        session.data['schedule_minutes'] = minutes
        session.steps_completed = 4
        
        embed = discord.Embed(
            title='⏰ Schedule Set',
            description=f'Messages will be sent in **{minutes} minutes**',
            color=0x00FF00
        )
        
        view = Step5View(session)
        await message.channel.send(embed=embed, view=view)
        session.stage = 'batch_settings'
        session.update_activity()
        
    except ValueError:
        await message.channel.send('❌ Invalid number. Enter minutes (1-1440):')

async def handle_batch_size_input(message, session, size_str):
    """Handle batch size input"""
    try:
        batch_size = int(size_str)
        target_count = len(session.data.get('targets', []))
        
        if batch_size < 1 or batch_size > min(50, target_count):
            await message.channel.send(f'❌ Invalid batch size. Enter 1-{min(50, target_count)}:')
            return
        
        session.data['batch_mode'] = 'batches'
        session.data['batch_size'] = batch_size
        session.steps_completed = 5
        
        batches_needed = (target_count + batch_size - 1) // batch_size
        
        embed = discord.Embed(
            title='📦 Batch Settings Set',
            description=f'**Batch size:** {batch_size}\n**Total batches:** {batches_needed}',
            color=0x00FF00
        )
        
        view = Step6View(session)
        await message.channel.send(embed=embed, view=view)
        session.stage = 'delay_settings'
        session.update_activity()
        
    except ValueError:
        await message.channel.send('❌ Invalid number. Enter batch size (1-50):')

async def handle_delay_time_input(message, session, delay_str):
    """Handle delay time input"""
    try:
        delay = int(delay_str)
        if delay < 1 or delay > 60:
            await message.channel.send('❌ Invalid delay. Enter seconds between 1-60:')
            return
        
        session.data['delay'] = delay
        session.steps_completed = 6
        
        embed = discord.Embed(
            title='⏱️ Delay Settings Set',
            description=f'**Delay between messages:** {delay} seconds',
            color=0x00FF00
        )
        
        view = Step7View(session)
        await message.channel.send(embed=embed, view=view)
        session.stage = 'safety_checks'
        session.update_activity()
        
    except ValueError:
        await message.channel.send('❌ Invalid number. Enter delay in seconds (1-60):')

async def handle_confirmation_code_input(message, session, code_str):
    """Handle confirmation code input"""
    expected_code = session.data.get('confirmation_code', '')
    
    if code_str != expected_code:
        await message.channel.send(f'❌ Incorrect code. Expected: `{expected_code}`')
        return
    
    session.steps_completed = 8
    
    embed = discord.Embed(
        title='✅ Confirmation Code Verified',
        description='Code verified successfully!',
        color=0x00FF00
    )
    
    view = Step9View(session)
    await message.channel.send(embed=embed, view=view)
    session.stage = 'design_selection'
    session.update_activity()

# Session cleanup task
async def cleanup_expired_sessions():
    """Clean up expired sessions"""
    while True:
        expired_sessions = []
        for session_id, session in active_sessions.items():
            if session.is_expired():
                expired_sessions.append(session_id)
        
        for session_id in expired_sessions:
            del active_sessions[session_id]
        
        await asyncio.sleep(300)  # Check every 5 minutes

# Start cleanup task when bot is ready
@bot.event
async def on_ready():
    print(f'{bot.user} has logged in!')
    bot.loop.create_task(cleanup_expired_sessions())
    
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

# Configuration
TARGET_ROLE_ID = 1382280238842515587
GUILD_ID = 1122152849833459842  # Your server ID
EVENT_LINK = 'https://discord.com/events/1122152849833459842/1384531945312227389'
GAME_LINK = 'https://www.roblox.com/games/13550599465/Trenches'
BATTLE_TIMESTAMP = '<t:1750507200:t>'  # This will show in user's timezone

class BattleButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # Buttons won't timeout
        
        # Add Game Link Button
        game_button = discord.ui.Button(
            label='🎮 Join Game',
            style=discord.ButtonStyle.primary,
            url=GAME_LINK
        )
        self.add_item(game_button)
        
        # Add Event Link Button  
        event_button = discord.ui.Button(
            label='📅 View Event',
            style=discord.ButtonStyle.secondary,
            url=EVENT_LINK
        )
        self.add_item(event_button)

async def send_battle_notifications():
    """Send battle notifications to all users with the target role"""
    try:
        print('starting notifications')
        
        # Get the guild
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            print('guild not found')
            return
        
        # Fetch all members to ensure we have complete member data
        await guild.chunk()
        
        # Find the target role
        target_role = guild.get_role(TARGET_ROLE_ID)
        if not target_role:
            print('role not found')
            return
        
        print(f'found role: {target_role.name} with {len(target_role.members)} members')
        
        # Create the embed message (without link fields)
        embed = discord.Embed(
            title='🔥 Battle Alert!',
            description=f"There will be a battle happening later today at {BATTLE_TIMESTAMP}! (this time is converted to your own time)",
            color=0xFF4444,
            timestamp=discord.utils.utcnow()
        )
        
        embed.add_field(
            name='✅ Can Attend?',
            value='Press "Interested" on the event and ping <@.iloh>',
            inline=False
        )
        
        embed.add_field(
            name='❌ Cannot Attend?',
            value='Ping <@.iloh> and let them know you cannot attend (no reason needed)',
            inline=False
        )
        
        embed.set_footer(text='Battle Notification System')
        
        # Create the button view
        view = BattleButtons()
        
        success_count = 0
        fail_count = 0
        
        # Send DM to each member with the role
        for member in target_role.members:
            try:
                await member.send(embed=embed, view=view)
                print(f'sent dm to {member.display_name}')
                success_count += 1
                
                # Add a small delay to avoid rate limiting
                await asyncio.sleep(1)
                
            except discord.Forbidden:
                print(f'dms disabled: {member.display_name}')
                fail_count += 1
            except discord.HTTPException as e:
                print(f'http error {member.display_name}: {e}')
                fail_count += 1
            except Exception as e:
                print(f'error {member.display_name}: {e}')
                fail_count += 1
        
        print(f'summary: sent {success_count} failed {fail_count} total {len(target_role.members)}')
        
        return success_count, fail_count
        
    except Exception as e:
        print(f'error in notifications: {e}')
        return 0, 0

@bot.command(name='sendi')
async def send_battle_command(ctx):
    """Command to trigger battle notifications"""
    # Add your user ID here for permission check
    authorized_users = [728201873366056992]  # Your Discord user ID
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    await ctx.send('sending notifications')
    
    success, fail = await send_battle_notifications()
    
    await ctx.send(f'done. sent: {success} failed: {fail}')

@bot.command(name='testicle')
async def test_battle_command(ctx):
    """Test command to send battle notification to yourself only"""
    # Add your user ID here for permission check
    authorized_users = [728201873366056992]  # Your Discord user ID
    
    if ctx.author.id not in authorized_users:
        await ctx.send('not authorized')
        return
    
    # Get your user object
    try:
        user = await bot.fetch_user(728201873366056992)
    except:
        await ctx.send('user not found')
        return
    
    # Create the embed message (without link fields)
    embed = discord.Embed(
        title='🔥 Battle Alert! (TEST)',
        description=f"There will be a battle happening later today at {BATTLE_TIMESTAMP}! (this time is converted to your own time)",
        color=0xFF4444,
        timestamp=discord.utils.utcnow()
    )
    
    embed.add_field(
        name='✅ Can Attend?',
        value='Press "Interested" on the event and ping <@.iloh>',
        inline=False
    )
    
    embed.add_field(
        name='❌ Cannot Attend?',
        value='Ping <@.iloh> and let them know you cannot attend (no reason needed)',
        inline=False
    )
    
    embed.set_footer(text='Battle Notification System - TEST MESSAGE')
    
    # Create the button view
    view = BattleButtons()
    
    try:
        await user.send(embed=embed, view=view)
        await ctx.send('test sent')
        print(f'test dm sent to {user.name}')
    except discord.Forbidden:
        await ctx.send('dms disabled')
        print('test dm failed: dms disabled')

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return  # Ignore unknown commands
    print(f'command error: {error}')

# Alternative: Auto-run when bot starts (uncomment if needed)
"""
@bot.event
async def on_ready():
    print(f'✅ Bot is ready! Logged in as {bot.user}')
    
    # Wait a bit for everything to load, then send notifications
    await asyncio.sleep(5)
    await send_battle_notifications()
"""

# Run the bot
if __name__ == "__main__":
    # Get token from environment variable
    token = os.getenv('DISCORD_TOKEN') or os.getenv('BOT_TOKEN')
    
    if not token:
        print("Error: No bot token found in environment variables!")
        print("Please set DISCORD_TOKEN or BOT_TOKEN environment variable")
        exit(1)
    
    bot.run(token)
