import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timedelta
import asyncio
import random
from typing import Dict, List, Optional

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Configuration
HOST_ROLES = [
    1255061914732597268,
    1134711656811855942,
    1279450222287655023
]

RANKS = [
    {"id": 1214438714508312596, "name": "Master Sergeant", "points": 80, "order": 8},
    {"id": 1214438711379370034, "name": "Staff Sergeant", "points": 65, "order": 7},
    {"id": 1207980354317844521, "name": "Sergeant Major", "points": 50, "order": 6},
    {"id": 1207980351826173962, "name": "Sergeant", "points": 35, "order": 5, "requires_exam": True},
    {"id": 1225058657507606600, "name": "Junior Sergeant", "points": 25, "order": 4},
    {"id": 1208374047994281985, "name": "Corporal", "points": 15, "order": 3},
    {"id": 1214438109173907546, "name": "Soldat", "points": 8, "order": 2},
    {"id": 1207981849528246282, "name": "Recruit", "points": 0, "order": 1}
]

class MilitaryPointsSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = 'military_data.json'
        self.data = self.load_data()

    def load_data(self):
        """Load data from JSON file"""
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "users": {},
                "monthly_points": {},
                "exams_passed": []
            }

    def save_data(self):
        """Save data to JSON file"""
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def is_host(self, member):
        """Check if user has host permissions"""
        return any(role.id in HOST_ROLES for role in member.roles)

    def get_user_data(self, user_id):
        """Get user's point data"""
        user_id = str(user_id)
        if user_id not in self.data["users"]:
            self.data["users"][user_id] = {
                "total_points": 0,
                "monthly_points": {},
                "point_history": []
            }
        return self.data["users"][user_id]

    def get_current_month(self):
        """Get current month string"""
        return datetime.now().strftime("%Y-%m")

    def add_points(self, user_id, points, reason, awarded_by):
        """Add points to user"""
        user_data = self.get_user_data(user_id)
        current_month = self.get_current_month()

        user_data["total_points"] += points

        if current_month not in user_data["monthly_points"]:
            user_data["monthly_points"][current_month] = 0
        user_data["monthly_points"][current_month] += points

        user_data["point_history"].append({
            "points": points,
            "reason": reason,
            "awarded_by": awarded_by,
            "timestamp": datetime.now().isoformat()
        })

        self.save_data()
        return user_data["total_points"]

    def get_user_rank(self, member):
        """Get user's current rank"""
        for rank in RANKS:
            if member.get_role(rank["id"]):
                return rank
        return RANKS[-1]  # Return Recruit if no rank found

    def get_next_rank(self, current_rank, total_points):
        """Get next available rank and points needed"""
        current_order = current_rank["order"]

        for rank in sorted(RANKS, key=lambda x: x["order"]):
            if rank["order"] > current_order and total_points >= rank["points"]:
                # Check if it's Sergeant and requires exam
                if rank.get("requires_exam", False):
                    return rank, 0, True  # rank, points_needed, requires_exam
                return rank, 0, False
            elif rank["order"] > current_order:
                points_needed = rank["points"] - total_points
                return rank, points_needed, rank.get("requires_exam", False)

        return None, 0, False

    def ai_determine_points(self, description):
        """AI-like function to determine points based on description"""
        description = description.lower()

        # Keywords and their point values
        excellent_keywords = ["excellent", "outstanding", "exceptional", "amazing", "perfect", "flawless"]
        good_keywords = ["good", "great", "well", "solid", "nice", "impressive", "active"]
        average_keywords = ["okay", "decent", "fine", "adequate", "participated", "showed up"]
        poor_keywords = ["late", "distracted", "minimal", "barely", "struggled", "poor"]

        # Count positive and negative indicators
        score = 3  # Base score

        # Add points for excellent performance
        if any(keyword in description for keyword in excellent_keywords):
            score += 2
        # Add points for good performance
        elif any(keyword in description for keyword in good_keywords):
            score += 1
        # Subtract points for poor performance
        elif any(keyword in description for keyword in poor_keywords):
            score -= 1

        # Check for specific military terms
        if any(term in description for term in ["leadership", "initiative", "discipline", "teamwork"]):
            score += 1

        # Ensure score is within 1-5 range
        return max(1, min(5, score))

    @commands.slash_command(name="award_points", description="Award points to a user for military event participation")
    async def award_points(self, ctx, user: discord.Member, points: int = None, *, description: str):
        """Award points to a user"""
        if not self.is_host(ctx.author):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to award points.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return

        # Use AI to determine points if not specified
        if points is None:
            points = self.ai_determine_points(description)
        else:
            # Ensure points are within valid range
            points = max(1, min(5, points))

        # Award points
        total_points = self.add_points(user.id, points, description, ctx.author.id)

        embed = discord.Embed(
            title="🏅 Points Awarded",
            description=f"**{user.mention}** has been awarded **{points} points**!",
            color=discord.Color.green()
        )
        embed.add_field(name="Reason", value=description, inline=False)
        embed.add_field(name="Total Points", value=f"{total_points} points", inline=True)
        embed.add_field(name="This Month", value=f"{self.get_user_data(user.id)['monthly_points'].get(self.get_current_month(), 0)} points", inline=True)
        embed.set_thumbnail(url=user.display_avatar.url)

        await ctx.respond(embed=embed)

    @commands.slash_command(name="my_points", description="Check your military points")
    async def my_points(self, ctx):
        """Check user's own points"""
        user_data = self.get_user_data(ctx.author.id)
        current_month = self.get_current_month()
        monthly_points = user_data['monthly_points'].get(current_month, 0)

        current_rank = self.get_user_rank(ctx.author)
        next_rank, points_needed, requires_exam = self.get_next_rank(current_rank, user_data['total_points'])

        embed = discord.Embed(
            title="🎖️ Your Military Points",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.add_field(name="Current Rank", value=current_rank['name'], inline=True)
        embed.add_field(name="Total Points", value=f"{user_data['total_points']} points", inline=True)
        embed.add_field(name="This Month", value=f"{monthly_points} points", inline=True)

        if next_rank:
            if requires_exam:
                embed.add_field(name="Next Rank", value=f"{next_rank['name']} (Requires Exam)", inline=False)
            elif points_needed > 0:
                embed.add_field(name="Next Rank", value=f"{next_rank['name']} ({points_needed} points needed)", inline=False)
            else:
                embed.add_field(name="Ready for Promotion!", value=f"You can be promoted to {next_rank['name']}", inline=False)
        else:
            embed.add_field(name="Rank Status", value="Maximum rank achieved!", inline=False)

        await ctx.respond(embed=embed)

    @commands.slash_command(name="check_points", description="Check another user's military points")
    async def check_points(self, ctx, user: discord.Member):
        """Check another user's points"""
        user_data = self.get_user_data(user.id)
        current_month = self.get_current_month()
        monthly_points = user_data['monthly_points'].get(current_month, 0)

        current_rank = self.get_user_rank(user)
        next_rank, points_needed, requires_exam = self.get_next_rank(current_rank, user_data['total_points'])

        embed = discord.Embed(
            title=f"🎖️ {user.display_name}'s Military Points",
            color=discord.Color.blue()
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.add_field(name="Current Rank", value=current_rank['name'], inline=True)
        embed.add_field(name="Total Points", value=f"{user_data['total_points']} points", inline=True)
        embed.add_field(name="This Month", value=f"{monthly_points} points", inline=True)

        if next_rank:
            if requires_exam:
                embed.add_field(name="Next Rank", value=f"{next_rank['name']} (Requires Exam)", inline=False)
            elif points_needed > 0:
                embed.add_field(name="Next Rank", value=f"{next_rank['name']} ({points_needed} points needed)", inline=False)
            else:
                embed.add_field(name="Ready for Promotion!", value=f"Can be promoted to {next_rank['name']}", inline=False)
        else:
            embed.add_field(name="Rank Status", value="Maximum rank achieved!", inline=False)

        await ctx.respond(embed=embed)

    @commands.slash_command(name="leaderboard", description="View the military points leaderboard")
    async def leaderboard(self, ctx, period: str = "total"):
        """Show leaderboard for total or monthly points"""
        if period not in ["total", "monthly"]:
            await ctx.respond("Please specify 'total' or 'monthly' for the leaderboard period.", ephemeral=True)
            return

        current_month = self.get_current_month()
        leaderboard_data = []

        for user_id, user_data in self.data["users"].items():
            try:
                member = ctx.guild.get_member(int(user_id))
                if member:
                    if period == "total":
                        points = user_data['total_points']
                    else:
                        points = user_data['monthly_points'].get(current_month, 0)

                    current_rank = self.get_user_rank(member)
                    leaderboard_data.append({
                        'member': member,
                        'points': points,
                        'rank': current_rank['name']
                    })
            except:
                continue

        # Sort by points (descending)
        leaderboard_data.sort(key=lambda x: x['points'], reverse=True)

        embed = discord.Embed(
            title=f"🏆 Military Points Leaderboard - {period.title()}",
            color=discord.Color.gold()
        )

        if period == "monthly":
            embed.description = f"Points for {datetime.now().strftime('%B %Y')}"

        leaderboard_text = ""
        for i, data in enumerate(leaderboard_data[:10], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            leaderboard_text += f"{medal} **{data['member'].display_name}** - {data['points']} points ({data['rank']})\n"

        if leaderboard_text:
            embed.add_field(name="Top 10", value=leaderboard_text, inline=False)
        else:
            embed.add_field(name="No Data", value="No points recorded yet!", inline=False)

        await ctx.respond(embed=embed)

    @commands.slash_command(name="promote", description="Promote a user to their next rank")
    async def promote(self, ctx, user: discord.Member):
        """Promote a user to next rank"""
        if not self.is_host(ctx.author) and user != ctx.author:
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You can only promote yourself, or you need host permissions to promote others.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return

        user_data = self.get_user_data(user.id)
        current_rank = self.get_user_rank(user)
        next_rank, points_needed, requires_exam = self.get_next_rank(current_rank, user_data['total_points'])

        if not next_rank:
            embed = discord.Embed(
                title="❌ Promotion Not Available",
                description=f"{user.display_name} is already at the maximum rank!",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return

        if points_needed > 0:
            embed = discord.Embed(
                title="❌ Insufficient Points",
                description=f"{user.display_name} needs {points_needed} more points to reach {next_rank['name']}.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return

        if requires_exam and str(user.id) not in self.data["exams_passed"]:
            embed = discord.Embed(
                title="❌ Exam Required",
                description=f"Promotion to {next_rank['name']} requires passing the sergeant exam first!",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return

        # Remove current rank and add new rank
        try:
            await user.remove_roles(ctx.guild.get_role(current_rank['id']))
            await user.add_roles(ctx.guild.get_role(next_rank['id']))

            embed = discord.Embed(
                title="🎉 Promotion Successful!",
                description=f"**{user.display_name}** has been promoted to **{next_rank['name']}**!",
                color=discord.Color.green()
            )
            embed.add_field(name="Previous Rank", value=current_rank['name'], inline=True)
            embed.add_field(name="New Rank", value=next_rank['name'], inline=True)
            embed.add_field(name="Total Points", value=f"{user_data['total_points']} points", inline=True)
            embed.set_thumbnail(url=user.display_avatar.url)

            await ctx.respond(embed=embed)
        except discord.HTTPException as e:
            embed = discord.Embed(
                title="❌ Promotion Failed",
                description=f"Failed to update roles: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(name="pass_exam", description="Mark a user as having passed the sergeant exam")
    async def pass_exam(self, ctx, user: discord.Member):
        """Mark user as having passed sergeant exam"""
        if not self.is_host(ctx.author):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to mark exams as passed.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return

        user_id = str(user.id)
        if user_id not in self.data["exams_passed"]:
            self.data["exams_passed"].append(user_id)
            self.save_data()

            embed = discord.Embed(
                title="✅ Exam Passed",
                description=f"**{user.display_name}** has been marked as having passed the sergeant exam!",
                color=discord.Color.green()
            )
            embed.add_field(name="Status", value="Can now be promoted to Sergeant rank", inline=False)
            await ctx.respond(embed=embed)
        else:
            embed = discord.Embed(
                title="ℹ️ Already Passed",
                description=f"{user.display_name} has already passed the sergeant exam.",
                color=discord.Color.blue()
            )
            await ctx.respond(embed=embed, ephemeral=True)

    @commands.slash_command(name="point_history", description="View your recent point history")
    async def point_history(self, ctx, user: discord.Member = None):
        """View point history for self or another user"""
        target_user = user or ctx.author

        # Only allow checking others if you're a host
        if user and not self.is_host(ctx.author):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You can only view your own point history.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return

        user_data = self.get_user_data(target_user.id)
        history = user_data.get('point_history', [])

        if not history:
            embed = discord.Embed(
                title="📋 Point History",
                description=f"No point history found for {target_user.display_name}",
                color=discord.Color.blue()
            )
            await ctx.respond(embed=embed)
            return

        # Show last 10 entries
        recent_history = history[-10:]

        embed = discord.Embed(
            title=f"📋 Point History - {target_user.display_name}",
            color=discord.Color.blue()
        )

        history_text = ""
        for entry in reversed(recent_history):
            try:
                awarded_by = ctx.guild.get_member(entry['awarded_by'])
                awarded_by_name = awarded_by.display_name if awarded_by else "Unknown"
                date = datetime.fromisoformat(entry['timestamp']).strftime('%m/%d/%Y')
                history_text += f"**+{entry['points']}** - {entry['reason']}\n*{date} by {awarded_by_name}*\n\n"
            except:
                continue

        if history_text:
            embed.description = history_text[:4000]  # Discord embed limit
        else:
            embed.description = "No valid history entries found."

        await ctx.respond(embed=embed)


# Bot Owner ID
BOT_OWNER_ID = 728201873366056992

class BotOwnerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = 'military_data.json'

    def is_bot_owner(self, user_id):
        """Check if user is the bot owner"""
        return user_id == BOT_OWNER_ID

    def load_data(self):
        """Load data from JSON file"""
        try:
            with open(self.data_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "users": {},
                "monthly_points": {},
                "exams_passed": []
            }

    def save_data(self, data):
        """Save data to JSON file"""
        with open(self.data_file, 'w') as f:
            json.dump(data, f, indent=2)

    async def owner_only_check(self, ctx):
        """Check if user is bot owner"""
        if not self.is_bot_owner(ctx.author.id):
            embed = discord.Embed(
                title="🚫 Bot Owner Only",
                description="This command is restricted to the bot owner only.",
                color=discord.Color.red()
            )
            await ctx.respond(embed=embed, ephemeral=True)
            return False
        return True

    @commands.slash_command(name="add_points_owner", descr