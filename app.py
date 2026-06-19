from flask import Flask, render_template, request, redirect
import pandas as pd
from database import get_connection

app = Flask(__name__)

@app.route("/")
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

@app.route("/box_score")
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
        SELECT g.game_id, g.date, g.win_loss,
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

    if not stats.empty:
        stats['fg_pct'] = (stats['fg_made'] / stats['fg_attempted']).round(3)
        stats['three_pct'] = (stats['three_made'] / stats['three_attempted']).round(3)
        stats['ft_pct'] = (stats['ft_made'] / stats['ft_attempted']).round(3)

    your_stats = stats[stats['is_your_team'] == 1].to_dict('records') if not stats.empty else []
    opp_stats = stats[stats['is_your_team'] == 0].to_dict('records') if not stats.empty else []

    return render_template("box_score.html",
        games=games.to_dict('records'),
        game_info=game_info.iloc[0].to_dict() if not game_info.empty else None,
        your_stats=your_stats,
        opp_stats=opp_stats,
        selected_game_id=game_id
    )

@app.route("/trends")
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

    game_totals = stats.groupby(['game_id', 'win_loss']).sum(numeric_only=True).reset_index()
    game_totals['fg_pct'] = (game_totals['fg_made'] / game_totals['fg_attempted']).round(3)
    game_totals['three_pct'] = (game_totals['three_made'] / game_totals['three_attempted']).round(3)
    game_totals['ft_pct'] = (game_totals['ft_made'] / game_totals['ft_attempted']).round(3)

    trends_data = game_totals.groupby('win_loss').mean(numeric_only=True).round(2).reset_index()

    return render_template("trends.html",
        trends=trends_data.to_dict('records')
    )

@app.route("/players")
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

    stats['fg_pct'] = (stats['fg_made'] / stats['fg_attempted']).round(3)
    stats['three_pct'] = (stats['three_made'] / stats['three_attempted']).round(3)
    stats['ft_pct'] = (stats['ft_made'] / stats['ft_attempted']).round(3)

    averages = stats.groupby(['team_name', 'player_name']).mean(numeric_only=True).round(2).reset_index()
    averages = averages.sort_values('points', ascending=False)

    conn.close()

    return render_template("players.html",
        players=averages.to_dict('records'),
        teams=teams,
        selected_team=selected_team
    )

@app.route("/search")
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

        game_totals['three_pct'] = (game_totals['total_3pm'] / game_totals['total_3pa']).round(3)
        game_totals['fg_pct'] = (game_totals['total_fgm'] / game_totals['total_fga']).round(3)
        game_totals['ft_pct'] = (game_totals['total_ftm'] / game_totals['total_fta']).round(3)

        df = game_totals.copy()

        if team != 'all':
            df = df[df['your_team'] == team]
        if result != 'all':
            df = df[df['win_loss'] == result]
        if date_from:
            df = df[df['date'] >= date_from]
        if date_to:
            df = df[df['date'] <= date_to]
        if min_pts:
            df = df[df['total_pts'] >= float(min_pts)]
        if max_pts:
            df = df[df['total_pts'] <= float(max_pts)]
        if min_3pp:
            df = df[df['three_pct'] >= float(min_3pp)]
        if max_3pp:
            df = df[df['three_pct'] <= float(max_3pp)]
        if min_fgp:
            df = df[df['fg_pct'] >= float(min_fgp)]
        if max_fgp:
            df = df[df['fg_pct'] <= float(max_fgp)]
        if min_ftp:
            df = df[df['ft_pct'] >= float(min_ftp)]
        if max_ftp:
            df = df[df['ft_pct'] <= float(max_ftp)]
        if min_ast:
            df = df[df['total_ast'] >= float(min_ast)]
        if max_ast:
            df = df[df['total_ast'] <= float(max_ast)]
        if min_reb:
            df = df[df['total_reb'] >= float(min_reb)]
        if max_reb:
            df = df[df['total_reb'] <= float(max_reb)]
        if min_stl:
            df = df[df['total_stl'] >= float(min_stl)]
        if max_stl:
            df = df[df['total_stl'] <= float(max_stl)]
        if min_blk:
            df = df[df['total_blk'] >= float(min_blk)]
        if max_blk:
            df = df[df['total_blk'] <= float(max_blk)]
        if min_to:
            df = df[df['total_to'] >= float(min_to)]
        if max_to:
            df = df[df['total_to'] <= float(max_to)]

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

        player_stats['fg_pct'] = (player_stats['fg_made'] / player_stats['fg_attempted']).round(3)
        player_stats['three_pct'] = (player_stats['three_made'] / player_stats['three_attempted']).round(3)

        dp = player_stats.copy()

        if player_name:
            dp = dp[dp['player_name'].str.lower() == player_name.lower()]
        if p_min_pts:
            dp = dp[dp['points'] >= float(p_min_pts)]
        if p_max_pts:
            dp = dp[dp['points'] <= float(p_max_pts)]
        if p_min_ast:
            dp = dp[dp['assists'] >= float(p_min_ast)]
        if p_max_ast:
            dp = dp[dp['assists'] <= float(p_max_ast)]
        if p_min_reb:
            dp = dp[dp['rebounds'] >= float(p_min_reb)]
        if p_max_reb:
            dp = dp[dp['rebounds'] <= float(p_max_reb)]
        if p_min_fgp:
            dp = dp[dp['fg_pct'] >= float(p_min_fgp)]
        if p_max_fgp:
            dp = dp[dp['fg_pct'] <= float(p_max_fgp)]
        if p_min_3pp:
            dp = dp[dp['three_pct'] >= float(p_min_3pp)]
        if p_max_3pp:
            dp = dp[dp['three_pct'] <= float(p_max_3pp)]

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

@app.route("/test")
def test():
    return render_template("search.html",
        teams=[],
        results=[],
        searched=False,
        total=0,
        team='all',
        result='all',
        date_from='',
        date_to='',
        min_pts='',
        max_pts='',
        min_3pp='',
        max_3pp='',
        min_ast='',
        max_ast='',
        min_to='',
        max_to=''
    )

# ─── MERGED ANALYSIS + MATCHUPS ──────────────────────

@app.route("/analysis")
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

@app.route("/matchups")
def matchups():
    return redirect('/analysis')

# ─── API: TEAM TREND CHART ───────────────────────────

@app.route("/api/chart_data")
def chart_data():
    conn = get_connection()

    chart_type = request.args.get('type', 'team')
    stat = request.args.get('stat', 'points')
    limit = request.args.get('limit', 'all')
    head_to_head = request.args.get('head_to_head', '0') == '1'
    selections = request.args.getlist('selections')
    print("Selections received:", selections)

    results = {}

    your_team_selections = []
    opp_team_selections = []

    if chart_type == 'team':
        for selection in selections:
            parts = selection.split('||')
            team_name = parts[0]
            side = parts[1] if len(parts) > 1 else 'yours'

            if side == 'yours':
                your_team_selections.append(team_name)
            else:
                opp_team_selections.append(team_name)

    for selection in selections:
        if chart_type == 'team':
            parts = selection.split('||')
            team_name = parts[0]
            side = parts[1] if len(parts) > 1 else 'yours'
            is_your_team = 1 if side == 'yours' else 0

            h2h_filter = ''
            h2h_params = []

            if head_to_head:
                opposite_teams = opp_team_selections if side == 'yours' else your_team_selections

                if opposite_teams:
                    placeholders = ','.join(['?'] * len(opposite_teams))
                    h2h_filter = f"AND t_other.team_name IN ({placeholders})"
                    h2h_params = opposite_teams
                else:
                    results[selection] = []
                    continue

            query = f"""
                SELECT g.game_id, g.date, g.win_loss, g.home_away,
                    t_other.team_name as opp_team,
                    SUM(ps.{stat}) as value
                FROM games g
                JOIN teams t ON g.game_id = t.game_id
                    AND t.is_your_team = ?
                    AND t.team_name = ?
                JOIN teams t_other ON g.game_id = t_other.game_id
                    AND t_other.is_your_team != t.is_your_team
                JOIN player_stats ps ON ps.team_id = t.team_id
                    AND ps.game_id = g.game_id
                WHERE 1 = 1
                {h2h_filter}
                GROUP BY g.game_id
                ORDER BY g.date ASC, g.game_id ASC
            """
            df = pd.read_sql_query(query, conn, params=[is_your_team, team_name] + h2h_params)
        else:
            parts = selection.split('||')
            player_name = parts[0]
            team_name = parts[1] if len(parts) > 1 else ''
            query = f"""
                SELECT g.date, g.win_loss, t2.team_name as opp_team,
                    ps.{stat} as value
                FROM player_stats ps
                JOIN teams t ON ps.team_id = t.team_id
                JOIN games g ON ps.game_id = g.game_id
                JOIN teams t2 ON g.game_id = t2.game_id AND t2.is_your_team = 0
                WHERE t.is_your_team = 1 AND ps.player_name = ? AND t.team_name = ?
                ORDER BY g.date ASC, g.game_id ASC
            """
            df = pd.read_sql_query(query, conn, params=(player_name, team_name))

        if limit != 'all':
            df = df.tail(int(limit))

        print(f"Processing selection: '{selection}', rows returned: {len(df)}")
        results[selection] = df.to_dict('records')

    conn.close()
    return results

# ─── API: PLAYER GRAPH (yours vs opp, home/away) ─────

@app.route("/api/player_graph_data")
def player_graph_data():
    conn = get_connection()

    selections = request.args.getlist('selections')
    stat = request.args.get('stat', 'points')
    limit = request.args.get('limit', 'all')

    results = {}

    for selection in selections:
        parts = selection.split('||')
        if len(parts) < 3:
            continue

        player_name = parts[0]
        team_name = parts[1]
        side = parts[2]           # 'yours' or 'opp'
        home_away = parts[3] if len(parts) > 3 else 'both'

        is_your_team = 1 if side == 'yours' else 0

        home_away_filter = ''
        if home_away == 'home':
            home_away_filter = "AND g.home_away = 'H'"
        elif home_away == 'away':
            home_away_filter = "AND g.home_away = 'A'"

        query = f"""
            SELECT g.game_id, g.date, g.win_loss, g.home_away,
                   t2.team_name as opp_team,
                   ps.{stat} as value
            FROM player_stats ps
            JOIN teams t ON ps.team_id = t.team_id
            JOIN games g ON ps.game_id = g.game_id
            JOIN teams t2 ON g.game_id = t2.game_id AND t2.is_your_team != t.is_your_team
            WHERE t.is_your_team = ?
            AND ps.player_name = ?
            AND t.team_name = ?
            {home_away_filter}
            ORDER BY g.date ASC, g.game_id ASC
        """

        df = pd.read_sql_query(query, conn, params=(is_your_team, player_name, team_name))

        if limit != 'all':
            df = df.tail(int(limit))

        results[selection] = df.to_dict('records')

    conn.close()
    return results

# ─── API: MATCHUP TABLES ─────────────────────────────

@app.route("/api/matchup_data")
def matchup_data():
    conn = get_connection()

    matchup_type = request.args.get('type', 'team')
    opp_team = request.args.get('opp_team', '')
    your_team = request.args.get('your_team', 'all')
    selections = request.args.getlist('selections')

    results = {}

    if matchup_type == 'team':
        overall = pd.read_sql_query("""
            SELECT SUM(ps.points) as pts, SUM(ps.assists) as ast,
                   SUM(ps.rebounds) as reb, SUM(ps.steals) as stl,
                   SUM(ps.blocks) as blk, SUM(ps.turnovers) as to_,
                   SUM(ps.fg_made) as fgm, SUM(ps.fg_attempted) as fga,
                   SUM(ps.three_made) as tpm, SUM(ps.three_attempted) as tpa,
                   SUM(ps.ft_made) as ftm, SUM(ps.ft_attempted) as fta,
                   g.game_id
            FROM player_stats ps
            JOIN teams t ON ps.team_id = t.team_id
            JOIN games g ON ps.game_id = g.game_id
            WHERE t.is_your_team = 1
            {team_filter}
            GROUP BY g.game_id
        """.format(team_filter=f"AND t.team_name = '{your_team}'" if your_team != 'all' else ''), conn)

        vs_opp = pd.read_sql_query("""
            SELECT SUM(ps.points) as pts, SUM(ps.assists) as ast,
                   SUM(ps.rebounds) as reb, SUM(ps.steals) as stl,
                   SUM(ps.blocks) as blk, SUM(ps.turnovers) as to_,
                   SUM(ps.fg_made) as fgm, SUM(ps.fg_attempted) as fga,
                   SUM(ps.three_made) as tpm, SUM(ps.three_attempted) as tpa,
                   SUM(ps.ft_made) as ftm, SUM(ps.ft_attempted) as fta,
                   g.game_id
            FROM player_stats ps
            JOIN teams t ON ps.team_id = t.team_id
            JOIN games g ON ps.game_id = g.game_id
            JOIN teams t2 ON g.game_id = t2.game_id AND t2.is_your_team = 0
            WHERE t.is_your_team = 1 AND t2.team_name = ?
            {team_filter}
            GROUP BY g.game_id
        """.format(team_filter=f"AND t.team_name = '{your_team}'" if your_team != 'all' else ''), conn, params=(opp_team,))

        def calc_avgs(df):
            if df.empty:
                return {}
            df['fg_pct'] = (df['fgm'] / df['fga']).round(3)
            df['three_pct'] = (df['tpm'] / df['tpa']).round(3)
            df['ft_pct'] = (df['ftm'] / df['fta']).round(3)
            return df.mean(numeric_only=True).round(2).to_dict()

        results = {
            'type': 'team',
            'overall': calc_avgs(overall),
            'vs_opp': calc_avgs(vs_opp),
            'games_vs': len(vs_opp),
            'total_games': len(overall)
        }

    else:
        for selection in selections:
            parts = selection.split('||')
            player_name = parts[0]
            team_name = parts[1] if len(parts) > 1 else ''

            overall = pd.read_sql_query("""
                SELECT ps.points as pts, ps.assists as ast,
                       ps.rebounds as reb, ps.steals as stl,
                       ps.blocks as blk, ps.turnovers as to_,
                       ps.fg_made as fgm, ps.fg_attempted as fga,
                       ps.three_made as tpm, ps.three_attempted as tpa,
                       ps.ft_made as ftm, ps.ft_attempted as fta
                FROM player_stats ps
                JOIN teams t ON ps.team_id = t.team_id
                WHERE t.is_your_team = 1 AND ps.player_name = ? AND t.team_name = ?
            """, conn, params=(player_name, team_name))

            vs_opp = pd.read_sql_query("""
                SELECT ps.points as pts, ps.assists as ast,
                       ps.rebounds as reb, ps.steals as stl,
                       ps.blocks as blk, ps.turnovers as to_,
                       ps.fg_made as fgm, ps.fg_attempted as fga,
                       ps.three_made as tpm, ps.three_attempted as tpa,
                       ps.ft_made as ftm, ps.ft_attempted as fta
                FROM player_stats ps
                JOIN teams t ON ps.team_id = t.team_id
                JOIN games g ON ps.game_id = g.game_id
                JOIN teams t2 ON g.game_id = t2.game_id AND t2.is_your_team = 0
                WHERE t.is_your_team = 1 AND ps.player_name = ?
                AND t.team_name = ? AND t2.team_name = ?
            """, conn, params=(player_name, team_name, opp_team))

            def calc_avgs(df):
                if df.empty:
                    return {}
                df['fg_pct'] = (df['fgm'] / df['fga']).round(3)
                df['three_pct'] = (df['tpm'] / df['tpa']).round(3)
                df['ft_pct'] = (df['ftm'] / df['fta']).round(3)
                return df.mean(numeric_only=True).round(2).to_dict()

            results[selection] = {
                'player_name': player_name,
                'team_name': team_name,
                'overall': calc_avgs(overall),
                'vs_opp': calc_avgs(vs_opp),
                'games_vs': len(vs_opp),
                'total_games': len(overall)
            }

    conn.close()
    return results

if __name__ == "__main__":
    app.run(debug=True)