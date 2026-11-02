# The grand imports — everything a D&D character builder needs to survive the internet
from flask import Flask, render_template, request, redirect, session
from flask_session import Session
from cachelib.file import FileSystemCache
from werkzeug.security import check_password_hash, generate_password_hash
from contextlib import closing
from functools import wraps
import json, os, sqlite3

# Everything is relative to this file, so "flask run" works from any folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "origin.db")

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
# The old "filesystem" session type is deprecated, so the session files are stored with cachelib instead (same idea, same folder)
app.config["SESSION_TYPE"] = "cachelib"
app.config["SESSION_CACHELIB"] = FileSystemCache(cache_dir=os.path.join(BASE_DIR, "flask_session"), threshold=500)
Session(app)



# ── D&D rules the app needs ──

ABILITIES = ["str", "dex", "con", "int", "wis", "cha"]

# The JSON data uses full names ("strength"), the app uses the short ones ("str")
FULL_TO_SHORT = {
    "strength": "str", "dexterity": "dex", "constitution": "con",
    "intelligence": "int", "wisdom": "wis", "charisma": "cha"
}
SHORT_TO_FULL = {short: full for full, short in FULL_TO_SHORT.items()}

# D&D 5e Point Buy — 27 points, scores from 8 to 15, and 14 & 15 cost extra
POINT_BUY_COSTS = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
POINT_BUY_BUDGET = 27

PROFICIENCY_BONUS = 2  # every level 1 character gets +2

# Which ability each skill uses. Culture and engineering come from some of the backgrounds in the data.
SKILL_ABILITIES = {
    "acrobatics": "dex", "animal handling": "wis", "arcana": "int", "athletics": "str",
    "deception": "cha", "history": "int", "insight": "wis", "intimidation": "cha",
    "investigation": "int", "medicine": "wis", "nature": "int", "perception": "wis",
    "performance": "cha", "persuasion": "cha", "religion": "int", "sleight of hand": "dex",
    "stealth": "dex", "survival": "wis", "culture": "int", "engineering": "int"
}

# The 18 standard skills — needed for the "choose any" edge case. Thanks, Guildmember.
ALL_SKILLS = [
    "acrobatics", "animal handling", "arcana", "athletics", "deception",
    "history", "insight", "intimidation", "investigation", "medicine",
    "nature", "perception", "performance", "persuasion", "religion",
    "sleight of hand", "stealth", "survival"
]

# The wizard steps in order, and the session key each one fills
STEPS = [
    ("name", "/create"),
    ("race", "/create/race"),
    ("class_", "/create/class"),
    ("background", "/create/background"),
    ("abilities", "/create/abilities"),
    ("skills", "/create/skills"),
]

# Which steps have to be done again when an earlier choice changes
# (racial bonuses depend on the race, and the skill list depends on race, class and background)
DEPENDS_ON = {
    "race": ["abilities", "skills"],
    "class_": ["skills"],
    "background": ["skills"]
}



# Load local data on startup
# added the encoding because the data includes some wierd letters — looking at you, D&D names with apostrophes
# Each JSON is a dict keyed by name, but templates want a list — so we splat each entry into {name: ..., ...data}
def load_data(file_name):
    with open(os.path.join(BASE_DIR, "data", file_name), encoding="utf-8") as f:
        return [{"name": name, **data} for name, data in json.load(f).items()]

CLASSES = load_data("clean_classes.json")
RACES = load_data("clean_races.json")
BACKGROUNDS = load_data("clean_backgrounds.json")


def find(items, name):
    """Finds a race / class / background by name, or None if it doesn't exist"""
    return next((item for item in items if item["name"] == name), None)



# ── Database helpers ──

def get_db():
    con = sqlite3.connect(DATABASE)
    con.row_factory = sqlite3.Row  # lets us access columns by name instead of index. Bless.
    return con


# Builds the database from schema.sql on every startup
def init_db():
    with closing(get_db()) as con:
        with open(os.path.join(BASE_DIR, "schema.sql")) as f:
            con.executescript(f.read())

# Run it immediately so the db is ready before any requests come in
init_db()



# ── Small helpers ──

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function


def error(message, code=400):
    """Shows a proper error page instead of a plain line of text"""
    return render_template("error.html", message=message), code


def modifier(score):
    """10-11 is +0, 12-13 is +1, 8-9 is -1 ... the classic D&D formula"""
    return (score - 10) // 2


def missing_step(character, step_key):
    """Returns the URL of the first step that isn't done yet before step_key, or None if everything is fine"""
    if not character:
        return "/create"
    for key, url in STEPS:
        if key == step_key:
            return None
        if key not in character:
            return url
    return None


def save_step(key, value):
    """Saves one step in the session. If the choice changed, the steps that depend on it are forgotten —
    if you go back and change your race, your old ability scores (with the old racial bonus) shouldn't stay."""
    character = session.get("character", {})
    if character.get(key) != value:
        for later_key in DEPENDS_ON.get(key, []):
            character.pop(later_key, None)
    character[key] = value
    session["character"] = character  # reassign so the session notices the change


def racial_bonus(race, bonus_choices):
    """Returns the racial ability increases as {"str": 2, ...}
    Half-elves get +2 CHA and +1 to two other abilities they choose (the "other" key in the data)"""
    bonus = {}
    for ability, amount in race["asi"].items():
        if ability == "other":
            for choice in bonus_choices:
                bonus[choice] = bonus.get(choice, 0) + 1
        else:
            short = FULL_TO_SHORT[ability]
            bonus[short] = bonus.get(short, 0) + amount
    return bonus


def skill_choices(character):
    """Works out which skills are given for free and which ones the user can pick.
    Returns (fixed_skills, available_skills, total_choices)"""
    sources = [find(RACES, character["race"]), find(CLASSES, character["class_"]), find(BACKGROUNDS, character["background"])]

    # Gather up all the free skills you get just for showing up
    fixed = []
    for source in sources:
        for skill in source.get("fixed_skills") or []:
            if skill not in fixed:
                fixed.append(skill)

    # Count the choices and build the pool. "any" can be a string (bard) or inside a list (half-elf)
    total = 0
    pool = []
    has_any = False
    for source in sources:
        total += source.get("num_choices") or 0
        choices = source.get("choice_skills") or []
        if choices == "any" or "any" in choices:
            has_any = True
        else:
            pool.extend(choices)
    if has_any:
        pool = ALL_SKILLS + pool

    available = []
    for skill in pool:
        if skill not in fixed and skill not in available:
            available.append(skill)

    # If the free skills already cover some options, you can't pick more than what's left
    return fixed, available, min(total, len(available))


def calculate_stats(character):
    """Level 1 HP, AC and speed from the class, race and final ability scores"""
    class_data = find(CLASSES, character["class_"])
    race = find(RACES, character["race"])
    scores = character["abilities"]

    # Level 1 HP = the max of your hit die + CON modifier (never less than 1)
    hit_die = int(class_data["hit_die"].split("d")[1])
    max_hp = max(1, hit_die + modifier(scores["con"]))

    # No armor yet, so AC = 10 + DEX. Barbarians and monks get their Unarmored Defense.
    armor_class = 10 + modifier(scores["dex"])
    if character["class_"] == "barbarian":
        armor_class += modifier(scores["con"])
    elif character["class_"] == "monk":
        armor_class += modifier(scores["wis"])

    return {"max_hp": max_hp, "armor_class": armor_class, "speed": race["speed"]}


def build_sheet(name, race, class_, background, level, scores, saves, skills, hp, max_hp, armor_class, speed):
    """Puts together everything the character sheet shows (used by the review page and the saved character page)"""
    abilities = [
        {"short": a, "full": SHORT_TO_FULL[a], "score": scores[a], "mod": modifier(scores[a])}
        for a in ABILITIES
    ]

    saving_throws = []
    for a in ABILITIES:
        proficient = SHORT_TO_FULL[a] in saves
        saving_throws.append({
            "name": SHORT_TO_FULL[a], "proficient": proficient,
            "mod": modifier(scores[a]) + (PROFICIENCY_BONUS if proficient else 0)
        })

    # All 18 skills, plus any extra ones from the background (culture / engineering)
    skill_rows = []
    for skill in ALL_SKILLS + [s for s in skills if s not in ALL_SKILLS]:
        ability = SKILL_ABILITIES.get(skill, "int")
        proficient = skill in skills
        skill_rows.append({
            "name": skill, "ability": ability, "proficient": proficient,
            "mod": modifier(scores[ability]) + (PROFICIENCY_BONUS if proficient else 0)
        })

    perception = next(row["mod"] for row in skill_rows if row["name"] == "perception")

    return {
        "name": name, "race": race, "class_": class_, "background": background, "level": level,
        "hp": hp, "max_hp": max_hp, "armor_class": armor_class, "speed": speed,
        "initiative": modifier(scores["dex"]), "proficiency_bonus": PROFICIENCY_BONUS,
        "passive_perception": 10 + perception,
        "abilities": abilities, "saving_throws": saving_throws, "skills": skill_rows
    }


# Lets templates show modifiers as +2 / -1 instead of 2 / -1
@app.template_filter("signed")
def signed(number):
    return f"+{number}" if number >= 0 else str(number)


# "sleight of hand" -> "Sleight of Hand" (Jinja's title filter would give "Sleight Of Hand")
@app.template_filter("skill_title")
def skill_title(skill):
    return " ".join(word if word == "of" else word.capitalize() for word in skill.split())



# ── Routes ──

# Home sweet home — shows all your characters, but only if you're logged in
@app.route("/")
@login_required
def index():
    with closing(get_db()) as con:
        characters = con.execute(
            "SELECT * FROM characters WHERE user_id = ? ORDER BY id DESC", (session["user_id"],)
        ).fetchall()
    return render_template("index.html", characters=characters)



# Sign up route — where heroes are born (one username at a time)
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Validate inputs — no blank submissions, we're not running a charity
        if not username or not password or not confirmation:
            return error("All fields are required")
        if password != confirmation:
            return error("Passwords do not match")

        hashed_password = generate_password_hash(password)

        # Store the user in the database
        # "with con" commits on success and rolls back on failure, so a failed insert can't leave the database locked
        with closing(get_db()) as con:
            try:
                with con:
                    con.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed_password))
            except sqlite3.IntegrityError:
                return error("Username already taken")  # someone else claimed it first. Too slow!

        return redirect("/login")

    else:
        return render_template("register.html")



# Login route — the gates of the kingdom
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password")

        # Validate inputs — can't login with nothing, that's not how identity works
        if not username or not password:
            return error("All fields are required")

        # Check the database for the user
        with closing(get_db()) as con:
            user = con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        # If no user found OR password is wrong, send 'em packing
        if not user or not check_password_hash(user["password_hash"], password):
            return error("Invalid username or password", 403)

        # Forget any old session, then remember which user has logged in
        session.clear()
        session["user_id"] = user["id"]

        return redirect("/")

    else:
        return render_template("login.html")



# Step 1 of character creation — every hero needs a name (even "Dave the Barbarian")
@app.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            return error("Please enter a name")
        if len(name) > 50:
            return error("That name is too long (50 characters max)")
        # Start building the character in session storage (or just rename it if you came back to this step)
        save_step("name", name)
        return redirect("/create/race")
    else:
        character = session.get("character") or {}
        return render_template("create.html", name=character.get("name", ""))



# Step 2 — pick your race. Elf? Dwarf? Human? The classic D&D identity crisis.
@app.route("/create/race", methods=["GET", "POST"])
@login_required
def create_race():
    character = session.get("character")
    step = missing_step(character, "race")
    if step:
        return redirect(step)

    if request.method == "POST":
        race = request.form.get("race")
        if not find(RACES, race):
            return error("Please select a race")
        save_step("race", race)
        return redirect("/create/class")
    else:
        return render_template("create_race.html", races=RACES, selected=character.get("race"))



# Step 3 — pick your class. Wizard? Fighter? Rogue? Choose your destiny (and your HP).
# Note: "class" is a Python reserved word, so I use "class_" — thanks, Guido.
@app.route("/create/class", methods=["GET", "POST"])
@login_required
def create_class():
    character = session.get("character")
    step = missing_step(character, "class_")
    if step:
        return redirect(step)

    if request.method == "POST":
        class_ = request.form.get("class_")
        if not find(CLASSES, class_):
            return error("Please select a class")
        save_step("class_", class_)
        return redirect("/create/background")
    else:
        return render_template("create_class.html", classes=CLASSES, selected=character.get("class_"))



# Step 4 — pick your background. Were you a sailor? A criminal? A noble? D&D's version of a resume.
@app.route("/create/background", methods=["GET", "POST"])
@login_required
def create_background():
    character = session.get("character")
    step = missing_step(character, "background")
    if step:
        return redirect(step)

    if request.method == "POST":
        background = request.form.get("background")
        if not find(BACKGROUNDS, background):
            return error("Please select a background")
        save_step("background", background)
        return redirect("/create/abilities")
    else:
        return render_template("create_background.html", backgrounds=BACKGROUNDS, selected=character.get("background"))



# Step 5 — ability scores! The classic point-buy mini-game that makes or breaks your character.
# JS does the point-buy math live on the page, but the server checks it again — never trust the browser.
@app.route("/create/abilities", methods=["GET", "POST"])
@login_required
def create_abilities():
    character = session.get("character")
    step = missing_step(character, "abilities")
    if step:
        return redirect(step)

    race = find(RACES, character["race"])
    other_bonus = race["asi"].get("other", 0)  # half-elves pick extra +1s

    if request.method == "POST":
        # Grab all six base scores and make sure they follow the point-buy rules
        base = {}
        for ability in ABILITIES:
            try:
                base[ability] = int(request.form.get(ability))
            except (TypeError, ValueError):
                return error("Missing ability score")
            if base[ability] not in POINT_BUY_COSTS:
                return error("Ability scores must be between 8 and 15 before racial bonuses")

        spent = sum(POINT_BUY_COSTS[score] for score in base.values())
        if spent > POINT_BUY_BUDGET:
            return error(f"You spent {spent} points but you only have {POINT_BUY_BUDGET}")

        # Half-elf: exactly two different abilities, and not the one that already gets +2
        bonus_choices = request.form.getlist("bonus")
        if other_bonus:
            fixed_bonus = [FULL_TO_SHORT[a] for a in race["asi"] if a != "other"]
            if (len(bonus_choices) != other_bonus or len(set(bonus_choices)) != other_bonus
                    or any(c not in ABILITIES or c in fixed_bonus for c in bonus_choices)):
                return error(f"Choose {other_bonus} different abilities for your racial bonus")
        else:
            bonus_choices = []

        bonus = racial_bonus(race, bonus_choices)
        final = {a: base[a] + bonus.get(a, 0) for a in ABILITIES}

        save_step("abilities", final)
        character = session["character"]
        character["base_abilities"] = base        # kept so the page remembers your choices if you come back
        character["bonus_choices"] = bonus_choices
        session["character"] = character
        return redirect("/create/skills")
    else:
        return render_template(
            "create_abilities.html",
            race=race,
            bonus=racial_bonus(race, []),
            other_bonus=other_bonus,
            base=character.get("base_abilities") or {a: 8 for a in ABILITIES},
            bonus_choices=character.get("bonus_choices") or [],
            costs=POINT_BUY_COSTS,
            budget=POINT_BUY_BUDGET,
            full_names=SHORT_TO_FULL
        )



# Step 6 — skill proficiency selection, the most chaotic part of D&D character creation.
# Some skills you get for free (from race/class/background), some you pick yourself.
# The "any" edge case exists because D&D data is... D&D data.
@app.route("/create/skills", methods=["GET", "POST"])
@login_required
def create_skills():
    character = session.get("character")
    step = missing_step(character, "skills")
    if step:
        return redirect(step)  # skipped a step? go back to it, do not collect $200

    fixed, available, total = skill_choices(character)

    if request.method == "POST":
        chosen = request.form.getlist("skills")
        # Same rules as the page: the right number of skills, no repeats, and only from the list you were given
        if len(chosen) != total or len(set(chosen)) != total or any(s not in available for s in chosen):
            return error(f"Choose exactly {total} skill{'s' if total != 1 else ''} from the list")
        save_step("skills", fixed + chosen)
        return redirect("/create/review")
    else:
        selected = [s for s in character.get("skills", []) if s in available]
        return render_template(
            "create_skills.html",
            fixed_skills=fixed,
            available_skills=available,
            total_choices=total,
            selected=selected
        )



# Step 7 — the review page. Look at your creation. Revel in it. Or go back and fix that 8 Wisdom.
@app.route("/create/review")
@login_required
def create_review():
    character = session.get("character")
    step = missing_step(character, "review")
    if step:
        return redirect(step)

    stats = calculate_stats(character)
    sheet = build_sheet(
        character["name"], character["race"], character["class_"], character["background"], 1,
        character["abilities"], find(CLASSES, character["class_"])["saves"], character["skills"],
        stats["max_hp"], stats["max_hp"], stats["armor_class"], stats["speed"]
    )
    return render_template("create_review.html", sheet=sheet)



# The final boss — actually saving the character to the database.
# This is where the rubber meets the road. Three inserts, one commit.
# It's a POST now, so just visiting the URL (or a page preloading it) can't save a character by accident.
@app.route("/create/save", methods=["POST"])
@login_required
def create_save():
    character = session.get("character")
    step = missing_step(character, "review")
    if step:
        return redirect(step)  # nothing to save? back you go

    stats = calculate_stats(character)
    abilities = character["abilities"]
    saves = find(CLASSES, character["class_"])["saves"]

    with closing(get_db()) as con:
        with con:  # one transaction — either the whole character is saved, or none of it
            # Insert into characters table — level 1, full HP
            cur = con.execute(
                "INSERT INTO characters (user_id, name, race, class, background, level, current_hp, max_hp, armor_class, speed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session["user_id"], character["name"], character["race"], character["class_"], character["background"],
                 1, stats["max_hp"], stats["max_hp"], stats["armor_class"], stats["speed"])
            )

            # Grab the auto-generated character ID so we can link the other tables
            character_id = cur.lastrowid

            # Skills and saving throws go in as JSON — they're always read and written as a whole list
            con.execute(
                "INSERT INTO proficiencies (character_id, saving_throws, skills) VALUES (?, ?, ?)",
                (character_id, json.dumps(saves), json.dumps(character["skills"]))
            )

            # Insert into ability_scores table — note the column is "intel" not "int" (SQL reserved word, fun!)
            con.execute(
                "INSERT INTO ability_scores (character_id, str, dex, con, intel, wis, cha) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (character_id, abilities["str"], abilities["dex"], abilities["con"], abilities["int"], abilities["wis"], abilities["cha"])
            )

    # Clear character from session — the session was just temporary storage for the wizard's journey
    session.pop("character", None)

    return redirect(f"/character/{character_id}")



# The character sheet of a saved character
@app.route("/character/<int:character_id>")
@login_required
def character_sheet(character_id):
    with closing(get_db()) as con:
        # user_id is checked too, so nobody can peek at someone else's character by changing the number in the URL
        character = con.execute(
            "SELECT * FROM characters WHERE id = ? AND user_id = ?", (character_id, session["user_id"])
        ).fetchone()
        if not character:
            return error("Character not found", 404)
        scores_row = con.execute("SELECT * FROM ability_scores WHERE character_id = ?", (character_id,)).fetchone()
        proficiencies = con.execute("SELECT * FROM proficiencies WHERE character_id = ?", (character_id,)).fetchone()

    scores = {"str": scores_row["str"], "dex": scores_row["dex"], "con": scores_row["con"],
              "int": scores_row["intel"], "wis": scores_row["wis"], "cha": scores_row["cha"]}

    # Characters saved by the old version have "1" as their saving throws, so fall back to the class data
    try:
        saves = json.loads(proficiencies["saving_throws"])
        if not isinstance(saves, list):
            raise ValueError
    except (TypeError, ValueError):
        class_data = find(CLASSES, character["class"])
        saves = class_data["saves"] if class_data else []

    sheet = build_sheet(
        character["name"], character["race"], character["class"], character["background"], character["level"],
        scores, saves, json.loads(proficiencies["skills"]),
        character["current_hp"], character["max_hp"], character["armor_class"], character["speed"]
    )
    return render_template("character.html", sheet=sheet, character_id=character_id)



# Deleting a character — gone, like a level 1 wizard in melee range
@app.route("/character/<int:character_id>/delete", methods=["POST"])
@login_required
def delete_character(character_id):
    with closing(get_db()) as con:
        with con:
            owner = con.execute(
                "SELECT id FROM characters WHERE id = ? AND user_id = ?", (character_id, session["user_id"])
            ).fetchone()
            if not owner:
                return error("Character not found", 404)
            con.execute("DELETE FROM ability_scores WHERE character_id = ?", (character_id,))
            con.execute("DELETE FROM proficiencies WHERE character_id = ?", (character_id,))
            con.execute("DELETE FROM characters WHERE id = ?", (character_id,))
    return redirect("/")



# Logout — yeet the session into the void and send 'em back to the login page
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")
