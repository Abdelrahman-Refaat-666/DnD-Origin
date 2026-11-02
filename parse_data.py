import json, os

# Quick-and-dirty data dump — load the cleaned D&D data and print some sample entries
# Basically a sanity check to make sure the JSON files aren't garbage
# Run it with: python parse_data.py

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

with open(os.path.join(DATA_DIR, "clean_classes.json"), encoding="utf-8") as f:
    CLASSES = json.load(f)  # all the classes: paladin, wizard, barbarian, etc.

with open(os.path.join(DATA_DIR, "clean_races.json"), encoding="utf-8") as f:
    RACES = json.load(f)  # all the races: elf, dwarf, human, and friends

with open(os.path.join(DATA_DIR, "clean_backgrounds.json"), encoding="utf-8") as f:
    BACKGROUNDS = json.load(f)  # all the backgrounds: Acolyte, Criminal, Sage, etc.


# Print a few entries to verify the data loaded correctly
# If you see structured JSON here instead of a traceback, we're golden
# (class and race names are lowercase in the clean files, background names are capitalized)
print(f"{len(CLASSES)} classes, {len(RACES)} races, {len(BACKGROUNDS)} backgrounds\n")
print(CLASSES["paladin"])
print(BACKGROUNDS["Acolyte"]["fixed_skills"], BACKGROUNDS["Acolyte"]["choice_skills"])
print(RACES["elf"])
