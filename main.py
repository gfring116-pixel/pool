import discord
from discord.ext import commands
import asyncio
import os
import time
import random
from datetime import datetime, timedelta

# Bot setup
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Storage
active_sessions = {}
send_statistics = {}

# Message templates
MESSAGE_TEMPLATES = {
    'announcement': {'title': '📢 Important Announcement', 'color': 0x5865F2, 'footer': 'Official Announcement'},
    'event': {'title': '📅 Event Notification', 'color': 0x00D4AA, 'footer': 'Event Management'},
    'urgent': {'title': '🚨 Urgent Notice', 'color': 0xFF4444, 'footer': 'Emergency Alert'},
    'reminder': {'title': '⏰ Reminder', 'color': 0xFFA500, 'footer': 'Reminder Service'},
    'update': {'title': '🔄 System Update', 'color': 0x9932CC, 'footer': 'Update Notification'}
}

AUTHORIZED_USER = 728201873366056992

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
            'design': 'standard',
            'batch_size': 10,
            'delay': 1,
            'confirmation_code': None
        }
        self.created_at = datetime.utcnow()

class TargetSelectionView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Role Members', style=discord.ButtonStyle.primary, emoji='👥')
    async def select_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('Not your session', ephemeral=True)
            return
        
        await interaction.response.send_message('Enter role ID:', ephemeral=True)
        self.session.stage = 'awaiting_role_id'

    @discord.ui.button(label='Mentioned Users', style=discord.ButtonStyle.secondary, emoji='@')
    async def select_mentions(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('Not your session', ephemeral=True)
            return
        
        await interaction.response.send_message('Mention users in next message:', ephemeral=True)
        self.session.stage = 'awaiting_mentions'

    @discord.ui.button(label='Custom List', style=discord.ButtonStyle.success, emoji='📝')
    async def select_custom(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('Not your session', ephemeral=True)
            return
        
        await interaction.response.send_message('Enter user IDs separated by commas:', ephemeral=True)
        self.session.stage = 'awaiting_custom_list'

class ContentTypeView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Plain Text', style=discord.ButtonStyle.secondary, emoji='📝')
    async def plain_text(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('Not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(content='Enter your message:', view=None)
        self.session.stage = 'awaiting_message_content'
        self.session.data['content_type'] = 'plain'

    @discord.ui.button(label='Template Based', style=discord.ButtonStyle.success, emoji='📋')
    async def template_based(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('Not your session', ephemeral=True)
            return
        
        template_view = TemplateSelectionView(self.session)
        await interaction.response.edit_message(content='Choose template:', view=template_view)
        self.session.stage = 'selecting_template'

class TemplateSelectionView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session
        
        for template_name in MESSAGE_TEMPLATES.keys():
            button = discord.ui.Button(
                label=template_name.title(),
                style=discord.ButtonStyle.secondary,
                custom_id=f"template_{template_name}"
            )
            button.callback = self.template_callback
            self.add_item(button)

    async def template_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('Not your session', ephemeral=True)
            return
        
        template_name = interaction.data['custom_id'].replace('template_', '')
        self.session.data['template'] = template_name
        
        await interaction.response.edit_message(
            content=f'Selected template: {template_name}\nEnter your message content:',
            view=None
        )
        self.session.stage = 'awaiting_template_content'

class BatchSettingsView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Small (5)', style=discord.ButtonStyle.secondary, emoji='🔢')
    async def small_batch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 5)

    @discord.ui.button(label='Medium (10)', style=discord.ButtonStyle.primary, emoji='🔢')
    async def medium_batch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 10)

    @discord.ui.button(label='Large (20)', style=discord.ButtonStyle.success, emoji='🔢')
    async def large_batch(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.set_batch_size(interaction, 20)

    async def set_batch_size(self, interaction, size):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('Not your session', ephemeral=True)
            return
        
        self.session.data['batch_size'] = size
        delay_view = DelaySettingsView(self.session)
        await interaction.response.edit_message(
            content=f'Batch size: {size}\nSet delay between batches:',
            view=delay_view
        )

class DelaySettingsView(discord.ui.View):
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

    async def set_delay(self, interaction, delay):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('Not your session', ephemeral=True)
            return
        
        self.session.data['delay'] = delay
        confirmation_view = ConfirmationView(self.session)
        await interaction.response.edit_message(
            content=f'Delay set: {delay}s\nGenerate confirmation code:',
            view=confirmation_view
        )

class ConfirmationView(discord.ui.View):
    def __init__(self, session):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label='Generate Code', style=discord.ButtonStyle.success, emoji='🔐')
    async def generate_code(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('Not your session', ephemeral=True)
            return
        
        code = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        self.session.data['confirmation_code'] = code
        
        await interaction.response.edit_message(
            content=f'Confirmation code: **{code}**\nType this code to proceed:',
            view=None
        )
        self.session.stage = 'awaiting_confirmation_code'

class FinalConfirmationView(discord.ui.View):
    def __init__(self, session, message_data):
        super().__init__(timeout=600)
        self.session = session
        self.message_data = message_data

    @discord.ui.button(label='Send Messages', style=discord.ButtonStyle.success, emoji='🚀')
    async def send_messages(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('Not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(content='Processing delivery...', embed=None, view=None)
        
        success, fail = await execute_message_delivery(self.session, self.message_data)
        update_statistics(self.session.user_id, success, fail)
        
        await interaction.followup.send(
            f'Delivery complete!\n'
            f'Sent: {success}\n'
            f'Failed: {fail}\n'
            f'Total targets: {len(self.session.data["targets"])}'
        )
        
        if self.session.session_id in active_sessions:
            del active_sessions[self.session.session_id]

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.danger, emoji='❌')
    async def cancel_send(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.session.user_id:
            await interaction.response.send_message('Not your session', ephemeral=True)
            return
        
        await interaction.response.edit_message(content='Message delivery cancelled', embed=None, view=None)
        if self.session.session_id in active_sessions:
            del active_sessions[self.session.session_id]

def create_message_from_session(session):
    """Create the final message based on session data"""
    content = session.data.get('message_content', '')
    template = session.data.get('template')
    
    if template and template in MESSAGE_TEMPLATES:
        template_data = MESSAGE_TEMPLATES[template]
        embed = discord.Embed(
            title=template_data['title'],
            description=content,
            color=template_data['color'],
            timestamp=datetime.utcnow()
        )
        embed.set_footer(text=template_data['footer'])
        return {'type': 'embed', 'embed': embed}
    
    return {'type': 'text', 'content': content}

async def execute_message_delivery(session, message_data):
    """Execute the actual message delivery"""
    targets = session.data['targets']
    batch_size = session.data['batch_size']
    delay = session.data['delay']
    
    success_count = 0
    fail_count = 0
    
    for i in range(0, len(targets), batch_size):
        batch = targets[i:i + batch_size]
        
        for target in batch:
            try:
                if message_data['type'] == 'text':
                    await target.send(message_data['content'])
                else:
                    await target.send(embed=message_data['embed'])
                
                success_count += 1
                await asyncio.sleep(0.5)
                
            except discord.Forbidden:
                fail_count += 1
            except Exception:
                fail_count += 1
        
        if i + batch_size < len(targets) and delay > 0:
            await asyncio.sleep(delay)
    
    return success_count, fail_count

def update_statistics(user_id, success, fail):
    """Update user sending statistics"""
    if user_id not in send_statistics:
        send_statistics[user_id] = {'total_sent': 0, 'total_failed': 0, 'sessions_completed': 0}
    
    stats = send_statistics[user_id]
    stats['total_sent'] += success
    stats['total_failed'] += fail
    stats['sessions_completed'] += 1

@bot.event
async def on_ready():
    print(f'Bot ready: {bot.user}')
    print(f'Guilds: {len(bot.guilds)}')

@bot.command(name='send')
async def send_message(ctx):
    """Start the message sending process"""
    if ctx.author.id != AUTHORIZED_USER:
        await ctx.send('Not authorized')
        return
    
    session = MessageSession(ctx.author.id, ctx.channel.id, ctx.guild.id)
    active_sessions[session.session_id] = session
    
    embed = discord.Embed(
        title='📨 Message Delivery System',
        description=f'Session ID: `{session.session_id}`\nStep 1: Select message recipients',
        color=0x5865F2,
        timestamp=datetime.utcnow()
    )
    
    view = TargetSelectionView(session)
    await ctx.send(embed=embed, view=view)
    session.stage = 'target_selection'

@bot.event
async def on_message(message):
    """Handle text input during sessions"""
    if message.author.bot:
        return
    
    user_session = None
    for session in active_sessions.values():
        if session.user_id == message.author.id and session.channel_id == message.channel.id:
            user_session = session
            break
    
    if not user_session:
        await bot.process_commands(message)
        return
    
    content = message.content.strip()
    stage = user_session.stage
    
    try:
        if stage == 'awaiting_role_id':
            role_id = int(content)
            role = message.guild.get_role(role_id)
            if not role:
                await message.channel.send('Role not found, try again:')
                return
            
            members = [member for member in role.members if not member.bot]
            if not members:
                await message.channel.send('No members in role, try again:')
                return
            
            user_session.data['targets'] = members
            view = ContentTypeView(user_session)
            await message.channel.send(f'✅ Selected {len(members)} members from {role.name}\nChoose message type:', view=view)
            user_session.stage = 'content_selection'
            
        elif stage == 'awaiting_mentions':
            mentioned_users = [user for user in message.mentions if not user.bot]
            if not mentioned_users:
                await message.channel.send('No valid users mentioned, try again:')
                return
            
            user_session.data['targets'] = mentioned_users
            view = ContentTypeView(user_session)
            await message.channel.send(f'✅ Selected {len(mentioned_users)} mentioned users\nChoose message type:', view=view)
            user_session.stage = 'content_selection'
            
        elif stage == 'awaiting_custom_list':
            user_ids = [int(uid.strip()) for uid in content.split(',')]
            users = []
            for user_id in user_ids:
                try:
                    user = await bot.fetch_user(user_id)
                    if user and not user.bot:
                        users.append(user)
                except:
                    continue
            
            if not users:
                await message.channel.send('No valid users found, try again:')
                return
            
            user_session.data['targets'] = users
            view = ContentTypeView(user_session)
            await message.channel.send(f'✅ Selected {len(users)} users from custom list\nChoose message type:', view=view)
            user_session.stage = 'content_selection'
            
        elif stage in ['awaiting_message_content', 'awaiting_template_content']:
            if len(content) > 2000:
                await message.channel.send('Message too long (max 2000 characters), try again:')
                return
            
            user_session.data['message_content'] = content
            view = BatchSettingsView(user_session)
            await message.channel.send('✅ Message content set\nConfigure batch settings:', view=view)
            
        elif stage == 'awaiting_confirmation_code':
            expected_code = user_session.data.get('confirmation_code')
            if content != expected_code:
                await message.channel.send(f'Incorrect code, expected: **{expected_code}**')
                return
            
            message_data = create_message_from_session(user_session)
            
            preview_content = "**PREVIEW:**"
            final_view = FinalConfirmationView(user_session, message_data)
            
            if message_data['type'] == 'embed':
                await message.channel.send(content=preview_content, embed=message_data['embed'], view=final_view)
            else:
                await message.channel.send(content=f"{preview_content}\n{message_data['content']}", view=final_view)
            
            user_session.stage = 'final_confirmation'
            
    except ValueError:
        await message.channel.send('Invalid input format, try again:')
    except Exception as e:
        await message.channel.send(f'Error processing input: {e}')

@bot.command(name='sessions')
async def list_sessions(ctx):
    """List active sessions"""
    if ctx.author.id != AUTHORIZED_USER:
        await ctx.send('Not authorized')
        return
    
    if not active_sessions:
        await ctx.send('No active sessions')
        return
    
    embed = discord.Embed(title='📊 Active Sessions', color=0x5865F2)
    
    for session_id, session in active_sessions.items():
        embed.add_field(
            name=f'Session: {session_id}',
            value=f'Stage: {session.stage}\nTargets: {len(session.data.get("targets", []))}',
            inline=True
        )
    
    await ctx.send(embed=embed)

@bot.command(name='stats')
async def show_stats(ctx):
    """Show user statistics"""
    if ctx.author.id != AUTHORIZED_USER:
        await ctx.send('Not authorized')
        return
    
    if ctx.author.id not in send_statistics:
        await ctx.send('No statistics available')
        return
    
    stats = send_statistics[ctx.author.id]
    embed = discord.Embed(title='📈 Your Statistics', color=0x00D4AA)
    embed.add_field(name='Messages Sent', value=stats['total_sent'], inline=True)
    embed.add_field(name='Failed Deliveries', value=stats['total_failed'], inline=True)
    embed.add_field(name='Sessions Completed', value=stats['sessions_completed'], inline=True)
    
    await ctx.send(embed=embed)

if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN') or os.getenv('BOT_TOKEN')
    if not token:
        print("Error: No bot token found in environment variables!")
        exit(1)
    bot.run(token)
