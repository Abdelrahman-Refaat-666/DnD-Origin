import json

with open("data/races.json", encoding="utf-8") as f:
    RACES = [i for i in json.load(f)["results"] if i["document__slug"] == "wotc-srd"]

with open("data/classes.json", encoding="utf-8") as f:
    CLASSES = [i for i in json.load(f)["results"] if i["document__slug"] == "wotc-srd"]

with open("data/backgrounds.json", encoding="utf-8") as f:
    BACKGROUNDS = [i for i in json.load(f)["results"] if i["document__slug"] in ["wotc-srd", "a5e"]]

print(len(RACES))

print(len(CLASSES))

print(len(BACKGROUNDS))
