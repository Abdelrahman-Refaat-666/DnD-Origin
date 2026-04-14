# The grand imports — everything a D&D character builder needs to survive the internet
from flask import Flask, render_template, request, redirect, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import json, sqlite3

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)



def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function



# Load local data on startup
# added the encoding because the data includes some wierd letters — looking at you, D&D names with apostrophes
# Each JSON is a dict keyed by name, but templates want a list — so we splat each entry into {name: ..., ...data}
with open("data/clean_classes.json", encoding="utf-8") as f:
    CLASSES = [{"name": name, **data} for name, data in json.load(f).items()]

with open("data/clean_races.json", encoding="utf-8") as f:
    RACES = [{"name": name, **data} for name, data in json.load(f).items()]

with open("data/clean_backgrounds.json", encoding="utf-8") as f:
    BACKGROUNDS = [{"name": name, **data} for name, data in json.load(f).items()]



# Home sweet home — shows all your characters, but only if you're logged in
@app.route("/")
@login_required
def index():
    con = sqlite3.connect("origin.db")
    con.row_factory = sqlite3.Row  # lets us access columns by name instead of index. Bless.
    characters = con.execute(
        "SELECT * FROM characters WHERE user_id = ?", (session["user_id"],)
    ).fetchall()
    con.close()
    return render_template("index.html", characters=characters)



# Builds the database from schema.sql on every startup
def init_db():
    con = sqlite3.connect("origin.db")
    with open("schema.sql") as f:
        con.executescript(f.read())
    con.close()

# Run it immediately so the db is ready before any requests come in
init_db()



# Sign up route — where heroes are born (one username at a time)
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Validate inputs — no blank submissions, we're not running a charity
        if not username or not password or not confirmation:
            return "All fields are required"
        if password != confirmation:
            return "Passwords do not match"

        hashed_password = generate_password_hash(password)

        #store the user in the database
        try:
            con = sqlite3.connect("origin.db")
            cur = con.cursor()
            cur.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed_password))
            con.commit()
        except:
                return "Username already taken"  # someone else claimed it first. Too slow!

        return redirect("/login")

    else:
        return render_template("register.html")
    


# Login route — the gates of the kingdom
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Validate inputs — can't login with nothing, that's not how identity works
        if not username or not password:
            return "All fields are required"

        #check the database for the user
        con = sqlite3.connect("origin.db")
        con.row_factory = sqlite3.Row
        user = con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        con.close()

        # If no user found OR password is wrong, send 'em packing
        if not user or not check_password_hash(user["password_hash"], password):
            return "Invalid username or password"

        # Remember which user has logged in
        session["user_id"] = user["id"]

        return redirect("/")

    else:
        return render_template("login.html")



# Step 1 of character creation — every hero needs a name (even "Dave the Barbarian")
@app.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        name = request.form.get("name")
        if not name:
            return "Please enter a name"
        session["character"] = {"name": name}  # start building the character in session storage
        return redirect("/create/race")
    else:
        return render_template("create.html")
    


# Step 2 — pick your race. Elf? Dwarf? Human? The classic D&D identity crisis.
@app.route("/create/race", methods=["GET", "POST"])
@login_required
def create_race():
    if request.method == "POST":
        race = request.form.get("race")
        if not race:
            return "Please select a race"
        session["character"]["race"] = race
        return redirect("/create/class")
    else:
        return render_template("create_race.html", races = RACES)
    


# Step 3 — pick your class. Wizard? Fighter? Rogue? Choose your destiny (and your HP).
# Note: "class" is a Python reserved word, so I use "class_" — thanks, Guido.
@app.route("/create/class", methods=["GET", "POST"])
@login_required
def create_class():
    if request.method == "POST":
        class_ = request.form.get("class_")
        if not class_:
            return "Please select a class"
        session["character"]["class_"] = class_
        return redirect("/create/background")
    else:
        return render_template("create_class.html", classes = CLASSES)  
    


# Step 4 — pick your background. Were you a sailor? A criminal? A noble? D&D's version of a resume.
@app.route("/create/background", methods=["GET", "POST"])
@login_required
def create_background():
    if request.method == "POST":
        background = request.form.get("background")
        if not background:
            return "Please select a background"
        session["character"]["background"] = background
        return redirect("/create/abilities")
    else:
        return render_template("create_background.html", backgrounds = BACKGROUNDS)
    


# Step 5 — ability scores! The classic point-buy mini-game that makes or breaks your character.
# JS handles the point-buy math on the frontend; we just collect the final scores here.
@app.route("/create/abilities", methods=["GET", "POST"])
@login_required
def create_abilities():
    if request.method == "POST":
        # Grab all six ability scores from the form and cast to int (they arrive as strings)
        abilities = {
            "str": int(request.form.get("str")),
            "dex": int(request.form.get("dex")),
            "con": int(request.form.get("con")),
            "int": int(request.form.get("int")),
            "wis": int(request.form.get("wis")),
            "cha": int(request.form.get("cha"))
        }
        session["character"]["abilities"] = abilities
        return redirect("/create/skills")
    else:
        return render_template("create_abilities.html")



# Step 6 — skill proficiency selection, the most chaotic part of D&D character creation.
# Some skills you get for free (from race/class/background), some you pick yourself.
# The "any" edge case exists because D&D data is... D&D data.
@app.route("/create/skills", methods=["GET", "POST"])
@login_required
def create_skills():
    character = session.get("character")
    if not character:
        return redirect("/create")  # no character in session? go back to start, do not collect $200

    # Hunt down the data for the chosen class, background, and race from our loaded lists
    class_data = next((c for c in CLASSES if c["name"] == character["class_"]), None)
    background_data = next((b for b in BACKGROUNDS if b["name"] == character["background"]), None)
    race_data = next((r for r in RACES if r["name"] == character["race"]), None)

    # Gather up all the free skills you get just for showing up
    skills_ = {"fixed_skills":[], "choice_skills":[]}

    for i in [background_data, class_data, race_data]:
        if i.get("fixed_skills"):
            skills_["fixed_skills"].extend(i["fixed_skills"])

    if request.method == "POST":
        skills_["choice_skills"] = request.form.getlist("skills")
        skills = skills_["fixed_skills"] + skills_["choice_skills"]
        session["character"]["skills"] = skills
        return redirect("/create/review")
    else:
        return render_template(
            "create_skills.html",
            character=character,
            class_data=class_data,
            background_data=background_data,
            race_data=race_data,
            skills=skills_,
            all_skills=[  # the full skill list — needed for the "choose any" edge case. Thanks, Guildmember.
                "acrobatics","animal handling","arcana","athletics","deception",
                "history","insight","intimidation","investigation","medicine",
                "nature","perception","performance","persuasion","religion",
                "sleight of hand","stealth","survival"
            ]
        )


# Step 7 — the review page. Look at your creation. Revel in it. Or go back and fix that 8 Wisdom.
@app.route("/create/review")
@login_required
def create_review():
    character = session.get("character")
    if not character:
        return redirect("/create")
    return render_template("create_review.html", character=character)



# The final boss — actually saving the character to the database.
# This is where the rubber meets the road. Three inserts, one commit.
@app.route("/create/save")
@login_required
def create_save():
    character = session.get("character")
    if not character:
        return redirect("/create")  # nothing to save? back you go

    con = sqlite3.connect("origin.db")
    con.row_factory = sqlite3.Row

    # Insert into characters table — level 1, zero HP/AC/speed because fresh out of the box
    cur = con.execute(
        "INSERT INTO characters (user_id, name, race, class, background, level, current_hp, max_hp, armor_class, speed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (session["user_id"], character["name"], character["race"], character["class_"], character["background"], 1, 0, 0, 0, 0)
    )

    # Grab the auto-generated character ID so we can link the other tables
    character_id = cur.lastrowid
    # Skills go in as JSON — because a comma-separated list in a single column is how we roll
    skills_json = json.dumps(character["skills"])
    cur = con.execute(
        "INSERT INTO proficiencies (character_id, skills) VALUES (?, ?)",
        (character_id, skills_json)
        )


    # Insert into ability_scores table — note the column is "intel" not "int" (SQL reserved word, fun!)
    abilities = character["abilities"]
    con.execute(
        "INSERT INTO ability_scores (character_id, str, dex, con, intel, wis, cha) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (character_id, abilities["str"], abilities["dex"], abilities["con"], abilities["int"], abilities["wis"], abilities["cha"])
    )

    con.commit()  # make it official
    con.close()    # and we're done here

    # Clear character from session — the session was just temporary storage for the wizard's journey
    session.pop("character", None)

    return redirect("/")



# Logout — yeet the session into the void and send 'em back to the login page
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

