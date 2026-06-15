import pandas as pd
from database import get_connection


def team_trends():
    conn = get_connection()

    stats = pd.read_sql_query("""
        SELECT g.game_id, g.win_loss,
               ps.points, ps.assists, ps.rebounds, ps.off_rebounds,
               ps.steals, ps.blocks, ps.turnovers,
               ps.fg_made, ps.fg_attempted,
               ps.three_made, ps.three_attempted,
               ps.ft_made, ps.ft_attempted,
               ps.fouls, ps.plus_minus, ps.points_responsible_for, ps.dunks
        FROM player_stats ps
        JOIN teams t ON ps.team_id = t.team_id
        JOIN games g ON ps.game_id = g.game_id
        WHERE t.is_your_team = 1
    """, conn)

    conn.close()

    if stats.empty:
        print("No data found.")
        return

    # Sum all players per game first to get team totals
    game_totals = stats.groupby(['game_id', 'win_loss']).sum(numeric_only=True).reset_index()

    # Calculate shooting percentages at game level
    game_totals['FG%'] = (game_totals['fg_made'] / game_totals['fg_attempted']).round(3)
    game_totals['3P%'] = (game_totals['three_made'] / game_totals['three_attempted']).round(3)
    game_totals['FT%'] = (game_totals['ft_made'] / game_totals['ft_attempted']).round(3)

    # Now average those game totals by win/loss
    trends = game_totals.groupby('win_loss').mean(numeric_only=True).round(2)

    trends = trends.rename(columns={
        'points': 'PTS', 'assists': 'AST', 'rebounds': 'REB',
        'off_rebounds': 'OREB', 'steals': 'STL', 'blocks': 'BLK',
        'turnovers': 'TO', 'fg_made': 'FGM', 'fg_attempted': 'FGA',
        'three_made': '3PM', 'three_attempted': '3PA',
        'ft_made': 'FTM', 'ft_attempted': 'FTA',
        'fouls': 'PF', 'plus_minus': '+/-',
        'points_responsible_for': 'PRF', 'dunks': 'DNK'
    })

    display_cols = ['PTS', 'AST', 'REB', 'OREB', 'STL', 'BLK', 'TO',
                    'FGM', 'FGA', 'FG%', '3PM', '3PA', '3P%',
                    'FTM', 'FTA', 'FT%', 'PF', 'PRF', 'DNK']

    print(f"\n{'='*60}")
    print("  YOUR TEAM TOTALS — WINS VS LOSSES")
    print(f"{'='*60}\n")
    print(trends[display_cols].to_string())


def player_averages():
    conn = get_connection()

    stats = pd.read_sql_query("""
        SELECT t.team_name, ps.player_name,
               ps.points, ps.assists, ps.rebounds, ps.off_rebounds,
               ps.steals, ps.blocks, ps.turnovers,
               ps.fg_made, ps.fg_attempted,
               ps.three_made, ps.three_attempted,
               ps.ft_made, ps.ft_attempted,
               ps.fouls, ps.plus_minus, ps.points_responsible_for, ps.dunks
        FROM player_stats ps
        JOIN teams t ON ps.team_id = t.team_id
        WHERE t.is_your_team = 1
    """, conn)

    conn.close()

    if stats.empty:
        print("No data found.")
        return

    stats['FG%'] = (stats['fg_made'] / stats['fg_attempted']).round(3)
    stats['3P%'] = (stats['three_made'] / stats['three_attempted']).round(3)
    stats['FT%'] = (stats['ft_made'] / stats['ft_attempted']).round(3)

    # Group by BOTH team and player name
    averages = stats.groupby(['team_name', 'player_name']).mean(numeric_only=True).round(2)
    averages = averages.sort_values('points', ascending=False)

    averages = averages.rename(columns={
        'points': 'PTS', 'assists': 'AST', 'rebounds': 'REB',
        'off_rebounds': 'OREB', 'steals': 'STL', 'blocks': 'BLK',
        'turnovers': 'TO', 'fg_made': 'FGM', 'fg_attempted': 'FGA',
        'three_made': '3PM', 'three_attempted': '3PA',
        'ft_made': 'FTM', 'ft_attempted': 'FTA',
        'fouls': 'PF', 'plus_minus': '+/-',
        'points_responsible_for': 'PRF', 'dunks': 'DNK'
    })

    display_cols = ['PTS', 'AST', 'REB', 'OREB', 'STL', 'BLK', 'TO',
                    'FGM', 'FGA', 'FG%', '3PM', '3PA', '3P%',
                    'FTM', 'FTA', 'FT%', 'PF', '+/-', 'PRF', 'DNK']

    print(f"\n{'='*60}")
    print("  YOUR TEAM — PLAYER AVERAGES BY TEAM")
    print(f"{'='*60}\n")
    print(averages[display_cols].to_string())


def player_win_loss_splits():
    conn = get_connection()

    stats = pd.read_sql_query("""
        SELECT t.team_name, ps.player_name, g.win_loss,
               ps.points, ps.assists, ps.rebounds, ps.off_rebounds,
               ps.steals, ps.blocks, ps.turnovers,
               ps.fg_made, ps.fg_attempted,
               ps.three_made, ps.three_attempted,
               ps.ft_made, ps.ft_attempted,
               ps.fouls, ps.plus_minus, ps.points_responsible_for, ps.dunks
        FROM player_stats ps
        JOIN teams t ON ps.team_id = t.team_id
        JOIN games g ON ps.game_id = g.game_id
        WHERE t.is_your_team = 1
    """, conn)

    conn.close()

    if stats.empty:
        print("No data found.")
        return

    stats['FG%'] = (stats['fg_made'] / stats['fg_attempted']).round(3)
    stats['3P%'] = (stats['three_made'] / stats['three_attempted']).round(3)
    stats['FT%'] = (stats['ft_made'] / stats['ft_attempted']).round(3)

    # Group by team, player, and win/loss
    splits = stats.groupby(['team_name', 'player_name', 'win_loss']).mean(numeric_only=True).round(2)

    splits = splits.rename(columns={
        'points': 'PTS', 'assists': 'AST', 'rebounds': 'REB',
        'off_rebounds': 'OREB', 'steals': 'STL', 'blocks': 'BLK',
        'turnovers': 'TO', 'fg_made': 'FGM', 'fg_attempted': 'FGA',
        'three_made': '3PM', 'three_attempted': '3PA',
        'ft_made': 'FTM', 'ft_attempted': 'FTA',
        'fouls': 'PF', 'plus_minus': '+/-',
        'points_responsible_for': 'PRF', 'dunks': 'DNK'
    })

    display_cols = ['PTS', 'AST', 'REB', 'OREB', 'STL', 'BLK', 'TO',
                    'FGM', 'FGA', 'FG%', '3PM', '3PA', '3P%',
                    'FTM', 'FTA', 'FT%', 'PF', '+/-', 'PRF', 'DNK']

    print(f"\n{'='*60}")
    print("  YOUR TEAM — PLAYER WIN/LOSS SPLITS BY TEAM")
    print(f"{'='*60}\n")
    print(splits[display_cols].to_string())


if __name__ == "__main__":
    import sys

    options = {
        'team': team_trends,
        'players': player_averages,
        'splits': player_win_loss_splits
    }

    if len(sys.argv) < 2 or sys.argv[1] not in options:
        print("Usage: python trends.py <team|players|splits>")
    else:
        options[sys.argv[1]]()