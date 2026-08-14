# Deploying this app — completely free

## Why not Vercel
Vercel only runs stateless, short-lived serverless functions with a read-only
filesystem. This app needs three things Vercel can't provide: a persistent
MySQL server, a live WebSocket connection for real-time notifications
(`Flask-SocketIO` + `eventlet`), and writable disk for uploaded profile
pictures. It'll build fine on Vercel, then fail on the first real request.

## The $0-forever stack: Render (app) + Aiven (MySQL)

Both have genuine permanent free tiers — no trial credit, no 30-day clock,
no card required.

- **Render free web service**: 750 hrs/month, sleeps after ~15 min idle
  (first visitor after a gap waits ~30-50s for it to wake up — fine for a
  learning project, not for something you want strangers hitting instantly).
- **Aiven free MySQL**: 1 GB storage/RAM, always free, no credit card, no
  time limit. Auto-powers-off after a long stretch of inactivity (you get
  an email first) — logging into the Aiven console wakes it back up.

### 1. Create the free MySQL database (Aiven)
1. Sign up at aiven.io (no card needed) → **Create service → MySQL** → pick
   the **Free** plan → choose a region → Create.
2. Once it's running, open the service's **Overview** page. Note down:
   `Host`, `Port`, `User`, `Password`, `Database name`.
3. On the same page, download the **CA Certificate** — save it as `ca.pem`.
   Aiven requires SSL, which is why this project's `app.py` has an optional
   `MYSQL_SSL_CA` setting built in for exactly this.

### 2. Push this project to GitHub
`otp.env` and `ca.pem` are already in `.gitignore` — your credentials and
cert never get committed.

### 3. Deploy on Render
1. **New → Web Service** → connect your GitHub repo.
2. Build command: `pip install -r requirements.txt`
   Start command: `python app.py`
3. **Environment → Secret Files** → add a file named `ca.pem`, paste in the
   contents of the cert you downloaded from Aiven, mount path `/etc/secrets/ca.pem`.
4. **Environment → Environment Variables** → add:

   ```
   MYSQL_HOST=<Aiven host>
   MYSQL_USER=<Aiven user>
   MYSQL_PASSWORD=<Aiven password>
   MYSQL_DB=<Aiven database name>
   MYSQL_SSL_CA=/etc/secrets/ca.pem

   BREVO_API_KEY=<API key from Brevo → Settings → SMTP & API → API Keys>
   BREVO_SENDER_EMAIL=<a verified sender address in your Brevo account>
   BREVO_SENDER_NAME=Secure Vote
   FLASK_SECRET_KEY=<any long random string — generate with: python -c "import secrets; print(secrets.token_hex(32))">
   FLASK_DEBUG=false
   ```

   **Why not Gmail SMTP anymore:** Render's free/starter web services block
   outbound traffic on the SMTP ports (25/465/587), which is exactly why OTP
   emails were failing with `[Errno 101] Network is unreachable`. Brevo's
   API is a plain HTTPS POST (port 443, always open), so it works from
   Render without any network/plan changes. Sign up free at
   https://www.brevo.com — the free plan covers this project's OTP volume.
   In Brevo, verify a sender email/domain first (Senders & IP → Senders),
   then generate an API key (SMTP & API → API Keys → Generate a new API key)
   and use that as `BREVO_API_KEY`.

5. Deploy. `init_db()` in `app.py` runs `CREATE TABLE IF NOT EXISTS` for
   every table against your fresh Aiven database on first boot — no manual
   SQL needed. `schema.sql` is the same schema for reference.
6. Render gives you a public `https://your-app.onrender.com` URL automatically.

Every step above is free indefinitely, with two honest trade-offs:
- **Cold starts**: ~30-50s wake-up after 15 minutes idle (Render free tier only).
- **Profile picture uploads**: written to local disk, which does not persist
  across Render redeploys on the free tier (no free persistent Volumes).
  Fine for demoing the app; if you want uploads to survive redeploys, that
  needs a cloud storage bucket (Cloudinary has a free tier too) — happy to
  wire that up if you want it.

## If you'd rather trade a few dollars for convenience
Railway (~$1/month after a $5 trial credit) skips step 1 and the SSL setup
entirely — its MySQL plugin is one click and auto-injects credentials
(`MYSQLHOST`, `MYSQLUSER`, `MYSQLPASSWORD`, `MYSQLDATABASE`). Map those to
`MYSQL_HOST` / `MYSQL_USER` / `MYSQL_PASSWORD` / `MYSQL_DB` in your Railway
service's Variables tab, same idea as above but no SSL cert needed.
