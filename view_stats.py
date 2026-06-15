import sqlite3
import pandas as pd
from database import get_connection

def view_box_score(game_id):
    conn = get_connection()

    # Get game info
    game = pd.read_sql_query("""
        SELECT g.game_id, g.date, g.home_away, g.win_loss,
               t1.team_name as your_team, t1.score as your_score,
               t2.team_name as opp_team, t2.score as opp_score
        FROM games g
        JOIN teams t1 ON g.game_id = t1.game_id AND t1.is_your_team = 1
        JOIN teams t2 ON g.game_id = t2.game_id AND t2.is_your_team = 0
        WHERE g.game_id = ?
    """, conn, params=(game_id,))

    if game.empty:
        print(f"No game found with id {game_id}")
        conn.close()
        return

    # Print game header
    row = game.iloc[0]
    print(f"\n{'='*60}")
    print(f"  {row['your_team']} vs {row['opp_team']}")
    print(f"  {row['date']} | {'Home' if row['home_away'] == 'H' else 'Away'} | {'Win' if row['win_loss'] == 'W' else 'Loss'}")
    print(f"  Final: {row['your_team']} {row['your_score']} - {row['opp_score']} {row['opp_team']}")
    print(f"{'='*60}")

    # Get player stats for both teams
    stats = pd.read_sql_query("""
        SELECT t.team_name, t.is_your_team, ps.player_name,
               ps.minutes, ps.points, ps.assists, ps.rebounds,
               ps.off_rebounds, ps.steals, ps.blocks, ps.turnovers,
               ps.fg_made, ps.fg_attempted, ps.three_made, ps.three_attempted,
               ps.ft_made, ps.ft_attempted, ps.fouls, ps.plus_minus,
               ps.points_responsible_for, ps.dunks
        FROM player_stats ps
        JOIN teams t ON ps.team_id = t.team_id
        WHERE ps.game_id = ?
        ORDER BY t.is_your_team DESC, ps.points DESC
    """, conn, params=(game_id,))

    conn.close()

    # Add percentage columns
    stats['FG%'] = (stats['fg_made'] / stats['fg_attempted']).round(3)
    stats['3P%'] = (stats['three_made'] / stats['three_attempted']).round(3)
    stats['FT%'] = (stats['ft_made'] / stats['ft_attempted']).round(3)

    # Rename columns for display
    stats = stats.rename(columns={
        'player_name': 'PLAYER',
        'minutes': 'MIN',
        'points': 'PTS',
        'assists': 'AST',
        'rebounds': 'REB',
        'off_rebounds': 'OREB',
        'steals': 'STL',
        'blocks': 'BLK',
        'turnovers': 'TO',
        'fg_made': 'FGM',
        'fg_attempted': 'FGA',
        'three_made': '3PM',
        'three_attempted': '3PA',
        'ft_made': 'FTM',
        'ft_attempted': 'FTA',
        'fouls': 'PF',
        'plus_minus': '+/-',
        'points_responsible_for': 'PRF',
        'dunks': 'DNK'
    })

    # Display columns
    display_cols = ['PLAYER', 'MIN', 'PTS', 'AST', 'REB', 'OREB',
                    'STL', 'BLK', 'TO', 'FGM', 'FGA', 'FG%',
                    '3PM', '3PA', '3P%', 'FTM', 'FTA', 'FT%',
                    'PF', '+/-', 'PRF', 'DNK']

    # Print your team
    your_team_name = game.iloc[0]['your_team']
    opp_team_name = game.iloc[0]['opp_team']

    print(f"\n  {your_team_name}")
    print("-"*60)
    your_stats = stats[stats['is_your_team'] == 1][display_cols]
    print(your_stats.to_string(index=False))

    print(f"\n  {opp_team_name}")
    print("-"*60)
    opp_stats = stats[stats['is_your_team'] == 0][display_cols]
    print(opp_stats.to_string(index=False))

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python view_stats.py <game_id>")
    else:
        view_box_score(int(sys.argv[1]))