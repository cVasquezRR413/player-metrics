from flask import Blueprint, render_template, request
import pandas as pd
from database import get_connection

pages = Blueprint("pages", __name__)

# Temporary helper copy while page routes are being split out.
# We can centralize helpers after the route split is stable.
def safe_pct(numerator, denominator, decimals=3):
    result = numerator / denominator
    result = result.where(denominator != 0)
    return result.round(decimals)

def add_shooting_pcts(df):
    df['fg_pct'] = safe_pct(df['fg_made'], df['fg_attempted'])
    df['three_pct'] = safe_pct(df['three_made'], df['three_attempted'])
    df['ft_pct'] = safe_pct(df['ft_made'], df['ft_attempted'])

    return df

@pages.route("/")
def home():
    conn = get_connection()
    
    # Total games
    games = pd.read_sql_query("SELECT * FROM games", conn)
    total_games = len(games)
    wins = len(games[games['win_loss'] == 'W'])
    losses = len(games[games['win_loss'] == 'L'])
    win_pct = round((wins / total_games * 100), 1) if total_games > 0 else 0

    # Recent games
    recent = pd.read_sql_query("""
        SELECT g.game_id, g.date, g.win_loss,
               t1.team_name as your_team, t1.score as your_score,
               t2.team_name as opp_team, t2.score as opp_score
        FROM games g
        JOIN teams t1 ON g.game_id = t1.game_id AND t1.is_your_team = 1
        JOIN teams t2 ON g.game_id = t2.game_id AND t2.is_your_team = 0
        ORDER BY g.game_id DESC
        LIMIT 10
    """, conn)
    
    conn.close()

    return render_template("home.html",
        total_games=total_games,
        wins=wins,
        losses=losses,
        win_pct=win_pct,
        recent_games=recent.to_dict('records')
    )

@pages.route("/box_score")
def box_score():
    conn = get_connection()
    
    game_id = request.args.get('game_id', 1, type=int)

    games = pd.read_sql_query("""
        SELECT g.game_id, g.date, g.win_loss,
               t1.team_name as your_team, t1.score as your_score,
               t2.team_name as opp_team, t2.score as opp_score
        FROM games g
        JOIN teams t1 ON g.game_id = t1.game_id AND t1.is_your_team = 1
        JOIN teams t2 ON g.game_id = t2.game_id AND t2.is_your_team = 0
        ORDER BY g.game_id DESC
    """, conn)

    game_info = pd.read_sql_query("""
        SELECT g.game_id, g.date, g.win_loss, g.home_away,
            t1.team_name as your_team, t1.score as your_score,
            t2.team_name as opp_team, t2.score as opp_score
        FROM games g
        JOIN teams t1 ON g.game_id = t1.game_id AND t1.is_your_team = 1
        JOIN teams t2 ON g.game_id = t2.game_id AND t2.is_your_team = 0
        WHERE g.game_id = ?
    """, conn, params=(game_id,))

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

    # Add shooting percentages for box score display.
    if not stats.empty:
        stats = add_shooting_pcts(stats)

    your_stats = stats[stats['is_your_team'] == 1].to_dict('records') if not stats.empty else []
    opp_stats = stats[stats['is_your_team'] == 0].to_dict('records') if not stats.empty else []

    return render_template("box_score.html",
        games=games.to_dict('records'),
        game_info=game_info.iloc[0].to_dict() if not game_info.empty else None,
        your_stats=your_stats,
        opp_stats=opp_stats,
        selected_game_id=game_id
    )