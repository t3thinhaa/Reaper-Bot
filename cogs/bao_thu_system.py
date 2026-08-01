import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
from datetime import datetime, timedelta, timezone

# Múi giờ VN
def get_vn_time():
    return datetime.now(timezone(timedelta(hours=7)))

# Prefix Nickname
PREFIX_DAY = "[🎭 Vía Nặng] "
PREFIX_WEEK = "[🌪️ Quả Báo Tới] "
PREFIX_MONTH = "[💀 Họa Thần] "
ALL_PREFIXES = [PREFIX_DAY, PREFIX_WEEK, PREFIX_MONTH, "🔱 ", " (Ách Vương Đế Tôn)"]

class IndividualVoteButton(discord.ui.Button):
    def __init__(self, member_id: int, member_name: str, label_index: int):
        super().__init__(
            label=f"Vote #{label_index} ({member_name[:10]})", 
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
                f"📢 Một ai đó đã bỏ phiếu luận tội cho **{target_member.display_name}**!", 
                delete_after=4
            )
        await view.update_embed(interaction)


class ActiveVoteView(discord.ui.View):
    def __init__(self, targets: list, db, parent_view, cog_ref):
        super().__init__(timeout=300) # Tăng lên 5 phút
        self.targets = targets
        self.db = db
        self.parent_view = parent_view
        self.cog_ref = cog_ref
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
                bar = "🟥" * count + "⬛" * max(0, (10 - count))
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
            roles_cfg = await self.cog_ref.get_guild_roles(guild.id)
            day_role = guild.get_role(roles_cfg.get("day"))
            ba_chu_role = guild.get_role(roles_cfg.get("ba_chu"))

            for w_id in winners:
                member = guild.get_member(w_id) or await guild.fetch_member(w_id)
                if member:
                    try:
                        await self.db.users_points.update_one(
                            {"user_id": str(w_id), "guild_id": str(guild.id)},
                            {"$inc": {"bao_day": 1, "bao_week": 1, "bao_month": 1}},
                            upsert=True
                        )
                        result_text += f"💥 {member.mention} gánh trọn `{max_votes}` phiếu phạt! Nhận `+1 Điểm Báo`.\n"
                        
                        if day_role:
                            await member.add_roles(day_role)
                        
                        has_ba_chu = ba_chu_role in member.roles if ba_chu_role else False
                        if not has_ba_chu:
                            clean_name = member.display_name
                            for p in ALL_PREFIXES: clean_name = clean_name.replace(p, "")
                            new_nick = f"{PREFIX_DAY}{clean_name.strip()}"[:32]
                            await member.edit(nick=new_nick)
                            result_text += f"➡️ Đã áp chế biệt danh: `{new_nick}`\n\n"

                    except Exception as err:
                        print(f"[BaoThu] Lỗi thi hành phán quyết cho {w_id}: {err}")

            embed = discord.Embed(title="🔨 PHIÊN TÒA KHÉP LẠI - THI HÀNH ÁN THÀNH CÔNG", description=result_text, color=discord.Color.dark_purple())
            await self.msg.edit(embed=embed, view=self.parent_view)
        except Exception as e:
            print(f"[BaoThu] Lỗi xử lý kết quả: {e}")


class CustomStringSelect(discord.ui.Select):
    def __init__(self, options, db, parent_view):
        super().__init__(
            placeholder="👥 Chọn các thành viên ăn hại tại trang này...",
            min_values=1,
            max_values=len(options),
            options=options,
            custom_id="custom_bao_thu_select"
        )
        self.db = db
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        # Lưu các giá trị được chọn từ trang hiện tại vào bộ nhớ chung của View
        for val in self.values:
            if val not in self.parent_view.selected_user_ids:
                if len(self.parent_view.selected_user_ids) < 5:
                    self.parent_view.selected_user_ids.add(int(val))
                else:
                    await interaction.response.send_message("❌ Bạn chỉ được chọn tối đa 5 người cho 1 phiên tòa!", ephemeral=True)
                    return

        selected_count = len(self.parent_view.selected_user_ids)
        await interaction.response.send_message(
            f"✅ Đã ghi nhận! Hiện tại bạn đã chọn tổng cộng **{selected_count}/5** thành viên. "
            f"(Bấm nút 'Lên Thớt Luận Tội' bên dưới để khởi tạo).", 
            ephemeral=True
        )


class SetupBaoThuView(discord.ui.View):
    def __init__(self, all_options, db, cog_ref):
        super().__init__(timeout=None)
        self.all_options = all_options
        self.db = db
        self.cog_ref = cog_ref
        self.current_page = 0
        self.per_page = 20
        self.selected_user_ids = set() # LƯU TRỮ NGƯỜI ĐƯỢC CHỌN XUYÊN SUỐT TRANG
        self.update_components()

    def update_components(self):
        self.clear_items()
        start = self.current_page * self.per_page
        end = start + self.per_page
        page_options = self.all_options[start:end]

        # Đánh dấu default = True nếu user_id đã từng được chọn trước đó
        for opt in page_options:
            opt.default = int(opt.value) in self.selected_user_ids

        self.add_item(CustomStringSelect(page_options, self.db, parent_view=self))

        total_pages = max(1, (len(self.all_options) - 1) // self.per_page + 1)

        prev_btn = discord.ui.Button(label="◀️ Trang cũ", style=discord.ButtonStyle.secondary, disabled=(self.current_page == 0), row=1)
        next_btn = discord.ui.Button(label="Trang sau ▶️", style=discord.ButtonStyle.secondary, disabled=(self.current_page >= total_pages - 1), row=1)
        page_indicator = discord.ui.Button(label=f"Trang {self.current_page + 1}/{total_pages}", style=discord.ButtonStyle.secondary, disabled=True, row=1)
        
        # Nút xác nhận khởi tạo phiên tòa
        confirm_btn = discord.ui.Button(label="🔥 LÊN THỚT LUẬN TỘI 🔥", style=discord.ButtonStyle.danger, row=2)

        async def prev_callback(interaction: discord.Interaction):
            self.current_page -= 1
            self.update_components()
            await interaction.response.edit_message(view=self)

        async def next_callback(interaction: discord.Interaction):
            self.current_page += 1
            self.update_components()
            await interaction.response.edit_message(view=self)

        async def confirm_callback(interaction: discord.Interaction):
            if len(self.selected_user_ids) < 2:
                await interaction.response.send_message("❌ Bạn phải chọn ít nhất **2 thành viên** mới đủ điều kiện mở phiên tòa!", ephemeral=True)
                return

            guild = interaction.guild
            valid_targets = []
            embed = discord.Embed(
                title="⚖️ PHIÊN TÒA LUẬN TỘI ĐỒ TRỰC TIẾP",
                description="🚨 **DANH SÁCH CÁC NGHI PHẠM ĐANG LÊN THỚT:**\n\n",
                color=discord.Color.red()
            )

            for idx, u_id in enumerate(self.selected_user_ids, 1):
                member = guild.get_member(u_id) or await guild.fetch_member(u_id)
                if member:
                    valid_targets.append((member.id, member.display_name, member.mention))
                    embed.description += f"`#{idx}` {member.mention} | Phiếu: `0`\n📊 ⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛\n\n"

            embed.set_footer(text="Sử dụng các nút bấm tương ứng số thứ tự phía dưới để bỏ phiếu ẩn danh.")
            await interaction.response.send_message("⚖️ Khởi tạo danh sách bình chọn thành công!", ephemeral=True)

            active_view = ActiveVoteView(targets=valid_targets, db=self.db, parent_view=self, cog_ref=self.cog_ref)
            msg = await interaction.channel.send(embed=embed, view=active_view)
            active_view.msg = msg
            
            # Reset danh sách đã chọn cho đợt tạo sau
            self.selected_user_ids.clear()
            self.update_components()

        prev_btn.callback = prev_callback
        next_btn.callback = next_callback
        confirm_btn.callback = confirm_callback

        self.add_item(prev_btn)
        self.add_item(page_indicator)
        self.add_item(next_btn)
        self.add_item(confirm_btn)


class BaoThuSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db = bot.db
        self.last_checked_date = None
        try:
            self.check_cycles.start()
        except Exception as e:
            print(f"[BaoThu] Lỗi khởi động loop: {e}")

    def cog_unload(self):
        self.check_cycles.cancel()

    # --- HÀM BỔ SUNG: LẤY CẤU HÌNH ROLE DỘNG TỪ MONGO ---
    async def get_guild_roles(self, guild_id: int):
        cfg = await self.db.guild_configs.find_one({"guild_id": str(guild_id)})
        if not cfg:
            return {"ba_chu": None, "sieu_cap": None, "month": None, "week": None, "day": None}
        return cfg.get("roles", {})

    # --- LỆNH ADMIN: THIẾT LẬP ROLE ID DỘNG ---
    @app_commands.command(name="config_baothu_roles", description="[Admin] Cấu hình các Role Báo Thủ cho Server")
    async def config_baothu_roles(
        self, interaction: discord.Interaction, 
        role_day: discord.Role, 
        role_week: discord.Role, 
        role_month: discord.Role,
        role_sieu_cap: discord.Role,
        role_ba_chu: discord.Role = None
    ):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Bạn không có quyền!", ephemeral=True)
            return

        roles_payload = {
            "day": role_day.id,
            "week": role_week.id,
            "month": role_month.id,
            "sieu_cap": role_sieu_cap.id,
            "ba_chu": role_ba_chu.id if role_ba_chu else None
        }

        await self.db.guild_configs.update_one(
            {"guild_id": str(interaction.guild_id)},
            {"$set": {"roles": roles_payload}},
            upsert=True
        )
        await interaction.response.send_message("✅ Đã cập nhật thành công toàn bộ ID Role Báo Thủ vào Database!", ephemeral=True)

    # --- LỆNH ADMIN: QUẢN LÝ / CỘNG / TRỪ / XÓA ĐIỂM BÁO THỦ ---
    @app_commands.command(name="manage_points", description="[Admin] Chỉnh sửa điểm Báo Thủ của thành viên")
    @app_commands.choices(thao_tac=[
        app_commands.Choice(name="Cộng điểm (+)", value="add"),
        app_commands.Choice(name="Trừ điểm (-)", value="sub"),
        app_commands.Choice(name="Reset về 0", value="reset")
    ])
    @app_commands.choices(loai=[
        app_commands.Choice(name="Điểm Ngày", value="bao_day"),
        app_commands.Choice(name="Điểm Tuần", value="bao_week"),
        app_commands.Choice(name="Điểm Tháng", value="bao_month")
    ])
    async def manage_points(self, interaction: discord.Interaction, target: discord.Member, thao_tac: str, loai: str, diem: int = 1):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Quyền Administrator là bắt buộc!", ephemeral=True)
            return

        user_filter = {"user_id": str(target.id), "guild_id": str(interaction.guild_id)}

        if thao_tac == "reset":
            await self.db.users_points.update_one(user_filter, {"$set": {loai: 0}}, upsert=True)
            await interaction.response.send_message(f"✅ Đã Reset thành công `{loai}` của {target.mention} về 0!")
        else:
            val = diem if thao_tac == "add" else -diem
            await self.db.users_points.update_one(user_filter, {"$inc": {loai: val}}, upsert=True)
            await interaction.response.send_message(f"✅ Đã điều chỉnh `{loai}` cho {target.mention} số lượng: `{val}` điểm!")

    @app_commands.command(name="setup_vote_bao", description="Tạo bảng cài đặt bầu chọn Báo Thủ cố định (Ẩn danh 100%)")
    async def setup_vote_bao(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Bạn cần có quyền Administrator!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            guild = interaction.guild
            all_options = []

            # Sử dụng guild.members đã cached để chống Timeout API
            for member in guild.members:
                if member.bot: continue
                
                clean_label = member.display_name
                for p in ALL_PREFIXES: clean_label = clean_label.replace(p, "")

                all_options.append(discord.SelectOption(
                    label=clean_label.strip()[:25],
                    value=str(member.id),
                    description=f"Tên gốc: {member.name[:40]}",
                    emoji="👤"
                ))

            if len(all_options) < 2:
                await interaction.followup.send("❌ Server không có đủ thành viên thực tế để thiết lập!", ephemeral=True)
                return

            embed = discord.Embed(
                title="🃏 TRUNG TÂM PHÂN XỬ & ĐÁNH GIÁ BÁO THỦ",
                description="Chọn từ **2 đến 5 thành viên** để đưa lên đoạn đầu đài luận tội!\n\n*(Lật trang thoải mái, hệ thống sẽ tự lưu lại những người bạn đã tích chọn)*",
                color=discord.Color.from_rgb(35, 35, 35)
            )
            embed.set_footer(text="Hệ thống tự động hóa 100% - Bảo mật danh tính người gọi lệnh.")

            await interaction.channel.send(embed=embed, view=SetupBaoThuView(all_options, self.db, cog_ref=self))
            await interaction.followup.send("✅ Khởi tạo hệ thống thành công!", ephemeral=True)

        except Exception as e:
            print(f"[BaoThu] Lỗi setup: {e}")
            await interaction.followup.send(f"❌ Có lỗi xảy ra: {e}", ephemeral=True)

    @app_commands.command(name="pickbaothu", description="[Admin] Chỉ định trực tiếp 1 thành viên làm Báo Thủ")
    @app_commands.choices(loai=[
        app_commands.Choice(name="Báo Thủ Của Ngày", value="day"),
        app_commands.Choice(name="Báo Thủ Của Tuần", value="week"),
        app_commands.Choice(name="Họa Thần Của Tháng", value="month")
    ])
    async def pickbaothu(self, interaction: discord.Interaction, target: discord.Member, loai: str, ly_do: str = "Không có lý do cụ thể"):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Bạn cần quyền Administrator!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        roles_cfg = await self.get_guild_roles(guild.id)

        config_map = {
            "day": {"role_id": roles_cfg.get("day"), "prefix": PREFIX_DAY, "title": "🎭 BÁO THỦ CỦA NGÀY", "color": discord.Color.gold(), "db_field": "bao_day"},
            "week": {"role_id": roles_cfg.get("week"), "prefix": PREFIX_WEEK, "title": "🌪️ BÁO THỦ CỦA TUẦN", "color": discord.Color.orange(), "db_field": "bao_week"},
            "month": {"role_id": roles_cfg.get("month"), "prefix": PREFIX_MONTH, "title": "💀 HỌA THẦN CỦA THÁNG", "color": discord.Color.dark_purple(), "db_field": "bao_month"}
        }

        cfg = config_map[loai]
        role = guild.get_role(cfg["role_id"]) if cfg["role_id"] else None
        ba_chu_role = guild.get_role(roles_cfg.get("ba_chu"))

        try:
            await self.db.users_points.update_one(
                {"user_id": str(target.id), "guild_id": str(guild.id)},
                {"$inc": {cfg["db_field"]: 1}},
                upsert=True
            )

            if role: await target.add_roles(role)

            has_ba_chu = ba_chu_role in target.roles if ba_chu_role else False
            if not has_ba_chu:
                clean_name = target.display_name
                for p in ALL_PREFIXES: clean_name = clean_name.replace(p, "")
                await target.edit(nick=f"{cfg['prefix']}{clean_name.strip()}"[:32])

            embed = discord.Embed(
                title=f"🚨 PHÁN QUYẾT CỦA HỘI ĐỒNG 🚨",
                description=f"Căn cứ theo hành vi, **{target.mention}** bị áp chế phong hiệu **{cfg['title']}**!\n\n📝 **Lý do:** {ly_do}",
                color=cfg["color"]
            )
            embed.set_thumbnail(url=target.display_avatar.url)
            await interaction.channel.send(embed=embed)
            await interaction.followup.send(f"✅ Đã áp chế {target.mention} thành **{cfg['title']}**!", ephemeral=True)

        except Exception as e:
            await interaction.followup.send(f"❌ Xảy ra lỗi: {e}", ephemeral=True)

    @tasks.loop(minutes=5)
    async def check_cycles(self):
        try:
            now_vn = get_vn_time()
            current_date_str = now_vn.strftime("%Y-%m-%d")

            if now_vn.hour == 5 and self.last_checked_date != current_date_str:
                for guild in self.bot.guilds:
                    roles_cfg = await self.get_guild_roles(guild.id)
                    await self.clear_all_day_titles(guild, roles_cfg.get("day"))

                    if now_vn.weekday() == 0: 
                        await self.reward_top_role(guild, "week", roles_cfg.get("week"), "📅 BÁO THỦ CỦA TUẦN", PREFIX_WEEK)

                    if now_vn.day == 1:
                        await self.reward_top_role(guild, "month", roles_cfg.get("month"), "💀 HỌA THẦN CỦA THÁNG", PREFIX_MONTH)
                        await self.process_sieu_cap_bao_thu(guild, roles_cfg.get("sieu_cap"), roles_cfg.get("ba_chu"))

                self.last_checked_date = current_date_str
        except Exception as loop_err:
            print(f"[BaoThu] Lỗi task loop: {loop_err}")

    async def clear_all_day_titles(self, guild, day_role_id):
        if not day_role_id: return
        day_role = guild.get_role(day_role_id)
        if day_role:
            for member in day_role.members:
                try:
                    await member.remove_roles(day_role)
                    new_nick = member.display_name
                    for p in ALL_PREFIXES: new_nick = new_nick.replace(p, "")
                    await member.edit(nick=None if new_nick.strip() == member.name else new_nick.strip())
                except: pass
        await self.db.users_points.update_many({"guild_id": str(guild.id)}, {"$set": {"bao_day": 0}})

    async def reward_top_role(self, guild, mode: str, role_id: int, role_title: str, prefix_string: str):
        if not role_id: return
        role = guild.get_role(role_id)
        if not role: return

        db_field = f"bao_{mode}"
        top_user = await self.db.users_points.find({"guild_id": str(guild.id)}).sort(db_field, -1).limit(1).to_list(length=1)
        if not top_user or top_user[0].get(db_field, 0) == 0: 
            await self.db.users_points.update_many({"guild_id": str(guild.id)}, {"$set": {db_field: 0}})
            return

        top_id = int(top_user[0]["user_id"])
        winner = guild.get_member(top_id) or await guild.fetch_member(top_id)
        
        if winner:
            try:
                await winner.add_roles(role)
                clean_name = winner.display_name
                for p in ALL_PREFIXES: clean_name = clean_name.replace(p, "")
                await winner.edit(nick=f"{prefix_string}{clean_name.strip()}"[:32])
            except: pass

        await self.db.users_points.update_many({"guild_id": str(guild.id)}, {"$set": {db_field: 0}})

    async def process_sieu_cap_bao_thu(self, guild, sieu_cap_role_id, ba_chu_role_id):
        if not sieu_cap_role_id: return
        top_user = await self.db.users_points.find({"guild_id": str(guild.id)}).sort("bao_month", -1).limit(1).to_list(length=1)
        if not top_user or top_user[0].get("bao_month", 0) == 0: return

        user_id = top_user[0]["user_id"]
        role_sieu_cap = guild.get_role(sieu_cap_role_id)
        
        current_date_str = get_vn_time().strftime("%d/%m/%Y")
        await self.db.users_points.update_one(
            {"user_id": user_id, "guild_id": str(guild.id)},
            {"$set": {"is_sieu_cap": True, "time_archive": current_date_str}}
        )

        member = guild.get_member(int(user_id)) or await guild.fetch_member(int(user_id))
        if member and role_sieu_cap:
            try:
                await member.add_roles(role_sieu_cap)
                pure_name = member.display_name
                for p in ALL_PREFIXES: pure_name = pure_name.replace(p, "")
                await member.edit(nick=f"🔱 {pure_name.strip()[:18]} (Siêu Báo)")
            except: pass


async def setup(bot):
    await bot.add_cog(BaoThuSystem(bot))