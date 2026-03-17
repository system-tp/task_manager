-- "user" テーブルに論理削除フラグを追加（PostgreSQL）
ALTER TABLE "user"
  ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE;

-- （任意）管理者別＋未削除ユーザの絞り込みを高速化
CREATE INDEX IF NOT EXISTS idx_user_admin_id_is_deleted
  ON "user"(admin_id, is_deleted);

