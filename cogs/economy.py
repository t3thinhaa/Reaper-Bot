from __future__ import annotations

import random
from datetime import datetime, timezone
import discord
from discord.ext import commands
from discord import app_commands

from sqlalchemy import select, update
from database import get_session, UserPoint

class EconomyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="Xem ví Điểm Linh Hồn và trạng thái thử thách của bạn")
    async def profile(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)

        try:
            async with get_session() as session:
                result = await session.execute(
                    select(UserPoint).where(UserPoint.user_id == user_id, UserPoint.guild_id == guild_id)
                )
                user_data = result.scalar_one_or_none()

            points = user_data.soul_points if user_data else 0
            status = user_data.status if (user_data and user_data.status) else "Chưa nhận"
            challenge = user_data.current_challenge if (user_data and user_data.current_challenge) else "Không có"

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
            async with get_session() as session:
                result = await session.execute(
                    select(UserPoint.user_name, UserPoint.soul_points)
                    .where(UserPoint.guild_id == guild_id)
                    .order_by(UserPoint.soul_points.desc())
                    .limit(10)
                )
                top_users = result.fetchall()

            embed = discord.Embed(title="🏆 BẢNG XẾP HẠNG QUYỀN LỰC REAPER", color=discord.Color.gold())
            
            description = ""
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for i, u in enumerate(top_users, 1):
                prefix = medals.get(i, f"`#{i}`")
                user_name = u[0] if u[0] else "Ẩn danh"
                points = u[1]
                description += f"{prefix} **{user_name}** — `{points}` điểm\n"
            
            embed.description = description if description else "Chưa có dữ liệu xếp hạng trong Server này."
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi truy vấn Bảng xếp hạng: {e}", ephemeral=True)

    @app_commands.command(name="diemdanh", description="Điểm danh hằng ngày để nhận Điểm Linh Hồn ngẫu nhiên")
    async def diemdanh(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        try:
            async with get_session() as session:
                result = await session.execute(
                    select(UserPoint).where(UserPoint.user_id == user_id, UserPoint.guild_id == guild_id)
                )
                user_db = result.scalar_one_or_none()

                # Kiểm tra ngày điểm danh gần nhất stored trong time_archive
                if user_db and user_db.time_archive == now_str:
                    return await interaction.response.send_message("⌛ Bạn đã điểm danh hôm nay rồi! Hãy quay lại vào ngày mai.", ephemeral=True)

                bonus_points = random.randint(10, 50)

                if user_db:
                    user_db.soul_points = (user_db.soul_points or 0) + bonus_points
                    user_db.time_archive = now_str
                    user_db.user_name = interaction.user.name
                else:
                    new_user = UserPoint(
                        user_id=user_id,
                        guild_id=guild_id,
                        user_name=interaction.user.name,
                        soul_points=bonus_points,
                        time_archive=now_str
                    )
                    session.add(new_user)

                await session.commit()

            embed = discord.Embed(
                title="🎁 ĐIỂM DANH THÀNH CÔNG!",
                description=f"**{interaction.user.mention}** đã điểm danh hôm nay và nhận được **`+{bonus_points}`** Điểm Linh Hồn!",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi điểm danh: {e}", ephemeral=True)

    @app_commands.command(name="add_points", description="[Admin] Cộng Điểm Linh Hồn cho một thành viên")
    @app_commands.checks.has_permissions(administrator=True)
    async def add_points(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("❌ Số điểm cộng vào phải lớn hơn 0!", ephemeral=True)

        user_id = str(member.id)
        guild_id = str(interaction.guild_id)

        try:
            async with get_session() as session:
                result = await session.execute(
                    select(UserPoint).where(UserPoint.user_id == user_id, UserPoint.guild_id == guild_id)
                )
                user_db = result.scalar_one_or_none()

                if user_db:
                    user_db.soul_points = (user_db.soul_points or 0) + amount
                    user_db.user_name = member.name
                else:
                    new_user = UserPoint(
                        user_id=user_id,
                        guild_id=guild_id,
                        user_name=member.name,
                        soul_points=amount
                    )
                    session.add(new_user)

                await session.commit()

            await interaction.response.send_message(f"✅ Đã cộng **+{amount}** Điểm Linh Hồn vào ví của {member.mention} thành công!")
        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi xử lý Database: {e}", ephemeral=True)

    @app_commands.command(name="remove_points", description="[Admin] Tịch thu / Trừ Điểm Linh Hồn của một thành viên")
    @app_commands.checks.has_permissions(administrator=True)
    async def remove_points(self, interaction: discord.Interaction, member: discord.Member, amount: int):
        if amount <= 0:
            return await interaction.response.send_message("❌ Số điểm trừ đi phải lớn hơn 0!", ephemeral=True)

        user_id = str(member.id)
        guild_id = str(interaction.guild_id)

        try:
            async with get_session() as session:
                result = await session.execute(
                    select(UserPoint).where(UserPoint.user_id == user_id, UserPoint.guild_id == guild_id)
                )
                user_db = result.scalar_one_or_none()

                current_points = user_db.soul_points if user_db else 0

                if current_points < amount:
                    return await interaction.response.send_message(
                        f"❌ Không thể trừ! Ví của {member.name} chỉ có `{current_points}` điểm, không đủ trừ `{amount}` điểm.", 
                        ephemeral=True
                    )

                user_db.soul_points = current_points - amount
                await session.commit()

            await interaction.response.send_message(f"🩸 Đã tịch thu **-{amount}** Điểm Linh Hồn từ ví của {member.mention}!")
        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi xử lý Database: {e}", ephemeral=True)

async def setup(bot):
    await bot.add_cog(EconomyCog(bot))