import discord
from discord.ext import commands
import datetime
import json
import uuid
import asyncio
import random
import time
from collections import defaultdict

class Economy(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_file = "economy_data.json"
        self.load_data()

        self.users = defaultdict(lambda: {
            "balance": 0,
            "inventory": [],
            "job": None,
            "job_activity": 0,
            "last_activity": None,
            "last_job_task": None,
            "businesses": [],
            "bank_balance": 0,
            "crypto_balances": defaultdict(int),
            "hunger": 100,
            "thirst": 100,
            "health": 100,
            "last_survival_update": datetime.datetime.now().isoformat(),
            "business_license": False,
            "career": None,
            "career_xp": 0,
            "reputation": 0,
            "job_progress": {"obj_idx": 0, "count": 0}
        })

        self.businesses = {}
        # Pending factory shipments: {shipment_id: {biz_id, units, eta_ts, fulfilled}}
        self.shipments = {}
        # Crime cooldowns: {user_id: last_attempt_ts}
        self.rob_cooldowns = {}
        self.heist_cooldowns = {}
        self.cryptocurrencies = {}
        self.bank = {
            "owner": None,
            "balance": 0,
            "interest_rate": 0.01,
            "applications": [],
            "category_id": None,
            "channel_id": None
        }
        self.feature_applications = {}
        self.license_applications = {}

        self.job_performance = defaultdict(lambda: defaultdict(int))

        # Track recent member joins for the welcome_member objective type:
        # {guild_id: {member_id: join_timestamp}}
        self.recent_joins = defaultdict(dict)
        # Invite-use snapshot for the invite_count objective type:
        # {guild_id: {invite_code: uses}}
        self.invite_cache = {}

        self.jobs = {
            "trendsetter": {
                "name": "Trendsetter",
                "description": "Recruit new members to the server using your personal invite link.",
                "cooldown": 3600 * 6,
                "pay": 150,
                "objectives": [
                    {"type": "invite_count", "target": 2,
                     "description": "Bring 2 new members into the server using your invite link"},
                ],
            },
            "merchandise_stocker": {
                "name": "Merchandise Stocker",
                "description": "Actually help members with shop/product questions in #shop-discussion.",
                "cooldown": 3600 * 8,
                "pay": 90,
                "objectives": [
                    {"type": "mod_approved",
                     "description": "Help a member with a real shop/product question in #shop-discussion. "
                                    "Once you've genuinely helped someone, ask a mod/admin to run "
                                    "`!approveobjective @you` to confirm it."},
                ],
            },
            "stylist": {
                "name": "Stylist",
                "description": "Train on outfit knowledge, then actually style a real member.",
                "cooldown": 3600 * 4,
                "pay": 130,
                "objectives": [
                    {"type": "button_choice",
                     "description": "Training: pick the right outfit for the scenario",
                     "question": "A customer wants an outfit for a punk rock concert. What do you recommend?",
                     "options": [
                         {"label": "Leather Jacket, Band Tee, Ripped Jeans", "correct": True},
                         {"label": "Flowy Dress, Sandals, Sun Hat", "correct": False},
                         {"label": "Business Suit, Tie, Dress Shoes", "correct": False}
                     ]},
                    {"type": "mod_approved",
                     "description": "Now do it for real — help an actual member put together a fit "
                                    "(fashion-talk or DMs), then get a mod/admin to `!approveobjective @you`."},
                ],
            },
            "cashier": {
                "name": "Cashier",
                "description": "Greet new members so they feel welcomed and stick around.",
                "cooldown": 3600 * 3,
                "pay": 80,
                "objectives": [
                    {"type": "welcome_member", "channel": "welcome", "target": 3, "window_minutes": 15,
                     "description": "Welcome 3 new members in #welcome within 15 minutes of them joining "
                                    "(mention them by name in your message)"},
                ],
            },
            "hype_caller": {
                "name": "Hype Caller",
                "description": "Spot real server activity — a VC filling up, an event starting, a drop going "
                                "live — and call it out so people actually see it.",
                "cooldown": 3600 * 2,
                "pay": 90,
                "objectives": [
                    {"type": "vc_alert",
                     "description": "Spot an active voice channel (2+ people) and call it with `!announcevc`"},
                ],
            },
            "stock_clerk": {
                "name": "Stock Clerk",
                "description": "Work for a hired business — move factory shipments onto the shelf so they're "
                                "actually sellable.",
                "cooldown": 3600 * 2,
                "pay": 60,
                "objectives": [
                    {"type": "stock_shelves", "target": 10,
                     "description": "Stock 10 units of received shipment at a business you're hired at "
                                    "using `!stockshelves <biz_id> <amount>`"},
                ],
            },
        }

        # ---------------------------------------------------------------
        # CAREER PATHS — long-term progression trees
        # Each path has ordered levels. xp_required is cumulative career_xp.
        # role_name auto-creates/assigns like the rank system.
        # channel/active_hours define where passive XP is earned via chatting.
        # ---------------------------------------------------------------
        self.career_paths = {
            "fashion_influencer": {
                "display_name": "Fashion Influencer",
                "channel": "fashion-talk",
                "active_hours": (18, 23),
                "levels": [
                    {"title": "Trendsetter", "xp_required": 0, "perks": []},
                    {"title": "Stylist", "xp_required": 500, "perks": ["poll"]},
                    {"title": "Fashion Coordinator", "xp_required": 1500, "perks": ["poll", "runway"]},
                ],
            },
            "retail_associate": {
                "display_name": "Retail Associate",
                "channel": "shop-discussion",
                "active_hours": (10, 17),
                "levels": [
                    {"title": "Merch Stocker", "xp_required": 0, "perks": []},
                    {"title": "Cashier", "xp_required": 500, "perks": []},
                    {"title": "Store Manager", "xp_required": 1500, "perks": ["flash_sale", "manage_shop"]},
                ],
            },
            "event_promoter": {
                "display_name": "Event Promoter",
                "channel": "events",
                "active_hours": (0, 24),
                "levels": [
                    {"title": "Hype Runner", "xp_required": 0, "perks": []},
                    {"title": "Promoter", "xp_required": 500, "perks": []},
                    {"title": "Event Director", "xp_required": 1500, "perks": ["giveaway", "watch_party"]},
                ],
            },
            "brand_owner": {
                "display_name": "Brand Owner",
                "channel": None,  # progression here comes from running a business, not chatting
                "active_hours": (0, 24),
                "levels": [
                    {"title": "Founder", "xp_required": 0, "perks": ["start_business"]},
                    {"title": "Established Brand", "xp_required": 1000, "perks": ["start_business", "hire"]},
                    {"title": "Industry Leader", "xp_required": 3000,
                     "perks": ["start_business", "hire", "custom_role", "custom_emoji"]},
                ],
            },
        }

        # XP gain settings for career chatting
        self.career_xp_min, self.career_xp_max = 5, 12
        self.career_msg_cooldowns = {}  # user_id -> last timestamp

        # Reputation: simple counter, gated by cooldown per giver->receiver per day
        self.reputation = defaultdict(int)  # user_id -> rep score
        self.rep_cooldowns = {}  # (giver_id, receiver_id) -> last timestamp

        # Active limited-time drops: item_id -> {"price":, "expires": ts, "name":}
        self.active_drops = {}

        self.shop_items = {
            "band_tee": {"name": "Vintage Band Tee", "price": 50, "description": "A classic tee from your favorite alt band.", "emoji": "👕"},
            "choker": {"name": "Spiked Choker", "price": 75, "description": "Adds an edge to any outfit.", "emoji": "⛓️"},
            "piercing": {"name": "Facial Piercing", "price": 100, "description": "Express yourself with some new metal.", "emoji": "✨"},
            "platform_boots": {"name": "Platform Boots", "price": 150, "description": "Elevate your style, literally.", "emoji": "👢"},
            "dye_kit": {"name": "Hair Dye Kit", "price": 60, "description": "Change your look with a vibrant new color.", "emoji": "🌈"},
            "water_bottle": {"name": "Water Bottle", "price": 10, "description": "Quenches your thirst.", "emoji": "💧", "effect": {"thirst": 20}},
            "energy_bar": {"name": "Energy Bar", "price": 20, "description": "Fills you up.", "emoji": "🍫", "effect": {"hunger": 20}},
            "first_aid_kit": {"name": "First Aid Kit", "price": 50, "description": "Heals minor wounds.", "emoji": "🩹", "effect": {"health": 30}},
            "tent": {"name": "Tent", "price": 200, "description": "Provides basic shelter.", "emoji": "⛺", "effect": {"housing": 1}},
            "apartment": {"name": "Apartment", "price": 1000, "description": "A cozy place to call home.", "emoji": "🏢", "effect": {"housing": 5}},
            "mansion": {"name": "Mansion", "price": 5000, "description": "Luxury living at its finest.", "emoji": "🏰", "effect": {"housing": 10}}
        }

    def save_data(self):
        data = {
            "users": {str(k): v for k, v in self.users.items()},
            "businesses": self.businesses,
            "cryptocurrencies": self.cryptocurrencies,
            "bank": self.bank,
            "feature_applications": self.feature_applications,
            "license_applications": self.license_applications
        }
        for user_data in data["users"].values():
            if isinstance(user_data.get("crypto_balances"), defaultdict):
                user_data["crypto_balances"] = dict(user_data["crypto_balances"])
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=4, default=str)

    def load_data(self):
        try:
            with open(self.data_file, "r") as f:
                data = json.load(f)
            self.users = defaultdict(lambda: self.users.default_factory(), {
                int(k): v for k, v in data.get("users", {}).items()
            })
            for user_data in self.users.values():
                user_data["crypto_balances"] = defaultdict(int, user_data.get("crypto_balances", {}))
                if isinstance(user_data.get("last_survival_update"), str):
                    try:
                        user_data["last_survival_update"] = datetime.datetime.fromisoformat(user_data["last_survival_update"])
                    except:
                        user_data["last_survival_update"] = datetime.datetime.now().isoformat()
            self.businesses = data.get("businesses", {})
            self.cryptocurrencies = data.get("cryptocurrencies", {})
            self.bank = data.get("bank", self.bank)
            self.feature_applications = data.get("feature_applications", {})
            self.license_applications = data.get("license_applications", {})
        except FileNotFoundError:
            print("economy_data.json not found. Starting fresh.")
        except Exception as e:
            print(f"Error loading economy data: {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        print('Economy cog loaded.')
        self.bot.loop.create_task(self.apply_bank_interest_loop())
        self.bot.loop.create_task(self.survival_loop())
        self.bot.loop.create_task(self.shipment_loop())
        for guild in self.bot.guilds:
            await self._cache_invites(guild)

    async def _cache_invites(self, guild):
        """Snapshot current invite use-counts so we can diff on member join.
        Requires the bot to have Manage Server permission."""
        try:
            invites = await guild.invites()
            self.invite_cache[guild.id] = {inv.code: inv.uses for inv in invites}
        except discord.Forbidden:
            self.invite_cache[guild.id] = {}
            print(f"[economy] Missing 'Manage Server' permission to track invites in {guild.name} — "
                  f"invite_count job objectives won't work there.")

    @commands.Cog.listener()
    async def on_member_join(self, member):
        guild = member.guild
        self.recent_joins[guild.id][member.id] = datetime.datetime.now().timestamp()

        # --- Invite-based recruitment tracking ---
        old_cache = self.invite_cache.get(guild.id, {})
        try:
            new_invites = await guild.invites()
        except discord.Forbidden:
            return
        new_cache = {inv.code: inv.uses for inv in new_invites}
        inviter = None
        for inv in new_invites:
            if new_cache.get(inv.code, 0) > old_cache.get(inv.code, 0):
                inviter = inv.inviter
                break
        self.invite_cache[guild.id] = new_cache

        if not inviter or inviter.bot:
            return

        user_data = self.get_user_data(inviter.id)
        job_id = user_data.get("job")
        if not job_id:
            return
        job = self.jobs[job_id]
        progress = user_data.setdefault("job_progress", {"obj_idx": 0, "count": 0})
        if progress["obj_idx"] >= len(job["objectives"]):
            return
        obj = job["objectives"][progress["obj_idx"]]
        if obj["type"] != "invite_count":
            return
        progress["count"] += 1
        self.save_data()
        channel = guild.system_channel or discord.utils.get(guild.text_channels, name="general")
        if progress["count"] >= obj["target"]:
            if channel:
                await channel.send(f"✅ {inviter.mention} hit their recruitment goal! Use `!work` to collect payout.")
        elif channel:
            await channel.send(f"📈 {inviter.mention} brought in a new member ({progress['count']}/{obj['target']} for their job objective).")

    async def apply_bank_interest_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now = datetime.datetime.now()
            if now.hour == 0 and now.minute == 0:
                print("Applying bank interest...")
                for user_data in self.users.values():
                    if user_data["bank_balance"] > 0:
                        interest = int(user_data["bank_balance"] * self.bank["interest_rate"])
                        user_data["bank_balance"] += interest
                        self.bank["balance"] += interest
                self.save_data()
            await asyncio.sleep(60)

    async def survival_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await asyncio.sleep(600)
            now = datetime.datetime.now()
            for user_data in self.users.values():
                if not user_data.get("last_survival_update"):
                    continue
                try:
                    last = user_data["last_survival_update"]
                    if isinstance(last, str):
                        last = datetime.datetime.fromisoformat(last)
                    hours = (now - last).total_seconds() / 3600
                    user_data["hunger"] = max(0, user_data["hunger"] - int(5 * hours))
                    user_data["thirst"] = max(0, user_data["thirst"] - int(7 * hours))
                    if user_data["hunger"] <= 20 or user_data["thirst"] <= 20:
                        user_data["health"] = max(0, user_data["health"] - int(10 * hours))
                    user_data["last_survival_update"] = now.isoformat()
                except:
                    pass
            self.save_data()

    def get_user_data(self, user_id):
        return self.users[user_id]

    # -------------------------------------------------------------------
    # Career path helpers
    # -------------------------------------------------------------------
    def career_level_index(self, path_id, xp):
        levels = self.career_paths[path_id]["levels"]
        idx = 0
        for i, lvl in enumerate(levels):
            if xp >= lvl["xp_required"]:
                idx = i
            else:
                break
        return idx

    def career_role_name(self, path_id, level_idx):
        return self.career_paths[path_id]["levels"][level_idx]["title"]

    async def ensure_career_role(self, guild, role_name):
        existing = discord.utils.get(guild.roles, name=role_name)
        if existing:
            return existing
        try:
            return await guild.create_role(name=role_name, reason="Auto-created career role")
        except discord.Forbidden:
            return None

    async def sync_career_role(self, member, path_id, old_xp, new_xp):
        old_idx = self.career_level_index(path_id, old_xp)
        new_idx = self.career_level_index(path_id, new_xp)
        if old_idx == new_idx:
            return None
        guild = member.guild
        all_titles = [lvl["title"] for lvl in self.career_paths[path_id]["levels"]]
        old_role = discord.utils.get(guild.roles, name=all_titles[old_idx])
        new_role = await self.ensure_career_role(guild, all_titles[new_idx])
        try:
            if old_role and old_role in member.roles:
                await member.remove_roles(old_role, reason="Career level change")
            if new_role:
                await member.add_roles(new_role, reason="Career level up")
        except discord.Forbidden:
            pass
        return all_titles[new_idx]

    def has_perk(self, user_data, perk):
        path_id = user_data.get("career")
        if not path_id:
            return False
        idx = self.career_level_index(path_id, user_data.get("career_xp", 0))
        return perk in self.career_paths[path_id]["levels"][idx]["perks"]

    def progress_bar(self, current, target, length=12):
        if target <= 0:
            return "█" * length
        filled = int(length * min(current / target, 1))
        return "█" * filled + "░" * (length - filled)

    # -------------------------------------------------------------------
    # Listener: passive career XP + legacy job message_activity payouts
    # -------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return
        user_data = self.get_user_data(message.author.id)
        now = datetime.datetime.now()
        now_ts = now.timestamp()

        # cooldown shared across career + job passive earning
        last = self.career_msg_cooldowns.get(message.author.id, 0)
        if now_ts - last < 30:
            return
        self.career_msg_cooldowns[message.author.id] = now_ts

        channel_name = getattr(message.channel, "name", "")
        hour = now.hour

        # --- Career chat XP ---
        path_id = user_data.get("career")
        if path_id:
            path = self.career_paths[path_id]
            if path["channel"] and channel_name == path["channel"]:
                start, end = path["active_hours"]
                in_window = (start <= hour < end) if start < end else True
                if in_window:
                    gained = random.randint(self.career_xp_min, self.career_xp_max)
                    old_xp = user_data["career_xp"]
                    user_data["career_xp"] += gained
                    new_title = await self.sync_career_role(message.author, path_id, old_xp, user_data["career_xp"])
                    if new_title:
                        await message.channel.send(
                            f"🎉 {message.author.mention} leveled up to **{new_title}** in {path['display_name']}!"
                        )
                    self.save_data()

        # --- Job objective progress: message_count and welcome_member auto-track here ---
        job_id = user_data.get("job")
        if job_id:
            job = self.jobs[job_id]
            progress = user_data.setdefault("job_progress", {"obj_idx": 0, "count": 0})
            if progress["obj_idx"] < len(job["objectives"]):
                obj = job["objectives"][progress["obj_idx"]]

                if obj["type"] == "message_count" and channel_name == obj["channel"]:
                    progress["count"] += 1
                    self.save_data()
                    if progress["count"] >= obj["target"]:
                        await message.channel.send(
                            f"✅ {message.author.mention} completed an objective for **{job['name']}**! "
                            f"Use `!work` to continue."
                        )

                elif obj["type"] == "welcome_member" and channel_name == obj["channel"] and message.mentions:
                    window = obj.get("window_minutes", 15) * 60
                    joins = self.recent_joins.get(message.guild.id, {})
                    for mentioned in message.mentions:
                        if mentioned.bot or mentioned.id == message.author.id:
                            continue
                        join_ts = joins.get(mentioned.id)
                        if join_ts and (now_ts - join_ts) <= window:
                            progress["count"] += 1
                            self.save_data()
                            if progress["count"] >= obj["target"]:
                                await message.channel.send(
                                    f"✅ {message.author.mention} completed their welcoming objective for "
                                    f"**{job['name']}**! Use `!work` to continue."
                                )
                            break

    # -------------------------------------------------------------------
    # /career command — show path, level, progress bar, perks
    # -------------------------------------------------------------------
    @commands.command(name="careers")
    async def list_careers(self, ctx):
        txt = "**Career Paths**\n\n"
        for pid, path in self.career_paths.items():
            level_names = " → ".join(lvl["title"] for lvl in path["levels"])
            txt += f"**{path['display_name']}** (`{pid}`)\n{level_names}\n\n"
        txt += "Choose one with `!choosecareer <career_id>`"
        await ctx.send(txt)

    @commands.command(name="choosecareer")
    async def choose_career(self, ctx, career_id: str):
        career_id = career_id.lower()
        if career_id not in self.career_paths:
            return await ctx.send("Unknown career. Check `!careers`.")
        user_data = self.get_user_data(ctx.author.id)
        user_data["career"] = career_id
        user_data["career_xp"] = 0
        self.save_data()
        path = self.career_paths[career_id]
        starting_title = path["levels"][0]["title"]
        role = await self.ensure_career_role(ctx.guild, starting_title)
        if role:
            try:
                await ctx.author.add_roles(role, reason="Started career")
            except discord.Forbidden:
                pass
        await ctx.send(f"You're now on the **{path['display_name']}** path, starting as **{starting_title}**!")

    @commands.command(name="career")
    async def career(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user_data = self.get_user_data(member.id)
        path_id = user_data.get("career")
        if not path_id:
            return await ctx.send(f"{member.display_name} hasn't picked a career yet. Use `!careers` then `!choosecareer`.")
        path = self.career_paths[path_id]
        xp = user_data.get("career_xp", 0)
        idx = self.career_level_index(path_id, xp)
        current_level = path["levels"][idx]
        next_level = path["levels"][idx + 1] if idx + 1 < len(path["levels"]) else None

        embed = discord.Embed(title=f"{member.display_name} — {path['display_name']}", color=discord.Color.dark_magenta())
        embed.add_field(name="Current Level", value=current_level["title"], inline=True)
        embed.add_field(name="Career XP", value=str(xp), inline=True)
        if next_level:
            bar = self.progress_bar(xp - current_level["xp_required"],
                                     next_level["xp_required"] - current_level["xp_required"])
            remaining = next_level["xp_required"] - xp
            embed.add_field(name=f"Progress to {next_level['title']}",
                             value=f"{bar}\n{remaining} XP to go", inline=False)
        else:
            embed.add_field(name="Progress", value="Max level reached", inline=False)
        perks = current_level["perks"]
        embed.add_field(name="Unlocked Perks", value=", ".join(perks) if perks else "None yet", inline=False)
        await ctx.send(embed=embed)

    # -------------------------------------------------------------------
    # Career perk-gated actions
    # -------------------------------------------------------------------
    @commands.command(name="outfitpoll")
    async def outfit_poll(self, ctx, question: str, *options: str):
        user_data = self.get_user_data(ctx.author.id)
        if not self.has_perk(user_data, "poll"):
            return await ctx.send("You need to reach **Stylist** in Fashion Influencer to host polls.")
        if len(options) < 2:
            return await ctx.send("Give at least 2 options.")
        numbered = "\n".join(f"{i+1}️⃣ {opt}" for i, opt in enumerate(options[:9]))
        msg = await ctx.send(f"**{question}**\n{numbered}")
        emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        for i in range(min(len(options), 9)):
            await msg.add_reaction(emojis[i])

    @commands.command(name="runway")
    async def runway_event(self, ctx, voice_channel: discord.VoiceChannel = None):
        user_data = self.get_user_data(ctx.author.id)
        if not self.has_perk(user_data, "runway"):
            return await ctx.send("You need to reach **Fashion Coordinator** to host runway events.")
        vc = voice_channel or (ctx.author.voice.channel if ctx.author.voice else None)
        if not vc:
            return await ctx.send("Join a voice channel or specify one.")
        await ctx.send(f"🚨 **Runway Event** hosted by {ctx.author.mention} starting in {vc.mention}! Come show your fit.")

    @commands.command(name="flashsale")
    async def flash_sale(self, ctx, item_id: str, discount_percent: int, minutes: int = 30):
        user_data = self.get_user_data(ctx.author.id)
        if not self.has_perk(user_data, "flash_sale"):
            return await ctx.send("You need to reach **Store Manager** in Retail Associate to run flash sales.")
        item_id = item_id.lower()
        if item_id not in self.shop_items:
            return await ctx.send("Unknown item.")
        original = self.shop_items[item_id]["price"]
        sale_price = max(1, int(original * (1 - discount_percent / 100)))
        self.active_drops[item_id] = {
            "price": sale_price,
            "expires": (datetime.datetime.now() + datetime.timedelta(minutes=minutes)).timestamp(),
            "name": self.shop_items[item_id]["name"],
        }
        await ctx.send(
            f"🔥 **FLASH SALE** — {self.shop_items[item_id]['name']} is {sale_price} bucks "
            f"(was {original}) for the next {minutes} minutes! Use `!buyrush {item_id}`"
        )

    @commands.command(name="giveaway")
    async def giveaway(self, ctx, prize: str, minutes: int = 10):
        user_data = self.get_user_data(ctx.author.id)
        if not self.has_perk(user_data, "giveaway"):
            return await ctx.send("You need to reach **Event Director** in Event Promoter to run giveaways.")
        msg = await ctx.send(f"🎁 **GIVEAWAY** — {prize}\nReact with 🎉 to enter! Ends in {minutes} minutes.")
        await msg.add_reaction("🎉")
        await asyncio.sleep(minutes * 60)
        msg = await ctx.channel.fetch_message(msg.id)
        reaction = discord.utils.get(msg.reactions, emoji="🎉")
        if not reaction:
            return await ctx.send("Giveaway ended — no entries.")
        users = [u async for u in reaction.users() if not u.bot]
        if not users:
            return await ctx.send("Giveaway ended — no entries.")
        winner = random.choice(users)
        await ctx.send(f"🎊 Congrats {winner.mention}, you won **{prize}**!")

    @commands.command(name="watchparty")
    async def watch_party(self, ctx, *, details: str):
        user_data = self.get_user_data(ctx.author.id)
        if not self.has_perk(user_data, "watch_party"):
            return await ctx.send("You need to reach **Event Director** in Event Promoter to host watch parties.")
        await ctx.send(f"🍿 **Watch Party** hosted by {ctx.author.mention}\n{details}")

    # -------------------------------------------------------------------
    # Drops — limited-time purchasable items, admin announced
    # -------------------------------------------------------------------
    @commands.command(name="announcedrop")
    @commands.has_permissions(administrator=True)
    async def announce_drop(self, ctx, item_id: str, price: int, minutes: int = 15):
        item_id = item_id.lower()
        if item_id not in self.shop_items:
            return await ctx.send("Unknown item.")
        self.active_drops[item_id] = {
            "price": price,
            "expires": (datetime.datetime.now() + datetime.timedelta(minutes=minutes)).timestamp(),
            "name": self.shop_items[item_id]["name"],
        }
        await ctx.send(
            f"⚡ **LIMITED DROP** ⚡\n{self.shop_items[item_id]['name']} — {price} bucks\n"
            f"Available for {minutes} minutes only! Use `!buyrush {item_id}`"
        )

    @commands.command(name="buyrush")
    async def buy_rush(self, ctx, item_id: str):
        item_id = item_id.lower()
        drop = self.active_drops.get(item_id)
        if not drop or datetime.datetime.now().timestamp() > drop["expires"]:
            self.active_drops.pop(item_id, None)
            return await ctx.send("No active drop for that item.")
        user_data = self.get_user_data(ctx.author.id)
        if user_data["balance"] < drop["price"]:
            return await ctx.send(f"Need {drop['price']} bucks, you have {user_data['balance']}.")
        user_data["balance"] -= drop["price"]
        user_data["inventory"].append(item_id)
        self.save_data()
        await ctx.send(f"⚡ {ctx.author.mention} grabbed **{drop['name']}** for {drop['price']} bucks!")

    # -------------------------------------------------------------------
    # Reputation
    # -------------------------------------------------------------------
    @commands.command(name="thank", aliases=["rep"])
    async def thank(self, ctx, member: discord.Member):
        if member.id == ctx.author.id or member.bot:
            return await ctx.send("Invalid target.")
        key = (ctx.author.id, member.id)
        now_ts = datetime.datetime.now().timestamp()
        last = self.rep_cooldowns.get(key, 0)
        if now_ts - last < 86400:
            return await ctx.send("You can only give reputation to the same person once a day.")
        self.rep_cooldowns[key] = now_ts
        user_data = self.get_user_data(member.id)
        user_data["reputation"] = user_data.get("reputation", 0) + 1
        self.save_data()
        await ctx.send(f"⭐ {ctx.author.mention} gave reputation to {member.mention}. New rep: {user_data['reputation']}")

    @commands.command(name="reputation")
    async def reputation_check(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user_data = self.get_user_data(member.id)
        await ctx.send(f"⭐ {member.display_name} has **{user_data.get('reputation', 0)}** reputation.")

    # -------------------------------------------------------------------
    # Businesses — Brand Owners can run a business and employ members
    # -------------------------------------------------------------------
    @commands.command(name="startbusiness")
    async def start_business(self, ctx, name: str, *, biz_type: str = "General"):
        user_data = self.get_user_data(ctx.author.id)
        if not self.has_perk(user_data, "start_business"):
            return await ctx.send("You need the **Brand Owner** career (Founder level+) to start a business. Use `!choosecareer brand_owner`.")
        cost = 500
        if user_data["balance"] < cost:
            return await ctx.send(f"Starting a business costs {cost} bucks.")
        user_data["balance"] -= cost
        biz_id = str(uuid.uuid4())[:8]
        self.businesses[biz_id] = {
            "owner": ctx.author.id,
            "name": name,
            "type": biz_type,
            "balance": 0,        # cash on hand — robbable via !heist
            "bank_balance": 0,   # secured vault — NOT robbable, only moved via !bizdeposit/!bizwithdraw
            "pending_stock": 0,  # units ordered from the factory, not yet arrived
            "shelved_stock": 0,  # units arrived AND stocked, ready to sell via !sellstock
            "employees": {},
            "investors": {},
            "level": 1,
        }
        user_data["businesses"].append(biz_id)
        self.save_data()
        await ctx.send(f"🏢 **{name}** ({biz_type}) founded! Business ID: `{biz_id}`\nHire people with `!hire @member {biz_id}`")

    @commands.command(name="mybusiness")
    async def my_business(self, ctx, biz_id: str = None):
        owned = [bid for bid, b in self.businesses.items() if b["owner"] == ctx.author.id]
        if not owned:
            return await ctx.send("You don't own a business. Use `!startbusiness`.")
        biz_id = biz_id or owned[0]
        biz = self.businesses.get(biz_id)
        if not biz or biz["owner"] != ctx.author.id:
            return await ctx.send("Business not found or not yours.")
        employee_lines = []
        for uid, info in biz["employees"].items():
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            employee_lines.append(f"{name} — {info['role']} (wage: {info['wage']})")
        invest_total = sum(biz["investors"].values())
        pending_shipments = [s for s in self.shipments.values() if s["biz_id"] == biz_id and not s["fulfilled"]]
        embed = discord.Embed(title=f"🏢 {biz['name']} (`{biz_id}`)", color=discord.Color.dark_gold())
        embed.add_field(name="Type", value=biz["type"], inline=True)
        embed.add_field(name="Cash on Hand", value=f"{biz['balance']} (robbable)", inline=True)
        embed.add_field(name="Bank Vault", value=f"{biz['bank_balance']} (secure)", inline=True)
        embed.add_field(name="Pending Stock", value=str(biz["pending_stock"]), inline=True)
        embed.add_field(name="Shelved Stock", value=str(biz["shelved_stock"]), inline=True)
        embed.add_field(name="Total Invested", value=str(invest_total), inline=True)
        if pending_shipments:
            ship_lines = []
            for s in pending_shipments:
                remaining = max(0, int(s["eta_ts"] - datetime.datetime.now().timestamp()))
                mins = remaining // 60
                ship_lines.append(f"{s['units']} units — ETA {mins}m")
            embed.add_field(name="Incoming Shipments", value="\n".join(ship_lines), inline=False)
        embed.add_field(name="Employees", value="\n".join(employee_lines) if employee_lines else "None yet", inline=False)
        await ctx.send(embed=embed)

    # -------------------------------------------------------------------
    # Supply chain — factory contracts, shipment delay, stocking, selling
    # -------------------------------------------------------------------
    UNIT_COST = 5       # cost per unit ordered from the factory
    UNIT_SELL_PRICE = 9 # revenue per unit when sold from shelved stock
    MINUTES_PER_UNIT = 1
    MIN_SHIPMENT_MINUTES = 5

    @commands.command(name="contractfactory")
    async def contract_factory(self, ctx, biz_id: str, units: int):
        """Negotiate a contract with the factory for raw stock. Costs business cash up front,
        takes real time to arrive (1 min/unit, 5 min minimum) — simulating an actual supply chain."""
        if units <= 0:
            return await ctx.send("Order at least 1 unit.")
        biz = self.businesses.get(biz_id)
        if not biz or biz["owner"] != ctx.author.id:
            return await ctx.send("Business not found or not yours.")
        cost = units * self.UNIT_COST
        if biz["balance"] < cost:
            return await ctx.send(f"Contract costs {cost} bucks (business cash on hand: {biz['balance']}).")
        biz["balance"] -= cost
        eta_minutes = max(self.MIN_SHIPMENT_MINUTES, units * self.MINUTES_PER_UNIT)
        eta_ts = datetime.datetime.now().timestamp() + eta_minutes * 60
        shipment_id = str(uuid.uuid4())[:8]
        self.shipments[shipment_id] = {"biz_id": biz_id, "units": units, "eta_ts": eta_ts, "fulfilled": False}
        self.save_data()
        await ctx.send(
            f"📦 Contract signed with the factory: **{units} units** for **{cost} bucks**.\n"
            f"Shipment `{shipment_id}` arriving in ~{eta_minutes} minutes. Check `!mybusiness` to track it."
        )

    async def shipment_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            now_ts = datetime.datetime.now().timestamp()
            for shipment_id, s in list(self.shipments.items()):
                if s["fulfilled"]:
                    continue
                if now_ts >= s["eta_ts"]:
                    biz = self.businesses.get(s["biz_id"])
                    if biz:
                        biz["pending_stock"] += s["units"]
                        s["fulfilled"] = True
                        self.save_data()
                        owner = self.bot.get_user(biz["owner"])
                        if owner:
                            try:
                                await owner.send(
                                    f"📦 Your shipment of {s['units']} units arrived at **{biz['name']}**! "
                                    f"Get a Stock Clerk to `!stockshelves {s['biz_id']} <amount>`."
                                )
                            except discord.Forbidden:
                                pass
            await asyncio.sleep(30)

    @commands.command(name="stockshelves")
    async def stock_shelves(self, ctx, biz_id: str, amount: int):
        """Employees move arrived shipment units from pending_stock to shelved_stock.
        Counts toward the Stock Clerk job objective if active."""
        if amount <= 0:
            return await ctx.send("Amount must be positive.")
        biz = self.businesses.get(biz_id)
        if not biz:
            return await ctx.send("Business not found.")
        if ctx.author.id not in biz["employees"] and biz["owner"] != ctx.author.id:
            return await ctx.send("You don't work there.")
        if biz["pending_stock"] < amount:
            return await ctx.send(f"Only {biz['pending_stock']} units available to stock.")
        biz["pending_stock"] -= amount
        biz["shelved_stock"] += amount
        self.save_data()
        await ctx.send(f"📋 Stocked {amount} units at **{biz['name']}**. Shelved stock: {biz['shelved_stock']}.")

        # Job objective progress
        user_data = self.get_user_data(ctx.author.id)
        job_id = user_data.get("job")
        if job_id == "stock_clerk":
            job = self.jobs[job_id]
            progress = user_data.setdefault("job_progress", {"obj_idx": 0, "count": 0})
            if progress["obj_idx"] < len(job["objectives"]):
                obj = job["objectives"][progress["obj_idx"]]
                if obj["type"] == "stock_shelves":
                    progress["count"] += amount
                    self.save_data()
                    if progress["count"] >= obj["target"]:
                        await ctx.send(f"✅ {ctx.author.mention} completed their Stock Clerk objective! Use `!work` to collect payout.")

    @commands.command(name="sellstock")
    async def sell_stock(self, ctx, biz_id: str, amount: int):
        """Owner converts shelved stock into cash (representing customer sales)."""
        if amount <= 0:
            return await ctx.send("Amount must be positive.")
        biz = self.businesses.get(biz_id)
        if not biz or biz["owner"] != ctx.author.id:
            return await ctx.send("Business not found or not yours.")
        if biz["shelved_stock"] < amount:
            return await ctx.send(f"Only {biz['shelved_stock']} units on the shelf.")
        biz["shelved_stock"] -= amount
        revenue = amount * self.UNIT_SELL_PRICE
        biz["balance"] += revenue
        self.save_data()
        await ctx.send(f"💵 Sold {amount} units for **{revenue} bucks**. Cash on hand: {biz['balance']}.")

    # -------------------------------------------------------------------
    # Business bank account — secured, NOT robbable
    # -------------------------------------------------------------------
    @commands.command(name="bizdeposit")
    async def biz_deposit(self, ctx, biz_id: str, amount: int):
        biz = self.businesses.get(biz_id)
        if not biz or biz["owner"] != ctx.author.id:
            return await ctx.send("Business not found or not yours.")
        if amount <= 0 or biz["balance"] < amount:
            return await ctx.send("Invalid amount or insufficient cash on hand.")
        biz["balance"] -= amount
        biz["bank_balance"] += amount
        self.save_data()
        await ctx.send(f"🏦 Secured {amount} bucks in **{biz['name']}**'s vault. Vault balance: {biz['bank_balance']}.")

    @commands.command(name="bizwithdraw")
    async def biz_withdraw(self, ctx, biz_id: str, amount: int):
        biz = self.businesses.get(biz_id)
        if not biz or biz["owner"] != ctx.author.id:
            return await ctx.send("Business not found or not yours.")
        if amount <= 0 or biz["bank_balance"] < amount:
            return await ctx.send("Invalid amount or insufficient vault balance.")
        biz["bank_balance"] -= amount
        biz["balance"] += amount
        self.save_data()
        await ctx.send(f"Withdrew {amount} bucks from the vault. Cash on hand: {biz['balance']}.")



    @commands.command(name="hire")
    async def hire(self, ctx, member: discord.Member, biz_id: str, role: str = "Worker", wage: int = 20):
        user_data = self.get_user_data(ctx.author.id)
        if not self.has_perk(user_data, "hire"):
            return await ctx.send("You need **Established Brand** level+ in Brand Owner to hire employees.")
        biz = self.businesses.get(biz_id)
        if not biz or biz["owner"] != ctx.author.id:
            return await ctx.send("Business not found or not yours.")
        if member.id == ctx.author.id or member.bot:
            return await ctx.send("Invalid hire target.")
        biz["employees"][member.id] = {"role": role, "wage": wage}
        self.save_data()
        await ctx.send(f"{member.mention} hired at **{biz['name']}** as **{role}** (wage: {wage}/shift).")

    @commands.command(name="fire")
    async def fire(self, ctx, member: discord.Member, biz_id: str):
        biz = self.businesses.get(biz_id)
        if not biz or biz["owner"] != ctx.author.id:
            return await ctx.send("Business not found or not yours.")
        if member.id in biz["employees"]:
            del biz["employees"][member.id]
            self.save_data()
            await ctx.send(f"{member.mention} was let go from **{biz['name']}**.")
        else:
            await ctx.send("That person doesn't work there.")

    @commands.command(name="clockin")
    async def clock_in(self, ctx, biz_id: str):
        """Employees work a shift at a business they're hired at — pays the employee
        and generates revenue for the business (simple flat-rate simulation)."""
        biz = self.businesses.get(biz_id)
        if not biz:
            return await ctx.send("Business not found.")
        emp = biz["employees"].get(ctx.author.id)
        if not emp:
            return await ctx.send("You don't work there. Ask the owner to `!hire` you.")
        user_data = self.get_user_data(ctx.author.id)
        wage = emp["wage"]
        revenue = int(wage * 1.5)
        user_data["balance"] += wage
        biz["balance"] += revenue
        self.save_data()
        await ctx.send(f"💼 Shift complete at **{biz['name']}**. You earned {wage} bucks, business made {revenue}.")

    @commands.command(name="invest")
    async def invest(self, ctx, biz_id: str, amount: int):
        if amount <= 0:
            return await ctx.send("Amount must be positive.")
        biz = self.businesses.get(biz_id)
        if not biz:
            return await ctx.send("Business not found.")
        if biz["owner"] == ctx.author.id:
            return await ctx.send("You can't invest in your own business.")
        user_data = self.get_user_data(ctx.author.id)
        if user_data["balance"] < amount:
            return await ctx.send("Not enough bucks.")
        user_data["balance"] -= amount
        biz["balance"] += amount
        biz["investors"][ctx.author.id] = biz["investors"].get(ctx.author.id, 0) + amount
        self.save_data()
        owner = ctx.guild.get_member(biz["owner"])
        await ctx.send(
            f"💰 {ctx.author.mention} invested **{amount}** bucks into **{biz['name']}**"
            + (f" (owned by {owner.display_name})" if owner else "") + "."
        )

    @commands.command(name="payout")
    async def payout(self, ctx, biz_id: str, member: discord.Member, amount: int):
        biz = self.businesses.get(biz_id)
        if not biz or biz["owner"] != ctx.author.id:
            return await ctx.send("Business not found or not yours.")
        if biz["balance"] < amount:
            return await ctx.send("Business doesn't have enough balance.")
        biz["balance"] -= amount
        recipient = self.get_user_data(member.id)
        recipient["balance"] += amount
        self.save_data()
        await ctx.send(f"Paid out {amount} bucks to {member.mention} from **{biz['name']}**.")

    @commands.command(name="brandrole")
    async def brand_role(self, ctx, biz_id: str, role_name: str, hex_color: str = "9b59b6"):
        user_data = self.get_user_data(ctx.author.id)
        if not self.has_perk(user_data, "custom_role"):
            return await ctx.send("You need **Industry Leader** in Brand Owner to create a custom brand role.")
        biz = self.businesses.get(biz_id)
        if not biz or biz["owner"] != ctx.author.id:
            return await ctx.send("Business not found or not yours.")
        try:
            color = discord.Color(int(hex_color.lstrip("#"), 16))
            role = await ctx.guild.create_role(name=role_name, color=color, reason=f"Brand role for {biz['name']}")
            await ctx.author.add_roles(role)
            await ctx.send(f"Created brand role **{role_name}** and assigned it to you.")
        except (ValueError, discord.Forbidden):
            await ctx.send("Couldn't create that role — check the hex color or my permissions.")

    @commands.command(name="businesses")
    async def list_businesses(self, ctx):
        if not self.businesses:
            return await ctx.send("No businesses exist yet.")
        lines = []
        for bid, biz in self.businesses.items():
            owner = ctx.guild.get_member(biz["owner"])
            owner_name = owner.display_name if owner else "Unknown"
            lines.append(f"`{bid}` — **{biz['name']}** ({biz['type']}) — Owner: {owner_name}")
        await ctx.send("**Server Businesses**\n" + "\n".join(lines))

    # -------------------------------------------------------------------
    # Hype Caller — VC / event / drop announcing
    # -------------------------------------------------------------------
    @commands.command(name="announcevc")
    async def announce_vc(self, ctx):
        """Spot an active voice channel and call it out. Completes the Hype Caller vc_alert objective."""
        active_vcs = [vc for vc in ctx.guild.voice_channels
                      if len([m for m in vc.members if not m.bot]) >= 2]
        if not active_vcs:
            return await ctx.send("Nothing popping off in VC right now. Check back later.")
        vc = max(active_vcs, key=lambda c: len(c.members))
        member_names = ", ".join(m.display_name for m in vc.members if not m.bot)
        await ctx.send(f"🔊 **{vc.name}** is live right now with {member_names}! Pull up.")

        user_data = self.get_user_data(ctx.author.id)
        if user_data.get("job") == "hype_caller":
            job = self.jobs["hype_caller"]
            progress = user_data.setdefault("job_progress", {"obj_idx": 0, "count": 0})
            if progress["obj_idx"] < len(job["objectives"]) and job["objectives"][progress["obj_idx"]]["type"] == "vc_alert":
                progress["count"] = 1  # single-shot objective, completion handled in !work
                self.save_data()
                await ctx.send(f"✅ {ctx.author.mention} — objective spotted, use `!work` to collect your payout.")

    @commands.command(name="announceevent")
    async def announce_event(self, ctx, *, details: str):
        await ctx.send(f"📣 **Event Announcement**\n{details}\n— called by {ctx.author.mention}")

    # -------------------------------------------------------------------
    # Crime — comedic, low-stakes PvP and business heists
    # -------------------------------------------------------------------
    ROB_COOLDOWN = 7200       # 2 hours
    HEIST_COOLDOWN = 14400    # 4 hours
    ROB_SUCCESS_CHANCE = 0.45
    HEIST_SUCCESS_CHANCE = 0.35

    ROB_SUCCESS_LINES = [
        "You lifted {amount} bucks out of {victim}'s studded wallet while they argued about which Hot Topic checkout line was faster.",
        "{victim} was deep in a debate about which MCR era was superior and didn't notice you walk off with {amount} bucks.",
        "You distracted {victim} with a 'is this shirt sold out online too' question and pocketed {amount} bucks.",
        "{victim}'s skinny jeans were too tight to chase you. Clean {amount} buck getaway.",
        "You swapped {victim}'s loyalty punch card for an empty one and somehow that got you {amount} bucks. Don't ask.",
    ]
    ROB_FAIL_LINES = [
        "Mall security in cargo shorts caught you red-handed. Fined {fine} bucks.",
        "Your platform boots gave you away — way too loud. Fined {fine} bucks for disturbing the clearance rack.",
        "{victim} turned around at the worst possible moment. You got fined {fine} bucks and major side-eye.",
        "You tripped over a misplaced Funko Pop display. Fined {fine} bucks and your dignity.",
        "The store's emo playlist was too loud, you couldn't hear security coming. Fined {fine} bucks.",
    ]
    HEIST_SUCCESS_LINES = [
        "You and your crew cleaned out the register at **{biz}** during a fire sale rush. Got away with {amount} bucks.",
        "While everyone argued over the last band tee in stock at **{biz}**, you slipped behind the counter and took {amount} bucks.",
        "Smoke machine malfunction at **{biz}** gave you perfect cover. {amount} bucks gone before anyone noticed.",
    ]
    HEIST_FAIL_LINES = [
        "The mannequins at **{biz}** apparently have security cameras in them now. Caught and fined {fine} bucks.",
        "You set off the anti-theft gates wearing 6 studded belts at once. Fined {fine} bucks at **{biz}**.",
        "**{biz}**'s manager recognized you from your TikTok fit checks. Fined {fine} bucks and banned from the clearance rack.",
    ]

    @commands.command(name="rob")
    async def rob(self, ctx, victim: discord.Member):
        if victim.bot or victim.id == ctx.author.id:
            return await ctx.send("Invalid target.")
        now_ts = datetime.datetime.now().timestamp()
        last = self.rob_cooldowns.get(ctx.author.id, 0)
        if now_ts - last < self.ROB_COOLDOWN:
            remaining = int(self.ROB_COOLDOWN - (now_ts - last))
            return await ctx.send(f"You're laying low. Try again in {remaining // 60}m.")

        victim_data = self.get_user_data(victim.id)
        robber_data = self.get_user_data(ctx.author.id)
        self.rob_cooldowns[ctx.author.id] = now_ts

        if victim_data["balance"] <= 0:
            return await ctx.send(f"{victim.display_name}'s wallet is as empty as the clearance rack on Black Friday. Nothing to take.")

        if random.random() < self.ROB_SUCCESS_CHANCE:
            amount = random.randint(int(victim_data["balance"] * 0.1), max(1, int(victim_data["balance"] * 0.3)))
            amount = min(amount, victim_data["balance"])
            victim_data["balance"] -= amount
            robber_data["balance"] += amount
            line = random.choice(self.ROB_SUCCESS_LINES).format(amount=amount, victim=victim.display_name)
            self.save_data()
            await ctx.send(f"🖤 {line}")
        else:
            fine = random.randint(20, 60)
            robber_data["balance"] = max(0, robber_data["balance"] - fine)
            line = random.choice(self.ROB_FAIL_LINES).format(fine=fine, victim=victim.display_name)
            self.save_data()
            await ctx.send(f"🚨 {line}")

    @commands.command(name="heist")
    async def heist(self, ctx, biz_id: str):
        biz = self.businesses.get(biz_id)
        if not biz:
            return await ctx.send("Business not found.")
        if biz["owner"] == ctx.author.id:
            return await ctx.send("Can't rob your own business — that's just expensing it.")
        now_ts = datetime.datetime.now().timestamp()
        last = self.heist_cooldowns.get(ctx.author.id, 0)
        if now_ts - last < self.HEIST_COOLDOWN:
            remaining = int(self.HEIST_COOLDOWN - (now_ts - last))
            return await ctx.send(f"You're still cooling off from the last job. Try again in {remaining // 60}m.")
        self.heist_cooldowns[ctx.author.id] = now_ts

        if biz["balance"] <= 0:
            return await ctx.send(f"**{biz['name']}**'s register is empty. Come back when they've got cash on hand.")

        robber_data = self.get_user_data(ctx.author.id)
        if random.random() < self.HEIST_SUCCESS_CHANCE:
            amount = random.randint(int(biz["balance"] * 0.15), max(1, int(biz["balance"] * 0.4)))
            amount = min(amount, biz["balance"])
            biz["balance"] -= amount
            robber_data["balance"] += amount
            line = random.choice(self.HEIST_SUCCESS_LINES).format(amount=amount, biz=biz["name"])
            self.save_data()
            await ctx.send(f"🖤 {line}")
        else:
            fine = random.randint(50, 150)
            robber_data["balance"] = max(0, robber_data["balance"] - fine)
            line = random.choice(self.HEIST_FAIL_LINES).format(fine=fine, biz=biz["name"])
            self.save_data()
            await ctx.send(f"🚨 {line}")

    # -------------------------------------------------------------------
    # Core balance / shop info
    # -------------------------------------------------------------------
    @commands.command(name="balance", aliases=["bal", "cash"])
    async def balance(self, ctx):
        user_data = self.get_user_data(ctx.author.id)
        await ctx.send(
            f"💵 Wallet: **{user_data['balance']}** Bucks\n"
            f"🏦 Bank: **{user_data['bank_balance']}** Bucks"
        )

    @commands.command(name="shop")
    async def shop(self, ctx):
        txt = "**Hot Topic Shop**\n\n"
        for iid, item in self.shop_items.items():
            txt += f"{item['emoji']} **{item['name']}** (`{iid}`) — {item['price']} bucks\n_{item['description']}_\n"
        txt += "\nBuy with `!buy <item_id>`"
        await ctx.send(txt)

    @commands.command(name="daily")
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily(self, ctx):
        user_data = self.get_user_data(ctx.author.id)
        user_data["balance"] += 200
        await ctx.send(f"+200 daily bucks! New balance: {user_data['balance']}")
        self.save_data()

    # -------------------------------------------------------------------
    # Buying / inventory / using items
    # -------------------------------------------------------------------
    @commands.command(name="buy")
    async def buy(self, ctx, item_id: str):
        item_id = item_id.lower()
        if item_id not in self.shop_items:
            return await ctx.send(f"Unknown item. Check `!shop` for valid IDs.")
        item = self.shop_items[item_id]
        user_data = self.get_user_data(ctx.author.id)
        if user_data["balance"] < item["price"]:
            return await ctx.send(f"You need {item['price']} bucks, you have {user_data['balance']}.")
        user_data["balance"] -= item["price"]
        user_data["inventory"].append(item_id)
        self.save_data()
        await ctx.send(f"{item['emoji']} Bought **{item['name']}** for {item['price']} bucks. Use `!use {item_id}` to apply it.")

    @commands.command(name="inventory", aliases=["inv"])
    async def inventory(self, ctx):
        user_data = self.get_user_data(ctx.author.id)
        if not user_data["inventory"]:
            return await ctx.send("Your inventory is empty. Buy something with `!shop` and `!buy`.")
        counts = defaultdict(int)
        for iid in user_data["inventory"]:
            counts[iid] += 1
        lines = []
        for iid, qty in counts.items():
            item = self.shop_items.get(iid)
            if item:
                lines.append(f"{item['emoji']} **{item['name']}** x{qty}")
        await ctx.send("**Your Inventory**\n" + "\n".join(lines))

    @commands.command(name="use")
    async def use(self, ctx, item_id: str):
        item_id = item_id.lower()
        user_data = self.get_user_data(ctx.author.id)
        if item_id not in user_data["inventory"]:
            return await ctx.send("You don't own that item.")
        item = self.shop_items.get(item_id)
        if not item:
            return await ctx.send("Unknown item.")
        effect = item.get("effect")
        if not effect:
            return await ctx.send(f"{item['name']} can't be used directly — it's cosmetic/equippable.")

        user_data["inventory"].remove(item_id)
        msgs = []
        for stat, amount in effect.items():
            if stat in ("hunger", "thirst", "health"):
                before = user_data[stat]
                user_data[stat] = min(100, user_data[stat] + amount)
                msgs.append(f"{stat.capitalize()}: {before} → {user_data[stat]}")
            elif stat == "housing":
                msgs.append(f"Housing tier set to {amount} (shelter upgraded)")
        self.save_data()
        await ctx.send(f"Used **{item['name']}**.\n" + "\n".join(msgs))

    # -------------------------------------------------------------------
    # Status (hunger/thirst/health/job)
    # -------------------------------------------------------------------
    @commands.command(name="status", aliases=["survival"])
    async def status(self, ctx):
        user_data = self.get_user_data(ctx.author.id)
        job_name = self.jobs[user_data["job"]]["name"] if user_data.get("job") else "Unemployed"
        await ctx.send(
            f"**{ctx.author.display_name}'s Status**\n"
            f"❤️ Health: {user_data['health']}/100\n"
            f"🍔 Hunger: {user_data['hunger']}/100\n"
            f"💧 Thirst: {user_data['thirst']}/100\n"
            f"💼 Job: {job_name}"
        )

    # -------------------------------------------------------------------
    # Jobs
    # -------------------------------------------------------------------
    @commands.command(name="jobs")
    async def list_jobs(self, ctx):
        txt = "**Available Jobs**\n\n"
        for jid, job in self.jobs.items():
            obj_count = len(job["objectives"])
            cd_hrs = job["cooldown"] // 3600
            txt += (f"**{job['name']}** (`{jid}`) — {job['pay']} bucks per shift "
                    f"({obj_count} objective{'s' if obj_count != 1 else ''}, {cd_hrs}h cooldown)\n"
                    f"_{job['description']}_\n\n")
        txt += "Apply with `!applyjob <job_id>`, then `!work` to start your shift."
        await ctx.send(txt)

    @commands.command(name="applyjob")
    async def apply_job(self, ctx, job_id: str):
        user_data = self.get_user_data(ctx.author.id)
        job_id = job_id.lower()
        if job_id not in self.jobs:
            return await ctx.send("Unknown job. Check `!jobs` for valid IDs.")
        user_data["job"] = job_id
        user_data["job_progress"] = {"obj_idx": 0, "count": 0}
        user_data["last_job_task"] = None
        self.save_data()
        await ctx.send(f"You are now a {self.jobs[job_id]['name']}! Use `!work` to start your shift.")

    @commands.command(name="quitjob")
    async def quit_job(self, ctx):
        user_data = self.get_user_data(ctx.author.id)
        if not user_data.get("job"):
            return await ctx.send("You don't have a job.")
        user_data["job"] = None
        self.save_data()
        await ctx.send("You quit your job.")

    @commands.command(name="work")
    async def work(self, ctx):
        """Step through your job's objective chain. Each job has one or more objectives
        (chat targets, questions, button choices). Complete them all in order to get paid,
        then the job goes on cooldown before the chain resets."""
        user_data = self.get_user_data(ctx.author.id)
        job_id = user_data.get("job")
        if not job_id:
            return await ctx.send("You don't have a job. Use `!jobs` then `!applyjob <job_id>`.")
        job = self.jobs[job_id]
        now = datetime.datetime.now()

        # cooldown only applies once the full objective chain has been completed
        last_task = user_data.get("last_job_task")
        if last_task:
            last_task_dt = datetime.datetime.fromisoformat(last_task) if isinstance(last_task, str) else last_task
            elapsed = (now - last_task_dt).total_seconds()
            if elapsed < job["cooldown"]:
                remaining = int(job["cooldown"] - elapsed)
                hrs, rem = divmod(remaining, 3600)
                mins = rem // 60
                return await ctx.send(f"On cooldown. Try again in {hrs}h {mins}m.")

        progress = user_data.setdefault("job_progress", {"obj_idx": 0, "count": 0})
        if progress["obj_idx"] >= len(job["objectives"]):
            # safety reset in case state got out of sync
            progress["obj_idx"] = 0
            progress["count"] = 0

        obj = job["objectives"][progress["obj_idx"]]
        obj_num = progress["obj_idx"] + 1
        total_objs = len(job["objectives"])

        if obj["type"] == "message_count":
            remaining = obj["target"] - progress["count"]
            if remaining > 0:
                return await ctx.send(
                    f"💼 **{job['name']}** — Objective {obj_num}/{total_objs}\n"
                    f"{obj['description']}\nProgress: {progress['count']}/{obj['target']} "
                    f"(post in #{obj['channel']} to make progress)"
                )
            await self._advance_objective(ctx, user_data, job_id, job, progress)
            return

        if obj["type"] == "question":
            await ctx.send(
                f"💼 **{job['name']}** — Objective {obj_num}/{total_objs}\n{obj['question']}\n_Reply within 30 seconds._"
            )

            def check(m):
                return m.author.id == ctx.author.id and m.channel.id == ctx.channel.id

            try:
                reply = await self.bot.wait_for("message", check=check, timeout=30)
            except asyncio.TimeoutError:
                return await ctx.send("Too slow — objective expired, try `!work` again.")

            if reply.content.strip() == obj["answer"]:
                await self._advance_objective(ctx, user_data, job_id, job, progress)
            else:
                await ctx.send(f"❌ Wrong answer (correct: {obj['answer']}). Try `!work` again to retry this objective.")
            return

        if obj["type"] == "button_choice":
            view = discord.ui.View(timeout=30)
            result = {"done": False}

            async def make_callback(option):
                async def callback(interaction: discord.Interaction):
                    if interaction.user.id != ctx.author.id:
                        return await interaction.response.send_message("This isn't your task.", ephemeral=True)
                    if result["done"]:
                        return
                    result["done"] = True
                    if option["correct"]:
                        await interaction.response.edit_message(
                            content=f"✅ Great choice! Objective {obj_num}/{total_objs} complete.", view=None
                        )
                        await self._advance_objective(ctx, user_data, job_id, job, progress)
                    else:
                        await interaction.response.edit_message(
                            content="❌ Not quite — try `!work` again to retry this objective.", view=None
                        )
                return callback

            for option in obj["options"]:
                btn = discord.ui.Button(label=option["label"], style=discord.ButtonStyle.secondary)
                btn.callback = await make_callback(option)
                view.add_item(btn)

            await ctx.send(f"💼 **{job['name']}** — Objective {obj_num}/{total_objs}\n{obj['question']}", view=view)
            return

        if obj["type"] == "invite_count":
            remaining = obj["target"] - progress["count"]
            if remaining > 0:
                return await ctx.send(
                    f"💼 **{job['name']}** — Objective {obj_num}/{total_objs}\n"
                    f"{obj['description']}\nProgress: {progress['count']}/{obj['target']} "
                    f"(use your personal invite link — check Server Settings → Invites for your link)"
                )
            await self._advance_objective(ctx, user_data, job_id, job, progress)
            return

        if obj["type"] == "welcome_member":
            remaining = obj["target"] - progress["count"]
            if remaining > 0:
                return await ctx.send(
                    f"💼 **{job['name']}** — Objective {obj_num}/{total_objs}\n"
                    f"{obj['description']}\nProgress: {progress['count']}/{obj['target']}"
                )
            await self._advance_objective(ctx, user_data, job_id, job, progress)
            return

        if obj["type"] == "mod_approved":
            return await ctx.send(
                f"💼 **{job['name']}** — Objective {obj_num}/{total_objs}\n"
                f"{obj['description']}\n_Status: waiting on mod/admin approval via `!approveobjective`._"
            )

        if obj["type"] == "vc_alert":
            return await ctx.send(
                f"💼 **{job['name']}** — Objective {obj_num}/{total_objs}\n"
                f"{obj['description']}\n_Run `!announcevc` when you spot one — it'll auto-complete this for you._"
            )

        if obj["type"] == "stock_shelves":
            remaining = obj["target"] - progress["count"]
            if remaining > 0:
                return await ctx.send(
                    f"💼 **{job['name']}** — Objective {obj_num}/{total_objs}\n"
                    f"{obj['description']}\nProgress: {progress['count']}/{obj['target']} "
                    f"(use `!stockshelves <biz_id> <amount>` at a business you're hired at)"
                )
            await self._advance_objective(ctx, user_data, job_id, job, progress)
            return

    async def _advance_objective(self, ctx, user_data, job_id, job, progress):
        """Moves to the next objective in the chain, or pays out + resets cooldown if the chain is done."""
        await self._advance_objective_for(ctx.channel, ctx.author, user_data, job_id, job, progress)

    async def _advance_objective_for(self, channel, member, user_data, job_id, job, progress):
        progress["obj_idx"] += 1
        progress["count"] = 0
        if progress["obj_idx"] >= len(job["objectives"]):
            user_data["balance"] += job["pay"]
            user_data["last_job_task"] = datetime.datetime.now().isoformat()
            self.job_performance[job_id][member.id] += 1
            progress["obj_idx"] = 0
            progress["count"] = 0
            self.save_data()
            await channel.send(f"🎉 Shift complete as **{job['name']}** for {member.mention}! +{job['pay']} bucks. On cooldown until next shift.")
        else:
            self.save_data()
            await channel.send(f"Objective complete for {member.mention}! Use `!work` to start the next one for **{job['name']}**.")

    @commands.command(name="approveobjective")
    @commands.has_permissions(manage_messages=True)
    async def approve_objective(self, ctx, member: discord.Member):
        """Mods/admins use this to confirm a member genuinely completed a mod_approved objective."""
        user_data = self.get_user_data(member.id)
        job_id = user_data.get("job")
        if not job_id:
            return await ctx.send(f"{member.display_name} doesn't have a job.")
        job = self.jobs[job_id]
        progress = user_data.setdefault("job_progress", {"obj_idx": 0, "count": 0})
        if progress["obj_idx"] >= len(job["objectives"]):
            return await ctx.send(f"{member.display_name} has no pending objective.")
        obj = job["objectives"][progress["obj_idx"]]
        if obj["type"] != "mod_approved":
            return await ctx.send(f"{member.display_name}'s current objective isn't mod-approved — it tracks automatically.")
        await ctx.send(f"✅ {ctx.author.mention} approved {member.mention}'s objective for **{job['name']}**.")
        await self._advance_objective_for(ctx.channel, member, user_data, job_id, job, progress)

    # -------------------------------------------------------------------
    # Bank
    # -------------------------------------------------------------------
    @commands.command(name="deposit")
    async def deposit(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send("Amount must be positive.")
        user_data = self.get_user_data(ctx.author.id)
        if user_data["balance"] < amount:
            return await ctx.send("You don't have that much in your wallet.")
        user_data["balance"] -= amount
        user_data["bank_balance"] += amount
        self.bank["balance"] += amount
        self.save_data()
        await ctx.send(f"Deposited {amount} bucks. Bank balance: {user_data['bank_balance']}")

    @commands.command(name="withdraw")
    async def withdraw(self, ctx, amount: int):
        if amount <= 0:
            return await ctx.send("Amount must be positive.")
        user_data = self.get_user_data(ctx.author.id)
        if user_data["bank_balance"] < amount:
            return await ctx.send("You don't have that much in the bank.")
        user_data["bank_balance"] -= amount
        user_data["balance"] += amount
        self.bank["balance"] -= amount
        self.save_data()
        await ctx.send(f"Withdrew {amount} bucks. Wallet balance: {user_data['balance']}")

    # -------------------------------------------------------------------
    # Give / leaderboard
    # -------------------------------------------------------------------
    @commands.command(name="give", aliases=["pay"])
    async def give(self, ctx, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send("Amount must be positive.")
        if member.bot or member.id == ctx.author.id:
            return await ctx.send("Invalid recipient.")
        sender = self.get_user_data(ctx.author.id)
        if sender["balance"] < amount:
            return await ctx.send("You don't have enough bucks.")
        sender["balance"] -= amount
        receiver = self.get_user_data(member.id)
        receiver["balance"] += amount
        self.save_data()
        await ctx.send(f"{ctx.author.mention} sent **{amount}** bucks to {member.mention}.")

    @commands.command(name="leaderboard", aliases=["lb"])
    async def leaderboard(self, ctx):
        ranked = sorted(self.users.items(), key=lambda kv: kv[1]["balance"] + kv[1]["bank_balance"], reverse=True)[:10]
        if not ranked:
            return await ctx.send("No economy data yet.")
        lines = []
        for i, (uid, data) in enumerate(ranked, start=1):
            member = ctx.guild.get_member(uid)
            name = member.display_name if member else f"User {uid}"
            total = data["balance"] + data["bank_balance"]
            lines.append(f"**{i}.** {name} — {total} bucks")
        await ctx.send("**🏆 Net Worth Leaderboard**\n" + "\n".join(lines))

    # -------------------------------------------------------------------
    # Admin
    # -------------------------------------------------------------------
    @commands.command(name="addbucks")
    @commands.has_permissions(administrator=True)
    async def addbucks(self, ctx, member: discord.Member, amount: int):
        user_data = self.get_user_data(member.id)
        user_data["balance"] += amount
        self.save_data()
        await ctx.send(f"Adjusted {member.mention} by {amount}. New balance: {user_data['balance']}")

async def setup(bot):
    await bot.add_cog(Economy(bot))
