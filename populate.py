from app import app, db, Admin, User, Task, TaskStatus, TaskName
from datetime import date

with app.app_context():
    # --- 既存データを削除 ---
    for table in ["task_status", "task", "task_name", "user", "admin"]:
        db.session.execute(f'TRUNCATE TABLE "{table}" RESTART IDENTITY CASCADE;')
    db.session.commit()

    # --- 管理者 ---
    admin1 = Admin(account_id="admin1", account_password="pass1", name="管理者1", role="admin")
    superadmin = Admin(account_id="superadmin", account_password="superpass", name="スーパー管理者", role="super_admin")
    db.session.add_all([admin1, superadmin])
    db.session.commit()

    # --- ユーザー ---
    user1 = User(name="田中 太郎", group="営業", admin_id=admin1.account_id)
    user2 = User(name="佐藤 花子", group="営業", admin_id=admin1.account_id)
    user3 = User(name="鈴木 次郎", group="開発", admin_id=superadmin.account_id)
    db.session.add_all([user1, user2, user3])
    db.session.commit()

    # --- タスク名 ---
    task_names_list = ["資料作成", "顧客対応", "開発レビュー"]
    task_name_objs = []
    for tn in task_names_list:
        tname = TaskName(name=tn)
        db.session.add(tname)
        task_name_objs.append(tname)
    db.session.commit()

    # --- タスク ---
    all_tasks = []
    for user in [user1, user2, user3]:
        for tname in task_name_objs:
            task = Task(user_id=user.userid, name=tname.name)
            db.session.add(task)
            all_tasks.append(task)
    db.session.commit()

    print("サンプルデータ作成完了（スーパーadmin含む・今日分のみ）")
