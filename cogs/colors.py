import discord
from discord.ext import commands
from discord import app_commands

# Định nghĩa từ khóa cho 3 trường phái lớn
EVIL_KEYWORDS = ["infernal", "sanguine", "catalism", "bloodrose", "crimson", "abyss", "void", "dark", "soul", "plague"]
GOOD_KEYWORDS = ["celestial", "radiant", "auric", "solar", "dawn", "light", "ethereal", "crystal", "neonpink", "lightpink"]

def get_reaper_faction(role_name: str) -> str:
    """Phân loại role vào 3 nhóm hướng Ác, hướng Thiện hoặc Hướng lung tung."""
    name_lower = role_name.lower()
    if any(word in name_lower for word in EVIL_KEYWORDS):
        return "EVIL"
    if any(word in name_lower for word in GOOD_KEYWORDS):
        return "GOOD"
    return "NEUTRAL"


# 1. Khai báo Dropdown với custom_id bắt buộc để tồn tại vĩnh viễn
class FactionColorSelect(discord.ui.Select):
    def __init__(self, roles_chunk, placeholder_text, custom_id_key):
        options = [
            discord.SelectOption(label=role.name, value=str(role.id), description=f"Bấm để chọn màu {role.name}")
            for role in roles_chunk[:25]
        ]
        super().__init__(
            placeholder=placeholder_text, 
            min_values=1, 
            max_values=1, 
            options=options, 
            custom_id=f"persistent_color_select:{custom_id_key}"
        )

    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        role = interaction.guild.get_role(role_id)
        
        if not role:
            await interaction.response.send_message("Không tìm thấy role này trên server!", ephemeral=True)
            return

        old_reaper_roles = [r for r in interaction.user.roles if r.name.lower().endswith('reaper')]
        if old_reaper_roles:
            await interaction.user.remove_roles(*old_reaper_roles)

        await interaction.user.add_roles(role)
        await interaction.response.send_message(f"✨ Bạn đã chọn màu hệ: **{role.name}** thành công!", ephemeral=True)


# 2. View vĩnh cửu (Đặt timeout=None)
class FactionColorView(discord.ui.View):
    def __init__(self, guild_roles=None):
        super().__init__(timeout=None)
        if guild_roles is None:
            return

        evil_roles = []
        good_roles = []
        neutral_roles = []
        
        for role in guild_roles:
            if role.name.lower().endswith('reaper') and not role.is_default():
                faction = get_reaper_faction(role.name)
                if faction == "EVIL":
                    evil_roles.append(role)
                elif faction == "GOOD":
                    good_roles.append(role)
                else:
                    neutral_roles.append(role)
                
        evil_roles.sort(key=lambda r: r.name.lower())
        good_roles.sort(key=lambda r: r.name.lower())
        neutral_roles.sort(key=lambda r: r.name.lower())

        if evil_roles:
            self.add_item(FactionColorSelect(evil_roles, f"😈 Reaper Ác Wuỹ ({len(evil_roles)} màu tối/đỏ)...", "evil"))
        if good_roles:
            self.add_item(FactionColorSelect(good_roles, f"😇 Reaper Hướng Thiện ({len(good_roles)} màu sáng/vàng)...", "good"))
        if neutral_roles:
            self.add_item(FactionColorSelect(neutral_roles, f"🌀 Reaper Hướng Lung Tung ({len(neutral_roles)} màu nhạt)...", "neutral"))


# 3. Class quản lý lệnh thiết lập dạng Slash Command thuần túy
class ColorsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup_roles", description="Tạo bảng chọn màu Embed vĩnh viễn trong kênh hiện tại")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_roles(self, interaction: discord.Interaction):
        # 1. Trả lời ẩn cho Admin biết bot đang chạy (Tin nhắn này chỉ một mình Admin gõ lệnh nhìn thấy)
        await interaction.response.send_message("🪄 Đang cấu hình và gửi bảng chọn màu độc lập...", ephemeral=True)

        # 2. Khởi tạo View dropdowns
        view = FactionColorView(interaction.guild.roles)

        # 3. Đọc file ảnh từ thư mục cục bộ của bot
        file = discord.File("data/images/ReaperChooseColor.png", filename="ReaperChooseColor.png")

        # 4. Thiết lập khung ảnh Embed
        embed = discord.Embed(
            title="Chọn đi Reaper",
            description="Hãy lựa chọn con đường mà người sẽ cất bước trên dòng chảy của luân hồi.",
            color=discord.Color.from_rgb(180, 26, 44)
        )
        embed.set_image(url="attachment://ReaperChooseColor.png")

        # 5. [Mẹo Pro]: Gửi THẲNG vào kênh thông qua đối tượng channel (Không qua luân hồi interaction)
        # Cách này giúp tin nhắn Embed đứng độc lập hoàn toàn, xóa sạch dòng chữ "đã trả lời..." phía trên!
        await interaction.channel.send(embed=embed, view=view, file=file)


async def setup(bot):
    cog = ColorsCog(bot)
    await bot.add_cog(cog)
    bot.add_view(FactionColorView())