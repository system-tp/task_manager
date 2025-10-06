# ベースイメージ
FROM python:3.11-slim

# 作業ディレクトリ作成
WORKDIR /app

# システム依存ライブラリをインストール（PostgreSQL ドライバ用）
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 必要なファイルをコピー
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 環境変数でポートを指定
ENV PORT=5000

# Render は gunicorn を推奨
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "app:app"]
