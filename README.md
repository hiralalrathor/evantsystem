# College Event Management System

This is a complete college event registration and ticketing system built with Python, SQLite, HTML, and CSS.

## Features

- Student registration and login
- Student, organizer, and admin profile editing
- Organizer event proposal submission
- Organizer optional event picture upload or picture URL option
- Organizer-controlled event approval: auto-publish or send to admin
- Admin event approval and rejection
- Approved event listing
- Student event registration
- Student cancellation within 1 hour of registration
- Student and organizer help chatbot
- Automatic ticket generation
- Printable ticket page
- Admin registration approval for restricted events
- Schedule management
- Sponsor management and event-sponsor linking

## Project Structure

```text
college-event-management-system/
  app.py
  README.md
  runtime.txt
  data/
    college_events.db      created automatically when app starts
  static/
    style.css
    uploads/               uploaded event images are saved here
```

## Requirements

- Python 3.10 or newer
- No external Python packages are required

## Step-by-Step Run Process

1. Open a terminal in this project folder.

2. Start the application:

   ```bash
   python app.py
   ```

3. Open this URL in a browser:

   ```text
   http://127.0.0.1:8000
   ```

4. Login with one of the demo accounts:

   ```text
   Admin:
   email: admin@college.edu
   password: admin123

   Organizer:
   email: organizer@college.edu
   password: organizer123

   Student:
   email: student@college.edu
   password: student123
   ```

## Publish on GitHub

1. Create a new GitHub repository.
2. Upload or push these files and folders:

   ```text
   app.py
   README.md
   render.yaml
   requirements.txt
   runtime.txt
   static/style.css
   static/uploads/.gitkeep
   .gitignore
   ```

3. Do not upload local SQLite database files from the `data` folder. The app creates the database automatically when it starts.

## Host on Render Free

1. Open https://dashboard.render.com.
2. Click New + > Web Service.
3. Connect your GitHub repository.
4. Use these settings:

   ```text
   Runtime: Python
   Build Command: pip install -r requirements.txt
   Start Command: python app.py
   Instance Type: Free
   ```

5. Deploy the service. Render will provide a public URL after deployment.

## Suggested Demo Flow

1. Login as organizer.
2. Open Organizer > Manage My Events.
3. Submit a new event with an optional event image upload or picture URL.
4. Choose whether the event needs admin approval. If No, it appears for students immediately.
5. Logout and login as admin if approval or schedules/sponsors are needed.
6. Open Admin > Event Approvals and approve pending events.
7. Add schedule sessions from Admin > Schedules.
8. Add sponsors and link them from Admin > Sponsors.
9. Logout and login as student.
10. Open the student dashboard and click Apply for Registration.
11. Choose the event and apply for registration.
12. Open the dashboard and print the generated ticket.

## Database Tables

- `users`
- `events`
- `registrations`
- `tickets`
- `schedules`
- `sponsors`
- `event_sponsors`

## Notes for College Submission

This project uses SQLite so it can run without a separate database server. For a larger production version, SQLite can be replaced with MySQL or PostgreSQL while keeping the same table design.

On Render free, uploaded event images are stored on the service filesystem, so they may disappear after redeploys or restarts. For a real production version, use cloud image storage.
