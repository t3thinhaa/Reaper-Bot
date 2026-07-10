import discord
from discord.ext import commands
from discord import app_commands
import random
import asyncio  # Cần thiết để làm countdown và xóa tin nhắn
from cogs.challenge import load_challenges_from_file

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
        db = interaction.client.db
        if db is None: return

        user_id = str(interaction.user.id)
        user_data = await db.users_points.find_one({"user_id": user_id})
        current_points = user_data.get("soul_points", 0) if user_data else 0

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
            await interaction.response.send_message(f"❌ Khí chất bất thành! Bạn cần có `{cost}` điểm, hiện tại bạn chỉ có `{current_points}` điểm. Hãy làm thêm thử thách!", ephemeral=True)
            return

        # Hàm helper xử lý thông báo tự hủy sau 10 giây (Có đếm ngược)
        async def send_temporary_announcement(embed_content=None, text_content=None):
            # Gửi thông báo ban đầu
            msg = await interaction.channel.send(content=text_content, embed=embed_content)
            # Khởi tạo đếm ngược (Countdown) bằng cách sửa tin nhắn mỗi giây
            for i in range(10, 0, -1):
                suffix = f"\n\n*🟢 Tin nhắn này sẽ tự hủy sau {i} giây...*"
                if embed_content:
                    # Tạo bản sao clone của embed để tránh ghi đè dữ liệu gốc
                    new_embed = embed_content.to_dict()
                    new_embed['description'] = embed_content.description + suffix
                    await msg.edit(embed=discord.Embed.from_dict(new_embed))
                else:
                    await msg.edit(content=text_content + suffix)
                await asyncio.sleep(1)
            # Tiến hành xóa sau khi hết 10 giây
            try:
                await msg.delete()
            except discord.NotFound:
                pass

        # ==========================================
        # LOGIC 1: THẺ MIỄN TỬ
        # ==========================================
        if selected_item == "item_disregard":
            status = user_data.get("status", "Chưa nhận") if user_data else "Chưa nhận"
            if status != "DOING":
                await interaction.response.send_message("❌ Bạn hiện tại đâu có thực hiện thử thách nào dở dang đâu!", ephemeral=True)
                return
            
            await db.users_points.update_one(
                {"user_id": user_id},
                {"$inc": {"soul_points": -cost}, "$set": {"status": "DONE", "current_challenge": "None", "challenge_reward": 0}}
            )
            await interaction.response.send_message("🛡️ Bạn đã sử dụng **Thẻ Miễn Tử** thành công!", ephemeral=True)
            
            # Kích hoạt thông báo tự hủy
            await send_temporary_announcement(text_content=f"💨 **{interaction.user.mention}** đã tiêu hao `100` Điểm Linh Hồn để kích hoạt **Thẻ Miễn Tử**, xóa sổ kèo đang làm dở thành công!")
            return

        # ==========================================
        # LOGIC 2: VÉ GÀI BẪY
        # ==========================================
        elif selected_item == "item_trap":
            all_members = [m for m in interaction.guild.members if not m.bot and m.id != interaction.user.id]
            all_members = [m for m in all_members if not any(r.id == BA_CHU_ROLE_ID for r in m.roles)]

            if not all_members:
                await interaction.response.send_message("❌ Server không có ai hợp lệ để gài bẫy!", ephemeral=True)
                return
            
            victim = random.choice(all_members)
            victim_id = str(victim.id)
            
            victim_data = await db.users_points.find_one({"user_id": victim_id})
            if victim_data and victim_data.get("status") == "DOING":
                await interaction.response.send_message(f"❌ Gài bẫy thất bại! Thần may mắn đã mỉm cười với {victim.name}.", ephemeral=True)
                return

            try:
                all_challenges = load_challenges_from_file()
                hard_challenges = [c for c in all_challenges if "Khó" in c['difficulty']]
                chosen_challenge = random.choice(hard_challenges) if hard_challenges else random.choice(all_challenges)
            except Exception:
                await interaction.response.send_message("❌ Hệ thống file thử thách gặp lỗi!", ephemeral=True)
                return

            await db.users_points.update_one({"user_id": user_id}, {"$inc": {"soul_points": -cost}})
            await db.users_points.update_one(
                {"user_id": victim_id},
                {"$set": {"user_name": victim.name, "current_challenge": chosen_challenge['title'], "challenge_reward": chosen_challenge['reward'], "status": "DOING"}},
                upsert=True
            )
            
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
        # ĐỀ XUẤT THÊM 1: VÉ ĐỔI VẬN (REROLL CHALLENGE)
        # ==========================================
        elif selected_item == "item_reroll":
            status = user_data.get("status", "Chưa nhận") if user_data else "Chưa nhận"
            if status != "DOING":
                await interaction.response.send_message("❌ Bạn phải đang làm một thử thách nào đó thì mới đổi được chứ!", ephemeral=True)
                return
            
            try:
                all_challenges = load_challenges_from_file()
                # Tìm thử thách mới ngẫu nhiên khác thử thách hiện tại
                available = [c for c in all_challenges if c['title'] != user_data.get("current_challenge")]
                new_challenge = random.choice(available)
            except Exception:
                await interaction.response.send_message("❌ Hệ thống file gặp lỗi!", ephemeral=True)
                return

            await db.users_points.update_one(
                {"user_id": user_id},
                {"$inc": {"soul_points": -cost}, "$set": {"current_challenge": new_challenge['title'], "challenge_reward": new_challenge['reward']}}
            )
            
            await interaction.response.send_message("🎲 Đã đổi vận thành công!", ephemeral=True)
            reroll_embed = discord.Embed(title="🎲 ĐỔI VẬN THÀNH CÔNG", color=discord.Color.purple())
            reroll_embed.description = f"🔄 **{interaction.user.mention}** đã đổi thử thách sang: **{new_challenge['title']}** (Thưởng: `{new_challenge['reward']}` điểm)"
            await send_temporary_announcement(embed_content=reroll_embed)
            return

        # ==========================================
        # ĐỀ XUẤT THÊM 2: KÍNH CHIẾU YÊU (XEM TRƯỚC FILE)
        # ==========================================
        elif selected_item == "item_reveal":
            try:
                all_challenges = load_challenges_from_file()
                preview_challenges = random.sample(all_challenges, min(3, len(all_challenges)))
                preview_text = "\n".join([f"• **{c['title']}** ({c['difficulty']}) - Thưởng: {c['reward']}" for c in preview_challenges])
            except Exception:
                await interaction.response.send_message("❌ Không thể đọc danh sách thử thách!", ephemeral=True)
                return

            await db.users_points.update_one({"user_id": user_id}, {"$inc": {"soul_points": -cost}})
            
            # Gửi tin nhắn ẩn (Ephemeral) riêng cho người mua để họ xem lén, không ai thấy được
            await interaction.response.send_message(f"🕶️ **Kính Chiếu Yêu hé lộ 3 thử thách ngẫu nhiên trong kho:**\n{preview_text}\n*(Tin nhắn này chỉ một mình bạn nhìn thấy)*", ephemeral=True)
            
            # Gửi thông báo công khai cho server biết có người hack map (tự xóa sau 10s)
            await send_temporary_announcement(text_content=f"🕶️ **{interaction.user.mention}** vừa mua **Kính Chiếu Yêu** để xem trước thiên cơ (kho thử thách)!")
            return

        # ==========================================
        # LOGIC 3: BÁ CHỦ CHIẾN TRƯỜNG
        # ==========================================
        elif selected_item == "item_bachu":
            role = interaction.guild.get_role(BA_CHU_ROLE_ID)
            if role in interaction.user.roles:
                await interaction.response.send_message("❌ Bạn đã đạt danh hiệu **Bá Chủ Chiến Trường** rồi!", ephemeral=True)
                return

            if role is None:
                await interaction.response.send_message("❌ Không tìm thấy Role mang ID này trên Server.", ephemeral=True)
                return

            try:
                await db.users_points.update_one({"user_id": user_id}, {"$inc": {"soul_points": -cost}})
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
                
                # Lưu ý: Thông báo Vua mới này giữ nguyên (không cho tự xóa) vì đây là sự kiện chấn động Server!
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
        # SỬA ĐỔI: Sử dụng interaction.response.send_message thông thường thay vì gán tên user 
        # Hệ thống View này sẽ nằm cố định tại Channel đó mãi mãi (persistent), không hiện ai gọi ra.
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
        
        # Gửi thẳng vào kênh chat (Tồn tại vĩnh viễn)
        await interaction.response.send_message(embed=embed, view=ShopView())

async def setup(bot):
    await bot.add_cog(ShopCog(bot))
    bot.add_view(ShopView())