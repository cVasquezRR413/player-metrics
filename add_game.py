import sqlite3
import csv
import io
import os
import sys
from datetime import datetime
from database import get_connection

def is_blank(line):
    return line.strip() == '' or all(c == ',' for c in line.strip())

def add_game(filepath):
    with open(filepath, newline='', encoding='utf-8-sig') as f:
        content = f.read()

    lines = content.split('\n')

    # Find all blank line indices
    blank_indices = [i for i, line in enumerate(lines) if is_blank(line)]

    if len(blank_indices) < 2:
        print("Error: Expected at least 2 blank separator lines.")
        return

    first_blank = blank_indices[0]
    second_blank = blank_indices[1]

    # Player stats: everything before second blank (two teams, one header)
    header_line = lines[0]
    team1_rows = lines[1:first_blank]
    team2_rows = lines[first_blank + 1:second_blank]

    # Build a single player section with one header
    all_player_lines = [header_line] + team1_rows + team2_rows
    player_section = '\n'.join(l for l in all_player_lines if not is_blank(l))

    # Metadata: after second blank
    meta_lines = [l for l in lines[second_blank + 1:] 
                  if l.strip() and not is_blank(l)]

    if len(meta_lines) < 2:
        print("Error: Could not find metadata.")
        return

    meta_headers = [h.strip() for h in meta_lines[0].split(',')]
    meta_values = [v.strip() for v in meta_lines[1].split(',')]
    meta = dict(zip(meta_headers, meta_values))

    away_team = meta.get('Away Team', '').strip()
    home_team = meta.get('Home Team', '').strip()
    away_score = int(meta.get('Away Score', 0))
    home_score = int(meta.get('Home Score', 0))
    date_raw = meta.get('Date', '').strip()
    user_team = meta.get('User Team', '').strip()

    try:
        date = datetime.strptime(date_raw, '%m/%d/%Y').strftime('%Y-%m-%d')
    except:
        date = date_raw

    if user_team == home_team:
        home_away = 'H'
        user_score = home_score
        opp_score = away_score
        opp_team = away_team
    else:
        home_away = 'A'
        user_score = away_score
        opp_score = home_score
        opp_team = home_team

    win_loss = 'W' if user_score > opp_score else 'L'

    # Parse player stats — team assignment comes directly from TEAM column
    player_reader = csv.DictReader(io.StringIO(player_section))
    player_rows = [r for r in player_reader if r.get('PLAYER_NAME', '').strip()]

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO games (date, home_away, win_loss)
        VALUES (?, ?, ?)
    """, (date, home_away, win_loss))
    game_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO teams (game_id, team_name, is_your_team, score)
        VALUES (?, ?, 1, ?)
    """, (game_id, user_team, user_score))
    your_team_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO teams (game_id, team_name, is_your_team, score)
        VALUES (?, ?, 0, ?)
    """, (game_id, opp_team, opp_score))
    opp_team_id = cursor.lastrowid

    def safe_int(val, default=0):
        try:
            return int(str(val).strip()) if str(val).strip() != '' else default
        except:
            return default

    for row in player_rows:
        team_name = row.get('TEAM', '').strip()
        # Direct string match — no fuzzy logic needed
        team_id = your_team_id if team_name == user_team else opp_team_id

        cursor.execute("""
            INSERT INTO player_stats (
                game_id, team_id, player_name, minutes, points, assists,
                rebounds, off_rebounds, steals, blocks, turnovers,
                fg_made, fg_attempted, three_made, three_attempted,
                ft_made, ft_attempted, fouls, plus_minus,
                points_responsible_for, dunks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            game_id, team_id, row.get('PLAYER_NAME', '').strip(),
            safe_int(row.get('MIN')), safe_int(row.get('PTS')),
            safe_int(row.get('AST')), safe_int(row.get('REB')),
            safe_int(row.get('OR')), safe_int(row.get('STL')),
            safe_int(row.get('BLK')), safe_int(row.get('TO')),
            safe_int(row.get('FG_MADE')), safe_int(row.get('FG_ATTEMPTED')),
            safe_int(row.get('THREE_MADE')), safe_int(row.get('THREE_ATTEMPTED')),
            safe_int(row.get('FT_MADE')), safe_int(row.get('FT_ATTEMPTED')),
            safe_int(row.get('FLS')), safe_int(row.get('PLUS_MINUS')),
            safe_int(row.get('PRF')), safe_int(row.get('DNK'))
        ))

    conn.commit()
    conn.close()
    print(f"Game logged successfully! {user_team} vs {opp_team} ({win_loss}) on {date}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python add_game.py <path_to_csv>")
    else:
        add_game(sys.argv[1])