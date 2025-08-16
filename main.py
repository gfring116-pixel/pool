import os
import json
import re
import discord
from discord.ext import commands
import gspread
import gspread.exceptions as gspread_exceptions
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from datetime import timedelta
from collections import defaultdict

# Abuse logging config
LOG_CHANNEL_ID = 1314931440496017481
MAX_POINTS_SINGLE_AWARD = 80
MAX_POINTS_HOURLY = 150

# Keep recent awards in memory: {(giver_id, receiver_id): [(points, datetime), ...]}
recent_awards = defaultdict(list)

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Google Sheets Setup
credentials_str = os.getenv("GOOGLE_CREDENTIALS")
creds_dict = json.loads(credentials_str)
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
main_sheet = client.open("__1ST VANGUARD DIVISION MERIT DATA__").sheet1
special_sheet = client.open("Points Tracker").sheet1

# Role IDs for regiments
REGIMENT_ROLES = {
    1320153442244886598: "MP",
    1234503490886176849: "6TH",
    1357959629359026267: "3RD",
    1387191982866038918919: "1ST",
    1251102603174215750: "4TH",
    1339571735028174919: "1AS"
}

# Host-only roles
HOST_ROLES = {
    1255061914732597268,
    1134711656811855942,
    1279450222287655023
}

# Ranks (threshold, full name, abbreviation, role ID)
RANKS = [
    (0,   "Recruit",         "Recruit",   1207981849528246282),
    (15,  "Soldat",          "SOLDAT",1214438109173907546),
    (65,  "Corporal",        "CPL",   1208374047994281985),
    (150, "Junior Sergeant", "SGT",  1225058657507606600),
    (275, "Sergeant",        "SGT",   1207980351826173962),
    (385, "Staff Sergeant",  "SSGT",  1214438711379370034),
    (555, "Sergeant Major",  "SMGT",   1207980354317844521),
    (700, "Master Sergeant", "MSGT",  1214438714508312596)
]

def extract_roblox_name(nickname: str) -> str:
    return nickname.split()[-1] if nickname else "Unknown"

def get_regiment_info(member: discord.Member):
    role_map = {
        1339571735028174919: ("1ST AIRFORCE SQUADRON", "main"),
        1357959629359026267: ("3RD IMPERIAL INFANTRY REGIMENT", "main"),
        1251102603174215750: ("4TH RIFLE'S INFANTERIE REGIMENT", "main"),
        1320153442244886598: ("MP", "special"),
        1387191982866038919: ("1ST", "special"),
        1234711656811855942: ("6TH", "special")
    }
    for role in member.roles:
        if role.id in role_map:
            header, sheet_type = role_map[role.id]
            return {"header": header, "sheet_type": sheet_type, "regiment": role.name}
    return None

@bot.command()
@commands.has_any_role(*HOST_ROLES)
async def awardpoints(ctx, member: discord.Member, points: int):
    if points <= 0:
        return await ctx.send("Points must be a positive number.")

    roblox_username = extract_roblox_name(member.display_name)
    if roblox_username == "Unknown":
        return await ctx.send("Member has no nickname set.")

    info = get_regiment_info(member)
    if not info:
        return await ctx.send("Could not determine regiment or unsupported regiment.")

    sheet = main_sheet if info["sheet_type"] == "main" else special_sheet

    # Locate headers
    try:
        name_cell = sheet.find("Name")
        merit_cell = sheet.find("Merits")
        rank_cell = sheet.find("Rank")
    except gspread_exceptions.CellNotFound:
        return await ctx.send("Could not find one of: Name, Merits, Rank headers.")

    # Defensive: if find returned None for any header, stop with helpful message
    if not (name_cell and merit_cell and rank_cell):
        return await ctx.send("Could not locate one of the headers: Name, Merits, Rank. Check sheet headers.")

    # Prepare indices
    name_col = name_cell.col
    merit_col = merit_cell.col
    rank_col = rank_cell.col
    data_start_row = name_cell.row + 1

    # Fetch existing names below header
    existing_names = sheet.col_values(name_col)[data_start_row - 1 :]

    # Check if user exists
    try:
        idx = existing_names.index(roblox_username)
        row = data_start_row + idx
        current_merits = int(sheet.cell(row, merit_col).value or 0)
    except ValueError:
        # New user: calculate threshold and insert
        member_role_ids = {r.id for r in member.roles}
        existing_threshold = next((t for t, _, _, rid in RANKS if rid in member_role_ids), 0)
        current_merits = existing_threshold

        new_total = current_merits + points
        new_rank = next((r for r in reversed(RANKS) if new_total >= r[0]), RANKS[0])

        # Find first empty slot in Name column under header
        insert_row = None
        for i, name in enumerate(existing_names):
            if not name.strip():
                insert_row = data_start_row + i
                break
        if insert_row is None:
            insert_row = data_start_row + len(existing_names)

        sheet.insert_row([roblox_username, new_total, new_rank[1]], index=insert_row)
        row = insert_row
    else:
        # Existing user: update merits and rank
        new_total = current_merits + points
        new_rank = next((r for r in reversed(RANKS) if new_total >= r[0]), RANKS[0])
        sheet.update_cell(row, merit_col, new_total)
        sheet.update_cell(row, rank_col, new_rank[1])

    # Role cleanup and assignment
    old_role_ids = {r[3] for r in RANKS}
    cleaned_roles = [r for r in member.roles if r.id not in old_role_ids]
    new_role = ctx.guild.get_role(new_rank[3])
    if new_role:
        cleaned_roles.append(new_role)
    final_abbr = new_rank[2]

    # Nickname update: swap only rank
    original_nick = member.nick or member.display_name
    pattern = r"^(\{.*?\})\s+\S+\s+\|\s+(.+)$"
    match = re.match(pattern, original_nick)
    if match:
        regiment_part, username_part = match.groups()
        raw_nick = f"{regiment_part} {final_abbr} | {username_part}"
    else:
        # determine regiment abbreviation from roles
        regiment_abbr = "UNK"
        for rid, abbr in REGIMENT_ROLES.items():
            if any(role.id == rid for role in member.roles):
                regiment_abbr = abbr
                break
        raw_nick = f"{{{regiment_abbr}}} {final_abbr} | {roblox_username}"
    new_nick = raw_nick[:32]

    # Apply edits
    if ctx.guild.me.top_role <= member.top_role:
        return await ctx.send("Cannot edit member: role hierarchy")
    try:
        await member.edit(roles=cleaned_roles, nick=new_nick)
    except discord.Forbidden:
        return await ctx.send("Could not update member roles or nickname: missing permissions")

    # Confirmation
    await ctx.send(f"Awarded {points} merits to {roblox_username}, total {new_total}, rank {final_abbr}")

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

@bot.command()
@commands.has_any_role(*HOST_ROLES)
async def sync(ctx):
    for sheet in (main_sheet, special_sheet):
        # find the headers anywhere
        try:
            name_cell  = sheet.find("Name")
            merit_cell = sheet.find("Merits")
            rank_cell  = sheet.find("Rank")
        except CellNotFound:
            continue

        name_col, merit_col, rank_col = name_cell.col, merit_cell.col, rank_cell.col
        data_start = name_cell.row + 1
        rows = sheet.get_all_values()[data_start:]

        for i, row_vals in enumerate(rows, start=data_start):
            username = row_vals[name_col-1].strip()
            if not username:
                continue

            # match member by roblox username (case-insensitive)
            member = next(
                (m for m in ctx.guild.members
                 if extract_roblox_name(m.display_name).lower() == username.lower()),
                None
            )
            if not member:
                # no user found, skip
                continue

            # current merits in sheet
            try:
                current = int(row_vals[merit_col-1])
            except (ValueError, TypeError):
                current = 0

            # if user already has a rank role above their merits, bump merits
            user_roles = {r.id for r in member.roles}
            existing_threshold = next(
                (thr for thr, _, _, rid in RANKS if rid in user_roles),
                0
            )
            if current < existing_threshold:
                current = existing_threshold
                sheet.update_cell(i, merit_col, current)

            # determine correct rank by merits
            threshold, rank_name, rank_abbr, role_id = next(
                (item for item in reversed(RANKS) if current >= item[0]),
                RANKS[0]
            )
            # write rank name into sheet
            sheet.update_cell(i, rank_col, rank_name)

    await ctx.send("sync complete")



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

# IDs
SERVER_A_ID = 1122152849833459842
SERVER_B_ID = 1404486943097487440

ROLE_MAPPING = {
    1387191982866038919: 1405179401712177182,  # Server A role -> Server B role
    1320153442244886598: 1405179343457488998
}

@bot.event
async def on_member_join(member: discord.Member):
    # Only trigger if the join is in Server B
    if member.guild.id != SERVER_B_ID:
        return

    # Try to find the same user in Server A
    guild_a = bot.get_guild(SERVER_A_ID)
    if not guild_a:
        print("Bot is not in Server A or cannot access it.")
        return

    member_a = guild_a.get_member(member.id)
    if not member_a:
        print(f"User {member} not found in Server A.")
        return

    # Check roles in Server A and assign corresponding roles in Server B
    roles_to_add = []
    for role_a_id, role_b_id in ROLE_MAPPING.items():
        if discord.utils.get(member_a.roles, id=role_a_id):
            role_b = discord.utils.get(member.guild.roles, id=role_b_id)
            if role_b:
                roles_to_add.append(role_b)

    if roles_to_add:
        await member.add_roles(*roles_to_add, reason="Role sync from Server A")
        print(f"Assigned roles {roles_to_add} to {member.name}")


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
