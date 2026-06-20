import discord
from discord.ext import commands
import datetime
import json
import uuid
import asyncio
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
            "businesses": [],
            "bank_balance": 0,
            "crypto_balances": defaultdict(int),
            "hunger": 100,
            "thirst": 100,
            "health": 100,
            "last_survival_update": datetime.datetime.now().isoformat(),
            "business_license": False
        })

        self.businesses = {}
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

        self.jobs = {
            "trendsetter": {
                "name": "Trendsetter",
                "description": "Post engaging messages in #fashion-talk during peak hours.",
                "min_messages": 10,
                "pay_per_message": 10,
                "cooldown": 3600 * 6,
                "active_hours": (18, 23),
                "task_type": "message_activity"
            },
            "merchandise_stocker": {
                "name": "Merchandise Stocker",
                "description": "Help users with shop queries in #shop-discussion.",
                "min_messages": 5,
                "pay_per_message": 15,
                "cooldown": 3600 * 8,
                "active_hours": (10, 17),
                "task_type": "message_activity"
            },
            "stylist": {
                "name": "Stylist",
                "description": "Help a customer choose an outfit based on their preferences.",
                "cooldown": 3600 * 4,
                "pay": 100,
                "task_type": "button_choice",
                "task_data": {
                    "question": "A customer wants an outfit for a punk rock concert. What do you recommend?",
                    "options": [
                        {"label": "Leather Jacket, Band Tee, Ripped Jeans", "correct": True},
                        {"label": "Flowy Dress, Sandals, Sun Hat", "correct": False},
                        {"label": "Business Suit, Tie, Dress Shoes", "correct": False}
                    ]
                }
            },
            "cashier": {
                "name": "Cashier",
                "description": "Process a customer's purchase.",
                "cooldown": 3600 * 2,
                "pay": 70,
                "task_type": "question_answer",
                "task_data": {
                    "question": "A customer is buying a 'Spiked Choker' (75 Bucks) and a 'Vintage Band Tee' (50 Bucks). How much is the total?",
                    "answer": "125"
                }
            }
        }

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

    @commands.command(name="balance", aliases=["bal", "cash"])
    async def balance(self, ctx):
        user_data = self.get_user_data(ctx.author.id)
        await ctx.send(f"Your balance: **{user_data['balance']}** Hot Topic Bucks.")

    @commands.command(name="shop")
    async def shop(self, ctx):
        txt = "**Hot Topic Shop**\n\n"
        for iid, item in self.shop_items.items():
            txt += f"{item['emoji']} **{item['name']}** — {item['price']} bucks\n"
        await ctx.send(txt)

    @commands.command(name="daily")
    @commands.cooldown(1, 86400, commands.BucketType.user)
    async def daily(self, ctx):
        user_data = self.get_user_data(ctx.author.id)
        user_data["balance"] += 200
        await ctx.send(f"+200 daily bucks! New balance: {user_data['balance']}")
        self.save_data()

    @commands.command(name="applyjob")
    async def apply_job(self, ctx, job_id: str):
        user_data = self.get_user_data(ctx.author.id)
        job_id = job_id.lower()
        if job_id not in self.jobs:
            return await ctx.send("Unknown job.")
        user_data["job"] = job_id
        await ctx.send(f"You are now a {self.jobs[job_id]['name']}!")
        self.save_data()

async def setup(bot):
    await bot.add_cog(Economy(bot))