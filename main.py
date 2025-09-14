from __future__ import annotations
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
import os
from threading import Thread
from flask import Flask
import threading, time, requests
import asyncio
import time
import sys
import io
import textwrap
import traceback
import contextlib


# ----------------- Flask for uptime -----------------
app = Flask("")

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=10000)

def keep_alive():
    url = "https://pool-cft0.onrender.com"  # your Render URL
    while True:
        try:
            requests.get(url)
            print("Pinged self to stay awake")
        except Exception as e:
            print("Ping failed:", e)
        time.sleep(300)  # every 5 minutes

# run in background thread
threading.Thread(target=keep_alive, daemon=True).start()

# cooldown tracker {user_id: last_trigger_time}
last_filter_trigger = {}
FILTER_COOLDOWN = 5  # seconds
Thread(target=run_flask).start()
# Abuse logging config
LOG_CHANNEL_ID = 1314931440496017481
MAX_POINTS_SINGLE_AWARD = 80
MAX_POINTS_HOURLY = 150

# A reasonably large replacement dict - kept as user provided
REPLACEMENTS: Dict[str, str] = {
    "shit": "shoot", "shits": "shoots", "shitty": "messy",
    "fuck": "fudge", "fucks": "fudges", "fucking": "freaking", "fucked": "fudged",
    "damn": "darn", "damned": "darned", "damnit": "darnit",
    "bitch": "witch", "bitches": "witches", "bitching": "complaining",
    "ass": "butt", "asses": "butts", "asshole": "meanie", "assholes": "meanies",
    "bastard": "rascal", "bastards": "rascals",
    "crap": "crud", "crappy": "cruddy",
    "hell": "heck", "hells": "hecks",
    "cunt": "meanie", "cunts": "meanies",
    "prick": "twig", "pricks": "twigs",
    "wanker": "clown", "wankers": "clowns",
    "motherfucker": "motherhugger", "motherfuckers": "motherhuggers",
    "bullshit": "nonsense", "bullshits": "nonsense", "bullshitting": "lying",
    "jackass": "donkey", "jackasses": "donkeys",
    "dumbass": "silly goose", "dumbasses": "silly geese",
    "piss": "pee", "pisses": "pees", "pissed": "upset", "pissing": "peeing",
    "bloody": "ruddy",
    "bugger": "rascal", "buggers": "rascals",
    "fuc": "fudge",
    "shi": "shoot",
    "bish": "witch",
    "assh": "meanie",
    "dic": "jerk",
    "dick": "jerk", "dicks": "jerks",
    "cock": "rooster", "cocks": "roosters",
    "pussy": "cat", "pussies": "cats",
    "penis": "banana", "penises": "bananas",
    "vagina": "peach", "vaginas": "peaches",
    "boobs": "balloons", "boob": "balloon",
    "tits": "birds", "tit": "bird",
    "boner": "oopsie", "boners": "oopsies",
    "cum": "milk", "cums": "milk", "cumming": "spilling",
    "jizz": "glue", "jizzes": "glue",
    "slut": "partygoer", "sluts": "partygoers",
    "whore": "worker", "whores": "workers",
    "jerkoff": "daydream", "jerking": "daydreaming",
    "masturbate": "meditate", "masturbating": "meditating",
    "porn": "cartoons", "porno": "cartoon", "pornography": "drawings",
    "stripper": "dancer", "strippers": "dancers",
    "hoe": "gardener", "hoes": "gardeners",
    "loser": "unlucky one", "losers": "unlucky ones",
    "idiot": "goof", "idiots": "goofs",
    "stupid": "silly", "stupids": "sillies",
    "moron": "dork", "morons": "dorks",
    "douche": "sponge", "douches": "sponges",
    "weirdo": "unique one", "weirdos": "unique ones",
    "fag": "friend", "fags": "friends", "faggot": "friend", "faggots": "friends",
    "nigga": "friend", "niggas": "friends",
    "nigger": "friend", "niggers": "friends",
    "retard": "silly", "retards": "sillies", "retarded": "silly",
    "kike": "person", "kikes": "people",
    "chink": "dude", "chinks": "dudes",
    "spic": "pal", "spics": "pals",
    "gypsy": "traveler", "gypsies": "travelers",
    "tranny": "person", "trannies": "people",
    "shemale": "person", "shemales": "people",
    "dyke": "friend", "dykes": "friends",
    "queer": "friend", "queers": "friends",
    "kraut": "person", "krauts": "people",
    "paki": "person", "pakis": "people",
    "redskin": "person", "redskins": "people",
    "cracker": "pal", "crackers": "pals"
}

# Keep recent awards in memory: {(giver_id, receiver_id): [(points, datetime), ...]}
recent_awards = defaultdict(list)

load_dotenv()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
filter_enabled: bool = True
WHITELIST: Set[str] = set()
replacements: Dict[str, str] = dict(REPLACEMENTS)  # runtime copy
foreign_words: Set[str] = set()

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


# --- Sheet helpers (single main_sheet only) ---
# Caches header columns for quicker access.
_HEADER_CACHE = {}

def _locate_headers(force=False):
    """Locate Name / Merits / Rank headers on the sheet and cache their cols/row.
    Returns (name_col, merit_col, rank_col, data_start_row)
    """
    if _HEADER_CACHE and not force:
        return _HEADER_CACHE['name_col'], _HEADER_CACHE['merit_col'], _HEADER_CACHE['rank_col'], _HEADER_CACHE['data_start_row']
    try:
        name_cell = main_sheet.find("Name")
        merit_cell = main_sheet.find("Merits")
        rank_cell = main_sheet.find("Rank")
    except Exception:
        raise RuntimeError("Sheet headers 'Name','Merits','Rank' not found")
    name_col, merit_col, rank_col = name_cell.col, merit_cell.col, rank_cell.col
    data_start_row = name_cell.row + 1
    _HEADER_CACHE.update({'name_col':name_col,'merit_col':merit_col,'rank_col':rank_col,'data_start_row':data_start_row})
    return name_col, merit_col, rank_col, data_start_row

def _get_all_records():
    """Return list of dicts: {'name':str,'merits':int,'row':int}
    Iterates rows after the header row; ignores empty name rows."""
    name_col, merit_col, rank_col, data_start = _locate_headers()
    rows = main_sheet.get_all_values()
    records = []
    for idx, r in enumerate(rows[data_start-1:], start=data_start):
        if not r or len(r) < 1:
            continue
        name = (r[name_col-1] if len(r) >= name_col else "").strip()
        if not name:
            continue
        # parse merits safely
        try:
            merits = int((r[merit_col-1] if len(r) >= merit_col else "0") or 0)
        except Exception:
            merits = 0
        records.append({'name': name, 'merits': merits, 'row': idx})
    return records

def _find_record(name):
    """Case-insensitive find. Returns record dict or None."""
    for rec in _get_all_records():
        if rec['name'].lower() == name.lower():
            return rec
    return None

def _set_merits_by_row(row, points):
    name_col, merit_col, rank_col, data_start = _locate_headers()
    main_sheet.update_cell(row, merit_col, points)

def _append_user(name, points, rank_name=None):
    # Try to append under first empty slot after data_start if possible
    name_col, merit_col, rank_col, data_start = _locate_headers()
    rows = main_sheet.get_all_values()
    # find empty row slot under name_col
    for i, r in enumerate(rows[data_start-1:], start=data_start):
        existing = (r[name_col-1] if len(r) >= name_col else "").strip()
        if not existing:
            main_sheet.insert_row([name, points, rank_name or ""], index=i)
            return i
    # otherwise append at end
    main_sheet.append_row([name, points, rank_name or ""])
    return len(rows) + 1

def _get_rank_for_points(points):
    for thr, full, abbr, roleid in reversed(RANKS):
        if points >= thr:
            return (thr, full, abbr, roleid)
    return RANKS[0]


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
    (385, "Staff Sergeant",  "SSG",  1214438711379370034),
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

async def log_award(ctx, giver, receiver, points, total, rank, status):
    log_channel = ctx.guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        embed = discord.Embed(
            title="merit award logged",
            description=status,
            color=discord.Color.gold(),
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="given by", value=f"{giver.mention} ({giver.id})", inline=False)
        embed.add_field(name="given to", value=f"{receiver.mention} ({receiver.id})", inline=False)
        embed.add_field(name="points awarded", value=str(points), inline=True)
        embed.add_field(name="new total", value=str(total), inline=True)
        embed.add_field(name="new rank", value=rank, inline=True)
        await log_channel.send(embed=embed)
    
@bot.command()
@commands.has_any_role(*HOST_ROLES)
async def awardpoints(ctx, *args):
    """
    Usage: !awardpoints <member...> <points>
    Members can be mentions, IDs, or usernames/display names (space-separated).
    The last argument must be the integer points to award.
    """
    if len(args) < 2:
        return await ctx.send("Usage: `!awardpoints <member...> <points>`")

    # parse points (last argument)
    try:
        points = int(args[-1])
    except ValueError:
        return await ctx.send("Last argument must be the points (integer).")

    if points <= 0:
        return await ctx.send("Points must be a positive number.")

    member_inputs = args[:-1]
    results = []

    # Pre-map mentions for quick lookup (mention text -> Member)
    mention_map = {}
    if ctx.message.mentions:
        for m in ctx.message.mentions:
            # canonical mention forms
            mention_map[f"<@{m.id}>"] = m
            mention_map[f"<@!{m.id}>"] = m
            mention_map[str(m.id)] = m

    for input_str in member_inputs:
        member = None
        raw = input_str.strip()

        # 1) Direct mention forms or direct ID
        if raw in mention_map:
            member = mention_map[raw]
        else:
            stripped = re.sub(r"[<@!>]", "", raw)
            if stripped.isdigit():
                member = ctx.guild.get_member(int(stripped))

        # 2) Try by exact username / display_name
        if not member:
            member = find(lambda m: m.name == raw or m.display_name == raw, ctx.guild.members)

        # 3) Try case-insensitive username/display_name partial fallback
        if not member:
            lowered = raw.lower()
            member = find(
                lambda m: m.name.lower() == lowered or m.display_name.lower() == lowered,
                ctx.guild.members,
            )

        if not member:
            results.append(f"Could not find member: `{input_str}`")
            continue

        try:
            msg = await _process_award(ctx, member, points)
            results.append(msg)
        except Exception as e:
            results.append(f"Error processing `{member.display_name}`: {e}")

    await ctx.send("\n".join(results))


async def _process_award(ctx: commands.Context, member: discord.Member, points: int) -> str:
    """
    Core logic to award points to a single member and update sheet/roles/nickname.
    Returns a short status string for that member.
    """
    roblox_username = extract_roblox_name(member.display_name)
    if roblox_username == "Unknown":
        return f"{member.display_name}: No nickname set."

    info = get_regiment_info(member)
    if not info:
        return f"{member.display_name}: Unsupported regiment."

    sheet = main_sheet if info.get("sheet_type") == "main" else main_sheet

    # Find headers on sheet
    try:
        name_cell = sheet.find("Name")
        merit_cell = sheet.find("Merits")
        rank_cell = sheet.find("Rank")
    except gspread_exceptions.CellNotFound:
        return f"{roblox_username}: Missing sheet headers (Name, Merits, Rank)."

    if not (name_cell and merit_cell and rank_cell):
        return f"{roblox_username}: Could not locate headers."

    name_col, merit_col, rank_col = name_cell.col, merit_cell.col, rank_cell.col
    data_start_row = name_cell.row + 1

    # Read existing names under header
    existing_names = sheet.col_values(name_col)[data_start_row - 1 :]

    # find current merits
    row = None
    try:
        idx = existing_names.index(roblox_username)
        row = data_start_row + idx
        current_merits = int(sheet.cell(row, merit_col).value or 0)
    except ValueError:
        # Not in DB: use their current Discord role baseline from RANKS
        member_role_ids = {r.id for r in member.roles}
        existing_threshold = next((t for t, _, _, rid in RANKS if rid in member_role_ids), 0)
        current_merits = existing_threshold
        row = None

    # Compute updated total and new rank
    new_total = current_merits + points
    new_rank = next((r for r in reversed(RANKS) if new_total >= r[0]), RANKS[0])
    new_rank_name = new_rank[1]
    new_rank_abbr = new_rank[2]
    new_rank_role_id = new_rank[3]

    # Insert or update sheet
    if row is None:
        # find first empty slot or append
        insert_row = None
        for i, name in enumerate(existing_names):
            if not name or not name.strip():
                insert_row = data_start_row + i
                break
        if insert_row is None:
            insert_row = data_start_row + len(existing_names)
        sheet.insert_row([roblox_username, new_total, new_rank_name], index=insert_row)
    else:
        sheet.update_cell(row, merit_col, new_total)
        sheet.update_cell(row, rank_col, new_rank_name)

    # Update roles: remove old rank roles, append new rank role
    old_role_ids = {rdef[3] for rdef in RANKS}
    cleaned_roles = [r for r in member.roles if r.id not in old_role_ids]

    new_role = ctx.guild.get_role(new_rank_role_id)
    if new_role and new_role not in cleaned_roles:
        cleaned_roles.append(new_role)

       # Nickname handling:
    # Cases handled:
    #  1. "{REGIMENT} RANK | Username"
    #  2. "[𝓡𝓛] {REGIMENT} RANK | Username"
    #  3. "[𝓡𝓛] RANK | Username"
    #  4. "RANK | Username"
    original_nick = member.nick or member.display_name or ""
    pattern = r"^(?:\[𝓡𝓛\]\s*)?(?:\{.*?\}\s+)?(\S+)\s+\|\s+(.+)$"
    match = re.match(pattern, original_nick)

    if match:
        # got the captured parts
        rank_part, username_part = match.groups()

        # keep regiment if present, else fallback
        regiment_match = re.match(r"^(?:\[𝓡𝓛\]\s*)?(\{.*?\})", original_nick)
        if regiment_match:
            regiment_part = regiment_match.group(1)
        else:
            regiment_part = "{UNK}"

        # if original had [𝓡𝓛], keep it
        rl_prefix = "[𝓡𝓛] " if original_nick.strip().startswith("[𝓡𝓛]") else ""

        raw_nick = f"{rl_prefix}{regiment_part} {new_rank_abbr} | {username_part}"
    else:
        # fallback: rebuild from scratch
        regiment_abbr = "UNK"
        for rid, abbr in REGIMENT_ROLES.items():
            if any(role.id == rid for role in member.roles):
                regiment_abbr = abbr
                break
        raw_nick = f"{{{regiment_abbr}}} {new_rank_abbr} | {roblox_username}"

    new_nick = raw_nick[:32]  # Discord max nick length

    # Role hierarchy check before editing
    if ctx.guild.me.top_role <= member.top_role:
        # We updated the sheet; but cannot change roles/nick due to hierarchy
        return f"{roblox_username}: Awarded {points} merits (total {new_total}, rank {new_rank_abbr}) — could not update roles/nickname due to role hierarchy."

    try:
        await member.edit(roles=cleaned_roles, nick=new_nick)
    except discord.Forbidden:
        return f"{roblox_username}: Awarded {points} merits (total {new_total}, rank {new_rank_abbr}) — missing permissions to update roles/nickname."
    except Exception as e:
        return f"{roblox_username}: Awarded {points} merits (total {new_total}, rank {new_rank_abbr}) — error updating member: {e}"

    return f"{roblox_username}: Awarded {points} merits (total {new_total}, rank {new_rank_abbr})"
@bot.command()
async def leaderboard(ctx):
    """Show top 10 from main_sheet."""
    try:
        records = _get_all_records()
    except Exception as e:
        return await ctx.send(f"❌ Failed to load data: {e}")
    sorted_records = sorted(records, key=lambda x: x['merits'], reverse=True)[:10]
    embed = discord.Embed(title="🏆 Leaderboard – Top 10", color=discord.Color.purple())
    for i, rec in enumerate(sorted_records, start=1):
        embed.add_field(name=f"{i}. {rec['name']}", value=f"{rec['merits']} pts", inline=False)
    await ctx.send(embed=embed)@bot.command()
async def mypoints(ctx):
    roblox_name = extract_roblox_name(ctx.author.display_name)
    try:
        rec = _find_record(roblox_name)
        if not rec:
            return await ctx.send("❌ You don't have any points yet.")
        total = rec['merits']
        embed = discord.Embed(title="📊 Your Points", color=discord.Color.blue())
        embed.add_field(name="Roblox Username", value=roblox_name)
        embed.add_field(name="Total Points", value=str(total))
        embed.set_footer(text="Note: Monthly breakdown not stored in this sheet.")
        return await ctx.send(embed=embed)
    except Exception as e:
        return await ctx.send(f"Error: {e}")@bot.command()
async def pointsneeded(ctx):
    roblox_name = extract_roblox_name(ctx.author.display_name)
    try:
        rec = _find_record(roblox_name)
        if not rec:
            return await ctx.send("❌ You don't have any points yet.")
        points = rec['merits']
        for threshold, name, abbr, _ in RANKS:
            if points < threshold:
                embed = discord.Embed(title="📈 Promotion Progress", description=f"You need `{threshold - points}` more points to reach **{name}**.", color=discord.Color.orange())
                return await ctx.send(embed=embed)
        return await ctx.send("🎉 You have reached the highest rank!")
    except Exception as e:
        return await ctx.send(f"Error: {e}")
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
        for sheet in [main_sheet]:
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

    for sheet in [main_sheet]:
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
    """Sync sheet merits with Discord roles; update 'Rank' column accordingly."""
    try:
        name_col, merit_col, rank_col, data_start = _locate_headers(force=True)
        rows = main_sheet.get_all_values()[data_start:]
        for i, row_vals in enumerate(rows, start=data_start):
            username = (row_vals[name_col-1] if len(row_vals) >= name_col else "").strip()
            if not username:
                continue
            member = next((m for m in ctx.guild.members if extract_roblox_name(m.display_name).lower() == username.lower()), None)
            if not member:
                continue
            try:
                current = int((row_vals[merit_col-1] if len(row_vals) >= merit_col else "0") or 0)
            except Exception:
                current = 0
            # ensure merits honor existing rank roles
            user_roles = {r.id for r in member.roles}
            existing_threshold = next((thr for thr, _, _, rid in RANKS if rid in user_roles), 0)
            if current < existing_threshold:
                current = existing_threshold
                main_sheet.update_cell(i, merit_col, current)
            threshold, rank_name, rank_abbr, role_id = _get_rank_for_points(current)
            main_sheet.update_cell(i, rank_col, rank_name)
        await ctx.send("sync complete")
    except Exception as e:
        await ctx.send(f"Sync failed: {e}")
@bot.command(name='cancel')
@is_authorized()
async def cancel_enlistment(ctx):
    # officer cancels any active session for the recruit they targeted earlier (if known)
    # allow officer to cancel any session they created by scanning active_sessions
    removed = []
    for rid, sess in list(active_sessions.items()):
        if sess.get('officer_id') == ctx.author.id:
            del active_sessions[rid]
            removed.append(rid)
            debug_log(f"Officer {ctx.author.id} cancelled session for recruit {rid}")
    if removed:
        await ctx.send(f"Cancelled enlistment session(s) for: {', '.join(str(x) for x in removed)}")
    else:
        await ctx.send("You don't have any active enlistment session.")

# Handle recruit free-text input (Roblox username)
@bot.event
async def on_message(message):
    # Early pass-through for non-enlist logic: preserve any other on_message handlers in file
    if message.author.bot:
        return

    # If the message author is a recruit with an active enlist session, process it
    if message.author.id in active_sessions:
        session = active_sessions[message.author.id]
        debug_log(f"Got message from active-session user: author={message.author.id} | step={session.get('step')} | content={message.content!r}")

        # ensure they're in the same channel the session expects
        if message.channel.id != session['channel'].id:
            debug_log(f"Message ignored: wrong channel (got {message.channel.id} expected {session['channel'].id})")
            # don't process commands if this was intended for enlist; return early
            return

        if session.get('step') == 'roblox_username':
            roblox_username = message.content.strip()
            debug_log(f"Processing roblox_username='{roblox_username}' for recruit {message.author.id}")

            if roblox_username.lower() == 'cancel':
                if message.author.id in active_sessions:
                    del active_sessions[message.author.id]
                    debug_log(f"Session cancelled by recruit {message.author.id}")
                await message.channel.send("❌ Enlistment cancelled.")
                return

            if not (3 <= len(roblox_username) <= 20):
                debug_log("Invalid roblox username length")
                return await message.channel.send("❌ Roblox username must be 3–20 characters.")

            # Construct the confirm view and show it in the channel
            view = ConfirmView(session.get('officer_id'), session['member'], session['regiment'], roblox_username)
            embed = discord.Embed(
                title="✅ Confirm Enlistment",
                description=f"**Member:** {session['member'].mention}\n**Regiment:** {session['regiment'].upper()}\n**Roblox Username:** {roblox_username}",
                color=0xffff00
            )
            await message.channel.send(embed=embed, view=view)
            debug_log("Sent confirm embed with buttons")
            return  # important: avoid falling through to bot.process_commands for this message

    # Let other commands and logic continue
    await bot.process_commands(message)

# Debug command to inspect active_sessions
@bot.command(name='enlistdebug')
@is_authorized()
async def enlistdebug(ctx):
    try:
        if not active_sessions:
            return await ctx.send("No active enlistment sessions.")
        lines = []
        for recruit_id, s in active_sessions.items():
            try:
                recruit = s.get('member')
                recruit_name = f"{recruit} ({recruit.id})" if recruit else str(recruit_id)
            except:
                recruit_name = str(recruit_id)
            lines.append(f"Recruit: `{recruit_name}` | Step: `{s.get('step')}` | Regiment: `{s.get('regiment')}` | Officer: `{s.get('officer_id')}` | Channel: `{getattr(s.get('channel'), 'id', 'unknown')}`")
        await ctx.send("```\n" + "\n".join(lines) + "\n```")
    except Exception as e:
        debug_log(f"enlistdebug error: {e}")
        await ctx.send(f"Error: {e}")

# ========== END ENLIST SYSTEM MERGE (REPLACED) ==========
ON_DUTY_CHANNEL_NAME = "on-duty"  # Must match exactly (case-insensitive ok)
CHEESECAKE_USER_ID = 728201873366056992, 940752980989341756  # Replace with your actual ID
managed_roles = {}

def is_cheesecake_user():
    async def predicate(ctx):
        return ctx.author.id == CHEESECAKE_USER_ID
    return commands.check(predicate)

def extract_number(value):
    """Extract numeric part from a string, default to 0 if not found."""
    if not value:
        return 0
    match = re.search(r'\d+', str(value))
    return int(match.group()) if match else 0

@bot.command()
@bot.command()
@commands.is_owner()
async def forceadd(ctx, *args):
    """Add points to one or more users. Usage flexible:
    - `!forceadd 10 target1 target2 @user 123456` (points first)
    - `!forceadd target1 target2 10` (points last)
    Targets may be Roblox usernames, Discord mentions, or numeric Discord IDs.
    """
    if not args:
        return await ctx.send("Usage: provide points and at least one target.")
    # determine points position: prefer first if int, otherwise last
    try:
        if len(args) >= 2 and str(args[0]).lstrip('-').isdigit():
            points = int(args[0])
            targets = args[1:]
        elif str(args[-1]).lstrip('-').isdigit():
            points = int(args[-1])
            targets = args[:-1]
        else:
            return await ctx.send("❌ Could not find points (must be an integer). Use `!forceadd 10 target1` or `!forceadd target1 10`.")
    except Exception as e:
        return await ctx.send(f"Error parsing points: {e}")

    if points <= 0:
        return await ctx.send("Points must be a positive integer.")

    results = []
    for t in targets:
        t = str(t).strip()
        member = None
        # mention form or id
        if t.startswith('<@') and t.endswith('>'):
            try:
                member_id = int(t.strip('<@!>'))
                member = ctx.guild.get_member(member_id)
            except:
                member = None
        elif t.isdigit():
            member = ctx.guild.get_member(int(t))
        else:
            # try find by exact name/display
            member = discord.utils.get(ctx.guild.members, name=t) or discord.utils.get(ctx.guild.members, display_name=t)

        if member:
            roblox_name = extract_roblox_name(member.display_name)
        else:
            roblox_name = t  # treat as raw roblox username

        try:
            rec = _find_record(roblox_name)
            if rec:
                total = rec['merits'] + points
                _set_merits_by_row(rec['row'], total)
                results.append(f"✅ {roblox_name}: now {total}")
            else:
                _append_user(roblox_name, points)
                results.append(f"➕ {roblox_name}: added with {points}")
        except Exception as e:
            results.append(f"❌ {roblox_name}: error {e}")

    await ctx.send("\\n".join(results))

@bot.command()
@bot.command()
@commands.is_owner()
async def resetmerit(ctx, *targets):
    """Reset one or more users' merits to 0.
    Usage: `!resetmerit user1 @user 123456`"""
    if not targets:
        return await ctx.send("Provide at least one username, mention, or ID.")
    results = []
    for t in targets:
        t = str(t).strip()
        member = None
        if t.startswith('<@') and t.endswith('>'):
            try:
                member_id = int(t.strip('<@!>'))
                member = ctx.guild.get_member(member_id)
            except:
                member = None
        elif t.isdigit():
            member = ctx.guild.get_member(int(t))
        else:
            member = discord.utils.get(ctx.guild.members, name=t) or discord.utils.get(ctx.guild.members, display_name=t)

        if member:
            roblox_name = extract_roblox_name(member.display_name)
        else:
            roblox_name = t

        try:
            rec = _find_record(roblox_name)
            if not rec:
                results.append(f"❌ {roblox_name}: not found")
            else:
                _set_merits_by_row(rec['row'], 0)
                results.append(f"✅ {roblox_name}: reset to 0")
        except Exception as e:
            results.append(f"❌ {roblox_name}: error {e}")
    await ctx.send("\\n".join(results))

@bot.command()
@bot.command()
@commands.is_owner()
async def purgeuser(ctx, *targets):
    """Remove one or more users from the sheet.
    Usage: `!purgeuser user1 @user 123456`"""
    if not targets:
        return await ctx.send("Provide at least one username, mention, or ID.")
    results = []
    for t in targets:
        t = str(t).strip()
        member = None
        if t.startswith('<@') and t.endswith('>'):
            try:
                member_id = int(t.strip('<@!>'))
                member = ctx.guild.get_member(member_id)
            except:
                member = None
        elif t.isdigit():
            member = ctx.guild.get_member(int(t))
        else:
            member = discord.utils.get(ctx.guild.members, name=t) or discord.utils.get(ctx.guild.members, display_name=t)

        if member:
            roblox_name = extract_roblox_name(member.display_name)
        else:
            roblox_name = t

        try:
            rec = _find_record(roblox_name)
            if not rec:
                results.append(f"❌ {roblox_name}: not found")
            else:
                main_sheet.delete_rows(rec['row'])
                results.append(f"🗑️ {roblox_name}: removed")
        except Exception as e:
            results.append(f"❌ {roblox_name}: error {e}")
    await ctx.send("\\n".join(results))

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

import discord
from discord.ext import commands
from discord.ext.commands import CommandOnCooldown, cooldown
import re

# role ids
promote_allowed = [1382604947924979793, 1134711656811855942]
extra_roles = [1279450222287655023, 1350321663996330037]
log_channel_id = 1314931440496017481

# rank structure (ordered lowest to highest)
ranks = [
    {"role": 1167334645671657502, "nick": "CDT"},
    {"role": 1167338203771047986, "nick": "2.LT"},
    {"role": 1167338264781394011, "nick": "1.LT"},
    {"role": 1207267583972212757, "nick": "CPT"},
    {"role": 1208384127418638336, "nick": "MJR"},
    {"role": 1210550474105819209, "nick": "LTCOL"},
]

def get_rank_index(member: discord.Member):
    for i, rank in enumerate(ranks):
        if discord.utils.get(member.roles, id=rank["role"]):
            return i
    return None

async def cleanup_roles(member: discord.Member, keep_role_id: int):
    for rank in ranks:
        if rank["role"] != keep_role_id:
            role = discord.utils.get(member.roles, id=rank["role"])
            if role:
                await member.remove_roles(role)

async def update_nickname(member: discord.Member, new_rank: str):
    """
    robust nickname updater:
    preserves optional [𝓡𝓛] prefix, optional {REGIMENT}, and username after '|'
    if regiment missing, inserts {UNK}
    returns True on success, False on failure (permission/error)
    """
    try:
        raw = (member.nick or member.display_name or "").strip()
    except Exception:
        raw = ""

    rl_prefix = ""
    regiment_part = None
    username_part = None

    if '|' in raw:
        left, right = raw.split('|', 1)
        left = left.strip()
        username_part = right.strip()

        # detect [𝓡𝓛] prefix (allow no space or a space)
        m_rl = re.match(r'^\[𝓡𝓛\]\s*(.*)$', left)
        if m_rl:
            rl_prefix = "[𝓡𝓛] "
            left = m_rl.group(1).strip()

        # detect {REGIMENT} if present
        m_reg = re.match(r'^(\{.*?\})\s*(.*)$', left)
        if m_reg:
            regiment_part = m_reg.group(1)
            # left_after_reg = m_reg.group(2).strip()  # old rank text, unused
    else:
        # no '|' present, attempt to salvage
        tmp = raw
        m_rl = re.match(r'^\[𝓡𝓛\]\s*(.*)$', tmp)
        if m_rl:
            rl_prefix = "[𝓡𝓛] "
            tmp = m_rl.group(1).strip()

        m_reg = re.match(r'^(\{.*?\})\s*(.*)$', tmp)
        if m_reg:
            regiment_part = m_reg.group(1)
            username_part = m_reg.group(2).strip() or None
        else:
            username_part = tmp or None

    if not username_part:
        username_part = member.display_name or member.name or "unknown"

    if not regiment_part:
        regiment_part = "{UNK}"

    new_rank_up = new_rank.upper()
    new_nick = f"{rl_prefix}{regiment_part} {new_rank_up} | {username_part}"
    new_nick = new_nick[:32]

    try:
        await member.edit(nick=new_nick)
        return True
    except discord.Forbidden:
        return False
    except Exception:
        return False

async def log_action(ctx, member: discord.Member, action: str, old_rank: str, new_rank: str):
    log_channel = ctx.guild.get_channel(log_channel_id)
    if log_channel:
        await log_channel.send(
            f"{member.mention} was officer {action} from {old_rank} → {new_rank} by {ctx.author.mention}"
        )

@bot.command(name="opromote")
@commands.has_any_role(*promote_allowed)
@cooldown(1, 60, commands.BucketType.user)
async def officer_promote(ctx, member: discord.Member):
    rank_index = get_rank_index(member)
    if rank_index is None:
        return await ctx.send(f"{member.mention} has no valid rank role")
    if rank_index == len(ranks) - 1:
        return await ctx.send(f"{member.mention} is already highest rank")

    old_rank = ranks[rank_index]
    new_rank = ranks[rank_index + 1]

    # role hierarchy check before attempting role edits
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"cannot change roles/nickname for {member.mention} due to role hierarchy")
        await log_action(ctx, member, "promoted (attempted - hierarchy)", old_rank["nick"], new_rank["nick"])
        return

    # remove other rank roles, give new rank
    await cleanup_roles(member, new_rank["role"])
    await member.add_roles(discord.Object(id=new_rank["role"]))

    # ensure extra roles present
    for role_id in extra_roles:
        if not discord.utils.get(member.roles, id=role_id):
            await member.add_roles(discord.Object(id=role_id))

    # update nickname using robust updater
    success = await update_nickname(member, new_rank["nick"])
    if not success:
        await ctx.send(f"could not change nickname for {member.mention}")

    await ctx.send(f"{member.mention} promoted to {new_rank['nick']}")
    await log_action(ctx, member, "promoted", old_rank["nick"], new_rank["nick"])


@bot.command(name="odemote")
@commands.has_any_role(*promote_allowed)
@cooldown(1, 60, commands.BucketType.user)
async def officer_demote(ctx, member: discord.Member):
    rank_index = get_rank_index(member)
    if rank_index is None:
        return await ctx.send(f"{member.mention} has no valid rank role")
    if rank_index == 0:
        return await ctx.send(f"{member.mention} is already lowest rank")

    old_rank = ranks[rank_index]
    new_rank = ranks[rank_index - 1]

    # role hierarchy check before attempting role edits
    if ctx.guild.me.top_role <= member.top_role:
        await ctx.send(f"cannot change roles/nickname for {member.mention} due to role hierarchy")
        await log_action(ctx, member, "demoted (attempted - hierarchy)", old_rank["nick"], new_rank["nick"])
        return

    # remove other rank roles, give new rank
    await cleanup_roles(member, new_rank["role"])
    await member.add_roles(discord.Object(id=new_rank["role"]))

    # ensure extra roles present
    for role_id in extra_roles:
        if not discord.utils.get(member.roles, id=role_id):
            await member.add_roles(discord.Object(id=role_id))

    # update nickname using robust updater
    success = await update_nickname(member, new_rank["nick"])
    if not success:
        await ctx.send(f"could not change nickname for {member.mention}")

    await ctx.send(f"{member.mention} demoted to {new_rank['nick']}")
    await log_action(ctx, member, "demoted", old_rank["nick"], new_rank["nick"])


@officer_promote.error
async def opromote_error(ctx, error):
    if isinstance(error, CommandOnCooldown):
        await ctx.send(f"wait {round(error.retry_after)}s before promoting again")
    elif isinstance(error, commands.MissingAnyRole):
        await ctx.send("you dont have permission to use this command")
    else:
        raise error

@officer_demote.error
async def odemote_error(ctx, error):
    if isinstance(error, CommandOnCooldown):
        await ctx.send(f"wait {round(error.retry_after)}s before demoting again")
    elif isinstance(error, commands.MissingAnyRole):
        await ctx.send("you dont have permission to use this command")
    else:
        raise error

@bot.command()
async def debug(ctx):
    latency = round(bot.latency * 1000)  # in milliseconds
    guilds = len(bot.guilds)
    members = sum(guild.member_count for guild in bot.guilds)
    await ctx.send(
        f"Bot is online ✅\n"
        f"Latency: {latency}ms\n"
        f"Connected servers: {guilds}\n"
        f"Total members: {members}"
    )


SERVER_A = 1409059947530031157
SERVER_B = 1122152849833459842
ROLE_ID = 1339571735028174919

@bot.event
async def on_member_join(member):
    # Check if they joined Server A
    if member.guild.id == SERVER_A:
        # Get Server B
        guild_b = bot.get_guild(SERVER_B)
        if guild_b is None:
            return
        
        # Check if user is also in Server B
        user_in_b = guild_b.get_member(member.id)
        if user_in_b:
            role = guild_b.get_role(ROLE_ID)
            if role:
                await user_in_b.add_roles(role)
                print(f"Gave {user_in_b} the Recruit role in Server B")

@bot.command()
async def delmsg(ctx, *ids: int):
    """Delete one or more messages by their IDs"""
    for msg_id in ids:
        try:
            msg = await ctx.channel.fetch_message(msg_id)
            await msg.delete()
            await ctx.send(f" Deleted message `{msg_id}`", delete_after=3)
        except:
            await ctx.send(f" Could not delete `{msg_id}`", delete_after=3)

OWNER_ID = 728201873366056992  # replace with your Discord user ID

@bot.command(name="eval")
async def _eval(ctx, *, code: str):
    # Restrict to owner only
    if ctx.author.id != OWNER_ID:
        return await ctx.send(" You can’t use this.")

    # Strip ```python ... ``` code blocks
    if code.startswith("```") and code.endswith("```"):
        code = "\n".join(code.split("\n")[1:-1])

    # Variables available inside eval
    env = {
        "bot": bot,
        "discord": discord,
        "ctx": ctx,
        "message": ctx.message,
        "author": ctx.author,
        "guild": ctx.guild,
        "channel": ctx.channel,
    }

    stdout = io.StringIO()
    try:
        with contextlib.redirect_stdout(stdout):
            exec(
                f"async def func():\n{textwrap.indent(code, '    ')}",
                env,
            )
            result = await env["func"]()
    except Exception:
        value = stdout.getvalue()
        error = traceback.format_exc()
        return await ctx.send(f" Error:\n```py\n{value}{error}\n```")

    value = stdout.getvalue()
    await ctx.send(f" Output:\n```py\n{value}{result}\n```")

    await bot.process_commands(message)


async def suspend_from_channel(member: discord.Member, channel: discord.TextChannel):
    user_id = member.id

    # track repeat offenses
    user_offenses[user_id] = user_offenses.get(user_id, 0) + 1
    offense_count = user_offenses[user_id]

    # escalate suspension time
    suspend_time = BASE_SUSPEND_TIME * offense_count

    # deny send messages
    overwrite = channel.overwrites_for(member)
    overwrite.send_messages = False
    await channel.set_permissions(member, overwrite=overwrite)

    await channel.send(
        f"{member.mention} has been suspended from posting in this channel for {suspend_time} seconds.",
        delete_after=30
    )

    # log suspension
    log_channel = channel.guild.get_channel(LOG_CHANNEL_ID)
    if log_channel:
        await log_channel.send(
            f"{member} ({member.id}) suspended from {channel.mention} "
            f"for {suspend_time} seconds (offense #{offense_count})."
        )

    # wait out suspension
    await asyncio.sleep(suspend_time)
    await channel.set_permissions(member, overwrite=None)

    # reset warnings
    user_warnings[user_id] = 0
    await channel.send(
        f"{member.mention} can now post again in this channel.",
        delete_after=30
    )

    # log reinstatement
    if log_channel:
        await log_channel.send(
            f"{member} ({member.id}) is now allowed to post again in {channel.mention}."
        )


# -------- Admin Whitelist Commands -------- #

@bot.command()
@commands.has_permissions(administrator=True)
async def addwhitelist(ctx, domain: str):
    domain = domain.lower()
    if domain not in WHITELISTED_SOURCES:
        WHITELISTED_SOURCES.append(domain)
        await ctx.send(f"Added {domain} to whitelist.")
    else:
        await ctx.send(f"{domain} is already whitelisted.")


@bot.command()
@commands.has_permissions(administrator=True)
async def removewhitelist(ctx, domain: str):
    domain = domain.lower()
    if domain in WHITELISTED_SOURCES:
        WHITELISTED_SOURCES.remove(domain)
        await ctx.send(f"Removed {domain} from whitelist.")
    else:
        await ctx.send(f"{domain} is not in the whitelist.")

# Run bot
                                        
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    print("ERROR: TOKEN environment variable not set. Exiting.")
    sys.exit(1)

async def start_bot():
    try:
        print("Attempting to login...")
        await bot.login(TOKEN)
        print("Login successful (this line normally won't be reached by itself). Starting bot...")
        await bot.connect(reconnect=True)
    except discord.HTTPException as e:
        # HTTPException wrapping REST problems (429/401/etc)
        print("Discord HTTPException during login:", repr(e))
        try:
            # Try to print response text if available
            if hasattr(e, 'response') and e.response is not None:
                print("Response status:", getattr(e.response, 'status', None))
        except Exception:
            pass
        sys.exit(1)
    except Exception as e:
        print("Unexpected exception during startup:", type(e), e)
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(start_bot())
    except KeyboardInterrupt:
        print("Shutting down.")




# ---- Patched awardpoints + enlist helpers (added by assistant) ----
import re as __re
from typing import Optional as __Optional
try:
    import discord as __discord
    from discord.ext import commands as __commands
except Exception:
    __discord = None
    __commands = None

async def resolve_member(ctx: __commands.Context, query: str) -> __Optional[__discord.Member]:
    """Robust member resolver: mention, ID, exact name/display_name, roblox-last-token, partial."""
    if not query or ctx is None or ctx.guild is None:
        return None
    guild = ctx.guild
    raw = str(query).strip()
    mention_match = __re.fullmatch(r'<@!?(\d+)>', raw)
    if mention_match:
        return guild.get_member(int(mention_match.group(1)))
    if raw.isdigit():
        return guild.get_member(int(raw))
    member = __discord.utils.get(guild.members, name=raw) or __discord.utils.get(guild.members, display_name=raw)
    if member:
        return member
    lowered = raw.lower()
    for m in guild.members:
        if (m.name and m.name.lower() == lowered) or (m.display_name and m.display_name.lower() == lowered):
            return m
    for m in guild.members:
        try:
            nick = m.display_name or m.name or ""
            if not nick:
                continue
            rbx = nick.split()[-1]
            if rbx.lower() == lowered:
                return m
        except Exception:
            continue
    for m in guild.members:
        if lowered in (m.name or "").lower() or lowered in (m.display_name or "").lower():
            return m
    return None

# Replace HOST_ROLES or import your HOST_ROLES from your main file. If you have a variable named HOST_ROLES in main, the decorator below will error if it's not available.
HOST_ROLES = set()

def _register_awardpoints(bot):
    @_commands.has_any_role(*HOST_ROLES)
    @bot.command(name="awardpoints")
    async def awardpoints(ctx: __commands.Context, *args: str):
        """Usage: !awardpoints <member...> <points>  (last arg is integer points)"""
        if len(args) < 2:
            return await ctx.send("Usage: `!awardpoints <member...> <points>`")
        try:
            points = int(args[-1])
        except ValueError:
            return await ctx.send("Last argument must be the points (integer).")
        if points <= 0:
            return await ctx.send("Points must be a positive number.")
        targets = args[:-1]
        results = []
        for inp in targets:
            member = await resolve_member(ctx, inp)
            if not member:
                results.append(f"Could not find member: `{inp}`")
                continue
            try:
                if hasattr(ctx.bot, "_process_award") and callable(ctx.bot._process_award):
                    msg = await ctx.bot._process_award(ctx, member, points)
                else:
                    msg = f"{member.display_name}: Awarded {points} merits (simulation)."
                results.append(msg)
            except Exception as e:
                results.append(f"Error processing `{getattr(member, 'display_name', str(member))}`: {e}")
        reply = "\n".join(results) or "No targets processed."
        if len(reply) <= 2000:
            await ctx.send(reply)
        else:
            chunks = []
            current = []
            curr_len = 0
            for line in results:
                if curr_len + len(line) + 1 > 1900:
                    chunks.append("\n".join(current))
                    current = [line]
                    curr_len = len(line) + 1
                else:
                    current.append(line)
                    curr_len += len(line) + 1
            if current:
                chunks.append("\n".join(current))
            for c in chunks:
                await ctx.send(c)
    return awardpoints

def _register_enlist(bot, active_sessions_ref):
    @_commands.has_any_role(*HOST_ROLES)
    @bot.command(name='enlist')
    async def enlist(ctx: __commands.Context, *, member_input: __Optional[str] = None):
        if ctx.author.id in active_sessions_ref:
            return await ctx.send("❌ You already have an active enlistment session.")
        if not member_input:
            embed = __discord.Embed(title="🎖️ Enlistment", description="Mention or type the member you want to enlist.", color=0x0099FF)
            embed.add_field(name="Examples", value="`!enlist @user`\n`!enlist Username`\n`!enlist 123456789012345678`")
            await ctx.send(embed=embed)
            return
        member = await resolve_member(ctx, member_input)
        if not member:
            return await ctx.send("❌ Member not found.")
        if member.bot or member.id == ctx.author.id:
            return await ctx.send("❌ You cannot enlist this user.")
        active_sessions_ref[member.id] = {
            'officer_id': ctx.author.id,
            'member': member,
            'channel': ctx.channel,
            'step': 'select_regiment'
        }
        await ctx.send(f"✅ Started enlistment for {member.mention}. Ask them to type their Roblox username in this channel.")
    return enlist

# ---- end patch ----
