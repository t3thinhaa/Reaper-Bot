import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import datetime, timedelta, timezone

# --- CẤU HÌNH ID ROLE TRÊN SERVER CỦA BẠN ---
ROLE_BA_CHU_ID = 1524827906357067879     # Role Bá Chủ Chiến Trường
ROLE_SIEU_CAP_ID = 1525111749777428550   # Role "Siêu Cấp Báo Thủ" (Vĩnh viễn)
ROLE_MONTH_ID = 1525112555406753812      # Role "Báo Thủ Của Tháng"
ROLE_WEEK_ID = 1525112809032253490       # Role "Báo Thủ Của Tuần"
ROLE_DAY_ID = 1525113028230774876        # Role "Báo Thủ Của Ngày"

# Cấu hình tiền tố biệt danh (Nickname Prefixes)
PREFIX_DAY = "[🎭 Vía Nặng] "
PREFIX_WEEK = "[🌪️ Quả Báo Tới] "
PREFIX_MONTH = "[💀 Họa Thần] "
ALL_PREFIXES = [PREFIX_DAY, PREFIX_WEEK, PREFIX_MONTH, "🔱 ", " (Siêu Báo)"]

def get_vn_time():
    """Hàm lấy thời gian hiện tại theo múi giờ Việt Nam (GMT+7)"""
    return datetime.now(timezone(timedelta(hours=7)))

class IndividualVoteButton(discord.ui.Button):
    def __init__(self, member_id: int, member_name: str, label_index: int):
        super().__init__(
            label=f"Vote #{label_index} ({member_name[:12]})", 
            style=discord.ButtonStyle.danger, 
            custom_id=f"v_btn_{member_id}",
            emoji="💀"
        )
        self.target_id = member_id

    async def callback(self, interaction: discord.Interaction):
        view: ActiveVoteView = self.view
        voter_id = interaction.user.id

        if voter_id in view.votes:
            if view.votes[voter_id] == self.target_id:
                del view.votes[voter_id]
                await interaction.response.send_message("🔄 Bạn đã rút lại phiếu bầu!", ephemeral=True)
            else:
                view.votes[voter_id] = self.target_id
                await interaction.response.send_message("🔄 Bạn đã đổi ý sang bầu cho tội đồ này!", ephemeral=True)
        else:
            view.votes[voter_id] = self.target_id
            await interaction.response.send_message("✅ Đã ghi nhận phiếu bầu ẩn danh của bạn!", ephemeral=True)

        target_member = interaction.guild.get_member(self.target_id) or await interaction.guild.fetch_member(self.target_id)
        if target_member:
            await interaction.channel.send(
                f"📢 **{interaction.user.display_name}** đã bỏ phiếu luận tội cho **{target_member.display_name}**!", 
                delete_after=5
            )
        await view.update_embed(interaction)

class ActiveVoteView(discord.ui.View):
    def __init__(self, targets: list, db, parent_view):
        super().__init__(timeout=180)
        self.targets = targets
        self.db = db
        self.parent_view = parent_view
        self.votes = {}
        self.msg = None

        for idx, (t_id, t_name, _) in enumerate(targets, 1):
            self.add_item(IndividualVoteButton(member_id=t_id, member_name=t_name, label_index=idx))

    async def update_embed(self, interaction: discord.Interaction):
        try:
            vote_counts = {t[0]: 0 for t in self.targets}
            for t_id in self.votes.values():
                if t_id in vote_counts: vote_counts[t_id] += 1

            embed = interaction.message.embeds[0]
            new_desc = "🚨 **DANH SÁCH TỘI ĐỒ ĐANG LÊN THỚT LUẬN TỘI:**\n\n"
            
            for idx, (t_id, _, t_mention) in enumerate(self.targets, 1):
                count = vote_counts[t_id]
                bar = "🟥" * count + "⬛" * (10 - count if count <= 10 else 0)
                new_desc += f"`#{idx}` {t_mention} | Phiếu: `{count}`\n📊 {bar}\n\n"
            
            embed.description = new_desc
            await interaction.message.edit(embed=embed, view=self)
        except Exception as e:
            print(f"[BaoThu] Lỗi cập nhật Embed: {e}")

    @discord.ui.button(label="🔨 Chốt Sổ Phiên Tòa", style=discord.ButtonStyle.success, custom_id="admin_chot_so_btn", row=1)
    async def admin_chot_so(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Chỉ Quản trị viên mới được chốt sổ sớm!", ephemeral=True)
            return
        await interaction.response.defer()
        self.stop()
        await self.process_results()

    async def on_timeout(self):
        await self.process_results()

    async def process_results(self):
        try:
            for item in self.children: item.disabled = True
            if not self.msg: return

            vote_counts = {t[0]: 0 for t in self.targets}
            for t_id in self.votes.values():
                if t_id in vote_counts: vote_counts[t_id] += 1

            max_votes = max(vote_counts.values()) if vote_counts else 0
            if max_votes == 0:
                embed = discord.Embed(title="⚖️ PHIÊN TÒA HUỶ BỎ", description="Không có ai tham gia bỏ phiếu, phiên tòa kết thúc vô hiệu!", color=discord.Color.gray())
                await self.msg.edit(embed=embed, view=self.parent_view)
                return

            winners = [k for k, v in vote_counts.items() if v == max_votes]
            result_text = "🔨 **KẾT QUẢ PHIÊN TÒA - ĐÃ BAN PHÁN QUYẾT LẬP TỨC:**\n\n"

            guild = self.msg.guild
            ba_chu_role = guild.get_role(ROLE_BA_CHU_ID)
            day_role = guild.get_role(ROLE_DAY_ID)

            for w_id in winners:
                member = guild.get_member(w_id) or await guild.fetch_member(w_id)
                if member:
                    try:
                        # 1. Cập nhật cơ sở dữ liệu MongoDB
                        await self.db.users_points.update_one(
                            {"user_id": str(w_id)},
                            {"$inc": {"bao_day": 1, "bao_week": 1, "bao_month": 1}},
                            upsert=True
                        )
                        result_text += f"💥 {member.mention} gánh trọn `{max_votes}` phiếu phạt! Nhận `+1 Điểm Báo`.\n"
                        
                        # 2. 🔥 THỰC THI PHÁN QUYẾT NGAY LẬP TỨC: Trao role Ngày & Sửa biệt danh
                        if day_role:
                            await member.add_roles(day_role)
                        
                        has_ba_chu = ba_chu_role in member.roles if ba_chu_role else False
                        if not has_ba_chu:
                            # Dọn sạch các tiền tố cũ trước khi áp tiền tố mới
                            clean_name = member.display_name
                            for p in ALL_PREFIXES:
                                clean_name = clean_name.replace(p, "")
                            await member.edit(nick=f"{PREFIX_DAY}{clean_name[:20]}")
                            result_text += f"➡️ Đã áp chế biệt danh: `{PREFIX_DAY}{clean_name[:20]}`\n\n"

                    except Exception as err:
                        print(f"[BaoThu] Lỗi thực thi phán quyết cho {w_id}: {err}")

            embed = discord.Embed(title="🔨 PHIÊN TÒA KHÉP LẠI - THI HÀNH ÁN THÀNH CÔNG", description=result_text, color=discord.Color.dark_purple())
            await self.msg.edit(embed=embed, view=self.parent_view)
        except Exception as e:
            print(f"[BaoThu] Lỗi xử lý kết quả: {e}")


class CustomStringSelect(discord.ui.Select):
    def __init__(self, options, db):
        super().__init__(
            placeholder="👥 Chọn từ 2 đến 5 thành viên ăn hại tại đây...",
            min_values=2,
            max_values=min(5, len(options)),
            options=options,
            custom_id="custom_bao_thu_select"
        )
        self.db = db

    async def callback(self, interaction: discord.Interaction):
        try:
            guild = interaction.guild
            selected_ids = [int(val) for val in self.values]
            
            valid_targets = []
            embed = discord.Embed(
                title="⚖️ PHIÊN TÒA LUẬN TỘI ĐỒ TRỰC TIẾP",
                description="🚨 **DANH SÁCH CÁC NGHI PHẠM ĐANG LÊN THỚT:**\n\n",
                color=discord.Color.red()
            )
            
            for idx, u_id in enumerate(selected_ids, 1):
                member = guild.get_member(u_id) or await guild.fetch_member(u_id)
                if member:
                    valid_targets.append((member.id, member.display_name, member.mention))
                    embed.description += f"`#{idx}` {member.mention} | Phiếu: `0`\n📊 ⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛\n\n"
            
            embed.set_footer(text="UI 2: Sử dụng các nút bấm tương ứng số thứ tự phía dưới để bỏ phiếu ẩn danh.")
            await interaction.response.send_message(content="⚖️ Khởi tạo danh sách bình chọn thành công!", ephemeral=True)
            
            active_view = ActiveVoteView(targets=valid_targets, db=self.db, parent_view=self.view)
            await interaction.message.edit(embed=embed, view=active_view)
            active_view.msg = interaction.message
        except Exception as e:
            print(f"[BaoThu] Lỗi tại callback chọn thành viên: {e}")


class SetupBaoThuView(discord.ui.View):
    def __init__(self, all_options, db):
        super().__init__(timeout=None)
        self.all_options = all_options
        self.db = db
        self.current_page = 0
        self.per_page = 20
        self.update_components()

    def update_components(self):
        self.clear_items()
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_options = self.all_options[start:end]

        self.add_item(CustomStringSelect(page_options, self.db))

        total_pages = (len(self.all_options) - 1) // self.per_page + 1

        prev_btn = discord.ui.Button(label="◀️ Trang cũ", style=discord.ButtonStyle.secondary, disabled=(self.current_page == 0))
        next_btn = discord.ui.Button(label="Trang sau ▶️", style=discord.ButtonStyle.secondary, disabled=(self.current_page >= total_pages - 1))
        page_indicator = discord.ui.Button(label=f"Trang {self.current_page + 1}/{total_pages}", style=discord.ButtonStyle.secondary, disabled=True)

        async def prev_callback(interaction: discord.Interaction):
            self.current_page -= 1
            self.update_components()
            await interaction.response.edit_message(view=self)

        async def next_callback(interaction: discord.Interaction):
            self.current_page += 1
            self.update_components()
            await interaction.response.edit_message(view=self)

        prev_btn.callback = prev_callback
        next_btn.callback = next_callback

        self.add_item(prev_btn)
        self.add_item(page_indicator)
        self.add_item(next_btn)


class BaoThuSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.last_checked_date = None # Đánh dấu ngày đã thực hiện reset tránh chạy lặp
        try:
            self.check_cycles.start()
        except Exception as e:
            print(f"[BaoThu] Lỗi khởi động vòng lặp task: {e}")

    def cog_unload(self):
        self.check_cycles.cancel()

    @app_commands.command(name="setup_vote_bao", description="Tạo bảng cài đặt bầu chọn Báo Thủ cố định (Ẩn danh 100%)")
    async def setup_vote_bao(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Bạn cần có quyền Administrator để thiết lập bảng này!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            guild = interaction.guild
            all_options = []

            async for member in guild.fetch_members(limit=None):
                if member.bot: continue
                has_bot_role = any(r.name.lower() == "bots" for r in member.roles)
                if has_bot_role: continue
                
                # Loại bỏ bớt tiền tố khi hiển thị trong danh sách lựa chọn cho gọn
                clean_label = member.display_name
                for p in ALL_PREFIXES:
                    clean_label = clean_label.replace(p, "")

                all_options.append(discord.SelectOption(
                    label=clean_label[:25],
                    value=str(member.id),
                    description=f"Tên gốc: {member.name[:50]}",
                    emoji="👤"
                ))

            if len(all_options) < 2:
                await interaction.followup.send("❌ Server không có đủ thành viên thực tế để thực hiện thiết lập!", ephemeral=True)
                return

            embed = discord.Embed(
                title="🃏 TRUNG TÂM PHÂN XỬ & ĐÁNH GIÁ BÁO THỦ",
                description="Chào mừng đến với hệ thống đánh giá đồng đội tự động. Hãy chọn từ **2 đến 5 thành viên** ở thanh menu bên dưới để đưa lên đoạn đầu đài luận tội!\n\n*(Sử dụng các nút bấm bên dưới để lật xem trang thành viên tiếp theo)*",
                color=discord.Color.from_rgb(35, 35, 35)
            )
            embed.set_footer(text="Hệ thống tự động hóa 100% - Bảo mật danh tính người gọi lệnh.")

            await interaction.channel.send(embed=embed, view=SetupBaoThuView(all_options, self.db))
            await interaction.followup.send("✅ Hệ thống phân trang đã nạp toàn bộ thành viên thành công!", ephemeral=True)

        except Exception as e:
            print(f"[BaoThu] Lỗi nghiêm trọng tại lệnh setup: {e}")
            await interaction.followup.send(f"❌ Đã có lỗi xảy ra trong quá trình đồng bộ: {e}", ephemeral=True)

    @app_commands.command(name="bxh_baothu", description="Xem Bảng Xếp Hạng tội đồ (Ngày / Tuần / Tháng)")
    @app_commands.choices(loai=[
        app_commands.Choice(name="Bảng xếp hạng NGÀY", value="day"),
        app_commands.Choice(name="Bảng xếp hạng TUẦN", value="week"),
        app_commands.Choice(name="Bảng xếp hạng THÁNG", value="month"),
        app_commands.Choice(name="Điện Thờ SIÊU CẤP BÁO THỦ (Vĩnh viễn)", value="legend")
    ])
    async def bxh_baothu(self, interaction: discord.Interaction, loai: str):
        try:
            if loai == "legend":
                legends = await self.db.users_points.find({"is_sieu_cap": True}).to_list(length=20)
                embed = discord.Embed(title="🏆 ĐIỆN THỜ SIÊU CẤP BÁO THỦ ĐẠI LỤC 🏆", description="*Những huyền thoại ăn hại găm tên vĩnh viễn vào lịch sử Server*\n\n", color=discord.Color.gold())
                if not legends:
                    embed.description += "🕊️ Chưa có ai đủ trình độ lọt vào Điện Thờ!"
                for i, u in enumerate(legends):
                    embed.description += f"`#{i+1}` <@{u['user_id']}> — Ngày Đăng Quang: `{u.get('time_archive', 'Không rõ')}`\n"
                await interaction.response.send_message(embed=embed)
                return

            db_field = f"bao_{loai}"
            title_map = {"day": "NGÀY", "week": "TUẦN", "month": "THÁNG"}
            top_list = await self.db.users_points.find({db_field: {"$gt": 0}}).sort(db_field, -1).limit(10).to_list(length=10)
            
            embed = discord.Embed(title=f"🃏 TOP 10 BÁO THỦ CỦA {title_map[loai]} 🃏", color=discord.Color.dark_orange())
            bxh_text = ""
            for idx, u_data in enumerate(top_list):
                score = u_data.get(db_field, 0)
                bxh_text += f"`#{idx+1}` <@{u_data['user_id']}> — `{score}` Điểm Báo\n"
            
            embed.description = bxh_text if bxh_text else "🕊️ Hiện tại chưa có dữ liệu ghi nhận chu kỳ này."
            await interaction.response.send_message(embed=embed)
        except Exception as e:
            await interaction.response.send_message(f"❌ Đã xảy ra lỗi khi tải BXH: {e}", ephemeral=True)

    @app_commands.command(name="clear_baothu_nicks", description="[Admin] Dọn dẹp sạch các biệt danh báo thủ bị dính lỗi trên Server")
    async def clear_baothu_nicks(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Bạn cần có quyền Administrator để dùng lệnh này!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        count = 0

        async for member in guild.fetch_members(limit=None):
            if member.display_name:
                has_prefix = any(member.display_name.startswith(p) for p in [PREFIX_DAY, PREFIX_WEEK, PREFIX_MONTH])
                if has_prefix:
                    new_nick = member.display_name
                    for p in ALL_PREFIXES:
                        new_nick = new_nick.replace(p, "")
                    try:
                        await member.edit(nick=None if new_nick == member.name else new_nick)
                        count += 1
                    except: pass

        await interaction.followup.send(f"✅ Đã giải trừ biệt danh lỗi thành công cho `{count}` thành viên!", ephemeral=True)


    @tasks.loop(minutes=5)
    async def check_cycles(self):
        """Vòng lặp chạy mỗi 5 phút để check mốc 5:00 sáng VN (GMT+7) thực hiện dọn dẹp và trao giải Tuần/Tháng"""
        try:
            now_vn = get_vn_time()
            current_date_str = now_vn.strftime("%Y-%m-%d")

            # Chỉ thực hiện xử lý nếu đã bước sang mốc 5 giờ sáng và chưa chạy cho ngày hôm nay
            if now_vn.hour == 5 and self.last_checked_date != current_date_str:
                print(f"[BaoThu] Đang thực hiện xử lý reset chu kỳ tự động lúc 5h sáng ngày {current_date_str}...")
                
                guilds = self.bot.guilds
                for guild in guilds:
                    # 1. 🔥 QUAN TRỌNG: Tự động gỡ sạch Nickname lỗi/cũ và thu hồi role Ngày hôm trước trước khi chạy chu kỳ mới
                    await self.clear_all_day_titles(guild)

                    # 2. Xử lý phong danh hiệu Tuần (Nếu là sáng Thứ Hai lúc 5h)
                    if now_vn.weekday() == 0: 
                        await self.reward_top_role(guild, "week", ROLE_WEEK_ID, "📅 BÁO THỦ CỦA TUẦN", PREFIX_WEEK)

                    # 3. Xử lý phong danh hiệu Tháng (Nếu hôm nay là ngày mùng 1 đầu tháng mới)
                    if now_vn.day == 1:
                        await self.reward_top_role(guild, "month", ROLE_MONTH_ID, "💀 HỌA THẦN CỦA THÁNG", PREFIX_MONTH)
                        await self.process_sieu_cap_bao_thu(guild)

                # Đánh dấu đã hoàn thành dọn dẹp ngày hôm nay
                self.last_checked_date = current_date_str
        except Exception as loop_err:
            print(f"[BaoThu] Lỗi vòng lặp đồng bộ chu kỳ: {loop_err}")

    async def clear_all_day_titles(self, guild):
        """Hàm quét dọn dẹp thu hồi biệt danh và gỡ role Ngày khi hết hạn vào 5h sáng"""
        day_role = guild.get_role(ROLE_DAY_ID)
        if day_role:
            for member in day_role.members:
                try:
                    await member.remove_roles(day_role)
                    # Hoàn tác biệt danh sạch
                    new_nick = member.display_name
                    for p in ALL_PREFIXES:
                        new_nick = new_nick.replace(p, "")
                    await member.edit(nick=None if new_nick == member.name else new_nick)
                except: pass
        # Sau khi dọn dẹp xong xuôi, xoá trắng bảng điểm NGÀY trong Database về 0
        await self.db.users_points.update_many({}, {"$set": {"bao_day": 0}})

    async def reward_top_role(self, guild, mode: str, role_id: int, role_title: str, prefix_string: str):
        """Hàm vinh danh trao giải cho chu kỳ lớn (Tuần / Tháng)"""
        try:
            role = guild.get_role(role_id)
            if not role: return

            db_field = f"bao_{mode}"
            top_user = await self.db.users_points.find().sort(db_field, -1).limit(1).to_list(length=1)
            if not top_user or top_user[0].get(db_field, 0) == 0: 
                # Nếu chu kỳ này không ai có điểm, xoá trắng data chu kỳ lớn cũ về 0 và kết thúc
                await self.db.users_points.update_many({}, {"$set": {db_field: 0}})
                return

            top_id = int(top_user[0]["user_id"])

            # Gỡ bỏ role chu kỳ cũ của những người trước đó dính giải
            for m in role.members:
                if m.id != top_id:
                    try:
                        await m.remove_roles(role)
                        new_nick = m.display_name.replace(prefix_string, "")
                        await m.edit(nick=None if new_nick == m.name else new_nick)
                    except: pass

            # Trao giải phong tước hiệu cho người thắng cuộc mới
            winner = guild.get_member(top_id) or await guild.fetch_member(top_id)
            if winner:
                ba_chu_role = guild.get_role(ROLE_BA_CHU_ID)
                has_ba_chu = ba_chu_role in winner.roles if ba_chu_role else False

                try:
                    await winner.add_roles(role)
                    if not has_ba_chu:
                        clean_name = winner.display_name
                        for p in ALL_PREFIXES:
                            clean_name = clean_name.replace(p, "")
                        await winner.edit(nick=f"{prefix_string}{clean_name[:20]}")
                    
                    channel = guild.system_channel
                    if channel:
                        await channel.send(f"🚨 **PHONG THẦN ĐẢO CHÍNH (5H SÁNG):** Kính cẩn nghiêng mình trước {winner.mention}, hung thần vừa chính thức sở hữu danh hiệu long trời lở đất **{role_title}**!")
                except: pass

            # Xoá trắng bảng điểm của chu kỳ này về 0 để chuẩn bị vòng đua mới
            await self.db.users_points.update_many({}, {"$set": {db_field: 0}})
        except Exception as e:
            print(f"[BaoThu] Lỗi xử lý trao role chu kỳ {mode}: {e}")

    async def process_sieu_cap_bao_thu(self, guild):
        """Hàm đẩy người đứng top tháng vào Điện thờ vĩnh viễn"""
        try:
            top_user = await self.db.users_points.find().sort("bao_month", -1).limit(1).to_list(length=1)
            if not top_user or top_user[0].get("bao_month", 0) == 0: return

            user_id = top_user[0]["user_id"]
            role_sieu_cap = guild.get_role(ROLE_SIEU_CAP_ID)
            
            current_date_str = get_vn_time().strftime("%d/%m/%Y")
            await self.db.users_points.update_one(
                {"user_id": user_id},
                {"$set": {"is_sieu_cap": True, "time_archive": current_date_str}}
            )

            member = guild.get_member(int(user_id)) or await guild.fetch_member(int(user_id))
            if member and role_sieu_cap:
                ba_chu_role = guild.get_role(ROLE_BA_CHU_ID)
                has_ba_chu = ba_chu_role in member.roles if ba_chu_role else False
                
                try:
                    await member.add_roles(role_sieu_cap)
                    if not has_ba_chu:
                        pure_name = member.display_name
                        for p in ALL_PREFIXES:
                            pure_name = pure_name.replace(p, "")
                        await member.edit(nick=f"🔱 {pure_name[:18]} (Siêu Báo)")
                except: pass
        except Exception as e:
            print(f"[BaoThu] Lỗi xử lý Siêu Cấp Báo Thủ vĩnh viễn: {e}")


async def setup(bot):
    await bot.add_cog(BaoThuSystem(bot))