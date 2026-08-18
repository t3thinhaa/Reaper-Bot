import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio
from cogs.challenge import load_challenges_from_file
from database import get_db_connection

# ID của Role "Bá Chủ Chiến Trường"
BA_CHU_ROLE_ID = 1524827906357067879  

class ShopDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🛡️ Thẻ Miễn Tử (100 điểm)", value="item_disregard", description="Hủy ngay thử thách đang làm dở mà không bị phạt"),
            discord.SelectOption(label="🎭 Vé Gài Bẫy (200 điểm)", value="item_trap", description="Ép một đồng đội ngẫu nhiên phải nhận kèo Khó"),
            discord.SelectOption(label="🎲 Vé Đổi Vận (150 điểm)", value="item_reroll", description="Đổi sang một thử thách ngẫu nhiên cùng độ khó"),
            discord.SelectOption(label="🕶️ Kính Chiếu Yêu (300 điểm)", value="item_reveal", description="Xem trước nội dung của 3 thử thách tiếp theo"),
            discord.SelectOption(label="👑 Danh Hiệu Bá Chủ (6666 điểm)", value="item_bachu", description="Danh hiệu tối thượng: Miễn nhiễm bẫy, sở hữu đặc quyền VIP")
        ]
        super().__init__(placeholder="Chọn vật phẩm muốn quy đổi từ Linh Hồn...", options=options, custom_id="reaper_shop_select")

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)

        # Lấy thông tin điểm và trạng thái người dùng từ PostgreSQL
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
        except Exception as e:
            return await interaction.response.send_message(f"❌ Lỗi kết nối Database: {e}", ephemeral=True)

        current_points = user_data[0] if user_data else 0
        status = user_data[1] if (user_data and user_data[1]) else "Chưa nhận"
        current_challenge = user_data[2] if (user_data and user_data[2]) else "None"

        prices = {
            "item_disregard": 100, 
            "item_trap": 200, 
            "item_reroll": 150, 
            "item_reveal": 300, 
            "item_bachu": 6666
        }
        
        selected_item = self.values[0]
        cost = prices[selected_item]

        if current_points < cost:
            return await interaction.response.send_message(f"❌ Khí chất bất thành! Bạn cần có `{cost}` điểm, hiện tại bạn chỉ có `{current_points}` điểm. Hãy làm thêm thử thách!", ephemeral=True)

        # Helper thông báo tự hủy
        async def send_temporary_announcement(embed_content=None, text_content=None):
            msg = await interaction.channel.send(content=text_content, embed=embed_content)
            for i in range(10, 0, -1):
                suffix = f"\n\n*🟢 Tin nhắn này sẽ tự hủy sau {i} giây...*"
                if embed_content:
                    new_embed = embed_content.to_dict()
                    new_embed['description'] = embed_content.description + suffix
                    await msg.edit(embed=discord.Embed.from_dict(new_embed))
                else:
                    await msg.edit(content=text_content + suffix)
                await asyncio.sleep(1)
            try:
                await msg.delete()
            except discord.NotFound:
                pass

        # ==========================================
        # LOGIC 1: THẺ MIỄN TỬ
        # ==========================================
        if selected_item == "item_disregard":
            if status != "DOING":
                return await interaction.response.send_message("❌ Bạn hiện tại đâu có thực hiện thử thách nào dở dang đâu!", ephemeral=True)
            
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE users_points 
                    SET soul_points = soul_points - %s, status = 'DONE', current_challenge = 'None', challenge_reward = 0 
                    WHERE user_id = %s AND guild_id = %s
                    """,
                    (cost, user_id, guild_id)
                )
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as e:
                return await interaction.response.send_message(f"❌ Lỗi xử lý Database: {e}", ephemeral=True)

            await interaction.response.send_message("🛡️ Bạn đã sử dụng **Thẻ Miễn Tử** thành công!", ephemeral=True)
            await send_temporary_announcement(text_content=f"💨 **{interaction.user.mention}** đã tiêu hao `100` Điểm Linh Hồn để kích hoạt **Thẻ Miễn Tử**, xóa sổ kèo đang làm dở thành công!")
            return

        # ==========================================
        # LOGIC 2: VÉ GÀI BẪY
        # ==========================================
        elif selected_item == "item_trap":
            all_members = [m for m in interaction.guild.members if not m.bot and m.id != interaction.user.id]
            all_members = [m for m in all_members if not any(r.id == BA_CHU_ROLE_ID for r in m.roles)]

            if not all_members:
                return await interaction.response.send_message("❌ Server không có ai hợp lệ để gài bẫy!", ephemeral=True)
            
            victim = random.choice(all_members)
            victim_id = str(victim.id)
            
            # Kiểm tra nạn nhân có đang bận thử thách khác không
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT status FROM users_points WHERE user_id = %s AND guild_id = %s", (victim_id, guild_id))
                victim_row = cursor.fetchone()
                victim_status = victim_row[0] if victim_row else None
            except Exception as e:
                return await interaction.response.send_message(f"❌ Lỗi kiểm tra nạn nhân: {e}", ephemeral=True)

            if victim_status == "DOING":
                cursor.close()
                conn.close()
                return await interaction.response.send_message(f"❌ Gài bẫy thất bại! Thần may mắn đã mỉm cười với {victim.name}.", ephemeral=True)

            try:
                all_challenges = load_challenges_from_file()
                hard_challenges = [c for c in all_challenges if "Khó" in c['difficulty']]
                chosen_challenge = random.choice(hard_challenges) if hard_challenges else random.choice(all_challenges)
            except Exception:
                cursor.close()
                conn.close()
                return await interaction.response.send_message("❌ Hệ thống file thử thách gặp lỗi!", ephemeral=True)

            try:
                # Trừ điểm kẻ gài bẫy
                cursor.execute("UPDATE users_points SET soul_points = soul_points - %s WHERE user_id = %s AND guild_id = %s", (cost, user_id, guild_id))
                
                # Sập bẫy nạn nhân (Upsert)
                trap_query = """
                    INSERT INTO users_points (user_id, guild_id, user_name, current_challenge, challenge_reward, status)
                    VALUES (%s, %s, %s, %s, %s, 'DOING')
                    ON CONFLICT (user_id, guild_id) DO UPDATE SET
                        user_name = EXCLUDED.user_name,
                        current_challenge = EXCLUDED.current_challenge,
                        challenge_reward = EXCLUDED.challenge_reward,
                        status = 'DOING';
                """
                cursor.execute(trap_query, (victim_id, guild_id, victim.name, chosen_challenge['title'], chosen_challenge['reward']))
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as e:
                return await interaction.response.send_message(f"❌ Lỗi gài bẫy Database: {e}", ephemeral=True)

            await interaction.response.send_message(f"🎭 Đã kích hoạt Vé Gài Bẫy thành công! `-200` điểm.", ephemeral=True)
            
            trap_embed = discord.Embed(title="🎭 ỐI DỒI ÔI! CÓ KẺ GÀI BẪY!", color=discord.Color.red())
            trap_embed.description = (
                f"👤 Kẻ thủ ác **{interaction.user.mention}** đã sử dụng **Vé Gài Bẫy**!\n\n"
                f"🎯 Nạn nhân xấu số: {victim.mention}\n"
                f"⚔️ Thử thách bị ép nhận: **{chosen_challenge['title']}**\n"
                f"🎁 Phần thưởng nếu vượt qua: `{chosen_challenge['reward']}` điểm."
            )
            await send_temporary_announcement(embed_content=trap_embed)
            return

        # ==========================================
        # LOGIC 3: VÉ ĐỔI VẬN (REROLL)
        # ==========================================
        elif selected_item == "item_reroll":
            if status != "DOING":
                return await interaction.response.send_message("❌ Bạn phải đang làm một thử thách nào đó thì mới đổi được chứ!", ephemeral=True)
            
            try:
                all_challenges = load_challenges_from_file()
                available = [c for c in all_challenges if c['title'] != current_challenge]
                new_challenge = random.choice(available)
            except Exception:
                return await interaction.response.send_message("❌ Hệ thống file gặp lỗi!", ephemeral=True)

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE users_points 
                    SET soul_points = soul_points - %s, current_challenge = %s, challenge_reward = %s 
                    WHERE user_id = %s AND guild_id = %s
                    """,
                    (cost, new_challenge['title'], new_challenge['reward'], user_id, guild_id)
                )
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as e:
                return await interaction.response.send_message(f"❌ Lỗi đổi vận Database: {e}", ephemeral=True)

            await interaction.response.send_message("🎲 Đã đổi vận thành công!", ephemeral=True)
            reroll_embed = discord.Embed(title="🎲 ĐỔI VẬN THÀNH CÔNG", color=discord.Color.purple())
            reroll_embed.description = f"🔄 **{interaction.user.mention}** đã đổi thử thách sang: **{new_challenge['title']}** (Thưởng: `{new_challenge['reward']}` điểm)"
            await send_temporary_announcement(embed_content=reroll_embed)
            return

        # ==========================================
        # LOGIC 4: KÍNH CHIẾU YÊU
        # ==========================================
        elif selected_item == "item_reveal":
            try:
                all_challenges = load_challenges_from_file()
                preview_challenges = random.sample(all_challenges, min(3, len(all_challenges)))
                preview_text = "\n".join([f"• **{c['title']}** ({c['difficulty']}) - Thưởng: {c['reward']}" for c in preview_challenges])
            except Exception:
                return await interaction.response.send_message("❌ Không thể đọc danh sách thử thách!", ephemeral=True)

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE users_points SET soul_points = soul_points - %s WHERE user_id = %s AND guild_id = %s", (cost, user_id, guild_id))
                conn.commit()
                cursor.close()
                conn.close()
            except Exception as e:
                return await interaction.response.send_message(f"❌ Lỗi trừ điểm Database: {e}", ephemeral=True)

            await interaction.response.send_message(f"🕶️ **Kính Chiếu Yêu hé lộ 3 thử thách ngẫu nhiên trong kho:**\n{preview_text}\n*(Tin nhắn này chỉ một mình bạn nhìn thấy)*", ephemeral=True)
            await send_temporary_announcement(text_content=f"🕶️ **{interaction.user.mention}** vừa mua **Kính Chiếu Yêu** để xem trước thiên cơ (kho thử thách)!")
            return

        # ==========================================
        # LOGIC 5: BÁ CHỦ CHIẾN TRƯỜNG
        # ==========================================
        elif selected_item == "item_bachu":
            role = interaction.guild.get_role(BA_CHU_ROLE_ID)
            if role in interaction.user.roles:
                return await interaction.response.send_message("❌ Bạn đã đạt danh hiệu **Bá Chủ Chiến Trường** rồi!", ephemeral=True)

            if role is None:
                return await interaction.response.send_message("❌ Không tìm thấy Role mang ID này trên Server.", ephemeral=True)

            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("UPDATE users_points SET soul_points = soul_points - %s WHERE user_id = %s AND guild_id = %s", (cost, user_id, guild_id))
                conn.commit()
                cursor.close()
                conn.close()

                await interaction.user.add_roles(role)

                try:
                    new_nick = f"🔥 {interaction.user.display_name}"
                    if len(new_nick) <= 32:
                        await interaction.user.edit(nick=new_nick)
                except Exception:
                    pass

                await interaction.response.send_message("👑 Danh hiệu **Bá Chủ Chiến Trường** đã được kích hoạt!", ephemeral=True)

                announce_embed = discord.Embed(title="⚡ TIẾNG THÉT CỦA VỊ VUA MỚI! ⚡", color=discord.Color.gold())
                announce_embed.description = (
                    f"🎉 Toàn bộ thành viên hãy quỳ xuống trước sự xuất hiện của **Bá Chủ Chiến Trường** mới!\n\n"
                    f"🔥 **{interaction.user.mention}** đã tiêu hao **`6,666` Điểm Linh Hồn** để đoạt lấy ngai vàng!\n\n"
                    f"✨ *Từ nay sở hữu mọi đặc quyền tối thượng, miễn nhiễm hoàn toàn cạm bẫy Chợ Đen!*"
                )
                announce_embed.set_thumbnail(url=interaction.user.display_avatar.url)
                
                await interaction.channel.send(embed=announce_embed)

            except discord.Forbidden:
                await interaction.response.send_message("❌ Bot không có đủ quyền hạn để trao Role.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Đã xảy ra lỗi: {e}", ephemeral=True)
            return

class ShopView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(ShopDropdown())

class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="shop", description="Mở cửa hàng vật phẩm tự động bằng Điểm Linh Hồn")
    async def shop(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="🏪 CHỢ ĐEN LINH HỒN (AUTOMATED REAPER SHOP)",
            description="Hệ thống tự động hóa 100%. Mua xong kích hoạt quyền lợi tại chỗ!",
            color=discord.Color.dark_red()
        )
        embed.add_field(name="📜 Hàng Hóa Có Sẵn:", value=(
            "• `🛡️ Thẻ Miễn Tử` — **100 Điểm** *(Hủy kèo đang làm dở)*\n"
            "• `🎲 Vé Đổi Vận` — **150 Điểm** *(Đổi thử thách ngẫu nhiên khác)*\n"
            "• `🎭 Vé Gài Bẫy` — **200 Điểm** *(Ép một người gánh kèo Khó)*\n"
            "• `🕶️ Kính Chiếu Yêu` — **300 Điểm** *(Xem trước 3 thử thách ngẫu nhiên)*\n"
            "• `👑 Bá Chủ Chiến Trường` — **6666 Điểm** *(👑 Quyền VIP, Miễn nhiễm bẫy)*"
        ), inline=False)
        embed.set_footer(text="Hãy chọn món đồ muốn sở hữu ở thanh chọn bên dưới!")
        
        await interaction.response.send_message(embed=embed, view=ShopView())

async def setup(bot):
    await bot.add_cog(ShopCog(bot))
    bot.add_view(ShopView())