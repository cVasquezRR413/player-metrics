from flask import Blueprint, render_template, request, redirect
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

# Convert pandas NaN values to None so templates receive clean records.
def clean_records(df):
    return df.astype(object).where(pd.notnull(df), None).to_dict('records')

# Add shooting percentages to team search totals.
def add_team_search_pcts(df):
    df['three_pct'] = safe_pct(df['total_3pm'], df['total_3pa'])
    df['fg_pct'] = safe_pct(df['total_fgm'], df['total_fga'])
    df['ft_pct'] = safe_pct(df['total_ftm'], df['total_fta'])

    return df

# Apply optional minimum and maximum filters to a numeric dataframe column.
def apply_numeric_filter(df, column, min_value='', max_value=''):
    if min_value:
        df = df[df[column] >= float(min_value)]

    if max_value:
        df = df[df[column] <= float(max_value)]

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

@pages.route("/trends")
def trends():
    conn = get_connection()

    stats = pd.read_sql_query("""
        SELECT g.game_id, g.win_loss,
               ps.points, ps.assists, ps.rebounds, ps.off_rebounds,
               ps.steals, ps.blocks, ps.turnovers,
               ps.fg_made, ps.fg_attempted,
               ps.three_made, ps.three_attempted,
               ps.ft_made, ps.ft_attempted,
               ps.fouls, ps.points_responsible_for, ps.dunks
        FROM player_stats ps
        JOIN teams t ON ps.team_id = t.team_id
        JOIN games g ON ps.game_id = g.game_id
        WHERE t.is_your_team = 1
    """, conn)

    conn.close()

    # Collapse player rows into one team total per game.
    game_totals = stats.groupby(['game_id', 'win_loss']).sum(numeric_only=True).reset_index()
    game_totals = add_shooting_pcts(game_totals)

    trends_data = game_totals.groupby('win_loss').mean(numeric_only=True).round(2).reset_index()

    return render_template("trends.html",
        trends=trends_data.to_dict('records')
    )

@pages.route("/players")
def players():
    conn = get_connection()

    selected_team = request.args.get('team', 'all')

    query = """
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
    """

    stats = pd.read_sql_query(query, conn)

    teams = stats['team_name'].unique().tolist()

    if selected_team != 'all':
        stats = stats[stats['team_name'] == selected_team]

    # Average each player's stats within each team roster.
    averages = stats.groupby(['team_name', 'player_name']).mean(numeric_only=True).reset_index()

    averages = add_shooting_pcts(averages)
    
    # Calculate efficiency metrics from the averaged shooting data.
    averages['efg_pct'] = safe_pct(
        averages['fg_made'] + (0.5 * averages['three_made']),
        averages['fg_attempted']
    )
    averages['ts_pct'] = safe_pct(
        averages['points'],
        2 * (averages['fg_attempted'] + (0.44 * averages['ft_attempted']))
    )

    averages = averages.round(2)
    averages[['fg_pct', 'three_pct', 'ft_pct', 'efg_pct', 'ts_pct']] = averages[
        ['fg_pct', 'three_pct', 'ft_pct', 'efg_pct', 'ts_pct']
    ].round(3)

    averages = averages.sort_values('points', ascending=False)

    conn.close()

    return render_template("players.html",
        players=clean_records(averages),
        teams=teams,
        selected_team=selected_team
    )

@pages.route("/efficiency")
def efficiency():
    conn = get_connection()

    selected_team = request.args.get('team', 'all')

    query = """
        SELECT t.team_name, ps.player_name,
               ps.points, ps.fg_made, ps.fg_attempted,
               ps.three_made, ps.ft_attempted
        FROM player_stats ps
        JOIN teams t ON ps.team_id = t.team_id
        WHERE t.is_your_team = 1
    """

    stats = pd.read_sql_query(query, conn)
    conn.close()

    if stats.empty:
        return render_template("efficiency.html",
            players=[],
            teams=[],
            selected_team=selected_team
        )

    teams = stats['team_name'].unique().tolist()

    if selected_team != 'all':
        stats = stats[stats['team_name'] == selected_team]

    averages = stats.groupby(['team_name', 'player_name']).mean(numeric_only=True).reset_index()

    averages['efg_pct'] = safe_pct(
        averages['fg_made'] + (0.5 * averages['three_made']),
        averages['fg_attempted']
    )
    averages['ts_pct'] = safe_pct(
        averages['points'],
        2 * (averages['fg_attempted'] + (0.44 * averages['ft_attempted']))
    )

    averages = averages.round(2)
    averages[['efg_pct', 'ts_pct']] = averages[['efg_pct', 'ts_pct']].round(3)

    averages = averages.sort_values('points', ascending=False)

    return render_template("efficiency.html",
        players=clean_records(averages),
        teams=teams,
        selected_team=selected_team
    )

@pages.route("/search")
def search():
    conn = get_connection()

    teams_df = pd.read_sql_query("""
        SELECT DISTINCT team_name FROM teams WHERE is_your_team = 1 ORDER BY team_name
    """, conn)
    teams = teams_df['team_name'].tolist()

    players_df = pd.read_sql_query("""
        SELECT DISTINCT ps.player_name FROM player_stats ps
        JOIN teams t ON ps.team_id = t.team_id
        WHERE t.is_your_team = 1
        ORDER BY ps.player_name
    """, conn)
    player_names = players_df['player_name'].tolist()

    # Team filter params
    team = request.args.get('team', 'all')
    result = request.args.get('result', 'all')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    min_pts = request.args.get('min_pts', '')
    max_pts = request.args.get('max_pts', '')
    min_3pp = request.args.get('min_3pp', '')
    max_3pp = request.args.get('max_3pp', '')
    min_fgp = request.args.get('min_fgp', '')
    max_fgp = request.args.get('max_fgp', '')
    min_ftp = request.args.get('min_ftp', '')
    max_ftp = request.args.get('max_ftp', '')
    min_ast = request.args.get('min_ast', '')
    max_ast = request.args.get('max_ast', '')
    min_reb = request.args.get('min_reb', '')
    max_reb = request.args.get('max_reb', '')
    min_stl = request.args.get('min_stl', '')
    max_stl = request.args.get('max_stl', '')
    min_blk = request.args.get('min_blk', '')
    max_blk = request.args.get('max_blk', '')
    min_to = request.args.get('min_to', '')
    max_to = request.args.get('max_to', '')

    # Player filter params
    player_name = request.args.get('player_name', '')
    p_min_pts = request.args.get('p_min_pts', '')
    p_max_pts = request.args.get('p_max_pts', '')
    p_min_ast = request.args.get('p_min_ast', '')
    p_max_ast = request.args.get('p_max_ast', '')
    p_min_reb = request.args.get('p_min_reb', '')
    p_max_reb = request.args.get('p_max_reb', '')
    p_min_fgp = request.args.get('p_min_fgp', '')
    p_max_fgp = request.args.get('p_max_fgp', '')
    p_min_3pp = request.args.get('p_min_3pp', '')
    p_max_3pp = request.args.get('p_max_3pp', '')

    # Only run each search section when the user has entered at least one filter.
    team_searched = any([team != 'all', result != 'all', date_from, date_to,
                    min_pts, max_pts, min_3pp, max_3pp, min_fgp, max_fgp,
                    min_ftp, max_ftp, min_ast, max_ast, min_reb, max_reb,
                    min_stl, max_stl, min_blk, max_blk, min_to, max_to])

    player_searched = any([player_name, p_min_pts, p_max_pts, p_min_ast, p_max_ast,
                           p_min_reb, p_max_reb, p_min_fgp, p_max_fgp, p_min_3pp, p_max_3pp])

    team_results = []
    player_results = []

    if team_searched:
        game_totals = pd.read_sql_query("""
            SELECT g.game_id, g.date, g.win_loss,
                   t1.team_name as your_team, t1.score as your_score,
                   t2.team_name as opp_team, t2.score as opp_score,
                   SUM(ps.points) as total_pts,
                   SUM(ps.assists) as total_ast,
                   SUM(ps.turnovers) as total_to,
                   SUM(ps.rebounds) as total_reb,
                   SUM(ps.steals) as total_stl,
                   SUM(ps.blocks) as total_blk,
                   SUM(ps.three_made) as total_3pm,
                   SUM(ps.three_attempted) as total_3pa,
                   SUM(ps.fg_made) as total_fgm,
                   SUM(ps.fg_attempted) as total_fga,
                   SUM(ps.ft_made) as total_ftm,
                   SUM(ps.ft_attempted) as total_fta
            FROM games g
            JOIN teams t1 ON g.game_id = t1.game_id AND t1.is_your_team = 1
            JOIN teams t2 ON g.game_id = t2.game_id AND t2.is_your_team = 0
            JOIN player_stats ps ON ps.game_id = g.game_id
            JOIN teams pt ON ps.team_id = pt.team_id AND pt.is_your_team = 1
            GROUP BY g.game_id
        """, conn)

        game_totals = add_team_search_pcts(game_totals)

        df = game_totals.copy()

        if team != 'all':
            df = df[df['your_team'] == team]
        if result != 'all':
            df = df[df['win_loss'] == result]
        if date_from:
            df = df[df['date'] >= date_from]
        if date_to:
            df = df[df['date'] <= date_to]
        
        df = apply_numeric_filter(df, 'total_pts', min_pts, max_pts)
        
        df = apply_numeric_filter(df, 'three_pct', min_3pp, max_3pp)
        df = apply_numeric_filter(df, 'fg_pct', min_fgp, max_fgp)
        df = apply_numeric_filter(df, 'ft_pct', min_ftp, max_ftp)

        df = apply_numeric_filter(df, 'total_ast', min_ast, max_ast)
        df = apply_numeric_filter(df, 'total_reb', min_reb, max_reb)
        df = apply_numeric_filter(df, 'total_stl', min_stl, max_stl)
        df = apply_numeric_filter(df, 'total_blk', min_blk, max_blk)
        df = apply_numeric_filter(df, 'total_to', min_to, max_to)

        df = df.sort_values('date', ascending=False)
        team_results = df.to_dict('records')

    if player_searched:
        player_stats = pd.read_sql_query("""
            SELECT g.game_id, g.date, g.win_loss,
                   t1.team_name as your_team, t2.team_name as opp_team,
                   t.team_name as player_team,
                   ps.player_name, ps.minutes, ps.points, ps.assists,
                   ps.rebounds, ps.steals, ps.blocks, ps.turnovers,
                   ps.fg_made, ps.fg_attempted,
                   ps.three_made, ps.three_attempted,
                   ps.ft_made, ps.ft_attempted,
                   ps.plus_minus, ps.points_responsible_for
            FROM player_stats ps
            JOIN teams t ON ps.team_id = t.team_id
            JOIN games g ON ps.game_id = g.game_id
            JOIN teams t1 ON g.game_id = t1.game_id AND t1.is_your_team = 1
            JOIN teams t2 ON g.game_id = t2.game_id AND t2.is_your_team = 0
            WHERE t.is_your_team = 1
        """, conn)

        player_stats['fg_pct'] = safe_pct(player_stats['fg_made'], player_stats['fg_attempted'])
        player_stats['three_pct'] = safe_pct(player_stats['three_made'], player_stats['three_attempted'])

        dp = player_stats.copy()

        if player_name:
            dp = dp[dp['player_name'].str.lower() == player_name.lower()]
        dp = apply_numeric_filter(dp, 'points', p_min_pts, p_max_pts)
        dp = apply_numeric_filter(dp, 'assists', p_min_ast, p_max_ast)
        dp = apply_numeric_filter(dp, 'rebounds', p_min_reb, p_max_reb)
        dp = apply_numeric_filter(dp, 'fg_pct', p_min_fgp, p_max_fgp)
        dp = apply_numeric_filter(dp, 'three_pct', p_min_3pp, p_max_3pp)

        dp = dp.sort_values('date', ascending=False)
        player_results = dp.to_dict('records')

    conn.close()

    return render_template("search.html",
        teams=teams,
        player_names=player_names,
        team_results=team_results,
        player_results=player_results,
        team_searched=team_searched,
        player_searched=player_searched,
        total_team=len(team_results),
        total_player=len(player_results),
        team=team, result=result,
        date_from=date_from, date_to=date_to,
        min_pts=min_pts, max_pts=max_pts,
        min_3pp=min_3pp, max_3pp=max_3pp,
        min_fgp=min_fgp, max_fgp=max_fgp,
        min_ftp=min_ftp, max_ftp=max_ftp,
        min_ast=min_ast, max_ast=max_ast,
        min_reb=min_reb, max_reb=max_reb,
        min_stl=min_stl, max_stl=max_stl,
        min_blk=min_blk, max_blk=max_blk,
        min_to=min_to, max_to=max_to,
        player_name=player_name,
        p_min_pts=p_min_pts, p_max_pts=p_max_pts,
        p_min_ast=p_min_ast, p_max_ast=p_max_ast,
        p_min_reb=p_min_reb, p_max_reb=p_max_reb,
        p_min_fgp=p_min_fgp, p_max_fgp=p_max_fgp,
        p_min_3pp=p_min_3pp, p_max_3pp=p_max_3pp
    )

@pages.route("/analysis")
def analysis():
    conn = get_connection()

    teams_df = pd.read_sql_query("""
        SELECT DISTINCT team_name FROM teams 
        WHERE is_your_team = 1 ORDER BY team_name
    """, conn)

    opp_teams_df = pd.read_sql_query("""
        SELECT DISTINCT team_name FROM teams 
        WHERE is_your_team = 0 ORDER BY team_name
    """, conn)

    your_players_df = pd.read_sql_query("""
        SELECT DISTINCT ps.player_name, t.team_name
        FROM player_stats ps
        JOIN teams t ON ps.team_id = t.team_id
        WHERE t.is_your_team = 1
        ORDER BY ps.player_name
    """, conn)

    opp_players_df = pd.read_sql_query("""
        SELECT DISTINCT ps.player_name, t.team_name
        FROM player_stats ps
        JOIN teams t ON ps.team_id = t.team_id
        WHERE t.is_your_team = 0
        ORDER BY ps.player_name
    """, conn)

    conn.close()

    return render_template("analysis.html",
        teams=teams_df['team_name'].tolist(),
        opp_teams=opp_teams_df['team_name'].tolist(),
        your_players=your_players_df.to_dict('records'),
        opp_players=opp_players_df.to_dict('records')
    )

@pages.route("/matchups")
def matchups():
    return redirect('/analysis')