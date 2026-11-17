# Going live for free: Render + TiDB Cloud

This guide needs **no credit card**. You need three free accounts:

| Service | What it does | Link |
|---|---|---|
| GitHub | Stores your code | https://github.com |
| TiDB Cloud Starter | The MySQL database, in the cloud | https://tidbcloud.com |
| Render | Runs the Flask website | https://render.com |

At the end your site will be at `https://reelmap-XXXX.onrender.com`.

---

## Step 1: Put the code on GitHub

1. Sign in to GitHub and click **New** (the green button) to create a repository.
2. Name it `reelmap-dbms`. Keep it **Public** (or Private; both work with Render). Do **not** add a README. Click **Create repository**.
3. Upload the code. Pick one way:

   **A. From the website (easiest)**
   1. Unzip `reelmap-dbms.zip` on your computer.
   2. On the new repository page, click **uploading an existing file**.
   3. Open the unzipped `reelmap-dbms` folder, select **everything inside it** and drag it onto the page.
   4. Click **Commit changes**.

   **B. With git, in a terminal inside the unzipped folder**
   ```
   git init
   git add .
   git commit -m "Reelmap DBMS mini project"
   git branch -M main
   git remote add origin https://github.com/YOUR-GITHUB-NAME/reelmap-dbms.git
   git push -u origin main
   ```

Check that `app.py`, `requirements.txt` and the `templates` folder are at the **top level** of the repository, not inside another folder.

> Never upload a `.env` file. It holds passwords. The zip does not include one.

---

## Step 2: Create the free MySQL database (TiDB Cloud Starter)

TiDB Cloud speaks the MySQL language, so the app works with it unchanged.

1. Go to https://tidbcloud.com and sign up (Google or GitHub sign-in is fine).
2. Click **Create Cluster**, choose **Starter** (the free plan), pick the region closest to you (for India: **Mumbai** if offered, else **Singapore**), and click **Create**. It is ready in under a minute.
3. Open the cluster and click **Connect** (top right).
4. In the dialog:
   - **Connection type:** Public
   - **Connect with:** General
   - Click **Generate Password** and **copy the password now**. It is shown only once.
5. Note these four values from the dialog:

   | Dialog shows | Example | You will use it as |
   |---|---|---|
   | HOST | `gateway01.ap-southeast-1.prod.aws.tidbcloud.com` | `MYSQL_HOST` |
   | PORT | `4000` | `MYSQL_PORT` |
   | USERNAME | `3xAbCdEfG.root` (has a prefix and a dot) | `MYSQL_USER` |
   | PASSWORD | the one you just generated | `MYSQL_PASSWORD` |

You do **not** need to create tables. The app creates the `reelmap` database, all 9 tables, the view and the idea bank by itself the first time it starts.

---

## Step 3: Create the website on Render

1. Go to https://render.com and click **Get Started**. Sign up **with GitHub**, so Render can see your repositories.
2. In the Render dashboard click **New +** then **Web Service**.
3. Choose your `reelmap-dbms` repository and click **Connect**.
   (If it is not listed, click **Configure account** and give Render access to it.)
4. Fill in the form:

   | Field | Value |
   |---|---|
   | Name | `reelmap` (this becomes part of the web address) |
   | Language | **Python 3** |
   | Branch | `main` |
   | Region | Singapore (closest to India) |
   | Build Command | `pip install -r requirements.txt` |
   | Start Command | `gunicorn app:app --workers 1 --threads 4 --timeout 60` |
   | Instance Type | **Free** |

5. Scroll to **Environment Variables** and click **Add Environment Variable** for each row:

   | Key | Value |
   |---|---|
   | `SECRET_KEY` | any long random text (see the tip below) |
   | `MYSQL_HOST` | HOST from Step 2 |
   | `MYSQL_PORT` | `4000` |
   | `MYSQL_USER` | USERNAME from Step 2 (with the prefix) |
   | `MYSQL_PASSWORD` | PASSWORD from Step 2 |
   | `MYSQL_DB` | `reelmap` |
   | `MYSQL_SSL` | `true` |
   | `PYTHON_VERSION` | `3.12.8` |
   | `GEMINI_API_KEY` | *(optional)* your key from https://aistudio.google.com/apikey |

   Tip: to make a random `SECRET_KEY`, run this on your computer and paste the output:
   ```
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

6. Click **Deploy Web Service**. Watch the log. After 2 to 4 minutes you should see lines like:
   ```
   No tables found. Creating them now...
   Database 'reelmap' is ready: 10 niches, 8 formats, 45 idea templates, 48 scene templates.
   ==> Your service is live 🎉
   ```

---

## Step 4: Open the site and become the admin

1. Click the address at the top of the Render page, e.g. `https://reelmap-xxxx.onrender.com`.
2. Click **Sign up** and create your account **first**. The first account becomes the **admin** and gets the **Idea bank** page.
3. Make a test plan: **New plan** → topic `home workout`, niche Fitness, style How-To Tutorial → **Get ideas** → pick one → **Build storyboard** → **Download PDF**.

---

## Updating the site later

Change the code, then push to GitHub again (or upload the changed files on the GitHub website). Render notices and redeploys by itself in a few minutes. Your data in TiDB stays as it is.

## Things to know about the free plans

- **Render sleeps after 15 minutes without visitors.** The next visit takes about a minute to wake it up. **Before your presentation, open the site 2 minutes early** and keep the tab open.
- Record IDs in TiDB can jump (for example 1, then 30001). This is normal for TiDB and does not affect the app.
- To start the database again from empty: in TiDB Cloud open **SQL Editor**, run `DROP DATABASE reelmap;`, then in Render click **Manual Deploy → Restart service**. The tables and idea bank are rebuilt on start.

## If something goes wrong

| What you see | What to check |
|---|---|
| Build failed in the Render log | `requirements.txt` must be at the top level of the repository. |
| `Could not check the database: (1045, ... Access denied)` | `MYSQL_USER` must include the prefix (e.g. `3xAbCdEfG.root`) and the password must be exact. Generate a new one in TiDB if unsure. |
| `(2003, ... Can't connect)` or a timeout | `MYSQL_HOST` or `MYSQL_PORT` is wrong (port is `4000`). |
| `Connections using insecure transport are prohibited` | Set `MYSQL_SSL` to `true`. |
| Page says "Database unavailable" | Same checks as above. After fixing a variable, Render restarts by itself. |
| "Ask AI" buttons missing | Normal without `GEMINI_API_KEY`. The idea bank works without it. |

To see the exact error, open your service on Render and click **Logs**.
