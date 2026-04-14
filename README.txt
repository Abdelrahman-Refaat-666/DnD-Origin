DnD Origin — CS50X Final Project
==================================

What is it?
-----------
DnD Origin is a web-based Dungeons & Dragons 5th Edition character creator built with
Python, Flask, and SQLite. It walks users through the full process of creating a D&D
character step by step — from picking a name all the way to reviewing and saving the
finished character sheet.

The app is structured as a multi-step wizard: Name → Race → Class → Background →
Ability Scores → Skill Proficiencies → Review & Save. At each step the user makes a
choice, and the selection is stored in the session until the character is complete and
committed to the database.

Tech Stack
----------
- Backend:  Python 3 / Flask
- Database: SQLite (via sqlite3, schema defined in schema.sql)
- Frontend: HTML templates (Jinja2), CSS
- Session:  Flask-Session (filesystem-backed)
- Data:     Local JSON files for D&D 5e races, classes, and backgrounds

Database Schema
---------------
Four tables power the app:

1. users — stores registered accounts with hashed passwords (werkzeug)
2. characters — the core character sheet (name, race, class, background, level, HP, AC, speed)
3. ability_scores — the six D&D ability scores (STR, DEX, CON, INT, WIS, CHA) linked to a character
4. proficiencies — skill proficiencies stored as JSON, linked to a character

Key Features
------------
- User registration and login with password hashing
- Login-required routes protected by a decorator (@login_required)
- Multi-step character creation with session-based state
- Point-buy system for ability scores (JavaScript handles the math on the frontend)
- Skill proficiency selection that accounts for fixed skills from class/race/background
  and user-chosen skills, including the "choose any" edge case
- Character review page before final save
- All D&D 5e SRD race, class, and background data loaded from cleaned JSON files

How to Run
----------
1. Install dependencies: pip install flask flask-session
2. Run the app: python app.py
3. Open a browser and go to http://127.0.0.1:5000 (or whatever port Flask uses)

File Overview
-------------
- app.py               — All Flask routes and logic
- schema.sql           — Database schema (auto-runs on startup)
- origin.db            — SQLite database (created automatically)
- data/                — Cleaned D&D 5e JSON data (races, classes, backgrounds)
- static/style.css     — All styling
- templates/           — Jinja2 HTML templates (layout, index, create steps, auth pages)

On AI Assistance
----------------
The frontend design (HTML/CSS) was mostly done with the help of AI. When it comes to
visual design and UI layout, AI models are simply in another league — they produce
coherent, polished interfaces far faster than I could have managed on my own. I leaned
on that strength heavily for the look and feel of the site.

Beyond just the frontend, I also used AI as a general-purpose collaborator throughout the
project. Most of the ideas I implemented — from the multi-step creation flow to the
session-based character building approach — were things I conceived, but I ran them past
AI to review and improve. It helped me catch edge cases, refactor messy logic, and
think through design decisions more carefully than I would have on my own. The final
result is better for it.

That said, every line of code was written with full understanding on my part. AI was a
tool I used to accelerate and improve my work, not a replacement for doing the work.