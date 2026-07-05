from flask import Flask, request
import pandas as pd
from database import get_connection
from routes.pages import pages

app = Flask(__name__)
app.register_blueprint(pages)

ALLOWED_STATS = {
    'points', 'assists', 'rebounds', 'steals', 'blocks',
    'turnovers', 'fg_made', 'three_made', 'plus_minus', 'dunks'
}

# Calculate percentages while avoiding divide-by-zero values.
def safe_pct(numerator, denominator, decimals=3):
    result = numerator / denominator
    result = result.where(denominator != 0)
    return result.round(decimals)

# Add standard shooting percentages to a dataframe.
def add_shooting_pcts(df):
    df['fg_pct'] = safe_pct(df['fg_made'], df['fg_attempted'])
    df['three_pct'] = safe_pct(df['three_made'], df['three_attempted'])
    df['ft_pct'] = safe_pct(df['ft_made'], df['ft_attempted'])

    return df

# Add shooting percentages to team search totals.
def add_team_search_pcts(df):
    df['three_pct'] = safe_pct(df['total_3pm'], df['total_3pa'])
    df['fg_pct'] = safe_pct(df['total_fgm'], df['total_fga'])
    df['ft_pct'] = safe_pct(df['total_ftm'], df['total_fta'])

    return df

# Convert pandas NaN values to None so templates receive clean records.
def clean_records(df):
    return df.astype(object).where(pd.notnull(df), None).to_dict('records')

# Limit a dataframe to the most recent rows when a numeric limit is selected.
def apply_limit(df, limit, sort_columns=None):
    if limit == 'all':
        return df

    if sort_columns:
        df = df.sort_values(sort_columns)

    return df.tail(int(limit))

# Apply optional minimum and maximum filters to a numeric dataframe column.
def apply_numeric_filter(df, column, min_value='', max_value=''):
    if min_value:
        df = df[df[column] >= float(min_value)]

    if max_value:
        df = df[df[column] <= float(max_value)]

    return df

# Split a selection string into the expected number of parts with safe fallback values.
def parse_selection(selection, defaults=None):
    parts = selection.split('||')
    defaults = defaults or []
    expected_length = len(defaults)

    return [
        parts[index] if index < len(parts) else defaults[index]
        for index in range(expected_length)
    ]

# Calculate average stat records for matchup tables.
def calc_stat_avgs(df):
    if df.empty:
        return {}

    df = df.copy()
    df['fg_pct'] = safe_pct(df['fgm'], df['fga'])
    df['three_pct'] = safe_pct(df['tpm'], df['tpa'])
    df['ft_pct'] = safe_pct(df['ftm'], df['fta'])

    avgs = df.mean(numeric_only=True).round(2)

    return avgs.astype(object).where(pd.notnull(avgs), None).to_dict()

# ─── API: TEAM TREND CHART ───────────────────────────

@app.route("/api/chart_data")
def chart_data():
    conn = get_connection()

    chart_type = request.args.get('type', 'team')
    stat = request.args.get('stat', 'points')
    limit = request.args.get('limit', 'all')
    head_to_head = request.args.get('head_to_head', '0') == '1'
    selections = request.args.getlist('selections')

    if stat not in ALLOWED_STATS:
        conn.close()
        return {'error': 'Invalid stat selected.'}, 400

    results = {}

    your_team_selections = []
    opp_team_selections = []

    if chart_type == 'team':
        for selection in selections:
            team_name, side = parse_selection(selection, defaults=['', 'yours'])

            if side == 'yours':
                your_team_selections.append(team_name)
            else:
                opp_team_selections.append(team_name)

    for selection in selections:
        if chart_type == 'team':
            team_name, side = parse_selection(selection, defaults=['', 'yours'])
            is_your_team = 1 if side == 'yours' else 0

            h2h_filter = ''
            h2h_params = []

            # In head-to-head mode, only keep games where the selected team faced the opposite-side selections.
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
            player_name, team_name = parse_selection(selection, defaults=['', ''])
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

        df = apply_limit(df, limit)

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
    head_to_head = request.args.get('head_to_head', '0') == '1'

    if stat not in ALLOWED_STATS:
        conn.close()
        return {'error': 'Invalid stat selected.'}, 400

    results = {}

    your_player_selections = []
    opp_player_selections = []

    for selection in selections:
        player_name, team_name, side = parse_selection(selection, defaults=['', '', ''])

        if not player_name or not team_name or not side:
            continue

        if side == 'yours':
            your_player_selections.append((player_name, team_name))
        else:
            opp_player_selections.append((player_name, team_name))

    for selection in selections:
        player_name, team_name, side, home_away = parse_selection(
            selection,
            defaults=['', '', '', 'both']
        )

        if not player_name or not team_name or not side:
            continue

        is_your_team = 1 if side == 'yours' else 0

        home_away_filter = ''
        if home_away == 'home':
            home_away_filter = "AND g.home_away = 'H'"
        elif home_away == 'away':
            home_away_filter = "AND g.home_away = 'A'"

        h2h_filter = ''
        h2h_params = []

        # Player head-to-head means the selected player appeared in games against the opposite-side player selections.
        if head_to_head:
            opposite_players = opp_player_selections if side == 'yours' else your_player_selections

            if opposite_players:
                player_conditions = []

                for opp_player_name, opp_team_name in opposite_players:
                    player_conditions.append("""
                        (ps_opp.player_name = ? AND t_opp.team_name = ?)
                    """)
                    h2h_params.extend([opp_player_name, opp_team_name])

                h2h_filter = f"""
                    AND EXISTS (
                        SELECT 1
                        FROM player_stats ps_opp
                        JOIN teams t_opp ON ps_opp.team_id = t_opp.team_id
                        WHERE ps_opp.game_id = g.game_id
                        AND t_opp.is_your_team != t.is_your_team
                        AND (
                            {' OR '.join(player_conditions)}
                        )
                    )
                """
            else:
                results[selection] = []
                continue

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
            {h2h_filter}
            ORDER BY g.date ASC, g.game_id ASC
        """

        df = pd.read_sql_query(
            query,
            conn,
            params=[is_your_team, player_name, team_name] + h2h_params
        )

        df = apply_limit(df, limit)

        results[selection] = df.to_dict('records')

    conn.close()
    return results

# ─── API: HEAD-TO-HEAD GRAPH DATA ────────────────────

@app.route("/api/h2h_graph_data")
def h2h_graph_data():
    conn = get_connection()

    chart_type = request.args.get('type', 'team')
    stat = request.args.get('stat', 'points')
    limit = request.args.get('limit', 'all')
    selections = request.args.getlist('selections')

    if stat not in ALLOWED_STATS:
        conn.close()
        return {'error': 'Invalid stat selected.'}, 400

    results = {}

    if chart_type == 'team':
        your_team_selections = []
        opp_team_selections = []

        for selection in selections:
            team_name, side = parse_selection(selection, defaults=['', ''])

            if not team_name or not side:
                continue

            if side == 'yours':
                your_team_selections.append(team_name)
            elif side == 'opp':
                opp_team_selections.append(team_name)

        for selection in selections:
            team_name, side = parse_selection(selection, defaults=['', ''])

            if not team_name or not side:
                results[selection] = []
                continue

            is_your_team = 1 if side == 'yours' else 0

            opposite_teams = opp_team_selections if side == 'yours' else your_team_selections

            if not opposite_teams:
                results[selection] = []
                continue

            placeholders = ','.join(['?'] * len(opposite_teams))

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
                    AND t_other.team_name IN ({placeholders})
                JOIN player_stats ps ON ps.team_id = t.team_id
                    AND ps.game_id = g.game_id
                GROUP BY g.game_id
                ORDER BY g.date ASC, g.game_id ASC
            """

            df = pd.read_sql_query(
                query,
                conn,
                params=[is_your_team, team_name] + opposite_teams
            )

            df = apply_limit(df, limit)

            results[selection] = df.to_dict('records')

    else:
        your_player_selections = []
        opp_player_selections = []

        for selection in selections:
            player_name, team_name, side = parse_selection(selection, defaults=['', '', ''])

            if not player_name or not team_name or not side:
                continue

            if side == 'yours':
                your_player_selections.append((player_name, team_name))
            elif side == 'opp':
                opp_player_selections.append((player_name, team_name))

        for selection in selections:
            player_name, team_name, side = parse_selection(selection, defaults=['', '', ''])

            if not player_name or not team_name or not side:
                results[selection] = []
                continue

            is_your_team = 1 if side == 'yours' else 0

            opposite_players = opp_player_selections if side == 'yours' else your_player_selections

            if not opposite_players:
                results[selection] = []
                continue

            player_conditions = []
            h2h_params = []

            for opp_player_name, opp_team_name in opposite_players:
                player_conditions.append("""
                    (ps_opp.player_name = ? AND t_opp.team_name = ?)
                """)
                h2h_params.extend([opp_player_name, opp_team_name])

            h2h_filter = f"""
                AND EXISTS (
                    SELECT 1
                    FROM player_stats ps_opp
                    JOIN teams t_opp ON ps_opp.team_id = t_opp.team_id
                    WHERE ps_opp.game_id = g.game_id
                    AND t_opp.is_your_team != t.is_your_team
                    AND (
                        {' OR '.join(player_conditions)}
                    )
                )
            """

            query = f"""
                SELECT g.game_id, g.date, g.win_loss, g.home_away,
                       t_other.team_name as opp_team,
                       ps.{stat} as value
                FROM player_stats ps
                JOIN teams t ON ps.team_id = t.team_id
                JOIN games g ON ps.game_id = g.game_id
                JOIN teams t_other ON g.game_id = t_other.game_id
                    AND t_other.is_your_team != t.is_your_team
                WHERE t.is_your_team = ?
                AND ps.player_name = ?
                AND t.team_name = ?
                {h2h_filter}
                ORDER BY g.date ASC, g.game_id ASC
            """

            df = pd.read_sql_query(
                query,
                conn,
                params=[is_your_team, player_name, team_name] + h2h_params
            )

            df = apply_limit(df, limit)

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
    limit = request.args.get('limit', 'all')
    selections = request.args.getlist('selections')

    results = {}

    if matchup_type == 'team':
        team_filter = ""
        overall_params = []

        if your_team != 'all':
            team_filter = "AND t.team_name = ?"
            overall_params.append(your_team)

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
            """.format(team_filter=team_filter), conn, params=overall_params)
        
        vs_opp_params = [opp_team]

        if your_team != 'all':
            vs_opp_params.append(your_team)

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
        """.format(team_filter=team_filter), conn, params=vs_opp_params)

        vs_opp = apply_limit(vs_opp, limit, sort_columns=['game_id'])

        results = {
            'type': 'team',
            'overall': calc_stat_avgs(overall),
            'vs_opp': calc_stat_avgs(vs_opp),
            'games_vs': len(vs_opp),
            'total_games': len(overall)
        }

    else:
        for selection in selections:
            player_name, team_name = parse_selection(selection, defaults=['', ''])

            if not player_name or not team_name:
                results[selection] = {}
                continue

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
                    ps.ft_made as ftm, ps.ft_attempted as fta,
                    g.game_id
                FROM player_stats ps
                JOIN teams t ON ps.team_id = t.team_id
                JOIN games g ON ps.game_id = g.game_id
                JOIN teams t2 ON g.game_id = t2.game_id AND t2.is_your_team = 0
                WHERE t.is_your_team = 1 AND ps.player_name = ?
                AND t.team_name = ? AND t2.team_name = ?
            """, conn, params=(player_name, team_name, opp_team))

            vs_opp = apply_limit(vs_opp, limit, sort_columns=['game_id'])

            results[selection] = {
                'player_name': player_name,
                'team_name': team_name,
                'overall': calc_stat_avgs(overall),
                'vs_opp': calc_stat_avgs(vs_opp),
                'games_vs': len(vs_opp),
                'total_games': len(overall)
            }

    conn.close()
    return results

if __name__ == "__main__":
    app.run(debug=True)