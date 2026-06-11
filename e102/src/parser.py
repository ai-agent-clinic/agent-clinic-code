import json
from pathlib import Path

MATCH_ID = 3869486
DATA_DIR = Path(__file__).parent.parent / "data"

_INTENSITY_WEIGHTS = {
    "Dribble": 4,
    "Foul Committed": 3,
    "Foul Won": 3,
    "Pressure": 2,
}
_SHOT_WEIGHT = 10
_GOAL_WEIGHT = 20
_KEY_PASS_WEIGHT = 7
_DEFAULT_WEIGHT = 1


class MatchData:
    def __init__(self):
        self._events = None
        self._frames = {}   # event_uuid -> frame dict
        self._lineups = None

    def load(self):
        events_path = DATA_DIR / "events" / f"{MATCH_ID}.json"
        frames_path = DATA_DIR / "threesixty" / f"{MATCH_ID}.json"
        lineups_path = DATA_DIR / "lineups" / f"{MATCH_ID}.json"

        with open(events_path, encoding="utf-8") as f:
            self._events = json.load(f)

        with open(frames_path, encoding="utf-8") as f:
            self._frames = {fr["event_uuid"]: fr for fr in json.load(f)}

        with open(lineups_path, encoding="utf-8") as f:
            self._lineups = json.load(f)

    def _require_loaded(self):
        if self._events is None:
            raise RuntimeError("Call load() before accessing data")

    def _team_names(self):
        return list({e["team"] for e in self._events if e.get("team")})

    def get_events(self):
        self._require_loaded()
        result = []
        for e in self._events:
            loc = e.get("location") or []
            # Each event type stores end location under a different key
            end_loc = (
                e.get("pass_end_location")
                or e.get("carry_end_location")
                or e.get("shot_end_location")  # may be 3-D [x, y, z]
                or []
            )
            result.append({
                "event_id": e["id"],
                "type": e.get("type"),
                "minute": e.get("minute"),
                "second": e.get("second"),
                "period": e.get("period"),
                "timestamp": e.get("timestamp"),
                "team": e.get("team"),
                "player": e.get("player"),
                "player_id": e.get("player_id"),
                "position": e.get("position"),
                "location_x": loc[0] if loc else None,
                "location_y": loc[1] if len(loc) > 1 else None,
                "end_location_x": end_loc[0] if end_loc else None,
                "end_location_y": end_loc[1] if len(end_loc) > 1 else None,
                # Shot attributes
                "shot_outcome": e.get("shot_outcome"),
                "shot_xg": e.get("shot_statsbomb_xg"),
                "shot_technique": e.get("shot_technique"),
                "shot_body_part": e.get("shot_body_part"),
                # Pass attributes
                "pass_outcome": e.get("pass_outcome"),
                "pass_length": e.get("pass_length"),
                "is_key_pass": bool(e.get("pass_shot_assist") or e.get("pass_goal_assist")),
                "is_goal_assist": bool(e.get("pass_goal_assist")),
                # Card / foul
                "foul_committed_card": e.get("foul_committed_card"),
                # Substitution
                "substitution_replacement": e.get("substitution_replacement"),
                # Other
                "under_pressure": e.get("under_pressure"),
                "play_pattern": e.get("play_pattern"),
            })
        return result

    def get_freeze_frame(self, event_id):
        self._require_loaded()
        event = next((e for e in self._events if e["id"] == event_id), None)
        if not event:
            return []

        actor_team = event.get("team", "")
        teams = self._team_names()
        other_team = next((t for t in teams if t != actor_team), None)

        # shot_freeze_frame carries player identities; prefer it over 360 data
        actor_name = event.get("player")
        actor_loc  = event.get("location") or []
        actor_pid  = event.get("player_id")

        sfp = event.get("shot_freeze_frame")
        if sfp:
            result = []
            for p in sfp:
                loc = p.get("location") or []
                pi  = p.get("player") or {}
                result.append({
                    "player_id":   pi.get("id"),
                    "player_name": pi.get("name"),
                    "team":        actor_team if p.get("teammate") else other_team,
                    "is_teammate": bool(p.get("teammate")),
                    "is_actor":    False,
                    "location_x":  loc[0] if loc else None,
                    "location_y":  loc[1] if len(loc) > 1 else None,
                })
            # StatsBomb shot_freeze_frame omits the shooter — inject them at the end
            if actor_name and not any(r["player_name"] == actor_name for r in result):
                result.append({
                    "player_id":   actor_pid,
                    "player_name": actor_name,
                    "team":        actor_team,
                    "is_teammate": True,
                    "is_actor":    True,
                    "location_x":  actor_loc[0] if actor_loc else None,
                    "location_y":  actor_loc[1] if len(actor_loc) > 1 else None,
                })
            return result

        # 360 data: positions without player identities
        frame = self._frames.get(event_id)
        if not frame:
            return []

        result = []
        for p in frame["freeze_frame"]:
            loc        = p.get("location") or []
            is_actor   = bool(p.get("actor", False))
            is_teammate = p.get("teammate", False)
            result.append({
                "player_id":   None,
                "player_name": actor_name if is_actor else None,
                "team":        actor_team if (is_teammate or is_actor) else other_team,
                "is_teammate": is_teammate or is_actor,
                "is_actor":    is_actor,
                "location_x":  loc[0] if loc else None,
                "location_y":  loc[1] if len(loc) > 1 else None,
            })
        return result

    def get_timeline_data(self):
        self._require_loaded()
        buckets = {
            m: {"raw_score": 0.0, "events_in_minute": [], "quality_multiplier": 1.0}
            for m in range(96)
        }

        for e in self._events:
            minute = min(int(e.get("minute") or 0), 95)
            etype = e.get("type", "")

            if etype == "Shot":
                outcome = e.get("shot_outcome", "")
                weight = _GOAL_WEIGHT if outcome == "Goal" else _SHOT_WEIGHT
                # Quality multiplier: best shot quality in this minute wins
                if outcome == "Goal":
                    multiplier = 2.5
                elif outcome in ("Saved", "Saved To Post"):
                    multiplier = 1.5
                else:  # Off T, Blocked, Post, Wayward
                    multiplier = 1.2
                buckets[minute]["quality_multiplier"] = max(
                    buckets[minute]["quality_multiplier"], multiplier
                )
            elif etype == "Pass" and (e.get("pass_shot_assist") or e.get("pass_goal_assist")):
                weight = _KEY_PASS_WEIGHT
            else:
                weight = _INTENSITY_WEIGHTS.get(etype, _DEFAULT_WEIGHT)

            buckets[minute]["raw_score"] += weight
            buckets[minute]["events_in_minute"].append(etype)

        # Apply quality multiplier then normalize
        for b in buckets.values():
            b["raw_score"] *= b["quality_multiplier"]

        max_score = max(b["raw_score"] for b in buckets.values()) or 1.0

        return [
            {
                "minute": m,
                "intensity_score": round(buckets[m]["raw_score"] / max_score, 4),
                "events_in_minute": buckets[m]["events_in_minute"],
            }
            for m in range(96)
        ]

    def get_lineups(self):
        self._require_loaded()
        return self._lineups

    def get_match_info(self):
        self._require_loaded()
        teams = sorted({e["team"] for e in self._events if e.get("team")})
        goals = {
            team: sum(
                1 for e in self._events
                if e.get("type") == "Shot"
                and e.get("shot_outcome") == "Goal"
                and e.get("team") == team
            )
            for team in teams
        }
        return {
            "match_id": MATCH_ID,
            "competition": "2022 FIFA World Cup",
            "stage": "Quarter-final",
            "date": "2022-12-10",
            "home_team": "Morocco",
            "away_team": "Portugal",
            "score": f"Morocco {goals.get('Morocco', 0)} - {goals.get('Portugal', 0)} Portugal",
            "goals": goals,
            "teams": teams,
        }
