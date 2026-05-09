from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse
from http.cookies import SimpleCookie
from pathlib import Path
import hashlib
import hmac
import html
import os
import secrets
import sqlite3
import time


BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "college_events.db"
STATIC_DIR = BASE_DIR / "static"
SECRET = "change-this-secret-for-production"


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password):
    salt = secrets.token_hex(16)
    digest = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${digest}"


def verify_password(password, stored):
    salt, digest = stored.split("$", 1)
    check = hashlib.sha256((salt + password).encode()).hexdigest()
    return hmac.compare_digest(check, digest)


def make_session(user_id):
    value = f"{user_id}:{int(time.time())}"
    sig = hmac.new(SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()
    return f"{value}:{sig}"


def read_session(cookie_header):
    if not cookie_header:
        return None
    cookie = SimpleCookie(cookie_header)
    morsel = cookie.get("cems_session")
    if not morsel:
        return None
    parts = morsel.value.split(":")
    if len(parts) != 3:
        return None
    value = f"{parts[0]}:{parts[1]}"
    expected = hmac.new(SECRET.encode(), value.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, parts[2]):
        return None
    return int(parts[0])


def init_db():
    DB_PATH.parent.mkdir(exist_ok=True)
    with get_db() as db:
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('student','organizer','admin')),
                department TEXT,
                phone TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                category TEXT NOT NULL,
                venue TEXT NOT NULL,
                event_date TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                approval_required INTEGER NOT NULL DEFAULT 0,
                admin_remarks TEXT,
                organizer_id INTEGER NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (organizer_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'Confirmed',
                registered_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, event_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (event_id) REFERENCES events(id)
            );

            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                registration_id INTEGER NOT NULL UNIQUE,
                ticket_code TEXT NOT NULL UNIQUE,
                issued_at TEXT DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'Valid',
                FOREIGN KEY (registration_id) REFERENCES registrations(id)
            );

            CREATE TABLE IF NOT EXISTS schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                session_title TEXT NOT NULL,
                speaker TEXT,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                venue TEXT NOT NULL,
                FOREIGN KEY (event_id) REFERENCES events(id)
            );

            CREATE TABLE IF NOT EXISTS sponsors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                contact_email TEXT,
                phone TEXT,
                sponsorship_level TEXT NOT NULL,
                amount REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS event_sponsors (
                event_id INTEGER NOT NULL,
                sponsor_id INTEGER NOT NULL,
                PRIMARY KEY(event_id, sponsor_id),
                FOREIGN KEY (event_id) REFERENCES events(id),
                FOREIGN KEY (sponsor_id) REFERENCES sponsors(id)
            );
            """
        )
        count = db.execute("SELECT COUNT(*) AS total FROM users").fetchone()["total"]
        if count == 0:
            db.execute(
                "INSERT INTO users(name,email,password_hash,role,department,phone) VALUES(?,?,?,?,?,?)",
                ("Admin User", "admin@college.edu", hash_password("admin123"), "admin", "Administration", "9999999999"),
            )
            db.execute(
                "INSERT INTO users(name,email,password_hash,role,department,phone) VALUES(?,?,?,?,?,?)",
                ("Event Organizer", "organizer@college.edu", hash_password("organizer123"), "organizer", "Computer Science", "8888888888"),
            )
            db.execute(
                "INSERT INTO users(name,email,password_hash,role,department,phone) VALUES(?,?,?,?,?,?)",
                ("Student User", "student@college.edu", hash_password("student123"), "student", "Information Technology", "7777777777"),
            )
            db.execute(
                """
                INSERT INTO events(title,description,category,venue,event_date,start_time,end_time,capacity,status,approval_required,organizer_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "TechFest 2026",
                    "A college technology festival with coding contests, project demos, and expert talks.",
                    "Technical",
                    "Main Auditorium",
                    "2026-08-20",
                    "09:00",
                    "17:00",
                    120,
                    "Approved",
                    0,
                    2,
                ),
            )
            db.execute(
                "INSERT INTO schedules(event_id,session_title,speaker,start_time,end_time,venue) VALUES(?,?,?,?,?,?)",
                (1, "Opening Ceremony", "Principal and Student Council", "09:00", "09:45", "Main Auditorium"),
            )
            db.execute(
                "INSERT INTO sponsors(name,contact_email,phone,sponsorship_level,amount) VALUES(?,?,?,?,?)",
                ("CodeLabs Pvt Ltd", "sponsor@codelabs.test", "9000000000", "Gold", 50000),
            )
            db.execute("INSERT INTO event_sponsors(event_id,sponsor_id) VALUES(?,?)", (1, 1))


def esc(value):
    return html.escape(str(value or ""))


def layout(title, body, user=None, message=""):
    nav = """
    <a href="/">Home</a>
    <a href="/events">Events</a>
    """
    if user:
        nav += '<a href="/dashboard">Dashboard</a>'
        if user["role"] == "admin":
            nav += '<a href="/admin/events">Admin</a>'
        if user["role"] == "organizer":
            nav += '<a href="/organizer/events">Organizer</a>'
        nav += '<a href="/logout">Logout</a>'
    else:
        nav += '<a href="/login">Login</a><a href="/register">Register</a>'
    banner = f'<div class="flash">{esc(message)}</div>' if message else ""
    return f"""<!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{esc(title)} | College Event Management</title>
        <link rel="stylesheet" href="/static/style.css">
    </head>
    <body>
        <header>
            <div>
                <h1>College Event Management System</h1>
                <p>Registration, ticketing, approvals, schedules, and sponsors</p>
            </div>
            <nav>{nav}</nav>
        </header>
        <main>
            {banner}
            {body}
        </main>
    </body>
    </html>"""


def form_value(data, name, default=""):
    return data.get(name, [default])[0].strip()


class App(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            self.route_get()
        except Exception as exc:
            self.error_page(500, str(exc))

    def do_POST(self):
        try:
            self.route_post()
        except Exception as exc:
            self.error_page(500, str(exc))

    def current_user(self):
        user_id = read_session(self.headers.get("Cookie"))
        if not user_id:
            return None
        with get_db() as db:
            return db.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()

    def send_html(self, content, status=200, cookie=None):
        encoded = content.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(encoded)

    def redirect(self, path, cookie=None):
        self.send_response(303)
        self.send_header("Location", path)
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def read_form(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return parse_qs(raw)

    def require_user(self, roles=None):
        user = self.current_user()
        if not user:
            self.redirect("/login")
            return None
        if roles and user["role"] not in roles:
            self.error_page(403, "You do not have permission to open this page.")
            return None
        return user

    def route_get(self):
        path = urlparse(self.path).path
        if path.startswith("/static/"):
            return self.static_file(path)
        user = self.current_user()
        if path == "/":
            return self.home(user)
        if path == "/login":
            return self.login_page(user)
        if path == "/register":
            return self.register_page(user)
        if path == "/logout":
            return self.redirect("/", "cems_session=; Path=/; Max-Age=0; HttpOnly")
        if path == "/dashboard":
            return self.dashboard()
        if path == "/events":
            return self.events_page(user)
        if path.startswith("/events/"):
            return self.event_detail(path, user)
        if path == "/organizer/events":
            return self.organizer_events()
        if path == "/admin/events":
            return self.admin_events()
        if path == "/admin/registrations":
            return self.admin_registrations()
        if path == "/admin/schedules":
            return self.admin_schedules()
        if path == "/admin/sponsors":
            return self.admin_sponsors()
        if path.startswith("/ticket/"):
            return self.ticket_page(path)
        return self.error_page(404, "Page not found.")

    def route_post(self):
        path = urlparse(self.path).path
        if path == "/login":
            return self.login_action()
        if path == "/register":
            return self.register_action()
        if path == "/events/register":
            return self.register_event()
        if path == "/events/cancel":
            return self.cancel_registration()
        if path == "/organizer/events":
            return self.create_event()
        if path == "/admin/event-status":
            return self.update_event_status()
        if path == "/admin/registration-status":
            return self.update_registration_status()
        if path == "/admin/schedules":
            return self.add_schedule()
        if path == "/admin/sponsors":
            return self.add_sponsor()
        if path == "/admin/link-sponsor":
            return self.link_sponsor()
        return self.error_page(404, "Action not found.")

    def static_file(self, path):
        name = path.replace("/static/", "", 1)
        file_path = (STATIC_DIR / name).resolve()
        if not str(file_path).startswith(str(STATIC_DIR.resolve())) or not file_path.exists():
            return self.error_page(404, "Static file not found.")
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/css; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def home(self, user):
        with get_db() as db:
            total_events = db.execute("SELECT COUNT(*) total FROM events WHERE status='Approved'").fetchone()["total"]
            total_regs = db.execute("SELECT COUNT(*) total FROM registrations WHERE status IN ('Confirmed','Pending')").fetchone()["total"]
            sponsors = db.execute("SELECT COUNT(*) total FROM sponsors").fetchone()["total"]
        body = f"""
        <section class="hero">
            <div>
                <h2>Manage every college event from proposal to entry gate.</h2>
                <p>Students register, organizers submit events, and admins control approvals, schedules, sponsors, and tickets.</p>
                <div class="actions">
                    <a class="button" href="/events">Browse Events</a>
                    <a class="button ghost" href="/login">Login</a>
                </div>
            </div>
            <div class="stats">
                <span><strong>{total_events}</strong> approved events</span>
                <span><strong>{total_regs}</strong> registrations</span>
                <span><strong>{sponsors}</strong> sponsors</span>
            </div>
        </section>
        <section class="grid three">
            <article><h3>Student</h3><p>Browse events, register, cancel, and view tickets.</p></article>
            <article><h3>Organizer</h3><p>Submit event proposals with venue, category, date, and capacity.</p></article>
            <article><h3>Admin</h3><p>Approve events, manage registrations, create schedules, and add sponsors.</p></article>
        </section>
        """
        return self.send_html(layout("Home", body, user))

    def login_page(self, user, message=""):
        if user:
            return self.redirect("/dashboard")
        body = """
        <section class="panel narrow">
            <h2>Login</h2>
            <form method="post" action="/login">
                <label>Email <input name="email" type="email" required></label>
                <label>Password <input name="password" type="password" required></label>
                <button type="submit">Login</button>
            </form>
            <p class="muted">Demo accounts: admin@college.edu/admin123, organizer@college.edu/organizer123, student@college.edu/student123</p>
        </section>
        """
        return self.send_html(layout("Login", body, None, message))

    def register_page(self, user, message=""):
        if user:
            return self.redirect("/dashboard")
        body = """
        <section class="panel narrow">
            <h2>Create Student Account</h2>
            <form method="post" action="/register">
                <label>Name <input name="name" required></label>
                <label>Email <input name="email" type="email" required></label>
                <label>Password <input name="password" type="password" required minlength="6"></label>
                <label>Department <input name="department"></label>
                <label>Phone <input name="phone"></label>
                <button type="submit">Register</button>
            </form>
        </section>
        """
        return self.send_html(layout("Register", body, None, message))

    def dashboard(self):
        user = self.require_user()
        if not user:
            return
        if user["role"] == "student":
            with get_db() as db:
                rows = db.execute(
                    """
                    SELECT r.*, e.title, e.event_date, e.venue, t.ticket_code
                    FROM registrations r
                    JOIN events e ON e.id=r.event_id
                    LEFT JOIN tickets t ON t.registration_id=r.id
                    WHERE r.user_id=?
                    ORDER BY r.registered_at DESC
                    """,
                    (user["id"],),
                ).fetchall()
            cards = "".join(
                f"""<article>
                    <h3>{esc(row['title'])}</h3>
                    <p>{esc(row['event_date'])} at {esc(row['venue'])}</p>
                    <p><span class="badge">{esc(row['status'])}</span></p>
                    {f'<a class="button small" href="/ticket/{row["id"]}">View Ticket</a>' if row["ticket_code"] else ''}
                </article>"""
                for row in rows
            ) or "<p>No registrations yet.</p>"
            body = f"""
            <div class="between dashboard-head">
                <h2>Student Dashboard</h2>
                <a class="button" href="/events">Apply for Registration</a>
            </div>
            <section class='grid'>{cards}</section>
            """
        elif user["role"] == "organizer":
            body = "<h2>Organizer Dashboard</h2><p>Submit and track your event proposals.</p><a class='button' href='/organizer/events'>Manage My Events</a>"
        else:
            body = """
            <h2>Admin Dashboard</h2>
            <section class="grid three">
                <a class="tile" href="/admin/events">Event Approvals</a>
                <a class="tile" href="/admin/registrations">Registration Approvals</a>
                <a class="tile" href="/admin/schedules">Schedules</a>
                <a class="tile" href="/admin/sponsors">Sponsors</a>
            </section>
            """
        return self.send_html(layout("Dashboard", body, user))

    def events_page(self, user):
        with get_db() as db:
            events = db.execute(
                """
                SELECT e.*, u.name organizer,
                (SELECT COUNT(*) FROM registrations r WHERE r.event_id=e.id AND r.status IN ('Confirmed','Pending')) registrations
                FROM events e JOIN users u ON u.id=e.organizer_id
                WHERE e.status='Approved'
                ORDER BY e.event_date, e.start_time
                """
            ).fetchall()
        cards = ""
        for event in events:
            left = max(event["capacity"] - event["registrations"], 0)
            cards += f"""
            <article>
                <div class="between"><h3>{esc(event['title'])}</h3><span class="badge">{esc(event['category'])}</span></div>
                <p>{esc(event['description'])}</p>
                <p><strong>{esc(event['event_date'])}</strong> {esc(event['start_time'])}-{esc(event['end_time'])} | {esc(event['venue'])}</p>
                <p>{left} of {event['capacity']} seats available</p>
                <a class="button small" href="/events/{event['id']}">View Details</a>
            </article>
            """
        body = f"<h2>Approved Events</h2><section class='grid'>{cards or '<p>No approved events available.</p>'}</section>"
        return self.send_html(layout("Events", body, user))

    def event_detail(self, path, user):
        event_id = path.rsplit("/", 1)[-1]
        with get_db() as db:
            event = db.execute("SELECT e.*, u.name organizer FROM events e JOIN users u ON u.id=e.organizer_id WHERE e.id=?", (event_id,)).fetchone()
            if not event or event["status"] != "Approved":
                return self.error_page(404, "Event not found.")
            schedules = db.execute("SELECT * FROM schedules WHERE event_id=? ORDER BY start_time", (event_id,)).fetchall()
            sponsors = db.execute(
                "SELECT s.* FROM sponsors s JOIN event_sponsors es ON es.sponsor_id=s.id WHERE es.event_id=?",
                (event_id,),
            ).fetchall()
            registrations = db.execute("SELECT COUNT(*) total FROM registrations WHERE event_id=? AND status IN ('Confirmed','Pending')", (event_id,)).fetchone()["total"]
            existing = None
            if user:
                existing = db.execute("SELECT * FROM registrations WHERE event_id=? AND user_id=?", (event_id, user["id"])).fetchone()
        left = max(event["capacity"] - registrations, 0)
        schedule_html = "".join(f"<li>{esc(s['start_time'])}-{esc(s['end_time'])}: {esc(s['session_title'])} ({esc(s['venue'])})</li>" for s in schedules) or "<li>No schedule added yet.</li>"
        sponsor_html = "".join(f"<li>{esc(s['name'])} - {esc(s['sponsorship_level'])}</li>" for s in sponsors) or "<li>No sponsors linked yet.</li>"
        action = ""
        if user and user["role"] == "student":
            if existing and existing["status"] != "Cancelled":
                action = f"""
                <p>Your registration status: <span class="badge">{esc(existing['status'])}</span></p>
                <form method="post" action="/events/cancel"><input type="hidden" name="event_id" value="{event_id}"><button class="danger">Cancel Registration</button></form>
                """
            elif left > 0:
                action = f"""
                <form method="post" action="/events/register">
                    <input type="hidden" name="event_id" value="{event_id}">
                    <button>Apply for Registration</button>
                </form>
                """
            else:
                action = "<p class='badge'>House full</p>"
        elif not user:
            action = '<a class="button" href="/login">Login to Register</a>'
        body = f"""
        <section class="panel">
            <div class="between"><h2>{esc(event['title'])}</h2><span class="badge">{esc(event['category'])}</span></div>
            <p>{esc(event['description'])}</p>
            <p><strong>Date:</strong> {esc(event['event_date'])} | <strong>Time:</strong> {esc(event['start_time'])}-{esc(event['end_time'])}</p>
            <p><strong>Venue:</strong> {esc(event['venue'])} | <strong>Organizer:</strong> {esc(event['organizer'])}</p>
            <p><strong>Seats:</strong> {left} available out of {event['capacity']}</p>
            {action}
        </section>
        <section class="grid two">
            <article><h3>Schedule</h3><ul>{schedule_html}</ul></article>
            <article><h3>Sponsors</h3><ul>{sponsor_html}</ul></article>
        </section>
        """
        return self.send_html(layout(event["title"], body, user))

    def organizer_events(self):
        user = self.require_user(["organizer"])
        if not user:
            return
        with get_db() as db:
            rows = db.execute("SELECT * FROM events WHERE organizer_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
        event_rows = "".join(
            f"<tr><td>{esc(r['title'])}</td><td>{esc(r['event_date'])}</td><td>{esc(r['venue'])}</td><td><span class='badge'>{esc(r['status'])}</span></td><td>{esc(r['admin_remarks'])}</td></tr>"
            for r in rows
        )
        body = f"""
        <section class="panel">
            <h2>Submit Event Proposal</h2>
            <form class="wide" method="post" action="/organizer/events">
                <label>Title <input name="title" required></label>
                <label>Category <input name="category" required></label>
                <label>Venue <input name="venue" required></label>
                <label>Date <input name="event_date" type="date" required></label>
                <label>Start Time <input name="start_time" type="time" required></label>
                <label>End Time <input name="end_time" type="time" required></label>
                <label>Capacity <input name="capacity" type="number" min="1" required></label>
                <label>Registration Needs Admin Approval
                    <select name="approval_required"><option value="0">No</option><option value="1">Yes</option></select>
                </label>
                <label class="full">Description <textarea name="description" required></textarea></label>
                <button type="submit">Submit for Approval</button>
            </form>
        </section>
        <section class="panel">
            <h2>My Events</h2>
            <table><thead><tr><th>Title</th><th>Date</th><th>Venue</th><th>Status</th><th>Remarks</th></tr></thead><tbody>{event_rows}</tbody></table>
        </section>
        """
        return self.send_html(layout("Organizer Events", body, user))

    def admin_events(self):
        user = self.require_user(["admin"])
        if not user:
            return
        with get_db() as db:
            rows = db.execute("SELECT e.*, u.name organizer FROM events e JOIN users u ON u.id=e.organizer_id ORDER BY e.created_at DESC").fetchall()
        table = ""
        for r in rows:
            table += f"""
            <tr>
                <td>{esc(r['title'])}<br><small>{esc(r['description'])}</small></td>
                <td>{esc(r['organizer'])}</td><td>{esc(r['event_date'])}</td><td>{esc(r['capacity'])}</td>
                <td><span class="badge">{esc(r['status'])}</span></td>
                <td>
                    <form class="inline" method="post" action="/admin/event-status">
                        <input type="hidden" name="event_id" value="{r['id']}">
                        <input name="remarks" placeholder="Remarks">
                        <button name="status" value="Approved">Approve</button>
                        <button class="danger" name="status" value="Rejected">Reject</button>
                    </form>
                </td>
            </tr>"""
        body = f"<section class='panel'><h2>Admin Event Approvals</h2><table><thead><tr><th>Event</th><th>Organizer</th><th>Date</th><th>Capacity</th><th>Status</th><th>Action</th></tr></thead><tbody>{table}</tbody></table></section>"
        return self.send_html(layout("Admin Events", body, user))

    def admin_registrations(self):
        user = self.require_user(["admin"])
        if not user:
            return
        with get_db() as db:
            rows = db.execute(
                """
                SELECT r.*, u.name student, u.email, e.title event_title
                FROM registrations r JOIN users u ON u.id=r.user_id JOIN events e ON e.id=r.event_id
                ORDER BY r.registered_at DESC
                """
            ).fetchall()
        table = ""
        for r in rows:
            table += f"""
            <tr><td>{esc(r['student'])}<br><small>{esc(r['email'])}</small></td><td>{esc(r['event_title'])}</td><td><span class="badge">{esc(r['status'])}</span></td>
            <td>
                <form class="inline" method="post" action="/admin/registration-status">
                    <input type="hidden" name="registration_id" value="{r['id']}">
                    <button name="status" value="Confirmed">Approve</button>
                    <button class="danger" name="status" value="Rejected">Reject</button>
                </form>
            </td></tr>"""
        body = f"<section class='panel'><h2>Registration Approvals</h2><table><thead><tr><th>Student</th><th>Event</th><th>Status</th><th>Action</th></tr></thead><tbody>{table}</tbody></table></section>"
        return self.send_html(layout("Admin Registrations", body, user))

    def admin_schedules(self):
        user = self.require_user(["admin"])
        if not user:
            return
        with get_db() as db:
            events = db.execute("SELECT id,title FROM events WHERE status='Approved' ORDER BY title").fetchall()
            schedules = db.execute("SELECT s.*, e.title FROM schedules s JOIN events e ON e.id=s.event_id ORDER BY e.title, s.start_time").fetchall()
        options = "".join(f"<option value='{e['id']}'>{esc(e['title'])}</option>" for e in events)
        rows = "".join(f"<tr><td>{esc(s['title'])}</td><td>{esc(s['session_title'])}</td><td>{esc(s['speaker'])}</td><td>{esc(s['start_time'])}-{esc(s['end_time'])}</td><td>{esc(s['venue'])}</td></tr>" for s in schedules)
        body = f"""
        <section class="panel">
            <h2>Add Schedule Session</h2>
            <form class="wide" method="post" action="/admin/schedules">
                <label>Event <select name="event_id" required>{options}</select></label>
                <label>Session Title <input name="session_title" required></label>
                <label>Speaker/Host <input name="speaker"></label>
                <label>Start Time <input name="start_time" type="time" required></label>
                <label>End Time <input name="end_time" type="time" required></label>
                <label>Venue <input name="venue" required></label>
                <button type="submit">Add Session</button>
            </form>
        </section>
        <section class="panel"><h2>Schedules</h2><table><thead><tr><th>Event</th><th>Session</th><th>Speaker</th><th>Time</th><th>Venue</th></tr></thead><tbody>{rows}</tbody></table></section>
        """
        return self.send_html(layout("Schedules", body, user))

    def admin_sponsors(self):
        user = self.require_user(["admin"])
        if not user:
            return
        with get_db() as db:
            events = db.execute("SELECT id,title FROM events WHERE status='Approved' ORDER BY title").fetchall()
            sponsors = db.execute("SELECT * FROM sponsors ORDER BY name").fetchall()
        event_options = "".join(f"<option value='{e['id']}'>{esc(e['title'])}</option>" for e in events)
        sponsor_options = "".join(f"<option value='{s['id']}'>{esc(s['name'])}</option>" for s in sponsors)
        sponsor_rows = "".join(f"<tr><td>{esc(s['name'])}</td><td>{esc(s['sponsorship_level'])}</td><td>{esc(s['amount'])}</td><td>{esc(s['contact_email'])}</td></tr>" for s in sponsors)
        body = f"""
        <section class="grid two">
            <article>
                <h2>Add Sponsor</h2>
                <form method="post" action="/admin/sponsors">
                    <label>Name <input name="name" required></label>
                    <label>Email <input name="contact_email" type="email"></label>
                    <label>Phone <input name="phone"></label>
                    <label>Level <select name="sponsorship_level"><option>Gold</option><option>Silver</option><option>Bronze</option><option>Partner</option></select></label>
                    <label>Amount <input name="amount" type="number" min="0" step="100"></label>
                    <button type="submit">Add Sponsor</button>
                </form>
            </article>
            <article>
                <h2>Link Sponsor to Event</h2>
                <form method="post" action="/admin/link-sponsor">
                    <label>Event <select name="event_id">{event_options}</select></label>
                    <label>Sponsor <select name="sponsor_id">{sponsor_options}</select></label>
                    <button type="submit">Link Sponsor</button>
                </form>
            </article>
        </section>
        <section class="panel"><h2>Sponsors</h2><table><thead><tr><th>Name</th><th>Level</th><th>Amount</th><th>Email</th></tr></thead><tbody>{sponsor_rows}</tbody></table></section>
        """
        return self.send_html(layout("Sponsors", body, user))

    def ticket_page(self, path):
        user = self.require_user(["student", "admin"])
        if not user:
            return
        reg_id = path.rsplit("/", 1)[-1]
        with get_db() as db:
            row = db.execute(
                """
                SELECT r.*, u.name student, u.email, e.title, e.event_date, e.start_time, e.venue, t.ticket_code, t.status ticket_status
                FROM registrations r
                JOIN users u ON u.id=r.user_id
                JOIN events e ON e.id=r.event_id
                JOIN tickets t ON t.registration_id=r.id
                WHERE r.id=?
                """,
                (reg_id,),
            ).fetchone()
        if not row or (user["role"] == "student" and row["user_id"] != user["id"]):
            return self.error_page(404, "Ticket not found.")
        qr = "".join("<span></span>" for _ in range(64))
        body = f"""
        <section class="ticket">
            <div>
                <h2>{esc(row['title'])}</h2>
                <p><strong>Student:</strong> {esc(row['student'])}</p>
                <p><strong>Email:</strong> {esc(row['email'])}</p>
                <p><strong>Date:</strong> {esc(row['event_date'])} {esc(row['start_time'])}</p>
                <p><strong>Venue:</strong> {esc(row['venue'])}</p>
                <p><strong>Ticket Code:</strong> {esc(row['ticket_code'])}</p>
                <p><span class="badge">{esc(row['ticket_status'])}</span></p>
            </div>
            <div class="qr">{qr}</div>
        </section>
        <button onclick="window.print()">Print Ticket</button>
        """
        return self.send_html(layout("Ticket", body, user))

    def login_action(self):
        data = self.read_form()
        email = form_value(data, "email").lower()
        password = form_value(data, "password")
        with get_db() as db:
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not user or not verify_password(password, user["password_hash"]):
            return self.login_page(None, "Invalid email or password.")
        return self.redirect("/dashboard", f"cems_session={make_session(user['id'])}; Path=/; HttpOnly; SameSite=Lax")

    def register_action(self):
        data = self.read_form()
        try:
            with get_db() as db:
                db.execute(
                    "INSERT INTO users(name,email,password_hash,role,department,phone) VALUES(?,?,?,?,?,?)",
                    (
                        form_value(data, "name"),
                        form_value(data, "email").lower(),
                        hash_password(form_value(data, "password")),
                        "student",
                        form_value(data, "department"),
                        form_value(data, "phone"),
                    ),
                )
            return self.login_page(None, "Account created. Please login.")
        except sqlite3.IntegrityError:
            return self.register_page(None, "Email already exists.")

    def register_event(self):
        user = self.require_user(["student"])
        if not user:
            return
        data = self.read_form()
        event_id = form_value(data, "event_id")
        with get_db() as db:
            event = db.execute("SELECT * FROM events WHERE id=? AND status='Approved'", (event_id,)).fetchone()
            if not event:
                return self.error_page(404, "Event not found.")
            existing = db.execute("SELECT * FROM registrations WHERE event_id=? AND user_id=?", (event_id, user["id"])).fetchone()
            if existing and existing["status"] != "Cancelled":
                return self.redirect("/dashboard")
            taken = db.execute("SELECT COUNT(*) total FROM registrations WHERE event_id=? AND status IN ('Confirmed','Pending')", (event_id,)).fetchone()["total"]
            if taken >= event["capacity"]:
                return self.redirect(f"/events/{event_id}")
            status = "Pending" if event["approval_required"] else "Confirmed"
            if existing:
                db.execute(
                    "UPDATE registrations SET status=?, registered_at=CURRENT_TIMESTAMP WHERE id=?",
                    (status, existing["id"]),
                )
                registration_id = existing["id"]
            else:
                cur = db.execute(
                    "INSERT INTO registrations(user_id,event_id,status) VALUES(?,?,?)",
                    (user["id"], event_id, status),
                )
                registration_id = cur.lastrowid
            if status == "Confirmed":
                self.issue_ticket(db, registration_id)
        return self.redirect("/dashboard")

    def cancel_registration(self):
        user = self.require_user(["student"])
        if not user:
            return
        event_id = form_value(self.read_form(), "event_id")
        with get_db() as db:
            reg = db.execute("SELECT * FROM registrations WHERE user_id=? AND event_id=?", (user["id"], event_id)).fetchone()
            if reg:
                db.execute("UPDATE registrations SET status='Cancelled' WHERE id=?", (reg["id"],))
                db.execute("UPDATE tickets SET status='Cancelled' WHERE registration_id=?", (reg["id"],))
        return self.redirect(f"/events/{event_id}")

    def create_event(self):
        user = self.require_user(["organizer"])
        if not user:
            return
        data = self.read_form()
        with get_db() as db:
            db.execute(
                """
                INSERT INTO events(title,description,category,venue,event_date,start_time,end_time,capacity,approval_required,organizer_id)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    form_value(data, "title"),
                    form_value(data, "description"),
                    form_value(data, "category"),
                    form_value(data, "venue"),
                    form_value(data, "event_date"),
                    form_value(data, "start_time"),
                    form_value(data, "end_time"),
                    int(form_value(data, "capacity", "1")),
                    int(form_value(data, "approval_required", "0")),
                    user["id"],
                ),
            )
        return self.redirect("/organizer/events")

    def update_event_status(self):
        user = self.require_user(["admin"])
        if not user:
            return
        data = self.read_form()
        with get_db() as db:
            db.execute(
                "UPDATE events SET status=?, admin_remarks=? WHERE id=?",
                (form_value(data, "status"), form_value(data, "remarks"), form_value(data, "event_id")),
            )
        return self.redirect("/admin/events")

    def update_registration_status(self):
        user = self.require_user(["admin"])
        if not user:
            return
        data = self.read_form()
        reg_id = form_value(data, "registration_id")
        status = form_value(data, "status")
        with get_db() as db:
            db.execute("UPDATE registrations SET status=? WHERE id=?", (status, reg_id))
            if status == "Confirmed":
                self.issue_ticket(db, reg_id)
            elif status == "Rejected":
                db.execute("UPDATE tickets SET status='Cancelled' WHERE registration_id=?", (reg_id,))
        return self.redirect("/admin/registrations")

    def add_schedule(self):
        user = self.require_user(["admin"])
        if not user:
            return
        data = self.read_form()
        with get_db() as db:
            db.execute(
                "INSERT INTO schedules(event_id,session_title,speaker,start_time,end_time,venue) VALUES(?,?,?,?,?,?)",
                (
                    form_value(data, "event_id"),
                    form_value(data, "session_title"),
                    form_value(data, "speaker"),
                    form_value(data, "start_time"),
                    form_value(data, "end_time"),
                    form_value(data, "venue"),
                ),
            )
        return self.redirect("/admin/schedules")

    def add_sponsor(self):
        user = self.require_user(["admin"])
        if not user:
            return
        data = self.read_form()
        with get_db() as db:
            db.execute(
                "INSERT INTO sponsors(name,contact_email,phone,sponsorship_level,amount) VALUES(?,?,?,?,?)",
                (
                    form_value(data, "name"),
                    form_value(data, "contact_email"),
                    form_value(data, "phone"),
                    form_value(data, "sponsorship_level"),
                    float(form_value(data, "amount", "0") or 0),
                ),
            )
        return self.redirect("/admin/sponsors")

    def link_sponsor(self):
        user = self.require_user(["admin"])
        if not user:
            return
        data = self.read_form()
        with get_db() as db:
            db.execute(
                "INSERT OR IGNORE INTO event_sponsors(event_id,sponsor_id) VALUES(?,?)",
                (form_value(data, "event_id"), form_value(data, "sponsor_id")),
            )
        return self.redirect("/admin/sponsors")

    def issue_ticket(self, db, registration_id):
        existing = db.execute("SELECT id FROM tickets WHERE registration_id=?", (registration_id,)).fetchone()
        if existing:
            db.execute("UPDATE tickets SET status='Valid' WHERE registration_id=?", (registration_id,))
            return
        code = "CEMS-" + secrets.token_hex(4).upper()
        db.execute("INSERT INTO tickets(registration_id,ticket_code,status) VALUES(?,?,?)", (registration_id, code, "Valid"))

    def error_page(self, status, message):
        self.send_html(layout(f"Error {status}", f"<section class='panel'><h2>Error {status}</h2><p>{esc(message)}</p></section>", self.current_user()), status)


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "8000"))
    server = HTTPServer(("0.0.0.0", port), App)
    print(f"College Event Management System running on port {port}")
    server.serve_forever()
