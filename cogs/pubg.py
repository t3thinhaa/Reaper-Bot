# cogs/pubg.py
import discord
from discord.ext import commands
from discord import app_commands
import random

from data.pubg_maps import MAPS_DATA 

# Tạo một Class View chứa nút bấm Reroll
class RerollView(discord.ui.View):
    def __init__(self, map_key: str, map_name: str):
        super().__init__(timeout=60) # Nút bấm có hiệu lực trong 60 giây
        self.map_key = map_key
        self.map_name = map_name

    @discord.ui.button(label="Xa quá! Random lại phát", style=discord.ButtonStyle.danger, emoji="🔄")
    async def reroll_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        locations = MAPS_DATA.get(self.map_key)
        new_lucky_spot = random.choice(locations)

        # Cập nhật lại Embed cũ với địa điểm mới
        embed = discord.Embed(
            title="🪂 PUBG DROP LOCATION (ĐÃ RANDOM LẠI) 🪂",
            description=f"Bản đồ đang chọn: **{self.map_name}**",
            color=discord.Color.red()
        )
        embed.add_field(name="Địa điểm nhảy mới:", value=f"🎯 **{new_lucky_spot}**", inline=False)
        embed.set_footer(text="Lần này mà xa nữa thì do ăn ở nhé anh em!")

        # Edit lại tin nhắn cũ kèm theo nút bấm cũ luôn
        await interaction.response.edit_message(embed=embed, view=self)


class PUBG(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="drop", description="Random địa điểm nhảy dù trong PUBG!")
    @app_commands.choices(map_name=[
        app_commands.Choice(name="Erangel", value="erangel"),
        app_commands.Choice(name="Miramar", value="miramar"),
        app_commands.Choice(name="Sanhok", value="sanhok"),
        app_commands.Choice(name="Taego", value="taego"),
        app_commands.Choice(name="Vikendi", value="vikendi"),
        app_commands.Choice(name="Deston", value="deston"),
        app_commands.Choice(name="Rondo", value="rondo"),
    ])
    async def drop(self, interaction: discord.Interaction, map_name: app_commands.Choice[str]):
        selected_map_key = map_name.value
        selected_map_name = map_name.name
        
        locations = MAPS_DATA.get(selected_map_key)
        lucky_spot = random.choice(locations)
        
        embed = discord.Embed(
            title="🪂 PUBG DROP LOCATION 🪂",
            description=f"Bản đồ đang chọn: **{selected_map_name}**",
            color=discord.Color.orange()
        )
        embed.add_field(name="Địa điểm nhảy đề xuất:", value=f"🎯 **{lucky_spot}**", inline=False)
        embed.set_footer(text="Chúc anh em loot được nhiều đồ ngon và 'Chicken Dinner'!")
        
        # Thêm view chứa nút bấm vào tin nhắn gửi đi
        view = RerollView(map_key=selected_map_key, map_name=selected_map_name)
        await interaction.response.send_message(embed=embed, view=view)

async def setup(bot: commands.Bot):
    await bot.add_cog(PUBG(bot))