from flask import Blueprint, render_template
import pandas as pd
from database import get_connection

pages = Blueprint("pages", __name__)

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