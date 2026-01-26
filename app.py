from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
from werkzeug.middleware.proxy_fix import ProxyFix
import calendar
import os

app = Flask(__name__)

app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# ミドルウェアとして適用
app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix='/task_manager')
# --- DATABASE ---
# Supabase（推奨: トランザクションプーラー6543番ポート）に接続
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'postgresql://taskuser:wpekusj9@localhost/task_manager'  # ローカル用フォールバック
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ✅【追加】接続リーク防止：リクエスト終了ごとにセッションをクリーンアップ
@app.teardown_appcontext
def shutdown_session(exception=None):
    """
    各リクエスト終了後にSQLAlchemyのセッションをクローズし、
    Supabaseの接続プールに確実に返却する。
    """
    db.session.remove()

# --- LOGIN ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

# --- MODELS ---
class Admin(UserMixin, db.Model):
    __tablename__ = "admin"
    account_id = db.Column(db.String(50), primary_key=True)
    name = db.Column(db.String(50))
    account_password = db.Column(db.String(50))  # 平文（本番ではハッシュ化推奨）
    role = db.Column(db.String(20), default="admin")  # admin / super_admin

    @property
    def id(self):
        return self.account_id

class User(db.Model):
    __tablename__ = "user"
    userid = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    group = db.Column(db.String(50))
    admin_id = db.Column(db.String(50))

    @property
    def id(self):
        return self.userid

class TaskName(db.Model):
    __tablename__ = "taskname"
    taskkey = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)

class Task(db.Model):
    __tablename__ = "task"
    taskkey = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.userid'))
    name = db.Column(db.String(100), nullable=False)

class TaskStatus(db.Model):
    __tablename__ = "taskstatus"
    user_id = db.Column(db.Integer, db.ForeignKey('user.userid'), primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('task.taskkey'), primary_key=True)
    date = db.Column(db.Date, primary_key=True)
    status = db.Column(db.Integer, default=0)  # 0:未, 1:済, 2:休

# --- LOGIN MANAGER ---
@login_manager.user_loader
def load_user(account_id):
    return Admin.query.get(account_id)

# --- JST共通関数 ---
def jst_today():
    """日本時間の今日の日付を返す"""
    return datetime.now(ZoneInfo("Asia/Tokyo")).date()

# --- ROUTES ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        account_id = request.form.get("account_id", "")
        password = request.form.get("password", "")
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
    view_mode = request.args.get("view", "day")  # デフォルトは日表示
    week_start_str = request.args.get("week", None)

    today = jst_today()
    today_param = date.fromisoformat(week_start_str) if week_start_str else today

    # --- ユーザー取得 ---
    if current_user.role == "super_admin":
        users = User.query.order_by(User.userid.asc()).all()
    else:
        users = User.query.filter_by(admin_id=current_user.id).order_by(User.userid.asc()).all()

    # --- タスク取得 ---
    user_ids = [u.userid for u in users]
    tasks = Task.query.filter(Task.user_id.in_(user_ids)).order_by(Task.user_id.asc(), Task.taskkey.asc()).all() if user_ids else []

    # --- 日付リスト作成と前後リンク ---
    if view_mode == "day":
        days = [today_param]
        prev_link = (today_param - timedelta(days=1)).isoformat()
        next_link = (today_param + timedelta(days=1)).isoformat()
    elif view_mode == "week":
        start_day = today_param - timedelta(days=(today_param.weekday() + 1) % 7)
        days = [start_day + timedelta(days=i) for i in range(7)]
        prev_link = (start_day - timedelta(days=7)).isoformat()
        next_link = (start_day + timedelta(days=7)).isoformat()
    elif view_mode == "month":
        first_day = today_param.replace(day=1)
        last_day = today_param.replace(day=calendar.monthrange(today_param.year, today_param.month)[1])
        days = [first_day + timedelta(days=i) for i in range((last_day - first_day).days + 1)]
        prev_link = (first_day - timedelta(days=1)).replace(day=1).isoformat()
        next_link = (last_day + timedelta(days=1)).replace(day=1).isoformat()
    else:
        days = [today_param]
        prev_link = (today_param - timedelta(days=1)).isoformat()
        next_link = (today_param + timedelta(days=1)).isoformat()

    # --- 現在のステータス取得 ---
    status_dict = {}
    taskkeys = [t.taskkey for t in tasks if t.taskkey is not None]
    if taskkeys:
        task_statuses = TaskStatus.query.filter(TaskStatus.task_id.in_(taskkeys)).all()
        for ts in task_statuses:
            status_dict.setdefault(ts.task_id, {})[ts.date] = ts.status

    # --- POST保存処理 ---
    if request.method == "POST":
        try:
            with db.session.no_autoflush:
                for key, value in request.form.items():
                    if key.startswith("task_"):
                        try:
                            _, taskkey_str, day_str = key.split("_", 2)
                            taskkey = int(taskkey_str)
                            day_date = date.fromisoformat(day_str)
                        except Exception:
                            continue
                        if not value or value.strip() == '':
                            continue
                        try:
                            status = int(value)
                        except ValueError:
                            continue
                        task = Task.query.get(taskkey)
                        if not task:
                            continue
                        ts = TaskStatus.query.filter_by(user_id=task.user_id, task_id=taskkey, date=day_date).with_for_update().first()
                        if not ts:
                            ts = TaskStatus(user_id=task.user_id, task_id=taskkey, date=day_date, status=status)
                            db.session.add(ts)
                        else:
                            ts.status = status
                db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error("DB保存エラー: %s", e)
        return redirect(url_for("dashboard", view=view_mode, week=week_start_str or today.isoformat()))

    # --- グループ分け ---
    groups = {}
    for user in users:
        g = user.group if user.group else "その他"
        groups.setdefault(g, []).append(user)

    # --- ユーザーごとのタスク辞書 ---
    tasks_by_user = {}
    for task in tasks:
        tasks_by_user.setdefault(task.user_id, []).append(task)

    from config import SYSTEM_START_DATE

    return render_template(
        "dashboard.html",
        groups=groups,
        users=users,
        tasks=tasks,
        tasks_by_user=tasks_by_user,
        status_dict=status_dict,
        days=days,
        view_mode=view_mode,
        prev_link=prev_link,
        next_link=next_link,
        today=today,
        system_start_date=SYSTEM_START_DATE
    )

@app.route("/update_status", methods=["POST"])
@login_required
def update_status():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"success": False, "error": "Invalid JSON"}), 400

    try:
        taskkey = int(data.get("taskkey"))
        day_str = data.get("day")
        status = int(data.get("status"))
    except Exception:
        return jsonify({"success": False, "error": "Invalid parameters"}), 400

    try:
        day_date = date.fromisoformat(day_str)
    except Exception:
        return jsonify({"success": False, "error": "Invalid date format"}), 400

    task = Task.query.get(taskkey)
    if not task:
        return jsonify({"success": False, "error": "Invalid task"}), 400

    try:
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
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        app.logger.error("update_status DBエラー: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/report/monthly")
@login_required
def monthly_report():
    from datetime import timedelta, date
    import calendar as cal

    # --- 達成率関数（先に定義） ---
    def calc_rate(completed, rest, none_count, total_days):
        if rest + none_count == total_days:
            return "--"
        denom = total_days - rest
        return round((completed + none_count) / denom * 100, 1) if denom > 0 else 0

    year_str = request.args.get("year")
    month_str = request.args.get("month")
    today = jst_today()

    year = int(year_str) if year_str and year_str.isdigit() else today.year
    month = int(month_str) if month_str and month_str.isdigit() else today.month

    from config import SYSTEM_START_DATE

    first_day = date(year, month, 1)
    last_day = date(year, month, cal.monthrange(year, month)[1])
    effective_first_day = max(first_day, SYSTEM_START_DATE)

    last_effective_day = min(last_day, today - timedelta(days=1))  # 当日を除外
    day_list = [effective_first_day + timedelta(days=i)
                for i in range((last_effective_day - effective_first_day).days + 1)]

    # 前月・翌月
    prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
    next_year, next_month = (year + 1, 1) if month == 12 else (year, month + 1)

    # --- ユーザー取得 ---
    if current_user.role == "super_admin":
        users = User.query.order_by(User.userid.asc()).all()
    else:
        users = User.query.filter_by(admin_id=current_user.id).order_by(User.userid.asc()).all()
    user_ids = [u.userid for u in users]

    # --- タスク取得 ---
    tasks = Task.query.filter(Task.user_id.in_(user_ids)).order_by(
        Task.user_id.asc(), Task.taskkey.asc()
    ).all() if user_ids else []

    # --- TaskStatus取得 ---
    taskkeys = [t.taskkey for t in tasks]
    task_statuses = TaskStatus.query.filter(
        TaskStatus.task_id.in_(taskkeys),
        TaskStatus.date >= first_day,
        TaskStatus.date <= last_day
    ).all() if taskkeys else []

    # --- ステータス辞書 ---
    status_dict = {}
    for ts in task_statuses:
        status_dict.setdefault(ts.task_id, {})[ts.date] = ts.status

    # --- グループ分け ---
    groups = {}
    for user in users:
        g = user.group if user.group else "その他"
        groups.setdefault(g, []).append(user)

    # --- 各種集計 ---
    report = {}
    user_summary = {}
    group_summary = {}
    overall_summary = {"completed": 0, "rest": 0, "none_count": 0, "total_days": 0, "task_count": 0}

    for task in tasks:
        user_id = task.user_id

        completed = sum(1 for d in day_list if status_dict.get(task.taskkey, {}).get(d) == 1)
        rest = sum(1 for d in day_list if status_dict.get(task.taskkey, {}).get(d) == 2)
        none_count = sum(1 for d in day_list if status_dict.get(task.taskkey, {}).get(d) == 3)
        total_days = len(day_list)

        # ★ タスク単位の達成率追加
        rate = calc_rate(completed, rest, none_count, total_days)

        report.setdefault(user_id, {})[task.taskkey] = {
            "task_name": task.name,
            "completed": completed,
            "rest": rest,
            "none_count": none_count,
            "total_days": total_days,
            "rate": rate,    # ← 追加
        }

        # --- user_summary 集計 ---
        user_summary.setdefault(user_id, {"completed": 0, "rest": 0,
                                          "none_count": 0, "total_days": 0, "task_count": 0})
        user_summary[user_id]["completed"] += completed
        user_summary[user_id]["rest"] += rest
        user_summary[user_id]["none_count"] += none_count
        user_summary[user_id]["total_days"] += total_days
        user_summary[user_id]["task_count"] += 1

        # --- group_summary 集計 ---
        user_obj = next((u for u in users if u.userid == user_id), None)
        group_name = user_obj.group if user_obj and user_obj.group else "その他"

        group_summary.setdefault(group_name,
                                 {"completed": 0, "rest": 0, "none_count": 0,
                                  "total_days": 0, "task_count": 0})

        group_summary[group_name]["completed"] += completed
        group_summary[group_name]["rest"] += rest
        group_summary[group_name]["none_count"] += none_count
        group_summary[group_name]["total_days"] += total_days
        group_summary[group_name]["task_count"] += 1

        # --- overall summary ---
        overall_summary["completed"] += completed
        overall_summary["rest"] += rest
        overall_summary["none_count"] += none_count
        overall_summary["total_days"] += total_days
        overall_summary["task_count"] += 1

    # --- タスク単位集計（部課別） ---
    task_report = {}
    task_group_summary = {}

    for task in tasks:
        user_obj = next((u for u in users if u.userid == task.user_id), None)
        group_name = user_obj.group if user_obj and user_obj.group else "その他"

        task_report.setdefault(group_name, {})
        task_group_summary.setdefault(group_name,
                                      {"completed": 0, "rest": 0, "none_count": 0,
                                       "total_days": 0, "task_count": 0})

        t = task_report[group_name].setdefault(task.name, {"completed": 0, "rest": 0,
                                                           "none_count": 0, "total_days": 0,
                                                           "rate": 0})

        for d in day_list:
            status = status_dict.get(task.taskkey, {}).get(d)
            if status == 1:  # 済
                t["completed"] += 1
                task_group_summary[group_name]["completed"] += 1
            elif status == 2:  # 休
                t["rest"] += 1
                task_group_summary[group_name]["rest"] += 1
            elif status == 3:  # 無
                t["none_count"] += 1
                task_group_summary[group_name]["none_count"] += 1

            t["total_days"] += 1
            task_group_summary[group_name]["total_days"] += 1

        task_group_summary[group_name]["task_count"] += 1

    # --- サマリーの rate 計算 ---
    for user_id, summary in user_summary.items():
        summary["rate"] = calc_rate(summary["completed"], summary["rest"],
                                    summary["none_count"], summary["total_days"])

    for group, summary in group_summary.items():
        summary["rate"] = calc_rate(summary["completed"], summary["rest"],
                                    summary["none_count"], summary["total_days"])

    for group, tasks_in_group in task_report.items():
        for t_name, t_info in tasks_in_group.items():
            t_info["rate"] = calc_rate(t_info["completed"], t_info["rest"],
                                       t_info["none_count"], t_info["total_days"])

    for group, summary in task_group_summary.items():
        summary["rate"] = calc_rate(summary["completed"], summary["rest"],
                                    summary["none_count"], summary["total_days"])

    return render_template(
        "monthly_report.html",
        groups=groups,
        report=report,
        user_summary=user_summary,
        group_summary=group_summary,
        overall_summary=overall_summary,
        task_report=task_report,
        task_group_summary=task_group_summary,
        day_list=day_list,
        year=year,
        month=month,
        prev_year=prev_year,
        prev_month=prev_month,
        next_year=next_year,
        next_month=next_month,
        system_start_date=SYSTEM_START_DATE
    )

@app.route("/")
def index():
    return redirect(url_for("login"))

# --- APP RUN ---
if __name__ == "__main__":
    with app.app_context():
        try:
            db.create_all()
        except Exception as e:
            print("❌ DB 作成エラー:", e)

    port = int(os.environ.get("PORT", 5000))  # ← Render対応
    app.run(host="0.0.0.0", port=port, debug=True)  # debug=Falseにしておく
