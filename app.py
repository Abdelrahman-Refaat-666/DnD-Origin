from flask import Flask, render_template
import json, sqlite3

app = Flask(__name__)

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
def index():
    return render_template("index.html")



def init_db():
    con = sqlite3.connect("origin.db")
    with open("schema.sql") as f:
        con.executescript(f.read())
    con.close()
    
init_db()

if __name__ == "__main__":
    app.run(debug=True)