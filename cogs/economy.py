import discord
from discord.ext import commands
from discord import app_commands
from database import get_db_connection

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="Xem ví Điểm Linh Hồn và trạng thái thử thách của bạn")
    async def profile(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT soul_points, status, current_challenge FROM users_points WHERE user_id = %s AND guild_id = %s",
                (user_id, guild_id)
            )
            user_data = cursor.fetchone()
            cursor.close()
            conn.close()

            if user_data:
                points = user_data[0]
                status = user_data[1] if user_data[1] else "Chưa nhận"
                challenge = user_data[2] if user_data[2] else "Không có"
            else:
                points = 0
                status = "Chưa nhận"
                challenge = "Không có"

            embed = discord.Embed(title=f"📜 SỔ SINH TỬ: {interaction.user.name}", color=discord.Color.purple())
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.add_field(name="💰 Ví Linh Hồn", value=f"`{points}` Điểm", inline=False)
            embed.add_field(name="⚔️ Thử thách hiện tại", value=f"**{challenge}** *({status})*", inline=False)
            
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi truy vấn Database: {e}", ephemeral=True)

    @app_commands.command(name="leaderboard", description="Xem Top 10 Reaper nhiều điểm nhất server")
    async def leaderboard(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_name, soul_points FROM users_points WHERE guild_id = %s ORDER BY soul_points DESC LIMIT 10",
                (guild_id,)
            )
            top_users = cursor.fetchall()
            cursor.close()
            conn.close()

            embed = discord.Embed(title="🏆 BẢNG XẾP HẠNG QUYỀN LỰC REAPER", color=discord.Color.gold())
            
            description = ""
            for i, u in enumerate(top_users, 1):
                medals = {1: "🥇", 2: "🥈", 3: "🥉"}
                prefix = medals.get(i, f"`#{i}`")
                user_name = u[0] if u[0] else "Ẩn danh"
                points = u[1]
                description += f"{prefix} **{user_name}** — `{points}` điểm\n"
            
            embed.description = description if description else "Chưa có dữ liệu xếp hạng trong Server này."
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi truy vấn Bảng xếp hạng: {e}", ephemeral=True)

    @app_commands.command(name="add_points", description="[Admin] Cộng Điểm Linh Hồn cho một thành viên")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_points(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("❌ Số điểm cộng vào phải lớn hơn 0 chứ bạn ơi!", ephemeral=True)

        user_id = str(member.id)
        guild_id = str(interaction.guild_id)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            query = '''
                INSERT INTO users_points (user_id, guild_id, user_name, soul_points)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id, guild_id) DO UPDATE SET
                    user_name = EXCLUDED.user_name,
                    soul_points = users_points.soul_points + EXCLUDED.soul_points;
            '''
            cursor.execute(query, (user_id, guild_id, member.name, amount))
            conn.commit()
            cursor.close()
            conn.close()

            await interaction.response.send_message(f"✅ Đã cộng **+{amount}** Điểm Linh Hồn vào ví của {member.mention} thành công!")
        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi xử lý Database: {e}", ephemeral=True)

    @app_commands.command(name="remove_points", description="[Admin] Tịch thu / Trừ Điểm Linh Hồn của một thành viên")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_points(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("❌ Số điểm trừ đi phải lớn hơn 0 chứ!", ephemeral=True)

        user_id = str(member.id)
        guild_id = str(interaction.guild_id)

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Kiểm tra số điểm hiện có
            cursor.execute("SELECT soul_points FROM users_points WHERE user_id = %s AND guild_id = %s", (user_id, guild_id))
            user_data = cursor.fetchone()
            current_points = user_data[0] if user_data else 0

            if current_points < amount:
                cursor.close()
                conn.close()
                return await interaction.response.send_message(
                    f"❌ Không thể trừ! Ví của {member.name} chỉ có `{current_points}` điểm, không đủ trừ `{amount}` điểm.", 
                    ephemeral=True
                )

            # Thực hiện trừ điểm
            cursor.execute(
                "UPDATE users_points SET soul_points = soul_points - %s WHERE user_id = %s AND guild_id = %s",
                (amount, user_id, guild_id)
            )
            conn.commit()
            cursor.close()
            conn.close()

            await interaction.response.send_message(f"🩸 Đã tịch thu **-{amount}** Điểm Linh Hồn từ ví của {member.mention}!")
        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi xử lý Database: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))