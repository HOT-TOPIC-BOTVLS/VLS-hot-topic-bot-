import discord
from discord.ext import commands
import random
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
                "cooldown": 3600 *