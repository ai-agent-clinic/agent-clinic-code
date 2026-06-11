import json
import math
import os
from collections import defaultdict

def parse_timestamp(ts_str):
    # ts_str is like '00:00:00.436' or '00:15:32'
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

    print(f"Loaded {len(events)} events.")

    # Group by period
    periods = defaultdict(list)
    for ev in events:
        periods[ev['period']].append(ev)

    all_gaps = []
    nonzero_gaps = []
    gaps_by_period = defaultdict(list)

    # We want to identify details for the max and min gaps
    max_gap = -1
    max_gap_info = {}
    min_nonzero_gap = float('inf')
    min_nonzero_gap_info = {}

    for period, p_events in sorted(periods.items()):
        # Sort by index within the period
        p_events_sorted = sorted(p_events, key=lambda x: x['index'])
        
        # Check timestamp consistency
        times = []
        for ev in p_events_sorted:
            times.append(parse_timestamp(ev['timestamp']))

        print(f"Period {period}: {len(p_events_sorted)} events. Time range: {p_events_sorted[0]['timestamp']} to {p_events_sorted[-1]['timestamp']}")

        for i in range(len(p_events_sorted) - 1):
            ev1 = p_events_sorted[i]
            ev2 = p_events_sorted[i+1]
            t1 = times[i]
            t2 = times[i+1]
            gap = t2 - t1
            if gap < 0:
                # Let's see if there are negative gaps (out of order timestamps vs index)
                # It's possible StatsBomb has small noise or we should check
                pass

            all_gaps.append(gap)
            gaps_by_period[period].append(gap)
            if gap > 0:
                nonzero_gaps.append(gap)

            if gap > max_gap:
                max_gap = gap
                max_gap_info = {
                    'period': period,
                    'gap': gap,
                    'event1': {
                        'index': ev1['index'],
                        'type': ev1['type'],
                        'timestamp': ev1['timestamp'],
                        'team': ev1.get('team', 'N/A'),
                        'player': ev1.get('player', 'N/A')
                    },
                    'event2': {
                        'index': ev2['index'],
                        'type': ev2['type'],
                        'timestamp': ev2['timestamp'],
                        'team': ev2.get('team', 'N/A'),
                        'player': ev2.get('player', 'N/A')
                    }
                }

            if 0 < gap < min_nonzero_gap:
                min_nonzero_gap = gap
                min_nonzero_gap_info = {
                    'period': period,
                    'gap': gap,
                    'event1': {
                        'index': ev1['index'],
                        'type': ev1['type'],
                        'timestamp': ev1['timestamp'],
                        'team': ev1.get('team', 'N/A'),
                        'player': ev1.get('player', 'N/A')
                    },
                    'event2': {
                        'index': ev2['index'],
                        'type': ev2['type'],
                        'timestamp': ev2['timestamp'],
                        'team': ev2.get('team', 'N/A'),
                        'player': ev2.get('player', 'N/A')
                    }
                }

    # Time Windows Bins
    bins = [
        ("Simultaneous (0.0s)", lambda g: g == 0.0),
        ("Micro-gap (0.0s < gap <= 0.5s)", lambda g: 0.0 < g <= 0.5),
        ("Short gap (0.5s < gap <= 1.0s)", lambda g: 0.5 < g <= 1.0),
        ("Quick play (1.0s < gap <= 2.0s)", lambda g: 1.0 < g <= 2.0),
        ("Standard play (2.0s < gap <= 5.0s)", lambda g: 2.0 < g <= 5.0),
        ("Transition (5.0s < gap <= 10.0s)", lambda g: 5.0 < g <= 10.0),
        ("Stoppage / Slow (10.0s < gap <= 30.0s)", lambda g: 10.0 < g <= 30.0),
        ("Dead ball / Brief pause (30.0s < gap <= 60.0s)", lambda g: 30.0 < g <= 60.0),
        ("Major stoppage (gap > 60.0s)", lambda g: g > 60.0)
    ]

    bin_counts = defaultdict(int)
    for gap in all_gaps:
        matched = False
        for name, cond in bins:
            if cond(gap):
                bin_counts[name] += 1
                matched = True
                break
        if not matched:
            bin_counts["Other / Negative"] += 1

    # Basic stats helper
    def stats(lst):
        if not lst:
            return {"min": 0, "max": 0, "mean": 0, "median": 0, "std": 0}
        lst_sorted = sorted(lst)
        n = len(lst)
        mean_val = sum(lst) / n
        median_val = lst_sorted[n // 2] if n % 2 != 0 else (lst_sorted[n // 2 - 1] + lst_sorted[n // 2]) / 2
        variance = sum((x - mean_val) ** 2 for x in lst) / n
        std_val = math.sqrt(variance)
        return {
            "min": min(lst),
            "max": max(lst),
            "mean": mean_val,
            "median": median_val,
            "std": std_val
        }

    all_stats = stats(all_gaps)
    nz_stats = stats(nonzero_gaps)

    # Let's build a nice markdown string
    report = []
    report.append("# Event Time Distribution Analysis Report")
    report.append(f"**Target Match ID:** 3869486 (Morocco vs Portugal, World Cup 2022)")
    report.append(f"**Total Events:** {len(events)}")
    report.append(f"**Total Calculated Gaps:** {len(all_gaps)}")
    report.append("")

    report.append("## Overall Gap Statistics (Including Simultaneous Events)")
    report.append(f"- **Minimum Gap:** {all_stats['min']:.3f} seconds")
    report.append(f"- **Maximum Gap (Longest):** {all_stats['max']:.3f} seconds")
    report.append(f"- **Mean (Average) Gap:** {all_stats['mean']:.3f} seconds")
    report.append(f"- **Median Gap:** {all_stats['median']:.3f} seconds")
    report.append(f"- **Standard Deviation:** {all_stats['std']:.3f} seconds")
    report.append("")

    report.append("## Non-Zero Gap Statistics (Excluding Simultaneous Events)")
    report.append("Since many soccer events (like a pass and receipt) are recorded at the exact same millisecond, simultaneous events (0.0s gap) make up a large portion of the dataset. Excluding them gives a better representation of active play timing:")
    report.append(f"- **Total Non-Zero Gaps:** {len(nonzero_gaps)} ({len(nonzero_gaps)/len(all_gaps)*100:.1f}% of all gaps)")
    report.append(f"- **Minimum Non-Zero Gap:** {nz_stats['min']:.3f} seconds")
    report.append(f"- **Maximum Gap:** {nz_stats['max']:.3f} seconds")
    report.append(f"- **Mean Gap:** {nz_stats['mean']:.3f} seconds")
    report.append(f"- **Median Gap:** {nz_stats['median']:.3f} seconds")
    report.append(f"- **Standard Deviation:** {nz_stats['std']:.3f} seconds")
    report.append("")

    report.append("## Gap Distribution by Time Window")
    report.append("| Time Window | Count | Percentage | Description |")
    report.append("| :--- | :---: | :---: | :--- |")
    for name, _ in bins:
        count = bin_counts[name]
        pct = (count / len(all_gaps)) * 100
        report.append(f"| {name} | {count} | {pct:.2f}% | |")
    if "Other / Negative" in bin_counts:
        count = bin_counts["Other / Negative"]
        pct = (count / len(all_gaps)) * 100
        report.append(f"| Other / Negative | {count} | {pct:.2f}% | |")
    report.append("")

    report.append("## Key Extremes Details")
    report.append("### Longest Time Gap between Events")
    report.append(f"**Duration:** {max_gap:.3f} seconds")
    report.append(f"- **Event 1 (Before):** Index {max_gap_info['event1']['index']} | Type: `{max_gap_info['event1']['type']}` | Timestamp: `{max_gap_info['event1']['timestamp']}` | Team: {max_gap_info['event1']['team']} | Player: {max_gap_info['event1']['player']}")
    report.append(f"- **Event 2 (After):** Index {max_gap_info['event2']['index']} | Type: `{max_gap_info['event2']['type']}` | Timestamp: `{max_gap_info['event2']['timestamp']}` | Team: {max_gap_info['event2']['team']} | Player: {max_gap_info['event2']['player']}")
    report.append(f"- **Context:** Usually occurs during major injury stoppages, VAR reviews, substitutions, or water breaks in the period.")
    report.append("")

    report.append("### Shortest Non-Zero Time Gap")
    report.append(f"**Duration:** {min_nonzero_gap:.3f} seconds")
    report.append(f"- **Event 1 (Before):** Index {min_nonzero_gap_info['event1']['index']} | Type: `{min_nonzero_gap_info['event1']['type']}` | Timestamp: `{min_nonzero_gap_info['event1']['timestamp']}` | Team: {min_nonzero_gap_info['event1']['team']} | Player: {min_nonzero_gap_info['event1']['player']}")
    report.append(f"- **Event 2 (After):** Index {min_nonzero_gap_info['event2']['index']} | Type: `{min_nonzero_gap_info['event2']['type']}` | Timestamp: `{min_nonzero_gap_info['event2']['timestamp']}` | Team: {min_nonzero_gap_info['event2']['team']} | Player: {min_nonzero_gap_info['event2']['player']}")
    report.append("")

    report.append("## Stats by Period")
    for period in sorted(periods.keys()):
        p_gaps = gaps_by_period[period]
        p_stats = stats(p_gaps)
        p_nz = [g for g in p_gaps if g > 0]
        p_nz_stats = stats(p_nz)
        report.append(f"### Period {period}")
        report.append(f"- **Total Gaps:** {len(p_gaps)}")
        report.append(f"- **All Gaps Mean:** {p_stats['mean']:.3f}s | Median: {p_stats['median']:.3f}s | Max: {p_stats['max']:.3f}s")
        report.append(f"- **Non-Zero Gaps Mean:** {p_nz_stats['mean']:.3f}s | Median: {p_nz_stats['median']:.3f}s | Max: {p_nz_stats['max']:.3f}s")
        report.append("")

    report_text = "\n".join(report)
    
    # Save the report
    with open('tmp/event_time_analysis.md', 'w') as f_out:
        f_out.write(report_text)
    
    # Save a JSON file as well
    json_data = {
        "total_events": len(events),
        "total_gaps": len(all_gaps),
        "all_gaps_stats": all_stats,
        "nonzero_gaps_stats": nz_stats,
        "bin_counts": dict(bin_counts),
        "max_gap": max_gap_info,
        "min_nonzero_gap": min_nonzero_gap_info
    }
    with open('tmp/event_time_analysis.json', 'w') as f_out:
        json.dump(json_data, f_out, indent=2)

    print("\n--- Summary ---")
    print(f"Total events: {len(events)}")
    print(f"Average time between all events: {all_stats['mean']:.3f}s")
    print(f"Average time between non-zero events: {nz_stats['mean']:.3f}s")
    print(f"Max gap: {max_gap:.3f}s (Index {max_gap_info['event1']['index']} to {max_gap_info['event2']['index']})")
    print(f"Min gap (overall): {all_stats['min']:.3f}s")
    print(f"Min non-zero gap: {min_nonzero_gap:.3f}s")
    print("Results saved to tmp/event_time_analysis.md and tmp/event_time_analysis.json")

if __name__ == '__main__':
    analyze()
