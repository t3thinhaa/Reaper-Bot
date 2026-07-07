import discord
from discord.ext import commands
from discord import app_commands

def get_color_emoji(role_name: str) -> str:
    name_lower = role_name.lower()
    if "crimson" in name_lower or "infernal" in name_lower:
        return "🔴"
    elif "dark" in name_lower or "abyss" in name_lower:
        return "⚫"
    elif "phantom" in name_lower or "void" in name_lower or "arcane" in name_lower or "astral" in name_lower:
        return "🟣"
    elif "pink" in name_lower or "rose" in name_lower:
        return "💗"
    elif "soul" in name_lower or "crystal" in name_lower or "frost" in name_lower:
        return "🔵"
    elif "forest" in name_lower:
        return "🟢"
    elif "light" in name_lower or "celestial" in name_lower or "radiant" in name_lower:
        return "🟡"
    return "⚪"

# 1. Thêm custom_id cho Dropdown để làm Persistent View
class ColorDropdown(discord.ui.Select):
    def __init__(self, color_roles):
        options = []
        for role in color_roles:
            emoji = get_color_emoji(role.name)
            options.append(discord.SelectOption(
                label=role.name, 
                value=str(role.id),
                description=f"Click để chọn màu {role.name}",
                emoji=emoji
            ))

        super().__init__(
            placeholder="🎨 Chọn một màu Reaper cho tên của bạn...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="persistent_color_dropdown" # Bắt buộc phải có ID cố định
        )

    async def callback(self, interaction: discord.Interaction):
        # Đóng nhận tương tác ẩn ngay lập tức để tránh lỗi hiển thị
        await interaction.response.defer(ephemeral=True)
        
        role_id = int(self.values[0])
        guild = interaction.guild
        member = interaction.user
        chosen_role = guild.get_role(role_id)

        if not chosen_role:
            await interaction.followup.send("❌ Không tìm thấy role màu này nữa!", ephemeral=True)
            return

        # Xóa các role màu Reaper cũ của thành viên
        roles_to_remove = [role for role in member.roles if role.name.endswith("Reaper") and role.id != role_id]
        if roles_to_remove:
            await member.remove_roles(*roles_to_remove)

        # Thêm role màu mới
        await member.add_roles(chosen_role)
        
        # CHỈ biến mất thông báo này thôi (bằng cách dùng ephemeral=True)
        await interaction.followup.send(f"🎉 Đã đổi màu tên của bạn sang **{chosen_role.name}** thành công!", ephemeral=True)


# 2. Định nghĩa View không có thời gian hết hạn (timeout=None)
class ColorDropdownView(discord.ui.View):
    def __init__(self, color_roles):
        super().__init__(timeout=None) # timeout=None giúp menu không bao giờ biến mất
        self.add_item(ColorDropdown(color_roles))


class Colors(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # 3. Khi bot khởi động, nạp lại View này vào bộ nhớ để menu cũ từ hôm trước vẫn bấm được
    @commands.Cog.listener()
    async def on_ready(self):
        # Chúng ta cần lấy danh sách role của một server (hoặc quét qua các server bot tham gia) để khôi phục View
        # Ở đây ta tạo một View rỗng để đăng ký custom_id với Discord chống lỗi nút chết
        self.bot.add_view(ColorDropdownView([]))
        print("🟢 Đã nạp lại hệ thống Persistent Color Dropdown thành công!")

    @app_commands.command(name="reaper_roles", description="Gửi bảng chọn màu cố định vào channel")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def reaper_roles(self, interaction: discord.Interaction):
        all_roles = sorted(interaction.guild.roles, key=lambda r: r.position, reverse=True)
        color_roles = [role for role in all_roles if role.name.endswith("Reaper")]

        if not color_roles:
            await interaction.response.send_message("❌ Server chưa có role nào kết thúc bằng chữ 'Reaper'!", ephemeral=True)
            return
        
        if len(color_roles) > 25:
            color_roles = color_roles[:25]

        view = ColorDropdownView(color_roles)
        # Gửi tin nhắn công khai vào kênh chat, menu này sẽ ở lại đây mãi mãi
        await interaction.response.send_message("💡 **HỆ THỐNG TỰ ĐỔI MÀU TÊN**\nHãy chọn một màu sắc bạn yêu thích ở menu dưới đây để làm đẹp cho trang cá nhân của mình nhé:", view=view)


async def setup(bot):
    await bot.add_cog(Colors(bot))