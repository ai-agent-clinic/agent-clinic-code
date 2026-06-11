from statsbombpy import sb
import requests
import json, os

os.makedirs("data/events", exist_ok=True)
three_sixty_url = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/three-sixty/3869486.json" # used the url to download raw json instead because of a known bug

# Save match events
events = sb.events(match_id=3869486)
events.to_json("data/events/3869486.json", orient="records")

os.makedirs("data/threesixty", exist_ok=True)

response = requests.get(three_sixty_url)

with open("data/threesixty/3869486.json", "w") as f:
    f.write(response.text)

# Save lineups
lineups = sb.lineups(match_id=3869486)
with open("data/lineups/3869486.json", "w") as f:
    json.dump({team: df.to_dict(orient="records") 
               for team, df in lineups.items()}, f)

print("Done")