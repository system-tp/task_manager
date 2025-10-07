from app import app, db, User, TaskName, Task

def generate_tasks_for_all_users():
    # ユーザーは userid 昇順
    users = User.query.order_by(User.userid.asc()).all()
    # タスク名は taskkey 昇順
    task_names = TaskName.query.order_by(TaskName.taskkey.asc()).all()

    for user in users:
        for task_name in task_names:
            # すでに同じタスクがユーザーに割り当てられていないか確認
            exists = Task.query.filter_by(user_id=user.userid, name=task_name.name).first()
            if not exists:
                task = Task(user_id=user.userid, name=task_name.name)
                db.session.add(task)
                print(f"Task created: {task_name.name} for user {user.name}")

    db.session.commit()
    print("✅ All tasks generated successfully!")

if __name__ == "__main__":
    with app.app_context():
        generate_tasks_for_all_users()
