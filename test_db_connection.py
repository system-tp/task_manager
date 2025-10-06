import psycopg2
from psycopg2 import OperationalError

try:
    conn = psycopg2.connect(
        host="db.sfwrixanwhadlkmquuus.supabase.co",
        dbname="postgres",
        user="postgres",
        password="wpekusj9",
        port=5432,
        connect_timeout=10,
        options='-4'  # IPv4を強制
    )
    print("✅ 接続成功")
    conn.close()
except OperationalError as e:
    print("❌ 接続失敗:", e)
