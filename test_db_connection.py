import psycopg2
import os

# 環境変数や直接文字列で設定可能
DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres.sfwrixanwhadlkmquuus:wpekusj9@aws-1-ap-northeast-1.pooler.supabase.com:5432/postgres"
)

try:
    conn = psycopg2.connect(DB_URL)
    print("✅ 接続成功！")
    conn.close()
except Exception as e:
    print("❌ 接続失敗:", e)
