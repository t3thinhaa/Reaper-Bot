import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from database import get_db_connection

CHALLENGES_FILE = "./data/challenges.json"

def load_challenges_from_file():
    if not os.path.exists(CHALLENGES_FILE):
        return []
    try:
        with open(CHALLENGES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Lỗi cấu trúc file JSON hoặc không đọc được file: {e}")
        return []

class ChallengeControlView(discord.ui.View):
    def __init__(self, current_challenge_idx=0):
        super().__init__(timeout=None)
        self.challenges = load_challenges_from_file()
        self.idx = current_challenge_idx if self.challenges else 0

    def get_current_embed(self):
        if not self.challenges:
            return discord.Embed(
                title="❌ Hệ Thống Trống", 
                description="Kho dữ liệu hiện đang trống hoặc file `challenges.json` bị lỗi định dạng.", 
                color=discord.Color.red()
            )
        
        c = self.challenges[self.idx % len(self.challenges)]
        embed = discord.Embed(
            title=f"⚔️ THỬ THÁCH SINH TỒN: {c.get('title', 'Nhiệm vụ vô danh')}", 
            description=c.get('description', 'Không có mô tả.'), 
            color=discord.Color.purple()
        )
        embed.add_field(name="Độ khó", value=f"🟡 {c.get('difficulty', 'Chưa rõ')}", inline=True)
        embed.add_field(name="🎁 Phần thưởng", value=f"`{c.get('reward', 0)}` Điểm Linh Hồn", inline=True)
        embed.set_footer(text=f"Kho dữ liệu vĩnh cửu: {len(self.challenges)} thử thách độc lạ!")
        
        if os.path.exists("./data/images/ReaperChallenge.png"):
            embed.set_image(url="attachment://ReaperChallenge.png")
        return embed

    @discord.ui.button(label="🎲 Đổi Thử Thách", style=discord.ButtonStyle.secondary, custom_id="btn_next_challenge")
    async def next_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.challenges = load_challenges_from_file()
        if not self.challenges:
            return await interaction.response.send_message("❌ File JSON trống hoặc lỗi cấu trúc!", ephemeral=True)
            
        self.idx += 1
        embed = self.get_current_embed()
        
        if os.path.exists("./data/images/ReaperChallenge.png"):
            file = discord.File("./data/images/ReaperChallenge.png", filename="ReaperChallenge.png")
            await interaction.message.edit(embed=embed, attachments=[file])
        else:
            await interaction.message.edit(embed=embed, attachments=[])
            
        await interaction.response.defer()

    @discord.ui.button(label="✅ Nhận Kèo", style=discord.ButtonStyle.success, custom_id="btn_accept_challenge")
    async def accept_challenge(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.challenges:
            return await interaction.response.send_message("❌ Không có thử thách khả dụng!", ephemeral=True)

        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        c = self.challenges[self.idx % len(self.challenges)]
        title = c.get('title', 'Thử thách ẩn')
        reward = c.get('reward', 0)
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO users_points (user_id, guild_id, user_name, current_challenge, challenge_reward, status)
                VALUES (%s, %s, %s, %s, %s, 'DOING')
                ON CONFLICT (user_id, guild_id) DO UPDATE SET
                    user_name = EXCLUDED.user_name,
                    current_challenge = EXCLUDED.current_challenge,
                    challenge_reward = EXCLUDED.challenge_reward,
                    status = 'DOING';
            ''', (user_id, guild_id, interaction.user.name, title, reward))
            conn.commit()
            cursor.close()
            conn.close()

            await interaction.response.send_message(f"⚔️ Bạn đã nhận thử thách: **{title}**. Hệ thống đã ghi nhận!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi ghi Database: {e}", ephemeral=True)

    @discord.ui.button(label="🏆 Tôi Đã Xong", style=discord.ButtonStyle.primary, custom_id="btn_self_complete")
    async def self_complete(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('SELECT current_challenge, challenge_reward, status FROM users_points WHERE user_id = %s AND guild_id = %s', (user_id, guild_id))
            user_data = cursor.fetchone()

            if not user_data or user_data[2] != "DOING" or user_data[0] == "None":
                cursor.close()
                conn.close()
                return await interaction.response.send_message("❌ Bạn chưa bấm nhận thử thách nào!", ephemeral=True)

            challenge_title = user_data[0]
            reward = user_data[1]

            cursor.execute('''
                UPDATE users_points
                SET status = 'DONE',
                    current_challenge = 'None',
                    challenge_reward = 0,
                    soul_points = soul_points + %s
                WHERE user_id = %s AND guild_id = %s;
            ''', (reward, user_id, guild_id))
            conn.commit()
            cursor.close()
            conn.close()

            await interaction.response.send_message(f"🎉 Hệ thống tự động cộng **`+{reward}`** Điểm Linh Hồn vào ví của bạn!", ephemeral=True)
            await interaction.channel.send(
                f"🔥 **{interaction.user.mention}** đã tự lực hoàn thành thử thách: **{challenge_title}** ➡️ Đút túi `{reward}` điểm!",
                delete_after=7
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Lỗi xử lý Database: {e}", ephemeral=True)

class ChallengeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup_challenge", description="Khởi tạo Bảng Điều Khiển Thử Thách JSON Vĩnh Cửu")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_challenge(self, interaction: discord.Interaction):
        view = ChallengeControlView()
        embed = view.get_current_embed()
        
        await interaction.response.send_message("⚙️ Đang tải lên thử thách", ephemeral=True)
        
        if os.path.exists("./data/images/ReaperChallenge.png"):
            file = discord.File("./data/images/ReaperChallenge.png", filename="ReaperChallenge.png")
            await interaction.channel.send(file=file, embed=embed, view=view)
        else:
            await interaction.channel.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(ChallengeCog(bot))
    bot.add_view(ChallengeControlView())