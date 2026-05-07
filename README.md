# College Event Management System

This is a complete college event registration and ticketing system built with Python, SQLite, HTML, and CSS.

## Features

- Student registration and login
- Organizer event proposal submission
- Admin event approval and rejection
- Approved event listing
- Student event registration
- Student payment method and transaction reference during registration
- Automatic ticket generation
- Printable ticket page
- Admin registration approval for restricted events
- Admin payment verification from the registration approval screen
- Organizer fee, UPI, bank/passbook, and other payment receiving method setup
- Schedule management
- Sponsor management and event-sponsor linking

## Project Structure

```text
college-event-management-system/
  app.py
  README.md
  data/
    college_events.db      created automatically when app starts
  static/
    style.css
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

## Suggested Demo Flow

1. Login as organizer.
2. Open Organizer > Manage My Events.
3. Submit a new event proposal with registration fee, UPI ID, bank/passbook details, and any other payment method.
4. Logout and login as admin.
5. Open Admin > Event Approvals.
6. Approve the event.
7. Add schedule sessions from Admin > Schedules.
8. Add sponsors and link them from Admin > Sponsors.
9. Logout and login as student.
10. Open the student dashboard and click Apply for Registration.
11. Choose the event, check payment details, select payment method, and enter transaction ID or receipt note.
12. Logout and login as admin.
13. Open Admin > Registration Approvals and approve the registration after checking payment.
14. Login as student again, open the dashboard, and print the generated ticket.

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

Payment is recorded for project/demo purposes. The app stores the selected method and transaction/reference number, while the actual money transfer happens outside the app through UPI, bank transfer, cash, or another method entered by the organizer.
