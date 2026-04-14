import json

# Quick-and-dirty data dump — load the cleaned D&D data and print some sample entries
# Basically a sanity check to make sure the JSON files aren't garbage

with open("data/clean_classes.json", encoding="utf-8") as f:
    CLASSES = json.load(f)  # all the classes: Paladin, Wizard, Barbarian, etc.

with open("data/clean_races.json", encoding="utf-8") as f:
    RACES = json.load(f)  # all the races: Elf, Dwarf, Human, and friends

with open("data/clean_backgrounds.json", encoding="utf-8") as f:
    BACKGROUNDS = json.load(f)  # all the backgrounds: Acolyte, Criminal, Noble, etc.


# Print a few entries to verify the data loaded correctly
# If you see structured JSON here instead of a traceback, we're golden
print(CLASSES["Paladin"])
print(BACKGROUNDS["Acolyte"])
print(RACES["Elf"])