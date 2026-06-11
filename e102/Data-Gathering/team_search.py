from statsbombpy import sb

matches = sb.matches(competition_id=43, season_id=106)

morocco_matches = matches[ # Replace morocco with the team you're looking for
    (matches['home_team'] == 'Morocco') |
    (matches['away_team'] == 'Morocco')
]

print(morocco_matches[['match_id', 'home_team', 'away_team', 'match_date', 'competition_stage']].to_string())