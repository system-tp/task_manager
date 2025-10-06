from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import date, timedelta
import calendar
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secretkey')  # 環境変数から取得
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'postgresql://taskuser:wpekusj9@localhost/task_manager'  # ローカル用フォールバック
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# --- モデル ---
class Admin(UserMixin, db.Model):
    account_id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(50))
    account_password = db.Column(db.String(50))  # 平文
    role = db.Column(db.String(20), default="admin")  # admin / super_admin

    @property
    def id(self):
        return self.account_id

class User(db.Model):
    userid = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    group = db.Column(db.String(50))
    admin_id = db.Column(db.String(50))

    @property
    def id(self):
        return self.userid

class TaskName(db.Model):
    taskkey = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)

class Task(db.Model):
    taskkey = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.userid'))
    name = db.Column(db.String(100), nullable=False)

class TaskStatus(db.Model):
    # 複合主キーに変更
    user_id = db.Column(db.Integer, db.ForeignKey('user.userid'), primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.taskkey'), primary_key=True)
    date = db.Column(db.Date, primary_key=True)
    status = db.Column(db.Integer, default=0)  # 0:未, 1:済, 2:休

# --- ログイン ---
@login_manager.user_loader
def load_user(account_id):
    return Admin.query.get(account_id)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        account_id = request.form["account_id"]
        password = request.form["password"]
        admin = Admin.query.get(account_id)
        if admin and admin.account_password == password:
            login_user(admin)
            return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    view_mode = request.args.get("view", "week")
    week_start_str = request.args.get("week", None)

    today = date.today()
    today_param = date.fromisoformat(week_start_str) if week_start_str else today

    # ユーザー取得
    if current_user.role == "super_admin":
        users = User.query.all()
    else:
        users = User.query.filter_by(admin_id=current_user.id).all()

    tasks = Task.query.filter(Task.user_id.in_([u.userid for u in users])).all()

    # 日付リスト
    if view_mode == "week":
        start_day = today_param - timedelta(days=(today_param.weekday() + 1) % 7)
        days = [start_day + timedelta(days=i) for i in range(7)]
        prev_week = (start_day - timedelta(days=7)).isoformat()
        next_week = (start_day + timedelta(days=7)).isoformat()
    elif view_mode == "month":
        first_day = today_param.replace(day=1)
        last_day = today_param.replace(day=calendar.monthrange(today_param.year, today_param.month)[1])
        days = [first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)]
        prev_month_last_day = first_day - timedelta(days=1)
        prev_month = prev_month_last_day.replace(day=1)
        next_month_first_day = last_day + timedelta(days=1)
        next_month = next_month_first_day.replace(day=1)
        prev_week = prev_month.isoformat()
        next_week = next_month.isoformat()

    # 現在のステータス取得
    status_dict = {}
    for ts in TaskStatus.query.filter(TaskStatus.task_id.in_([t.taskkey for t in tasks])).all():
        if ts.task_id not in status_dict:
            status_dict[ts.task_id] = {}
        status_dict[ts.task_id][ts.date] = ts.status

    # POST保存処理
    if request.method == "POST":
        try:
            with db.session.no_autoflush:
                for key, value in request.form.items():
                    print(f"{key} = '{value}'")
                    if key.startswith("task_"):
                        _, taskkey, day_str = key.split("_", 2)
                        taskkey = int(taskkey)
                        day_date = date.fromisoformat(day_str)

                        # 空文字はスキップ
                        if not value or value.strip() == '':
                            continue

                        status = int(value)

                        # taskkey から user_id を取得
                        task = Task.query.get(taskkey)
                        if not task:
                            continue

                        ts = TaskStatus.query.filter_by(
                            user_id=task.user_id,
                            task_id=taskkey,
                            date=day_date
                        ).with_for_update().first()

                        if not ts:
                            ts = TaskStatus(
                                user_id=task.user_id,
                                task_id=taskkey,
                                date=day_date,
                                status=status
                            )
                            db.session.add(ts)
                        else:
                            ts.status = status
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            print("DB保存エラー:", e)
        return redirect(url_for("dashboard", view=view_mode, week=week_start_str or today.isoformat()))

    # グループ分け
    groups = {}
    for user in users:
        if user.group not in groups:
            groups[user.group] = []
        groups[user.group].append(user)

    return render_template(
        "dashboard.html",
        groups=groups,
        users=users,
        tasks=tasks,
        status_dict=status_dict,
        days=days,
        view_mode=view_mode,
        prev_week=prev_week,
        next_week=next_week,
        today=today
    )

@app.route("/")
def index():
    return redirect(url_for("login"))

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        print("✅ Tables created successfully!")
    app.run(host="0.0.0.0", port=5000)
