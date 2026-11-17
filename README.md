# Reelmap: content idea and storyboard planner

A DBMS mini project built with **Python (Flask) and MySQL**.

Creators enter a topic and pick a niche, a UGC video style and a platform. Reelmap then:
- picks 5 English content ideas from an **idea bank stored in the database** (optionally, Gemini AI writes more);
- builds a **storyboard drawn with stick figures** for the chosen idea;
- exports the full plan (hook, script, checklist and storyboard) as a **PDF**.

## Features
- Sign-up and login with hashed passwords; the first account becomes the admin
- Dashboard with counts (projects, ideas, storyboards, PDF downloads)
- Create, view, search, filter, update and delete content plans (full CRUD)
- 8 UGC formats × 10 niches, 45 idea templates and 48 storyboard scenes
- Storyboard editor: change the pose (12), shot size (3), prop (10), text, dialogue and duration of every scene
- PDF export, with every download logged in the `downloads` table
- Admin "Idea bank" page to add, hide or delete templates, with usage counts
- Optional Gemini AI for extra ideas and storyboards (`GEMINI_API_KEY`)
- Security: CSRF tokens on every form, owner checks on every query, parameterised SQL

## Project structure
```
app.py            Flask routes (pages and forms)
db.py             MySQL connection helpers (PyMySQL)
generator.py      Idea bank queries and the optional Gemini AI
stickfigure.py    Stick-figure drawings (SVG for the web, vector for the PDF)
pdf_export.py     Builds the downloadable PDF (fpdf2)
config.py         Settings from environment variables / .env
init_db.py        Creates the tables and loads the idea bank
seed_data.py      Idea bank data (niches, formats, templates, scenes)
sql/schema.sql    CREATE TABLE statements + the summary view
sql/seed.sql      The idea bank as INSERT statements
sql/queries.sql   Sample CRUD, JOIN and aggregate queries
templates/        HTML pages (Jinja2)
static/           CSS, a small JS file and the icon
tests/            Automated tests (pytest)
```

## Run it on your computer
1. Install **Python 3.10+** and **MySQL 8** (or XAMPP's MariaDB).
2. Create a database:
   ```sql
   CREATE DATABASE reelmap CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
3. Copy `.env.example` to `.env` and fill in your MySQL user and password.
4. Install the packages and set up the tables:
   ```
   pip install -r requirements.txt
   python init_db.py
   ```
5. Start the app with `python app.py`, then open http://localhost:5000 and sign up. The first account is the admin.

(Step 4's `python init_db.py` is optional: when the tables are missing, the app creates them on start.)

To run the tests: `pip install pytest`, then `python -m pytest`.

## Put it live for free (Render + TiDB Cloud)
The website runs on **Render** and the MySQL database on **TiDB Cloud Starter**. Both are free and need no card.
See **DEPLOY.md** for the step-by-step guide.
