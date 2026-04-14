# DnD Origin

## Overview

DnD Origin is a web-based Dungeons & Dragons 5th Edition character creator built with Python, Flask, and SQLite. It guides users through the complete process of building a D&D character step by step — from choosing a name all the way to reviewing and persisting a finished character sheet to the database. The application is designed to feel like an interactive character-creation wizard, where each step builds on the last and all state is held in the server-side session until the user commits the character.

The creation flow follows a seven-step sequence: Name → Race → Class → Background → Ability Scores → Skill Proficiencies → Review & Save. At every step, the user makes a choice that is stored in the Flask session object under a `character` key. Only after the user reviews their choices on the final step and clicks "Confirm & Save" is the character written to the database across three tables in a single transaction. This session-based approach means the user can build a character incrementally without polluting the database with half-finished entries, and it keeps the creation process atomic — either the whole character is saved, or none of it is.

## Tech Stack

- **Backend:** Python 3 / Flask — all routing, session management, and database interaction live in a single `app.py` file
- **Database:** SQLite via the `sqlite3` standard library module; the schema is defined in `schema.sql` and auto-executed on every app startup
- **Frontend:** Jinja2 HTML templates rendered by Flask, styled entirely with a custom `style.css` — no CSS frameworks
- **Session Management:** Flask-Session configured for filesystem-backed storage, keeping user login state and in-progress character data on the server
- **Data Layer:** Local JSON files containing cleaned D&D 5e SRD data for races, classes, and backgrounds, loaded into memory at application startup

## File-by-File Breakdown

### `app.py` — Application Logic

This is the heart of the project. Every Flask route, the `login_required` decorator, the database initialization function, and the data-loading code live here. On startup, `app.py` reads three JSON files (`clean_classes.json`, `clean_races.json`, `clean_backgrounds.json`) into in-memory lists so the templates can iterate over them. It also calls `init_db()`, which reads and executes `schema.sql` against the SQLite database, ensuring the schema exists before any request is handled.

The routes follow a clear pattern. Authentication routes (`/register`, `/login`, `/logout`) handle user creation and session management. The home route (`/`) queries the database for all characters belonging to the logged-in user and renders them as cards. The character creation routes (`/create`, `/create/race`, `/create/class`, `/create/background`, `/create/abilities`, `/create/skills`, `/create/review`, `/create/save`) each handle one step of the wizard. Each creation route follows the same structure: on a GET request, render the template with the necessary data; on a POST request, validate the input, store the selection in `session["character"]`, and redirect to the next step.

A notable design choice in `app.py` is the use of raw `sqlite3` rather than an ORM like SQLAlchemy. This was a deliberate decision to keep the project simple and transparent — every query is explicit and readable, and there is no abstraction layer to debug through. The tradeoff is that the database code is more verbose and must be handled carefully (opening and closing connections manually, using parameterized queries to prevent SQL injection), but for a project of this scope, that felt like the right balance.

Another design choice was storing the in-progress character entirely in the Flask session rather than writing partial rows to the database with a "draft" flag. The session approach avoids the complexity of draft-vs-committed states and keeps the database clean — only complete characters exist in it. The downside is that session data is volatile; if the user closes their browser mid-creation, their progress is lost. For a character creator where the whole process takes a few minutes, that is an acceptable tradeoff.

### `schema.sql` — Database Schema

This file defines four tables. `users` stores registered accounts with auto-incrementing IDs, unique usernames, and hashed passwords. `characters` is the core character sheet table, storing the character's name, race, class, background, level, current and max HP, armor class, and speed, all linked to a user via a foreign key. `ability_scores` stores the six D&D ability scores (STR, DEX, CON, INT, WIS, CHA) as separate columns, linked to a character. `proficiencies` stores skill proficiencies as a JSON-encoded string in a single `skills` column, linked to a character.

One design decision worth noting is the use of JSON for the skills column rather than a separate `character_skills` junction table. A normalized approach would use a many-to-many relationship, but since skills are always read and written as a complete set (never queried individually or filtered on), storing them as JSON keeps the schema simpler and the queries fewer. The `intel` column name (instead of `int`) in `ability_scores` is also a deliberate choice — `int` is a reserved word in SQL, and rather than quoting it everywhere, renaming it to `intel` avoids the issue entirely. Similarly, the `class_` variable name in Python templates sidesteps the `class` reserved word conflict.

### `data/` — D&D 5e Data Files

The `data/` directory contains three pairs of JSON files. The "raw" files (`races.json`, `classes.json`, `backgrounds.json`) contain the original data as sourced, while the "clean" files (`clean_races.json`, `clean_classes.json`, `clean_backgrounds.json`) are curated versions with only the fields the application needs. The app loads only the clean versions at startup.

Each clean JSON file is structured as a dictionary keyed by the entity name (race, class, or background). The values contain fields like `fixed_skills` (skills granted unconditionally), `choice_skills` (skills the user can pick from), `num_choices` (how many skills the user gets to choose), `asi` (ability score increases for races), `hit_die` and `saves` for classes, and `feature` and `equipment` for backgrounds. The app transforms these dictionaries into lists of objects (each with a `name` key) at load time so Jinja2 templates can iterate over them cleanly.

### `templates/` — Jinja2 HTML Templates

All templates extend `layout.html`, which provides the HTML skeleton, a stylesheet link, and a navigation bar that conditionally shows links (Home, New Character, Logout) only when a user is logged in. The `{% block content %}` placeholder is where each page injects its specific markup.

- **`layout.html`** — Base template with nav bar and content block. The nav uses Jinja2's `session.user_id` check to conditionally render links.
- **`index.html`** — Home page showing all of the logged-in user's characters as cards. Displays character name, race, class, background, and level.
- **`login.html`** and **`register.html`** — Authentication forms. Register includes a password confirmation field. Both link to each other for easy switching.
- **`create.html`** — Step 1: a simple text input for the character's name.
- **`create_race.html`**, **`create_class.html`**, **`create_background.html`** — Steps 2–4: dropdown selects populated from the loaded JSON data.
- **`create_abilities.html`** — Step 5: a 3×2 grid of ability score boxes with +/− buttons. The page embeds a JavaScript point-buy calculator that enforces the D&D 5e rules — 27 points to distribute, scores range from 8 to 15, and the cost table matches the official rules (e.g., going from 13 to 14 costs 2 points instead of 1). Hidden inputs carry the final scores to the server on form submission.
- **`create_skills.html`** — Step 6: the most complex template. It computes which skills are "innate" (granted by race, class, or background) and which are available for the user to choose. It handles the edge case where a class like Bard has `choice_skills: "any"`, meaning the user can pick from the entire skill list rather than a restricted subset. A counter shows how many skill choices remain, and JavaScript enforces the maximum — once the user has selected their allotted number, remaining cards become visually locked. Fixed skills are displayed separately as non-interactive tags.
- **`create_review.html`** — Step 7: a summary page showing the character's name, race, class, background, and all six ability scores. A "Confirm & Save" link triggers the final save route, which writes the character to the database and clears the session.

### `static/style.css` — Styling

The stylesheet creates a dark, fantasy-themed aesthetic using CSS custom properties for a consistent color palette — deep blacks and browns for backgrounds, muted golds for accents and headings, and warm parchment tones for text. The design uses two Google Fonts: Cinzel (a serif display font) for headings, labels, and buttons, and Crimson Text (a readable serif) for body copy. The entire UI is built with custom CSS — no frameworks — relying on CSS Grid for the ability score layout and skill card grid, flexbox for navigation and inline elements, and subtle transitions for hover states. The navbar is fixed at the top with a frosted-glass effect using `backdrop-filter: blur`. Cards for the character list and review page use border transitions on hover to give the interface a responsive, tactile feel.

## Design Choices and Tradeoffs

**SQLite over PostgreSQL or another production database:** SQLite was chosen because it requires no separate server process, no configuration, and no credentials. The entire database is a single file (`origin.db`) that is created automatically on first run. For a single-user or small-scale application, this simplicity is a major advantage. The limitation is that SQLite does not handle concurrent writes well, so scaling this app to many simultaneous users would require migrating to a client-server database (or that was what I read, i'm simply more familiar with SQLite and all that's said above is why I didn't change it).

**Raw `sqlite3` over an ORM:** Using direct SQL queries keeps the code transparent — you can see exactly what query runs against the database. The cost is verbosity and manual connection management, but the project is small enough that this overhead is minimal (I got lost a thousand times in the project but the readability saved me everytime).

**Session-based character building over database drafts:** Storing the in-progress character in the Flask session avoids creating a "draft" state in the database and keeps the schema clean. The tradeoff is that progress is lost if the session expires or the user closes the browser. For a short, guided creation process, this felt like the right call.

**JSON for skills storage over a junction table:** Skills are stored as a JSON string in a single column because they are always written and read as a complete set — the app never needs to query for individual skills or join on them. A normalized junction table would add schema complexity without providing a meaningful query advantage, and I also have to mention that the data was already in a JSON format online.

**In-memory data loading over database lookup for D&D reference data:** The JSON data files are loaded into Python lists at startup and passed directly to templates. An alternative would be storing races, classes, and backgrounds in database tables, but since this data is static reference material that never changes at runtime, reading it from JSON once and keeping it in memory is faster and simpler.

**Custom CSS over a framework:** The entire frontend is styled with hand-written CSS. While a framework like Bootstrap or Tailwind would speed up initial development, the custom approach gives full control over the fantasy aesthetic — the dark color palette, the serif typography, the gold accents — and results in a lighter page with no external CSS dependency beyond the two Google Fonts (AI can use that full control to it's maximum).

## How to Run

install flask and hit the "flask run" boiiii.

The database (`origin.db`) is created automatically on first run. No additional setup is required.

## On AI Assistance

The frontend design (HTML/CSS) was developed with significant help from AI. When it comes to visual design and UI layout, AI models produce coherent, polished interfaces far faster than would be possible manually. That strength was leveraged heavily for the look and feel of the site (and so is the documentation, I only took simple notes and gave them to it and told it to make documentaion out of it, and an agent was used for commenting). Beyond that, AI was also used as a general-purpose collaborator throughout the project. Most of the ideas implemented — from the multi-step creation flow to the session-based character building approach — were conceived independently, but AI helped review and improve them, catching edge cases, refactoring messy logic, and thinking through design decisions more carefully. Every line of code was written with full understanding. AI was a tool used to accelerate and improve the work, not a replacement for doing it.
