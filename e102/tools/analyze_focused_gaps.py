import json
import math
import os
from collections import defaultdict

def parse_timestamp(ts_str):
    parts = ts_str.split(':')
    h = int(parts[0])
    m = int(parts[1])
    s = float(parts[2])
    return h * 3600 + m * 60 + s

def analyze():
    filepath = 'data/events/3869486.json'
    if not os.path.exists(filepath):
        print(f"Error: file not found at {filepath}")
        return

    print("Loading data...")
    with open(filepath, 'r') as f:
        events = json.load(f)

    # Group by period
    periods = defaultdict(list)
    for ev in events:
        periods[ev['period']].append(ev)

    # Define our different event classes
    # 1. Core Key Events (Shots, Fouls/Cards, Substitutions, Key Passes)
    def is_core_key_event(e):
        etype = e.get('type')
        if etype == 'Shot':
            return True
        if etype in ('Foul Committed', 'Foul Won'):
            return True
        if etype == 'Substitution':
            return True
        if etype == 'Pass':
            # Key Pass / Assist check
            if e.get("pass_shot_assist") or e.get("pass_goal_assist"):
                return True
        # Cards are handled under Foul Committed, but let's make sure
        if e.get("foul_committed_card"):
            return True
        return False

    # 2. All App-Weighted Events (Core Key Events + Dribbles, Pressures)
    def is_app_weighted_event(e):
        if is_core_key_event(e):
            return True
        etype = e.get('type')
        if etype in ('Dribble', 'Pressure'):
            return True
        return False

    # Collect gaps
    original_gaps_gt_10 = []
    core_key_events_list = []
    app_weighted_events_list = []
    
    # Track transition pairs for >10s gaps
    transition_pairs = defaultdict(int)

    for period, p_events in sorted(periods.items()):
        p_events_sorted = sorted(p_events, key=lambda x: x['index'])
        times = [parse_timestamp(ev['timestamp']) for ev in p_events_sorted]

        # 1. Gaps in original stream > 10 seconds
        for i in range(len(p_events_sorted) - 1):
            ev1 = p_events_sorted[i]
            ev2 = p_events_sorted[i+1]
            gap = times[i+1] - times[i]
            if gap >= 10.0:
                original_gaps_gt_10.append({
                    'period': period,
                    'gap': gap,
                    't1': times[i],
                    't2': times[i+1],
                    'ev1': ev1,
                    'ev2': ev2
                })
                # Log transition pair of types
                pair = (ev1.get('type', 'Unknown'), ev2.get('type', 'Unknown'))
                transition_pairs[pair] += 1

        # 2. Filter list of Core Key Events
        for ev in p_events_sorted:
            if is_core_key_event(ev):
                core_key_events_list.append(ev)
            if is_app_weighted_event(ev):
                app_weighted_events_list.append(ev)

    # Calculate gaps between consecutive filtered events (within same period)
    def calc_filtered_gaps(filtered_evs):
        gaps = []
        # Group by period
        p_groups = defaultdict(list)
        for ev in filtered_evs:
            p_groups[ev['period']].append(ev)
        
        for period, evs in sorted(p_groups.items()):
            evs_sorted = sorted(evs, key=lambda x: x['index'])
            for i in range(len(evs_sorted) - 1):
                t1 = parse_timestamp(evs_sorted[i]['timestamp'])
                t2 = parse_timestamp(evs_sorted[i+1]['timestamp'])
                gaps.append(t2 - t1)
        return gaps

    core_key_gaps = calc_filtered_gaps(core_key_events_list)
    app_weighted_gaps = calc_filtered_gaps(app_weighted_events_list)

    # Basic stats helper
    def stats(lst):
        if not lst:
            return {"count": 0, "min": 0, "max": 0, "mean": 0, "median": 0, "std": 0}
        lst_sorted = sorted(lst)
        n = len(lst)
        mean_val = sum(lst) / n
        median_val = lst_sorted[n // 2] if n % 2 != 0 else (lst_sorted[n // 2 - 1] + lst_sorted[n // 2]) / 2
        variance = sum((x - mean_val) ** 2 for x in lst) / n
        std_val = math.sqrt(variance)
        return {
            "count": n,
            "min": min(lst),
            "max": max(lst),
            "mean": mean_val,
            "median": median_val,
            "std": std_val
        }

    core_stats = stats(core_key_gaps)
    weighted_stats = stats(app_weighted_gaps)
    gt10_gaps = [item['gap'] for item in original_gaps_gt_10]
    gt10_stats = stats(gt10_gaps)

    # Build report
    report = []
    report.append("# Focused Event Gap Analysis Report")
    report.append(f"**Target Match:** Morocco vs Portugal (World Cup 2022)")
    report.append("")

    report.append("## Part 1: Gaps Between Core Key Events (Shots, Fouls, Cards, Key Passes, Substitutions)")
    report.append("These are the premium, high-impact events that are displayed in the timeline or highlighted as key events in the app.")
    report.append(f"- **Total Core Key Events Found:** {len(core_key_events_list)}")
    report.append(f"- **Total Calculated Gaps:** {core_stats['count']}")
    report.append(f"- **Minimum Gap:** {core_stats['min']:.3f} seconds")
    report.append(f"- **Maximum Gap:** {core_stats['max']:.3f} seconds ({core_stats['max']/60:.1f} minutes)")
    report.append(f"- **Average (Mean) Gap:** {core_stats['mean']:.3f} seconds ({core_stats['mean']/60:.2f} minutes)")
    report.append(f"- **Median Gap:** {core_stats['median']:.3f} seconds ({core_stats['median']/60:.2f} minutes)")
    report.append(f"- **Standard Deviation:** {core_stats['std']:.3f} seconds")
    report.append("")

    report.append("## Part 2: Gaps Between All App-Weighted Events (Shots, Fouls, Cards, Key Passes, Substitutions, Pressures, Dribbles)")
    report.append("These are all events that are given non-default weights in the app's timeline intensity calculation.")
    report.append(f"- **Total Weighted Events Found:** {len(app_weighted_events_list)}")
    report.append(f"- **Total Calculated Gaps:** {weighted_stats['count']}")
    report.append(f"- **Minimum Gap:** {weighted_stats['min']:.3f} seconds")
    report.append(f"- **Maximum Gap:** {weighted_stats['max']:.3f} seconds")
    report.append(f"- **Average (Mean) Gap:** {weighted_stats['mean']:.3f} seconds")
    report.append(f"- **Median Gap:** {weighted_stats['median']:.3f} seconds")
    report.append(f"- **Standard Deviation:** {weighted_stats['std']:.3f} seconds")
    report.append("")

    report.append("## Part 3: Deep Dive into Original Gaps > 10 Seconds")
    report.append(f"In the raw chronological event sequence, we found **{gt10_stats['count']}** gaps that were longer than 10 seconds.")
    report.append(f"- **Average Stoppage/Delay:** {gt10_stats['mean']:.3f} seconds")
    report.append(f"- **Median Stoppage/Delay:** {gt10_stats['median']:.3f} seconds")
    report.append(f"- **Maximum Stoppage/Delay:** {gt10_stats['max']:.3f} seconds (Romain Saïss injury substitution)")
    report.append("")

    report.append("### Top 10 Event Transitions Preceding & Succeeding Gaps > 10s")
    report.append("What causes the game to stop? We looked at the events immediately *before* and *after* each 10s+ gap:")
    report.append("| Event Before | Event After | Occurrences | Likely Scenario |")
    report.append("| :--- | :--- | :---: | :--- |")
    
    sorted_pairs = sorted(transition_pairs.items(), key=lambda x: x[1], reverse=True)
    for pair, count in sorted_pairs[:10]:
        before, after = pair
        scenario = "Unknown"
        if before == "Pass" and after == "Pass":
            scenario = "Incomplete pass went out of bounds, followed by throw-in/free-kick pass"
        elif before == "Foul Committed" and after == "Pass":
            scenario = "Foul committed, followed by a free kick pass"
        elif before == "Shot" and after == "Pass":
            scenario = "Shot went wide or saved, followed by goal kick or corner pass"
        elif before == "Substitution" and after == "Pass":
            scenario = "Substitution completed, play restarts"
        elif before == "Foul Committed" and after == "Foul Won":
            scenario = "Foul blown, player down or card shown"
        elif "Stoppage" in before or "Injury" in before:
            scenario = "Official stoppage / injury break"
        elif before == "Injury Stoppage" and after == "Substitution":
            scenario = "Injured player substituted out"
        elif before == "Ball Recovery" and after == "Pass":
            scenario = "Ball won back, delay before next pass"
        elif before == "Clearance" and after == "Pass":
            scenario = "Ball cleared out of bounds, followed by throw-in pass"
        else:
            scenario = f"Restart/reset after {before.lower()}"
        report.append(f"| `{before}` | `{after}` | {count} | {scenario} |")
    report.append("")

    report.append("### Breakdown of the 5 Longest Gaps (>30s) in the Match")
    # Sort original gaps by gap duration
    longest_gaps = sorted(original_gaps_gt_10, key=lambda x: x['gap'], reverse=True)
    report.append("| Rank | Duration | Period | Start Time | Preceding Event | Succeeding Event | Context / Detail |")
    report.append("| :---: | :---: | :---: | :---: | :--- | :--- | :--- |")
    for i, g in enumerate(longest_gaps[:5]):
        ev1 = g['ev1']
        ev2 = g['ev2']
        desc = ""
        if ev1.get('type') == 'Injury Stoppage' and ev2.get('type') == 'Substitution':
            desc = f"Injury to {ev1.get('player','player')} leading to substitution of {ev2.get('substitution_replacement','replacement')}"
        elif ev1.get('type') == 'Foul Committed' and ev1.get('foul_committed_card'):
            desc = f"Foul leading to a card ({ev1.get('foul_committed_card')}) for {ev1.get('player','player')}"
        elif ev1.get('type') == 'Shot' and ev1.get('shot_outcome') == 'Goal':
            desc = f"Goal celebration and kickoff reset (Goal by {ev1.get('player','player')})"
        else:
            desc = f"Restart after {ev1.get('type').lower()} by {ev1.get('player','N/A')}"
            
        report.append(f"| {i+1} | {g['gap']:.1f}s | {g['period']} | {ev1.get('timestamp')} | `{ev1.get('type')}` ({ev1.get('player','—')}) | `{ev2.get('type')}` ({ev2.get('player','—')}) | {desc} |")
    report.append("")

    report_text = "\n".join(report)
    
    with open('tmp/event_time_analysis_focused.md', 'w') as f_out:
        f_out.write(report_text)

    # Save JSON structure
    json_data = {
        "core_key_stats": core_stats,
        "app_weighted_stats": weighted_stats,
        "gt10_stats": gt10_stats,
        "top_transitions": [[list(k), v] for k, v in sorted_pairs[:10]],
        "longest_gaps": [
            {
                "gap": g['gap'],
                "period": g['period'],
                "t1_str": g['ev1'].get('timestamp'),
                "type1": g['ev1'].get('type'),
                "player1": g['ev1'].get('player'),
                "type2": g['ev2'].get('type'),
                "player2": g['ev2'].get('player')
            }
            for g in longest_gaps[:10]
        ]
    }
    with open('tmp/event_time_analysis_focused.json', 'w') as f_out:
        json.dump(json_data, f_out, indent=2)

    print("\n--- Summary ---")
    print(f"Core key events gap mean: {core_stats['mean']:.3f}s | Max: {core_stats['max']:.3f}s")
    print(f"Weighted events gap mean: {weighted_stats['mean']:.3f}s | Max: {weighted_stats['max']:.3f}s")
    print(f"Gaps > 10s count: {gt10_stats['count']} | Mean duration: {gt10_stats['mean']:.3f}s")
    print("Results saved to tmp/event_time_analysis_focused.md and tmp/event_time_analysis_focused.json")

if __name__ == '__main__':
    analyze()
