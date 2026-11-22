"""SpendWise - a simple expense tracker built with Flask and SQLite."""
import csv
import io
import os
import sqlite3
from datetime import date
from functools import wraps

from flask import (Flask, Response, flash, g, redirect, render_template,
                   request, session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-in-production")
DATABASE = os.path.join(os.path.dirname(__file__), "spendwise.db")

CATEGORIES = ["Food", "Travel", "Education", "Shopping", "Bills", "Health", "Other"]


# ---------- Database helpers ----------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DATABASE)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            amount REAL NOT NULL CHECK (amount > 0),
            category TEXT NOT NULL,
            spent_on TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
        """
    )
    db.commit()
    db.close()


# ---------- Auth ----------
def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        error = None
        if len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        if error is None:
            try:
                get_db().execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, generate_password_hash(password)),
                )
                get_db().commit()
                flash("Account created. Log in to continue.")
                return redirect(url_for("login"))
            except sqlite3.IntegrityError:
                error = "That username is already taken."
        flash(error, "error")
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = get_db().execute(
            "SELECT * FROM users WHERE username = ?", (request.form["username"].strip(),)
        ).fetchone()
        if user and check_password_hash(user["password_hash"], request.form["password"]):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("dashboard"))
        flash("Wrong username or password.", "error")
    return render_template("auth.html", mode="login")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("login"))


# ---------- Expenses ----------
def filtered_expenses(user_id):
    month = request.args.get("month", date.today().strftime("%Y-%m"))
    category = request.args.get("category", "")
    query = "SELECT * FROM expenses WHERE user_id = ? AND substr(spent_on, 1, 7) = ?"
    params = [user_id, month]
    if category in CATEGORIES:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY spent_on DESC, id DESC"
    rows = get_db().execute(query, params).fetchall()
    return rows, month, category


@app.route("/")
@login_required
def dashboard():
    rows, month, category = filtered_expenses(session["user_id"])
    total = sum(r["amount"] for r in rows)
    by_category = {}
    for r in rows:
        by_category[r["category"]] = by_category.get(r["category"], 0) + r["amount"]
    breakdown = sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)
    top = breakdown[0][1] if breakdown else 1
    return render_template(
        "dashboard.html", expenses=rows, month=month, category=category,
        total=total, breakdown=breakdown, top=top, categories=CATEGORIES,
    )


def read_expense_form():
    title = request.form["title"].strip()
    category = request.form["category"]
    spent_on = request.form["spent_on"]
    try:
        amount = float(request.form["amount"])
    except ValueError:
        amount = 0
    if not title or amount <= 0 or category not in CATEGORIES or not spent_on:
        return None
    return title, amount, category, spent_on


@app.route("/expense/new", methods=["GET", "POST"])
@login_required
def add_expense():
    if request.method == "POST":
        data = read_expense_form()
        if data:
            get_db().execute(
                "INSERT INTO expenses (user_id, title, amount, category, spent_on) "
                "VALUES (?, ?, ?, ?, ?)", (session["user_id"], *data))
            get_db().commit()
            flash("Expense added.")
            return redirect(url_for("dashboard", month=data[3][:7]))
        flash("Enter a title, an amount above 0, a category and a date.", "error")
    return render_template("expense_form.html", expense=None, categories=CATEGORIES,
                           today=date.today().isoformat())


def get_own_expense(expense_id):
    row = get_db().execute(
        "SELECT * FROM expenses WHERE id = ? AND user_id = ?",
        (expense_id, session["user_id"])).fetchone()
    return row


@app.route("/expense/<int:expense_id>/edit", methods=["GET", "POST"])
@login_required
def edit_expense(expense_id):
    expense = get_own_expense(expense_id)
    if expense is None:
        flash("Expense not found.", "error")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        data = read_expense_form()
        if data:
            get_db().execute(
                "UPDATE expenses SET title=?, amount=?, category=?, spent_on=? "
                "WHERE id=? AND user_id=?", (*data, expense_id, session["user_id"]))
            get_db().commit()
            flash("Expense updated.")
            return redirect(url_for("dashboard", month=data[3][:7]))
        flash("Enter a title, an amount above 0, a category and a date.", "error")
    return render_template("expense_form.html", expense=expense, categories=CATEGORIES,
                           today=date.today().isoformat())


@app.route("/expense/<int:expense_id>/delete", methods=["POST"])
@login_required
def delete_expense(expense_id):
    get_db().execute("DELETE FROM expenses WHERE id=? AND user_id=?",
                     (expense_id, session["user_id"]))
    get_db().commit()
    flash("Expense deleted.")
    return redirect(request.referrer or url_for("dashboard"))


@app.route("/export")
@login_required
def export_csv():
    rows, month, _ = filtered_expenses(session["user_id"])
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Date", "Title", "Category", "Amount"])
    for r in rows:
        writer.writerow([r["spent_on"], r["title"], r["category"], r["amount"]])
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename=expenses-{month}.csv"})


init_db()

if __name__ == "__main__":
    app.run(debug=True)
