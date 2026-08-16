<div align="center">

# 🗳️ Secure Vote — Online Voting System

A full-stack web application for running secure, role-based online elections — built with Flask and MySQL.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Framework-black?logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![MySQL](https://img.shields.io/badge/MySQL-Database-4479A1?logo=mysql&logoColor=white)](https://www.mysql.com/)
[![Socket.IO](https://img.shields.io/badge/Socket.IO-Realtime-black?logo=socketdotio&logoColor=white)](https://flask-socketio.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#license)

[Features](#-features) • [Tech Stack](#-tech-stack) • [Getting Started](#-getting-started) • [Deployment](#-deployment) • [Security](#-security-notes)

</div>

---
Live Demo : [https://online-voting-system.com/](https://online-voting-system-5dvv.onrender.com) <br>
For Demo Use : <br>
Role: Voter <br>
Name : Voter <br>
Voter Id : 111<br>
Email : demoproject123@gmail.com <br>
Password : Demo123 <br>

## 📖 Overview

Secure Vote is a role-based online voting platform. Voters register, verify
their email with a one-time code, and cast exactly one vote per election.
Admins create and manage elections, add candidates, and monitor live
results — all backed by a MySQL schema that enforces "one vote per
election" at the database level, not just in application code.

## ✨ Features

| Category | Details |
|---|---|
| 🔐 **Authentication** | Session-based login, hashed passwords (Werkzeug), separate voter/admin roles |
| 📧 **Email OTP** | One-time codes for registration and password reset, sent via Gmail SMTP |
| 🗳️ **Elections** | Admins create, edit, delete elections; track status (Upcoming / Active / Completed) |
| 👥 **Candidates** | Add individually or in bulk, linked to an election |
| ✅ **Duplicate-vote protection** | `UNIQUE (user_id, election_id)` DB constraint backs up the application check — safe even under a race condition |
| 📊 **Live results** | Real-time vote tallies per candidate |
| 🔔 **Notifications** | Real-time push via WebSockets (Flask-SocketIO) for new elections, deadlines, vote confirmations |
| 🌗 **Dark mode** | Per-user preference, persisted to the database |
| 🖼️ **Profile management** | Update name, profile picture, password |
| 📋 **Voter records (admin)** | Browse registered voters and their details |

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3, Flask, Flask-SocketIO (eventlet) |
| **Database** | MySQL (via Flask-MySQLdb) |
| **Auth** | Server-side sessions, Werkzeug password hashing, email OTP |
| **Frontend** | HTML, CSS, vanilla JavaScript |
| **Email** | Gmail SMTP |
| **Deployment** | Render / Railway (see [Deployment](#-deployment)) |

## 📁 Project Structure
Online_Voting_System/
├── app.py # Routes, auth, DB logic, notifications, WebSocket events <br>
├── schema.sql # Database schema (reference — auto-created by app.py on first run) <br>
├── requirements.txt # Python dependencies <br>
├── Procfile # Start command for Railway/Render <br>
├── runtime.txt # Python version pin <br>
├── otp.env # Local secrets — MySQL & Gmail credentials (gitignored) <br>
├── templates/ # Jinja2 HTML templates <br>
├── static/ # CSS, JS, uploaded profile pictures <br>
├── DEPLOY.md # Step-by-step free deployment guide <br>
└── README.md  <br>

## 🚀 Getting Started

### Prerequisites
- Python 3.11+
- A running MySQL server
- A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833) enabled (for OTP emails)

### Installation

```bash
git clone https://github.com/<your-username>/<your-repo>.git
cd Online_Voting_System
pip install -r requirements.txt
```

### Configuration

Create an `otp.env` file in the project root — it's gitignored, so your
credentials never get committed:

```env
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DB=online_voting

GMAIL_USER=your_email@gmail.com
GMAIL_PASS=your_gmail_app_password

FLASK_SECRET_KEY=some_long_random_string
FLASK_DEBUG=true
```

| Variable | Required | Description |
|---|---|---|
| `MYSQL_HOST` | ✅ | MySQL server hostname |
| `MYSQL_USER` | ✅ | MySQL username |
| `MYSQL_PASSWORD` | ✅ | MySQL password |
| `MYSQL_DB` | ✅ | Database name |
| `MYSQL_SSL_CA` | ⬜ | Path to a CA cert, only needed for hosts that require TLS (e.g. Aiven) |
| `GMAIL_USER` | ✅ | Gmail address used to send OTP emails |
| `GMAIL_PASS` | ✅ | Gmail App Password (not your account password) |
| `FLASK_SECRET_KEY` | ✅ | Any long random string, used to sign session cookies |
| `FLASK_DEBUG` | ⬜ | `true` for local development, `false` in production |

### Run it

```bash
python app.py
```

On first run, `init_db()` automatically creates every table (`users`,
`elections`, `candidates`, `votes`, `notifications`) — no manual SQL needed.
The app runs at **http://localhost:5500**.

## ☁️ Deployment

Full step-by-step instructions live in [`DEPLOY.md`](DEPLOY.md), including
a completely free path (Render + Aiven MySQL — no credit card, no expiry)
and a paid-but-simpler alternative (Railway).

> **Note:** This app depends on a persistent MySQL connection, live
> WebSockets, and local file storage — it is **not compatible with
> serverless platforms like Vercel**. `DEPLOY.md` explains why and what
> to use instead.

## 🔒 Security Notes

- Passwords are hashed with `werkzeug.security.generate_password_hash` — never stored in plaintext.
- Every admin-only route requires an authenticated admin session (`@admin_required`).
- Duplicate voting is blocked both at the application level and by a database `UNIQUE` constraint.
- All credentials are read from environment variables — nothing is hardcoded in source.

## 🗺️ Roadmap

- [ ] Move profile picture storage to a cloud bucket (Cloudinary/S3) for redeploy-safe persistence
- [ ] Add a formal foreign key from `candidates.voterId` to `users.voterId`
- [ ] Admin analytics dashboard (turnout %, per-election breakdowns)

## 🤝 Contributing

This started as a learning project. Issues and pull requests are welcome if
you'd like to extend it — please open an issue first to discuss any larger
changes.

## 📄 License

Licensed under the [MIT License](LICENSE) — feel free to use this project
as a learning reference or a starting point for your own.

---

<div align="center">

Built as a learning project to practice full-stack development, authentication, and real-time features.

</div>
