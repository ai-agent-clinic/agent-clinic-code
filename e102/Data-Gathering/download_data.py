import os
import sys
import json
import requests

def setup_data():
    """Download StatsBomb open data for Match ID 3869486."""
    
    # 1. Verify dependencies
    try:
        from statsbombpy import sb
    except ImportError:
        print("Error: 'statsbombpy' not found. Please run 'pip install statsbombpy' or 'uv sync'.")
        sys.exit(1)

    match_id = 3869486
    base_dir = "data"
    
    # 2. Create directory structure
    dirs = [
        os.path.join(base_dir, "events"),
        os.path.join(base_dir, "lineups"),
        os.path.join(base_dir, "threesixty"),
        os.path.join(base_dir, "worldcup_2026")
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"Directory ready: {d}")

    # 3. Download Match Events
    print(f"Downloading events for match {match_id}...")
    events = sb.events(match_id=match_id)
    events_path = os.path.join(base_dir, "events", f"{match_id}.json")
    events.to_json(events_path, orient="records")
    print(f"Saved: {events_path}")

    # 4. Download 360 Frames (using raw URL due to known statsbombpy bug)
    print(f"Downloading 360 frames for match {match_id}...")
    three_sixty_url = f"https://raw.githubusercontent.com/statsbomb/open-data/master/data/three-sixty/{match_id}.json"
    ts_path = os.path.join(base_dir, "threesixty", f"{match_id}.json")
    try:
        response = requests.get(three_sixty_url)
        response.raise_for_status()
        with open(ts_path, "w", encoding="utf-8") as f:
            f.write(response.text)
        print(f"Saved: {ts_path}")
    except Exception as e:
        print(f"Warning: Failed to download 360 frames: {e}")

    # 5. Download Lineups
    print(f"Downloading lineups for match {match_id}...")
    lineups = sb.lineups(match_id=match_id)
    lineups_path = os.path.join(base_dir, "lineups", f"{match_id}.json")
    with open(lineups_path, "w", encoding="utf-8") as f:
        json.dump({team: df.to_dict(orient="records") for team, df in lineups.items()}, f)
    print(f"Saved: {lineups_path}")

    # 6. World Cup 2026 Data
    # Note: These files are specific mock data provided with the project.
    # If missing, they must be restored from a project backup.
    wc2026_dir = os.path.join(base_dir, "worldcup_2026")
    files = ["games.csv", "groups.csv", "stadiums.csv", "teams.csv"]
    missing = [f for f in files if not os.path.exists(os.path.join(wc2026_dir, f))]
    
    if missing:
        print("\nNote: World Cup 2026 mock data files are missing:")
        for f in missing:
            print(f"  - {f}")
        print("These files are required for the championship preview feature.")
    
    print("\nData setup complete.")

if __name__ == "__main__":
    setup_data()