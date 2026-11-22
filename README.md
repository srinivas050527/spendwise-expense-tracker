# SpendWise - Expense Tracker

A web app to record daily expenses, see a monthly category breakdown, and export data to CSV.
Built with **Python, Flask, SQLite, HTML, CSS**.

## Features
- Register and log in (passwords stored as hashes, never plain text)
- Add, edit and delete expenses
- Filter by month and category
- Monthly total and category-wise bar chart
- Download expenses as a CSV file
- Each user sees only their own data

## Run it locally
```bash
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000 in your browser.

## Project structure
```
app.py            Flask routes and database code
templates/        HTML pages (Jinja2)
static/style.css  Styling
```

## What I learned
- Building a CRUD app with Flask routes and Jinja2 templates
- Designing SQL tables with foreign keys, and using parameterised queries
- Password hashing and session-based login
