<div align="center">

# 🗳️ Secure Vote — Online Voting System

A full-stack web application for running secure, role-based online elections — built with Flask and MySQL.

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python\&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Framework-black?logo=flask\&logoColor=white)](https://flask.palletsprojects.com/)
[![MySQL](https://img.shields.io/badge/MySQL-Database-4479A1?logo=mysql\&logoColor=white)](https://www.mysql.com/)
[![Brevo](https://img.shields.io/badge/Email-Brevo-0B996E?logo=brevo\&logoColor=white)](https://www.brevo.com/)
[![Socket.IO](https://img.shields.io/badge/Socket.IO-Realtime-black?logo=socketdotio\&logoColor=white)](https://flask-socketio.readthedocs.io/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](#-license)

[Features](#-features) • [Tech Stack](#-tech-stack) • [Getting Started](#-getting-started) • [Deployment](#-deployment) • [Security](#-security-notes)

</div>

---

## 🌐 Live Demo

**Secure Vote V3:**
https://secure-vote-285s.onrender.com/

You can register a new account or use the demo voter account below.

### 🎯 Demo Account

| Field        | Demo Value                 |
| ------------ | -------------------------- |
| **Role**     | Voter                      |
| **Name**     | Voter                      |
| **Voter ID** | `111`                      |
| **Email**    | `demoproject123@gmail.com` |
| **Password** | `Demo123`                  |

> **Note:** The demo account is provided for testing and demonstration purposes only. Do not use the demo credentials for sensitive or personal information.

---

## 📖 Overview

**Secure Vote V3** is a role-based online voting platform designed to provide a simple and secure digital election experience.

Voters can register, verify their email using a one-time password (OTP), log in securely, participate in active elections, and receive confirmation of their vote.

Administrators can create and manage elections, add candidates, monitor voter activity, and review election results.

The application uses MySQL to store application data and enforces duplicate-vote protection at both the application and database levels.

---

## ✨ Features

| Category                        | Details                                                                         |
| ------------------------------- | ------------------------------------------------------------------------------- |
| 🔐 **Authentication**           | Session-based authentication with separate voter and administrator roles        |
| 🔑 **Password Security**        | Passwords are securely hashed using Werkzeug                                    |
| 📧 **Email OTP**                | One-time verification codes delivered through the Brevo transactional email API |
| 🗳️ **Elections**               | Admins can create, edit, delete, and manage elections                           |
| 👥 **Candidates**               | Candidates can be added individually and managed within elections               |
| ✅ **Duplicate-vote protection** | Application checks plus a database `UNIQUE` constraint prevent multiple votes   |
| 📊 **Election Results**         | Vote totals are displayed for candidates and elections                          |
| 🔔 **Notifications**            | Real-time notifications using Flask-SocketIO                                    |
| 🌗 **Dark Mode**                | User-specific dark-mode preference                                              |
| 🖼️ **Profile Management**      | Users can manage their profile information and password                         |
| 📋 **Voter Records**            | Administrators can review registered voter records                              |
| 📱 **Responsive UI**            | Designed to work across desktop and mobile devices                              |
| 🛡️ **Security-focused V3**     | Updated release focused on a cleaner authentication and deployment experience   |

---

## 🛠️ Tech Stack

| Layer                      | Technology                                 |
| -------------------------- | ------------------------------------------ |
| **Backend**                | Python 3, Flask                            |
| **Realtime Communication** | Flask-SocketIO / Socket.IO                 |
| **Database**               | MySQL                                      |
| **Authentication**         | Flask sessions + Werkzeug password hashing |
| **Email / OTP**            | Brevo Transactional Email API              |
| **Frontend**               | HTML5, CSS3, Vanilla JavaScript            |
| **Templating**             | Jinja2                                     |
| **Deployment**             | Render                                     |
| **Version Control**        | Git + GitHub                               |

Brevo's transactional email API is used for automated emails such as account verification and password-reset messages. Brevo authenticates API requests using an API key and requires a configured sender for transactional messages.

---

## 📁 Project Structure

```text
SecureVote/
├── app.py                         # Flask application, routes and backend logic
├── schema.sql                     # Database schema/reference
├── requirements.txt               # Python dependencies
├── Procfile                       # Production start command
├── runtime.txt                    # Python runtime version
├── templates/                     # Jinja2 HTML templates
│   ├── login.html
│   ├── home.html
│   ├── header.html
│   ├── admin.html
│   ├── Voting.html
│   ├── vote.html
│   ├── results.html
│   └── ...
├── static/                        # CSS, JavaScript and media
├── DEPLOY.md                      # Deployment instructions
└── README.md                      # Project documentation
```

---

# 🚀 Getting Started

## Prerequisites

Before running Secure Vote locally, install:

* Python 3.11+
* MySQL
* Git
* A Brevo account with a configured transactional email sender

Brevo provides an API specifically for transactional emails such as verification messages and password resets.

---

## 📥 Installation

Clone the repository:

```bash
git clone https://github.com/kapilkumawat18/SecureVote-V2-Safety-Test.git
cd SecureVote-V2-Safety-Test
```

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

---

# ⚙️ Configuration

Create your local environment configuration file.

**Never commit your API keys, database passwords, or Flask secret key to GitHub.**

Example:

```env
MYSQL_HOST=localhost
MYSQL_USER=root
MYSQL_PASSWORD=your_mysql_password
MYSQL_DB=online_voting

BREVO_API_KEY=your_brevo_api_key
BREVO_SENDER_EMAIL=your_verified_sender_email
BREVO_SENDER_NAME=Secure Vote

FLASK_SECRET_KEY=your_long_random_secret_key
FLASK_DEBUG=true
```

### Environment Variables

| Variable             | Required | Description                                        |
| -------------------- | -------- | -------------------------------------------------- |
| `MYSQL_HOST`         | ✅        | MySQL database hostname                            |
| `MYSQL_USER`         | ✅        | MySQL database username                            |
| `MYSQL_PASSWORD`     | ✅        | MySQL database password                            |
| `MYSQL_DB`           | ✅        | MySQL database name                                |
| `MYSQL_SSL_CA`       | ⬜        | CA certificate path when the database requires TLS |
| `BREVO_API_KEY`      | ✅        | Secret Brevo API key used for transactional email  |
| `BREVO_SENDER_EMAIL` | ✅        | Verified email sender configured in Brevo          |
| `BREVO_SENDER_NAME`  | ⬜        | Display name used for outgoing emails              |
| `FLASK_SECRET_KEY`   | ✅        | Secret used to sign Flask sessions                 |
| `FLASK_DEBUG`        | ⬜        | Enable Flask development mode locally              |

> ⚠️ **Never publish `BREVO_API_KEY` in this README or commit it to GitHub.**

Brevo's API key is passed as an authentication header when sending transactional emails.

---

# ▶️ Run Locally

Start the application:

```bash
python app.py
```

The application will normally be available at:

```text
http://localhost:5500
```

The application initializes the required database tables when configured to do so by the project.

---

# 📧 Email & OTP

Secure Vote uses **Brevo's transactional email API** for OTP and account-related emails.

Typical email flows include:

* Account verification
* OTP verification
* Password reset
* Other account-related transactional messages

The application communicates with Brevo from the backend rather than exposing the API key to the browser.

A successful Brevo transactional email request returns a message ID that can be used for delivery tracking.

---

# 🗳️ Voting Flow

The general voter flow is:

```text
Register
   ↓
Email Verification
   ↓
Login
   ↓
View Elections
   ↓
Select Election
   ↓
Review Candidates
   ↓
Cast Vote
   ↓
Vote Confirmation
   ↓
View Results
```

The application is designed so that a voter can cast only one vote in an election.

---

# 👨‍💼 Admin Flow

Administrators can:

```text
Admin Login
    ↓
Admin Dashboard
    ↓
Create / Manage Elections
    ↓
Add Candidates
    ↓
Monitor Elections
    ↓
Review Voting Activity
    ↓
View Results
```

Administrative routes require an authenticated administrator session.

---

# ☁️ Deployment

Secure Vote is designed to run as a traditional Flask web application rather than as a serverless frontend.

The production deployment can be hosted on platforms such as **Render**, with MySQL provided by a compatible database service.

Typical production configuration includes:

```text
Render
  │
  ├── Flask application
  │
  ├── Environment variables
  │     ├── Database credentials
  │     ├── Brevo API key
  │     └── Flask secret key
  │
  └── External MySQL database
```

### Production Environment Variables

Configure the following through your hosting provider's environment-variable settings:

```text
MYSQL_HOST
MYSQL_USER
MYSQL_PASSWORD
MYSQL_DB
MYSQL_SSL_CA
BREVO_API_KEY
BREVO_SENDER_EMAIL
BREVO_SENDER_NAME
FLASK_SECRET_KEY
FLASK_DEBUG=false
```

> 🔒 Production secrets should be configured through the hosting provider's secret/environment-variable system rather than committed to the repository.

---

# 🔒 Security Notes

Secure Vote V3 follows several security practices:

### Password protection

Passwords are hashed using Werkzeug's password-hashing functionality rather than being stored as plaintext.

### Session authentication

Authenticated sessions are used to control access to voter and administrator functionality.

### Role-based access

Administrator functionality is protected separately from normal voter functionality.

### Duplicate-vote protection

The application checks whether a voter has already voted, while the database also provides a uniqueness constraint to prevent duplicate votes under concurrent requests.

### API key protection

The Brevo API key is stored server-side and should never be exposed in frontend JavaScript, HTML, or GitHub.

### Environment secrets

Database credentials and application secrets should be supplied through environment variables.

### Email verification

Account-related OTP messages are sent through Brevo's transactional email API rather than exposing email-service credentials to the client.

---

# 🛡️ V3 Release

**Secure Vote V3** represents the current release of the project.

The V3 release focuses on:

* Stable authentication
* Improved login flow
* Reliable OTP/email functionality
* Cleaner user experience
* Role-based access control
* Duplicate-vote protection
* Production deployment readiness
* Security-focused configuration
* Removal of outdated email-service configuration

> **V3 is the recommended version for deployment and demonstration.**

---

# 🗺️ Roadmap

Future improvements may include:

* [ ] Cloud storage for profile images
* [ ] Advanced admin analytics
* [ ] Election turnout statistics
* [ ] Improved audit logging
* [ ] Additional authentication protections
* [ ] Enhanced accessibility
* [ ] Automated security testing
* [ ] Automated deployment pipeline
* [ ] More detailed election reporting

---

# 🤝 Contributing

Secure Vote started as a learning project focused on full-stack development, authentication, databases, and real-time web applications.

Contributions, suggestions, and improvements are welcome.

For larger changes, please open an issue first to discuss the proposed modification.

---

# 📄 License

Licensed under the **MIT License**.

See [`LICENSE`](LICENSE) for the complete license text.

---

<div align="center">

### 🗳️ Secure Vote V3

Built as a learning project to practice full-stack development, authentication, database management, email APIs, and real-time web applications.

**Secure • Simple • Transparent**

</div>
