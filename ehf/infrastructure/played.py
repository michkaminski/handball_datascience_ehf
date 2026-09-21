PLAYED_SQL = (
    "m.status = 'played' AND NOT COALESCE(m.is_walkover, FALSE) "
    "AND COALESCE(m.result_type, '') <> 'walkover'"
)

HOME_NAME = "COALESCE(home_ed.display_name, home_team.display_name)"
AWAY_NAME = "COALESCE(away_ed.display_name, away_team.display_name)"
SCORE_HOME = "COALESCE(m.score_home, home_team.goals)"
SCORE_AWAY = "COALESCE(m.score_away, away_team.goals)"

TEAM_JOINS = """
LEFT JOIN ehf.club_edition home_ed
    ON home_ed.club_id = m.home_club_id
   AND home_ed.competition_edition_id = m.competition_edition_id
LEFT JOIN ehf.club_edition away_ed
    ON away_ed.club_id = m.away_club_id
   AND away_ed.competition_edition_id = m.competition_edition_id
LEFT JOIN ehf.match_team home_team
    ON home_team.match_id = m.id AND home_team.side = 'home'
LEFT JOIN ehf.match_team away_team
    ON away_team.match_id = m.id AND away_team.side = 'away'
"""

EDITION_JOINS = """
JOIN ehf.competition_edition ce ON ce.id = m.competition_edition_id
JOIN ehf.season s ON s.id = ce.season_id
JOIN ehf.competition c ON c.id = ce.competition_id
"""
