import discord
from discord.ext import commands
from discord import app_commands

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="Xem ví Điểm Linh Hồn và trạng thái thử thách của bạn")
    async def profile(self, interaction: discord.Interaction):
        # Mình bốc database ra xài, nếu db sập thì báo bận ngay lập tức
        db = self.bot.db
        if db is None: 
            return await interaction.response.send_message("❌ Hệ thống database đang bận, vui lòng thử lại sau!", ephemeral=True)

        user_id = str(interaction.user.id)
        user_data = await db.users_points.find_one({"user_id": user_id})

        # Mình bọc dữ liệu an toàn ở đây, nếu người mới chưa có trong hệ thống thì gán bằng 0 luôn cho đỡ sập code
        if user_data:
            points = user_data.get("soul_points", 0)
            status = user_data.get("status", "Chưa nhận")
            challenge = user_data.get("current_challenge", "Không có")
        else:
            points = 0
            status = "Chưa nhận"
            challenge = "Không có"

        # Thiết kế Embed giao diện Sổ Sinh Tử nhìn cho chất chơi, huyền bí
        embed = discord.Embed(title=f"📜 SỔ SINH TỬ: {interaction.user.name}", color=discord.Color.purple())
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="💰 Ví Linh Hồn", value=f"`{points}` Điểm", inline=False)
        embed.add_field(name="⚔️ Thử thách hiện tại", value=f"**{challenge}** *({status})*", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="Xem Top 10 Reaper nhiều điểm nhất server")
    async def leaderboard(self, interaction: discord.Interaction):
        db = self.bot.db
        if db is None: 
            return await interaction.response.send_message("❌ Hệ thống bận", ephemeral=True)

        # Lấy top 10 người giàu nhất, sắp xếp giảm dần (sort -1) dựa theo trường dữ liệu soul_points
        cursor = db.users_points.find().sort("soul_points", -1).limit(10)
        top_users = await cursor.to_list(length=10)

        embed = discord.Embed(title="🏆 BẢNG XẾP HẠNG QUYỀN LỰC REAPER", color=discord.Color.gold())
        
        description = ""
        for i, u in enumerate(top_users, 1):
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            prefix = medals.get(i, f"`#{i}`")
            description += f"{prefix} **{u.get('user_name', 'Ẩn danh')}** — `{u.get('soul_points', 0)}` điểm\n"
        
        embed.description = description if description else "Chưa có dữ liệu xếp hạng."
        await interaction.response.send_message(embed=embed)

    # --- TÍNH NĂNG MỚI: ADMIN CỘNG ĐIỂM HỒN ---
    @app_commands.command(name="add_points", description="[Admin] Cộng Điểm Linh Hồn cho một thành viên")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_points(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        db = self.bot.db
        if db is None: return await interaction.response.send_message("Lỗi DB", ephemeral=True)
        
        if amount <= 0:
            return await interaction.response.send_message("❌ Số điểm cộng vào phải lớn hơn 0 chứ bạn ơi!", ephemeral=True)

        user_id = str(member.id)
        # Sử dụng toán tử $inc để cộng dồn trực tiếp, upsert=True nghĩa là nếu ông này chưa có trong DB thì tự tạo luôn
        await db.users_points.update_one(
            {"user_id": user_id},
            {"$inc": {"soul_points": amount}, "$set": {"user_name": member.name}},
            upsert=True
        )
        await interaction.response.send_message(f"✅ Đã cộng **+{amount}** Điểm Linh Hồn vào ví của {member.mention} thành công!")

    # --- TÍNH NĂNG MỚI: ADMIN TRỪ ĐIỂM HỒN ---
    @app_commands.command(name="remove_points", description="[Admin] Tịch thu / Trừ Điểm Linh Hồn của một thành viên")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_points(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        db = self.bot.db
        if db is None: return await interaction.response.send_message("Lỗi DB", ephemeral=True)
        
        if amount <= 0:
            return await interaction.response.send_message("❌ Số điểm trừ đi phải lớn hơn 0 chứ!", ephemeral=True)

        user_id = str(member.id)
        # Truy vấn xem ví hiện tại có bao nhiêu điểm để tránh trừ âm tiền người ta
        user_data = await db.users_points.find_one({"user_id": user_id})
        current_points = user_data.get("soul_points", 0) if user_data else 0

        if current_points < amount:
            return await interaction.response.send_message(f"❌ Không thể trừ! Ví của {member.name} chỉ có `{current_points}` điểm, không đủ trừ `{amount}` điểm.", ephemeral=True)

        # Tiến hành trừ điểm
        await db.users_points.update_one(
            {"user_id": user_id},
            {"$inc": {"soul_points": -amount}}
        )
        await interaction.response.send_message(f"🩸 Đã tịch thu **-{amount}** Điểm Linh Hồn từ ví của {member.mention}!")

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))