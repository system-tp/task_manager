# ベースイメージ
FROM python:3.11-slim

# 作業ディレクトリ
WORKDIR /app

# 依存関係をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリをコピー
COPY . .

# 環境変数で DB 接続を設定する
# render.com の PostgreSQL は DATABASE_URL が提供される
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV SQLALCHEMY_DATABASE_URI=${DATABASE_URL}

# ポート設定
EXPOSE 5000

# コンテナ起動時に実行
CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]
