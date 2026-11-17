"""Reelmap: plan short-form video ideas and stick-figure storyboards (Flask + MySQL)."""
import re
import secrets
from functools import wraps

import pymysql
from flask import (Flask, Response, abort, flash, g, redirect, render_template, request, session,
                   url_for)
from werkzeug.security import check_password_hash, generate_password_hash

import config
import generator
import stickfigure as sf
from db import close_db, execute, get_db, query_all, query_one
from pdf_export import build_pdf

app = Flask(__name__)
app.config.update(SECRET_KEY=config.SECRET_KEY, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax")
app.teardown_appcontext(close_db)

if config.AUTO_INIT_DB:  # create the tables on the very first start (e.g. on Render)
    from init_db import ensure_schema
    ensure_schema(log=app.logger.warning)

PLATFORMS = ["Instagram Reels", "YouTube Shorts", "Facebook Reels", "LinkedIn Video"]
STATUSES = ["draft", "planned", "filmed", "posted"]
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ------------------------------------------------------------------ security helpers
def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


@app.before_request
def load_user_and_check_csrf():
    g.user = None
    if "user_id" in session:
        g.user = query_one("SELECT user_id, full_name, email, role FROM users WHERE user_id = %s",
                           (session["user_id"],))
        if g.user is None:
            session.clear()
    if request.method == "POST" and request.form.get("csrf_token") != session.get("csrf"):
        abort(400, "Your session expired. Please go back and try again.")


@app.after_request
def security_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    return resp


@app.context_processor
def template_globals():
    return {"csrf_token": csrf_token, "sf": sf, "ai_enabled": generator.ai_enabled()}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            flash("Please log in first.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if g.user["role"] != "admin":
            abort(403)
        return view(*args, **kwargs)
    return wrapped


# ------------------------------------------------------------------ data access (owner checks)
def get_project(project_id):
    """Return the project with its niche and format names, only if it belongs to the user."""
    row = query_one(
        """SELECT p.*, n.name AS niche, f.name AS format_name, f.default_duration, f.style
           FROM projects p
           JOIN niches n ON n.niche_id = p.niche_id
           JOIN content_formats f ON f.format_id = p.format_id
           WHERE p.project_id = %s AND p.user_id = %s""",
        (project_id, g.user["user_id"]))
    if row is None:
        abort(404)
    return row


def get_idea(idea_id):
    """Return (project, idea) for an idea owned by the user."""
    idea = query_one(
        """SELECT i.* FROM ideas i JOIN projects p ON p.project_id = i.project_id
           WHERE i.idea_id = %s AND p.user_id = %s""", (idea_id, g.user["user_id"]))
    if idea is None:
        abort(404)
    return get_project(idea["project_id"]), idea


def delete_rows(statements):
    """Run several deletes as one transaction, children first (mirrors ON DELETE CASCADE)."""
    conn = get_db()
    try:
        with conn.cursor() as cur:
            for sql, param in statements:
                cur.execute(sql, (param,))
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def get_frames(idea_id):
    return query_all("SELECT * FROM storyboard_frames WHERE idea_id = %s ORDER BY frame_no", (idea_id,))


# ------------------------------------------------------------------ public pages and auth
@app.route("/")
def home():
    if g.user:
        return redirect(url_for("dashboard"))
    formats = query_all("SELECT name, description, icon_pose FROM content_formats ORDER BY format_id")
    return render_template("home.html", formats=formats)


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        error = None
        if not 2 <= len(name) <= 80:
            error = "Enter your name (2 to 80 characters)."
        elif not EMAIL_RE.match(email):
            error = "Enter a valid email address."
        elif len(password) < 8:
            error = "Use a password with at least 8 characters."
        if error is None:
            first_user = query_one("SELECT COUNT(*) AS n FROM users")["n"] == 0
            try:
                user_id = execute(
                    "INSERT INTO users (full_name, email, password_hash, role) VALUES (%s, %s, %s, %s)",
                    (name, email, generate_password_hash(password), "admin" if first_user else "creator"))
            except pymysql.err.IntegrityError:
                error = "An account with this email already exists. Try logging in."
            else:
                session.clear()
                session["user_id"] = user_id
                flash(f"Welcome to Reelmap, {name.split()[0]}!", "success")
                return redirect(url_for("dashboard"))
        flash(error, "error")
    return render_template("auth.html", mode="signup")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = query_one("SELECT user_id, password_hash FROM users WHERE email = %s", (email,))
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session["user_id"] = user["user_id"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("dashboard"))
        flash("Wrong email or password.", "error")
    return render_template("auth.html", mode="login")


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("You're logged out.", "info")
    return redirect(url_for("home"))


# ------------------------------------------------------------------ dashboard and projects
@app.route("/dashboard")
@login_required
def dashboard():
    uid = g.user["user_id"]
    stats = query_one(
        """SELECT
             (SELECT COUNT(*) FROM projects WHERE user_id = %s) AS projects,
             (SELECT COUNT(*) FROM ideas i JOIN projects p ON p.project_id = i.project_id
               WHERE p.user_id = %s) AS ideas,
             (SELECT COUNT(DISTINCT sf.idea_id) FROM storyboard_frames sf
               JOIN ideas i ON i.idea_id = sf.idea_id JOIN projects p ON p.project_id = i.project_id
               WHERE p.user_id = %s) AS storyboards,
             (SELECT COUNT(*) FROM downloads WHERE user_id = %s) AS downloads""", (uid, uid, uid, uid))
    recent = query_all("SELECT * FROM v_project_summary WHERE user_id = %s ORDER BY updated_at DESC LIMIT 5", (uid,))
    by_status = query_all(
        "SELECT status, COUNT(*) AS n FROM projects WHERE user_id = %s GROUP BY status", (uid,))
    return render_template("dashboard.html", stats=stats, recent=recent,
                           by_status={r["status"]: r["n"] for r in by_status})


@app.route("/projects")
@login_required
def projects():
    q = request.args.get("q", "").strip()[:60]
    niche = request.args.get("niche", "")
    status = request.args.get("status", "")
    sql = "SELECT * FROM v_project_summary WHERE user_id = %s"
    params = [g.user["user_id"]]
    if q:
        sql += " AND (title LIKE %s OR topic LIKE %s)"
        params += [f"%{q}%", f"%{q}%"]
    if niche:
        sql += " AND niche = %s"
        params.append(niche)
    if status in STATUSES:
        sql += " AND status = %s"
        params.append(status)
    rows = query_all(sql + " ORDER BY updated_at DESC", params)
    niches = query_all("SELECT name FROM niches ORDER BY name")
    return render_template("projects.html", rows=rows, niches=niches, q=q, niche=niche, status=status,
                           statuses=STATUSES)


@app.route("/projects/new", methods=["GET", "POST"])
@login_required
def new_project():
    niches = query_all("SELECT niche_id, name FROM niches ORDER BY name")
    formats = query_all("SELECT * FROM content_formats ORDER BY format_id")
    form = request.form
    if request.method == "POST":
        topic = generator.clean_topic(form.get("topic"))
        audience = form.get("target_audience", "").strip()[:120]
        niche_id, format_id = form.get("niche_id", type=int), form.get("format_id", type=int)
        platform = form.get("platform")
        valid_niche = any(n["niche_id"] == niche_id for n in niches)
        valid_format = any(f["format_id"] == format_id for f in formats)
        if len(topic) < 3:
            flash("Tell us your topic in a few words, for example 'home workouts'.", "error")
        elif not (valid_niche and valid_format and platform in PLATFORMS):
            flash("Pick a niche, a video format and a platform.", "error")
        else:
            title = form.get("title", "").strip()[:120] or f"{topic[:1].upper()}{topic[1:]} videos"
            pid = execute(
                "INSERT INTO projects (user_id, niche_id, format_id, title, topic, platform, target_audience) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (g.user["user_id"], niche_id, format_id, title, topic, platform, audience or "everyone"))
            generator.bank_ideas(get_project(pid))
            flash("Here are 5 ideas from the idea bank. Pick one to build its storyboard.", "success")
            return redirect(url_for("project_detail", project_id=pid))
    return render_template("project_new.html", niches=niches, formats=formats, platforms=PLATFORMS, form=form)


@app.route("/projects/<int:project_id>")
@login_required
def project_detail(project_id):
    project = get_project(project_id)
    ideas = query_all(
        """SELECT i.*, COUNT(sf.frame_id) AS frame_count
           FROM ideas i LEFT JOIN storyboard_frames sf ON sf.idea_id = i.idea_id
           WHERE i.project_id = %s GROUP BY i.idea_id ORDER BY i.is_selected DESC, i.created_at DESC, i.idea_id""",
        (project_id,))
    return render_template("project_detail.html", project=project, ideas=ideas, statuses=STATUSES)


@app.route("/projects/<int:project_id>/status", methods=["POST"])
@login_required
def project_status(project_id):
    get_project(project_id)
    status = request.form.get("status")
    if status in STATUSES:
        execute("UPDATE projects SET status = %s WHERE project_id = %s", (status, project_id))
        flash(f"Status changed to {status}.", "success")
    return redirect(url_for("project_detail", project_id=project_id))


@app.route("/projects/<int:project_id>/delete", methods=["POST"])
@login_required
def project_delete(project_id):
    get_project(project_id)
    delete_rows([
        ("DELETE d FROM downloads d JOIN ideas i ON i.idea_id = d.idea_id WHERE i.project_id = %s", project_id),
        ("DELETE sf FROM storyboard_frames sf JOIN ideas i ON i.idea_id = sf.idea_id WHERE i.project_id = %s",
         project_id),
        ("DELETE FROM ideas WHERE project_id = %s", project_id),
        ("DELETE FROM projects WHERE project_id = %s", project_id),
    ])
    flash("Project deleted, along with its ideas and storyboards.", "info")
    return redirect(url_for("projects"))


@app.route("/projects/<int:project_id>/ideas", methods=["POST"])
@login_required
def more_ideas(project_id):
    project = get_project(project_id)
    if request.form.get("source") == "ai":
        try:
            n = generator.ai_ideas(project)
            flash(f"AI added {n} new ideas.", "success")
        except generator.AIError as e:
            flash(str(e), "error")
    else:
        n = generator.bank_ideas(project)
        flash(f"Added {n} more idea{'s' if n != 1 else ''}." if n else
              "You've used every idea in the bank for this format. Try AI ideas or another format.",
              "success" if n else "info")
    return redirect(url_for("project_detail", project_id=project_id))


# ------------------------------------------------------------------ ideas and storyboards
@app.route("/ideas/<int:idea_id>/delete", methods=["POST"])
@login_required
def idea_delete(idea_id):
    project, _ = get_idea(idea_id)
    delete_rows([("DELETE FROM downloads WHERE idea_id = %s", idea_id),
                 ("DELETE FROM storyboard_frames WHERE idea_id = %s", idea_id),
                 ("DELETE FROM ideas WHERE idea_id = %s", idea_id)])
    flash("Idea removed.", "info")
    return redirect(url_for("project_detail", project_id=project["project_id"]))


@app.route("/ideas/<int:idea_id>/storyboard", methods=["GET", "POST"])
@login_required
def storyboard(idea_id):
    project, idea = get_idea(idea_id)
    if request.method == "POST":
        try:
            if request.form.get("source") == "ai":
                generator.ai_storyboard(project, idea)
                flash("AI drew a new storyboard.", "success")
            else:
                generator.bank_storyboard(project, idea)
                flash("Storyboard ready. Edit any scene to make it yours.", "success")
        except generator.AIError as e:
            flash(str(e), "error")
        return redirect(url_for("storyboard", idea_id=idea_id))
    frames = get_frames(idea_id)
    if not frames:
        generator.bank_storyboard(project, idea)
        frames = get_frames(idea_id)
    start = 0
    for f in frames:
        f["start"] = start
        start += f["duration_sec"]
    return render_template("storyboard.html", project=project, idea=idea, frames=frames, total=start)


@app.route("/frames/<int:frame_id>", methods=["POST"])
@login_required
def frame_update(frame_id):
    frame = query_one(
        """SELECT sf.frame_id, sf.idea_id FROM storyboard_frames sf
           JOIN ideas i ON i.idea_id = sf.idea_id JOIN projects p ON p.project_id = i.project_id
           WHERE sf.frame_id = %s AND p.user_id = %s""", (frame_id, g.user["user_id"]))
    if frame is None:
        abort(404)
    f = request.form
    if f.get("action") == "delete":
        execute("DELETE FROM storyboard_frames WHERE frame_id = %s", (frame_id,))
        # renumber the remaining frames 1..n
        rows = get_frames(frame["idea_id"])
        for no, r in enumerate(rows, start=1):
            if r["frame_no"] != no:
                execute("UPDATE storyboard_frames SET frame_no = %s WHERE frame_id = %s", (no, r["frame_id"]))
        flash("Scene deleted.", "info")
    else:
        shot, pose, prop = f.get("shot_type"), f.get("pose"), f.get("prop")
        if shot not in sf.SHOTS or pose not in sf.POSES or prop not in sf.PROPS:
            abort(400)
        execute(
            "UPDATE storyboard_frames SET shot_type=%s, pose=%s, prop=%s, action_text=%s, dialogue=%s, "
            "on_screen_text=%s, duration_sec=%s WHERE frame_id=%s",
            (shot, pose, prop, generator.clip(f.get("action_text"), "action_text") or "Film this scene.",
             generator.clip(f.get("dialogue"), "dialogue"), generator.clip(f.get("on_screen_text"), "on_screen_text"),
             max(1, min(60, f.get("duration_sec", 5, type=int))), frame_id))
        flash("Scene saved.", "success")
    return redirect(url_for("storyboard", idea_id=frame["idea_id"]) + f"#frame-{frame_id}")


@app.route("/ideas/<int:idea_id>/frames", methods=["POST"])
@login_required
def frame_add(idea_id):
    get_idea(idea_id)
    nxt = query_one("SELECT COALESCE(MAX(frame_no), 0) + 1 AS n FROM storyboard_frames WHERE idea_id = %s",
                    (idea_id,))["n"]
    if nxt > 12:
        flash("A short video works best with 12 scenes or fewer.", "info")
    else:
        fid = execute(
            "INSERT INTO storyboard_frames (idea_id, frame_no, shot_type, pose, prop, action_text, dialogue, "
            "on_screen_text, duration_sec) VALUES (%s, %s, 'medium', 'talk', 'none', %s, '', '', 5)",
            (idea_id, nxt, "Describe what happens in this scene."))
        flash("New scene added at the end.", "success")
        return redirect(url_for("storyboard", idea_id=idea_id) + f"#frame-{fid}")
    return redirect(url_for("storyboard", idea_id=idea_id))


@app.route("/ideas/<int:idea_id>/pdf")
@login_required
def idea_pdf(idea_id):
    project, idea = get_idea(idea_id)
    frames = get_frames(idea_id)
    if not frames:
        flash("Build the storyboard first.", "info")
        return redirect(url_for("storyboard", idea_id=idea_id))
    pdf = build_pdf(project, idea, frames)
    execute("INSERT INTO downloads (user_id, idea_id) VALUES (%s, %s)", (g.user["user_id"], idea_id))
    safe = re.sub(r"[^a-z0-9]+", "-", idea["title"].lower()).strip("-")[:60] or "content-plan"
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="reelmap-{safe}.pdf"'})


# ------------------------------------------------------------------ idea bank (admin)
@app.route("/idea-bank", methods=["GET", "POST"])
@admin_required
def idea_bank():
    formats = query_all("SELECT format_id, name FROM content_formats ORDER BY format_id")
    niches = query_all("SELECT niche_id, name FROM niches ORDER BY name")
    if request.method == "POST":
        f = request.form
        action = f.get("action")
        tid = f.get("template_id", type=int)
        if action == "toggle" and tid:
            execute("UPDATE idea_templates SET is_active = 1 - is_active WHERE template_id = %s", (tid,))
        elif action == "delete" and tid:
            delete_rows([("UPDATE ideas SET template_id = NULL WHERE template_id = %s", tid),
                         ("DELETE FROM idea_templates WHERE template_id = %s", tid)])
            flash("Template deleted.", "info")
        elif action == "add":
            title, hook, desc = (f.get(k, "").strip() for k in ("title_template", "hook_template", "description_template"))
            fmt = f.get("format_id", type=int)
            niche = f.get("niche_id", type=int) or None
            if title and hook and desc and any(x["format_id"] == fmt for x in formats):
                execute("INSERT INTO idea_templates (format_id, niche_id, title_template, hook_template, "
                        "description_template, difficulty, created_by) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                        (fmt, niche, title[:150], hook[:200], desc[:400],
                         f.get("difficulty") if f.get("difficulty") in ("easy", "medium", "hard") else "easy",
                         g.user["user_id"]))
                flash("Template added to the idea bank.", "success")
            else:
                flash("Fill in the format, title, hook and description.", "error")
        return redirect(url_for("idea_bank"))
    templates = query_all(
        """SELECT t.*, f.name AS format_name, COALESCE(n.name, 'All niches') AS niche_name,
                  COUNT(i.idea_id) AS times_used
           FROM idea_templates t
           JOIN content_formats f ON f.format_id = t.format_id
           LEFT JOIN niches n ON n.niche_id = t.niche_id
           LEFT JOIN ideas i ON i.template_id = t.template_id
           GROUP BY t.template_id ORDER BY t.format_id, t.template_id""")
    summary = query_all(
        """SELECT f.name, COUNT(t.template_id) AS templates, SUM(t.is_active) AS active
           FROM content_formats f LEFT JOIN idea_templates t ON t.format_id = f.format_id
           GROUP BY f.format_id, f.name ORDER BY f.format_id""")
    return render_template("idea_bank.html", templates=templates, formats=formats, niches=niches, summary=summary)


# ------------------------------------------------------------------ errors
@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
def http_error(e):
    return render_template("error.html", code=e.code, message=getattr(e, "description", "")), e.code


@app.errorhandler(pymysql.err.OperationalError)
def db_down(_e):
    return render_template("error.html", code=503,
                           message="The database isn't reachable. Check the MySQL settings and try again."), 503


if __name__ == "__main__":
    app.run(debug=True, port=5000)
