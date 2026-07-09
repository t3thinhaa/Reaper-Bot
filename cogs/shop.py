import discord
from discord.ext import commands
from discord import app_commands
import random
from cogs.challenge import load_challenges_from_file

# Đặt ID của Role "Bá Chủ Chiến Trường" ở đây để Bot biết đường mà add
# Bạn tạo Role trên Server xong, click chuột phải vào Role đó chọn "Copy Role ID" rồi dán thay thế vào số dưới đây nhé!
BA_CHU_ROLE_ID = 1524827906357067879  # <--- THAY ID ROLE CỦA BẠN VÀO ĐÂY

class ShopDropdown(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="🛡️ Thẻ Miễn Tử (100 điểm)", value="item_disregard", description="Hủy ngay thử thách đang làm dở mà không bị phạt"),
            discord.SelectOption(label="🎭 Vé Gài Bẫy (200 điểm)", value="item_trap", description="Ép một đồng đội ngẫu nhiên phải nhận kèo Khó"),
            discord.SelectOption(label="👑 Danh Hiệu Bá Chủ Chiến Trường (6666 điểm)", value="item_bachu", description="Danh hiệu tối thượng: Thống trị BXH, sở hữu đặc quyền VIP")
        ]
        super().__init__(placeholder="Chọn vật phẩm muốn quy đổi từ Linh Hồn...", options=options, custom_id="reaper_shop_select")

    async def callback(self, interaction: discord.Interaction):
        db = interaction.client.db
        if db is None: return

        user_id = str(interaction.user.id)
        user_data = await db.users_points.find_one({"user_id": user_id})
        current_points = user_data.get("soul_points", 0) if user_data else 0

        # Cập nhật lại bảng giá Chợ Đen: Món số 3 lên giá 6666 oán khí
        prices = {"item_disregard": 100, "item_trap": 200, "item_bachu": 6666}
        item_names = {"item_disregard": "🛡️ Thẻ Miễn Tử", "item_trap": "🎭 Vé Gài Bẫy", "item_bachu": "👑 Danh Hiệu Bá Chủ Chiến Trường"}
        
        selected_item = self.values[0]
        cost = prices[selected_item]

        # 1. Kiểm tra số dư ví linh hồn
        if current_points < cost:
            await interaction.response.send_message(f"❌ Khí chất bất thành! Bạn cần có `{cost}` điểm, hiện tại bạn chỉ có `{current_points}` điểm linh hồn. Hãy làm thêm thử thách!", ephemeral=True)
            return

        # ==========================================
        # LOGIC 1: THẺ MIỄN TỬ (TỰ ĐỘNG HỦY KÈO)
        # ==========================================
        if selected_item == "item_disregard":
            status = user_data.get("status", "Chưa nhận") if user_data else "Chưa nhận"
            if status != "DOING":
                await interaction.response.send_message("❌ Bạn hiện tại đâu có thực hiện thử thách nào dở dang đâu mà cần dùng Thẻ Miễn Tử!", ephemeral=True)
                return
            
            await db.users_points.update_one(
                {"user_id": user_id},
                {
                    "$inc": {"soul_points": -cost},
                    "$set": {"status": "DONE", "current_challenge": "None", "challenge_reward": 0}
                }
            )
            await interaction.response.send_message("🛡️ Bạn đã sử dụng **Thẻ Miễn Tử** thành công! Thử thách cũ đã bị xóa sổ.", ephemeral=True)
            await interaction.channel.send(f"💨 **{interaction.user.mention}** đã tiêu hao `100` Điểm Linh Hồn để kích hoạt **Thẻ Miễn Tử**, xóa sổ kèo đang làm dở thành công!")
            return

        # ==========================================
        # LOGIC 2: VÉ GÀI BẪY (TỰ ĐỘNG DÍ KÈO)
        # ==========================================
        elif selected_item == "item_trap":
            all_members = [m for m in interaction.guild.members if not m.bot and m.id != interaction.user.id]
            
            # --- ĐẶC QUYỀN BÁ CHỦ: Nếu người đó có Role Bá Chủ, Bot sẽ lọc loại bỏ luôn không cho làm nạn nhân ---
            all_members = [m for m in all_members if not any(r.id == BA_CHU_ROLE_ID for r in m.roles)]

            if not all_members:
                await interaction.response.send_message("❌ Server không có ai hợp lệ (hoặc những người khác đều là Bá Chủ) để gài bẫy!", ephemeral=True)
                return
            
            victim = random.choice(all_members)
            victim_id = str(victim.id)
            
            victim_data = await db.users_points.find_one({"user_id": victim_id})
            if victim_data and victim_data.get("status") == "DOING":
                await interaction.response.send_message(f"❌ Gài bẫy thất bại! Thần may mắn đã mỉm cười với {victim.name} vì người này đang bận làm việc khác.", ephemeral=True)
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
                {
                    "$set": {
                        "user_name": victim.name,
                        "current_challenge": chosen_challenge['title'],
                        "challenge_reward": chosen_challenge['reward'],
                        "status": "DOING"
                    }
                },
                upsert=True
            )
            
            await interaction.response.send_message(f"🎭 Đã kích hoạt Vé Gài Bẫy thành công! `-200` điểm.", ephemeral=True)
            
            trap_embed = discord.Embed(title="🎭 ỐI DỒI ÔI! CÓ KẺ GÀI BẪY!", color=discord.Color.red())
            trap_embed.description = (
                f"👤 Kẻ thủ ác **{interaction.user.mention}** đã bỏ ra `200` điểm mua **Vé Gài Bẫy**!\n\n"
                f"🎯 Nạn nhân xấu số bị oán khí chọn trúng là: {victim.mention}\n"
                f"⚔️ Thử thách bị ép nhận: **{chosen_challenge['title']}**\n"
                f"📝 Mô tả: *{chosen_challenge['description']}*\n"
                f"🎁 Làm xong được nhận: `{chosen_challenge['reward']}` điểm."
            )
            await interaction.channel.send(embed=trap_embed)
            return

        # ==========================================
        # LOGIC 3: BÁ CHỦ CHIẾN TRƯỜNG (TỰ ĐỘNG CẤP ROLE VÀ ĐỔI TÊN)
        # ==========================================
        elif selected_item == "item_bachu":
            # Kiểm tra xem ông này đã là Bá Chủ từ trước chưa, tránh việc mua trùng phí tiền
            role = interaction.guild.get_role(BA_CHU_ROLE_ID)
            if role in interaction.user.roles:
                await interaction.response.send_message("❌ Bạn đã đạt danh hiệu **Bá Chủ Chiến Trường** từ trước rồi, không cần mua lại đâu!", ephemeral=True)
                return

            if role is None:
                await interaction.response.send_message("❌ Lỗi cấu hình hệ thống: Không tìm thấy Role mang ID này trên Server. Hãy báo Admin kiểm tra code!", ephemeral=True)
                return

            try:
                # 1. Trừ điểm trên MongoDB đám mây luôn
                await db.users_points.update_one({"user_id": user_id}, {"$inc": {"soul_points": -cost}})

                # 2. Bot tự động trao quyền/add Role trực tiếp cho người mua
                await interaction.user.add_roles(role)

                # 3. Thêm hiệu ứng đổi biệt danh cho chất chơi (Ví dụ: Thêm ký tự 🔥 vào trước tên)
                try:
                    new_nick = f"🔥 {interaction.user.display_name}"
                    if len(new_nick) <= 32: # Giới hạn ký tự tên của Discord là 32
                        await interaction.user.edit(nick=new_nick)
                except Exception:
                    # Nếu bot không đủ quyền đổi biệt danh (ví dụ người mua là Server Owner) thì bỏ qua bước đổi tên này
                    pass

                # Phản hồi thành công mỹ mãn cho người mua
                await interaction.response.send_message("👑 Bạn đã bước lên đỉnh vinh quang! Danh hiệu **Bá Chủ Chiến Trường** đã được kích hoạt trực tiếp cho bạn!", ephemeral=True)

                # Bắn thông báo chấn động toàn Server
                announce_embed = discord.Embed(title="⚡ TIẾNG THÉT CỦA VỊ VUA MỚI! ⚡", color=discord.Color.gold())
                announce_embed.description = (
                    f"🎉 Toàn bộ thành viên hãy quỳ xuống trước sự xuất hiện của **Bá Chủ Chiến Trường** mới!\n\n"
                    f"🔥 **{interaction.user.mention}** đã chính thức tiêu hao vô lượng oán khí tương đương **`6,666` Điểm Linh Hồn** để đoạt lấy ngai vàng độc quyền!\n\n"
                    f"✨ *Từ nay, vị vua này sở hữu mọi đặc quyền tối thượng, miễn nhiễm hoàn toàn với mọi cạm bẫy Chợ Đen!*"
                )
                announce_embed.set_thumbnail(url=interaction.user.display_avatar.url)
                await interaction.channel.send(embed=announce_embed)

            except discord.Forbidden:
                await interaction.response.send_message("❌ Bot không có đủ quyền hạn để trao Role. Admin hãy kéo Role của Bot lên vị trí cao hơn Role Bá Chủ nhé!", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ Đã xảy ra lỗi không xác định: {e}", ephemeral=True)
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
            "• `🛡️ Thẻ Miễn Tử` — **100 Điểm** *(Tự động hủy kèo đang làm dở)*\n"
            "• `🎭 Vé Gài Bẫy` — **200 Điểm** *(Ép ngẫu nhiên một đứa gánh kèo Khó)*\n"
            "• `👑 Bá Chủ Chiến Trường` — **6666 Điểm** *(Đạt danh hiệu Vua, tự động cấp Role VIP, miễn nhiễm cạm bẫy)*"
        ), inline=False)
        embed.set_footer(text="Hãy chọn món đồ muốn sở hữu ở thanh chọn bên dưới!")
        
        await interaction.response.send_message(embed=embed, view=ShopView())

async def setup(bot):
    await bot.add_cog(ShopCog(bot))
    bot.add_view(ShopView())