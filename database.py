import os
import psycopg2
from psycopg2.extras import RealDictCursor

# External URL mặc định cho Local Dev
DEFAULT_LOCAL_URL = "postgresql://reaper_db_avmf_user:vNlx5ompEuSfkbUcoSeIFJxjuGqLnhLr@dpg-da20033ncjis73880o2g-a.oregon-postgres.render.com/reaper_db_avmf"

def get_db_connection():
    # Ưu tiên lấy DATABASE_URL từ Render Environment, nếu không có mới dùng Local URL
    url = os.getenv("DATABASE_URL", DEFAULT_LOCAL_URL)
    
    # Chuẩn hóa prefix từ postgres:// sang postgresql:// cho psycopg2
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
        
    return psycopg2.connect(url)

def init_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Bảng lưu thông tin user, điểm số, thử thách & báo thủ
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users_points (
                user_id VARCHAR(50),
                guild_id VARCHAR(50) DEFAULT '0',
                user_name TEXT,
                soul_points INT DEFAULT 0,
                current_challenge TEXT DEFAULT 'None',
                challenge_reward INT DEFAULT 0,
                status VARCHAR(20) DEFAULT 'IDLE',
                bao_day INT DEFAULT 0,
                bao_week INT DEFAULT 0,
                bao_month INT DEFAULT 0,
                is_sieu_cap INT DEFAULT 0,
                time_archive TEXT,
                PRIMARY KEY (user_id, guild_id)
            );
        ''')
        
        # Bảng lưu config role báo thủ của từng Server
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS guild_roles (
                guild_id VARCHAR(50) PRIMARY KEY,
                role_day BIGINT,
                role_week BIGINT,
                role_month BIGINT,
                role_sieu_cap BIGINT,
                role_ba_chu BIGINT
            );
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Đã kết nối và khởi tạo PostgreSQL thành công!")
    except Exception as e:
        print(f"❌ Lỗi kết nối PostgreSQL: {e}")