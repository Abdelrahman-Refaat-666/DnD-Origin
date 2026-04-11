from flask import Flask, render_template, request, redirect, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import json, sqlite3

app = Flask(__name__)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)


# Decorator to require login for certain routes
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get("user_id") is None:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function



# Load local data on startup
# added the encoding because the data includes some wierd letters
# Used a technique called list comprehension to fitler out non-original data
with open("data/races.json", encoding="utf-8") as f:
    RACES = [i for i in json.load(f)["results"] if i["document__slug"] == "wotc-srd"]

with open("data/classes.json", encoding="utf-8") as f:
    CLASSES = [i for i in json.load(f)["results"] if i["document__slug"] == "wotc-srd"]

with open("data/backgrounds.json", encoding="utf-8") as f:
    BACKGROUNDS = [i for i in json.load(f)["results"] if i["document__slug"] in ["wotc-srd", "a5e"]]



@app.route("/")
@login_required
def index():
    con = sqlite3.connect("origin.db")
    con.row_factory = sqlite3.Row
    characters = con.execute(
        "SELECT * FROM characters WHERE user_id = ?", (session["user_id"],)
    ).fetchall()
    con.close()
    return render_template("index.html", characters=characters)



def init_db():
    con = sqlite3.connect("origin.db")
    with open("schema.sql") as f:
        con.executescript(f.read())
    con.close()
    
init_db()



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        # Validate inputs
        if not username or not password or not confirmation:
            return "All fields are required"
        if password != confirmation:
            return "Passwords do not match"
        
        # Hash the password
        hashed_password = generate_password_hash(password)

        #store the user in the database
        try:
            con = sqlite3.connect("origin.db")
            cur = con.cursor()
            cur.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, hashed_password))
            con.commit()
        except:
                return "Username already taken"

        return redirect("/login")

    else:
        return render_template("register.html")
    


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        # Validate inputs
        if not username or not password:
            return "All fields are required"

        #check the database for the user
        con = sqlite3.connect("origin.db")
        con.row_factory = sqlite3.Row
        user = con.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        con.close()

        if not user or not check_password_hash(user["password_hash"], password):
            return "Invalid username or password"

        # Remember which user has logged in
        session["user_id"] = user["id"]

        # Redirect user to home page
        return redirect("/")

    else:
        return render_template("login.html")



@app.route("/create", methods=["GET", "POST"])
@login_required
def create():
    if request.method == "POST":
        name = request.form.get("name")
        if not name:
            return "Please enter a name"
        session["character"] = {"name": name}
        return redirect("/create/race")
    else:
        return render_template("create.html")
    


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


    
@app.route("/create/abilities", methods=["GET", "POST"])
@login_required
def create_abilities():
    if request.method == "POST":
        abilities = {
            "str": int(request.form.get("str")),
            "dex": int(request.form.get("dex")),
            "con": int(request.form.get("con")),
            "int": int(request.form.get("int")),
            "wis": int(request.form.get("wis")),
            "cha": int(request.form.get("cha"))
        }
        session["character"]["abilities"] = abilities
        return redirect("/create/review")
    else:
        return render_template("create_abilities.html")
    


@app.route("/create/review")
@login_required
def create_review():
    character = session.get("character")
    if not character:
        return redirect("/create")
    return render_template("create_review.html", character=character)



@app.route("/create/save")
@login_required
def create_save():
    character = session.get("character")
    if not character:
        return redirect("/create")

    con = sqlite3.connect("origin.db")
    con.row_factory = sqlite3.Row

    # Insert into characters table
    cur = con.execute(
        "INSERT INTO characters (user_id, name, race, class, background, level, current_hp, max_hp, armor_class, speed) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (session["user_id"], character["name"], character["race"], character["class_"], character["background"], 1, 0, 0, 0, 0)
    )
    character_id = cur.lastrowid

    # Insert into ability_scores table
    abilities = character["abilities"]
    con.execute(
        "INSERT INTO ability_scores (character_id, str, dex, con, intel, wis, cha) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (character_id, abilities["str"], abilities["dex"], abilities["con"], abilities["int"], abilities["wis"], abilities["cha"])
    )

    con.commit()
    con.close()

    # Clear character from session
    session.pop("character", None)

    return redirect("/")



@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

