import os

import discord
from discord.ext import commands

from config import TOKEN


class ReaperBot(commands.Bot):

    def __init__(self):

        intents = discord.Intents.default()
        intents.guilds = True
        intents.members = True

        super().__init__(
            command_prefix="!",
            intents=intents,
        )

    async def setup_hook(self):

        for file in os.listdir("./cogs"):

            if file.endswith(".py") and file != "__init__.py":

                await self.load_extension(f"cogs.{file[:-3]}")

                print(f"Loaded: {file}")

        synced = await self.tree.sync()

        print(f"Synced {len(synced)} command(s)")

    async def on_ready(self):

        print("=" * 40)
        print(f"Logged in as {self.user}")
        print(f"ID : {self.user.id}")
        print("=" * 40)


bot = ReaperBot()

bot.run(TOKEN)