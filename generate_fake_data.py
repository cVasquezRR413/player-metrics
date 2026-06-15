import csv
import os
import random
import subprocess
from datetime import datetime, timedelta

# Your teams
YOUR_TEAMS = [
    "2005-06 Miami Heat",
    "2012-13 Miami Heat"
]

# Opponent teams
OPP_TEAMS = [
    "2000-01 Los Angeles Lakers",
    "2000-01 Philadelphia 76ers",
    "2001-02 New Jersey Nets",
    "2001-02 Sacramento Kings",
    "2002-03 Dallas Mavericks",
    "2002-03 Phoenix Suns",
    "2003-04 Detroit Pistons",
    "2003-04 Los Angeles Lakers",
    "2003-04 Minnesota Timberwolves",
    "2004-05 Phoenix Suns",
    "2004-05 San Antonio Spurs",
    "2005-06 Memphis Grizzlies",
    "2006-07 Cleveland Cavaliers",
    "2006-07 Golden State Warriors",
    "2006-07 Washington Wizards",
    "2007-08 Boston Celtics",
    "2007-08 Denver Nuggets",
    "2007-08 Houston Rockets",
    "2009-10 Portland Trail Blazers",
    "2010-11 Chicago Bulls",
    "2010-11 Dallas Mavericks",
    "2011-12 New York Knicks",
    "2011-12 Oklahoma City Thunder",
    "2012-13 Memphis Grizzlies",
    "2013-14 Indiana Pacers",
    "2013-14 Los Angeles Clippers",
    "2013-14 San Antonio Spurs",
    "2015-16 Cleveland Cavaliers",
    "2015-16 Golden State Warriors"
]

# 05-06 Heat roster with realistic stat ranges
# Format: [min, pts, ast, reb, oreb, stl, blk, to, fg_made, fg_att, 3pm, 3pa, ftm, fta, fouls, prf_bonus, dunk_chance]
HEAT_0506 = {
    "Dwyane Wade":      [38, 27, 7, 5, 1, 2, 1, 3, 10, 22, 1, 3, 7, 10, 2, 35, 0.3],
    "Shaquille O'Neal": [32, 18, 2, 9, 3, 1, 2, 2, 7,  12, 0, 0, 5, 9,  3, 28, 0.4],
    "Antoine Walker":   [30, 12, 3, 5, 1, 1, 0, 2, 4,  12, 2, 6, 2, 3,  3, 16, 0.05],
    "Jason Williams":   [28, 8,  5, 3, 0, 1, 0, 2, 3,  8,  1, 4, 1, 2,  2, 12, 0.0],
    "Udonis Haslem":    [28, 8,  1, 7, 2, 1, 0, 1, 3,  6,  0, 0, 2, 3,  3, 10, 0.0],
    "Gary Payton":      [22, 7,  4, 2, 0, 1, 0, 2, 3,  7,  1, 2, 1, 2,  2, 10, 0.0],
    "James Posey":      [20, 5,  1, 3, 1, 1, 0, 1, 2,  5,  1, 3, 1, 2,  2, 7,  0.0],
    "Alonzo Mourning":  [18, 6,  1, 5, 2, 0, 2, 1, 2,  4,  0, 0, 2, 3,  3, 9,  0.1],
    "Derek Anderson":   [15, 5,  1, 2, 0, 1, 0, 1, 2,  5,  1, 2, 1, 1,  2, 6,  0.0],
    "Damon Jones":      [12, 4,  1, 1, 0, 0, 0, 1, 1,  4,  1, 3, 0, 0,  1, 5,  0.0],
}

# 12-13 Heat roster with realistic stat ranges
HEAT_1213 = {
    "LeBron James":     [38, 26, 7, 8, 1, 2, 1, 3, 10, 18, 1, 4, 5, 7,  2, 38, 0.2],
    "Dwyane Wade":      [34, 21, 5, 5, 1, 2, 1, 3, 8,  17, 0, 2, 5, 7,  3, 28, 0.2],
    "Chris Bosh":       [32, 18, 2, 7, 2, 1, 1, 2, 7,  14, 1, 2, 3, 4,  3, 24, 0.1],
    "Mario Chalmers":   [28, 8,  4, 3, 0, 2, 0, 2, 3,  8,  2, 5, 1, 2,  3, 11, 0.0],
    "Udonis Haslem":    [22, 6,  1, 6, 2, 1, 0, 1, 2,  5,  0, 0, 2, 3,  3, 8,  0.0],
    "Ray Allen":        [28, 10, 1, 2, 0, 1, 0, 1, 3,  7,  2, 5, 2, 2,  2, 13, 0.0],
    "Shane Battier":    [24, 6,  1, 3, 1, 1, 0, 1, 2,  5,  1, 4, 1, 1,  2, 8,  0.0],
    "Norris Cole":      [18, 4,  2, 2, 0, 1, 0, 1, 2,  5,  0, 1, 1, 2,  2, 6,  0.0],
    "Mike Miller":      [18, 6,  1, 3, 1, 0, 0, 1, 2,  5,  2, 4, 0, 0,  2, 7,  0.0],
    "Chris Andersen":   [15, 4,  0, 5, 2, 0, 2, 1, 2,  3,  0, 0, 1, 2,  3, 7,  0.2],
}

# Generic opponent player templates
OPP_PLAYERS = {
    "Star PG":    [36, 22, 8, 4, 0, 2, 0, 3, 8,  18, 2, 6, 4, 5,  2, 28, 0.05],
    "Star SG":    [36, 24, 4, 4, 1, 2, 1, 2, 9,  20, 2, 5, 4, 5,  2, 30, 0.15],
    "Star SF":    [36, 20, 5, 7, 2, 2, 1, 2, 8,  17, 1, 4, 3, 4,  2, 27, 0.1],
    "Star PF":    [34, 18, 3, 9, 3, 1, 2, 2, 7,  14, 0, 1, 4, 6,  3, 24, 0.1],
    "Star C":     [32, 16, 2, 10,4, 1, 3, 2, 6,  11, 0, 0, 4, 7,  3, 22, 0.3],
    "Role PG":    [24, 8,  4, 2, 0, 1, 0, 2, 3,  8,  1, 4, 1, 2,  2, 10, 0.0],
    "Role SG":    [22, 7,  2, 3, 1, 1, 0, 1, 3,  7,  1, 3, 1, 2,  2, 9,  0.05],
    "Role SF":    [20, 6,  2, 4, 1, 1, 0, 1, 2,  6,  1, 3, 1, 2,  2, 8,  0.0],
    "Role PF":    [20, 6,  1, 5, 2, 0, 1, 1, 2,  5,  0, 1, 2, 3,  2, 8,  0.05],
    "Role C":     [18, 5,  1, 5, 2, 0, 1, 1, 2,  4,  0, 0, 1, 2,  3, 7,  0.1],
}

def rand_stat(base, variance=0.25):
    low = max(0, int(base * (1 - variance)))
    high = max(low + 1, int(base * (1 + variance)))
    return random.randint(low, high)

def generate_player_row(team_name, player_name, template):
    min_, pts, ast, reb, oreb, stl, blk, to, fgm, fga, tpm, tpa, ftm, fta, fouls, prf_base, dunk_chance = template

    minutes = rand_stat(min_, 0.15)
    points = rand_stat(pts)
    assists = rand_stat(ast)
    rebounds = rand_stat(reb)
    off_rebounds = rand_stat(oreb)
    steals = rand_stat(stl)
    blocks = rand_stat(blk)
    turnovers = rand_stat(to)
    fg_made = rand_stat(fgm)
    fg_attempted = max(fg_made, rand_stat(fga))
    three_made = rand_stat(tpm)
    three_attempted = max(three_made, rand_stat(tpa))
    ft_made = rand_stat(ftm)
    ft_attempted = max(ft_made, rand_stat(fta))
    foul_count = rand_stat(fouls)
    plus_minus = random.randint(-15, 15)
    prf = rand_stat(prf_base)
    dunks = 1 if random.random() < dunk_chance else 0

    return [
        team_name, player_name, minutes, points, assists, rebounds,
        off_rebounds, steals, blocks, turnovers, fg_made, fg_attempted,
        three_made, three_attempted, ft_made, ft_attempted,
        foul_count, plus_minus, prf, dunks
    ]

def generate_game_csv(game_num, date, your_team_name, opp_team_name, win_loss, your_score, opp_score, roster):
    filename = f"fake_game_{game_num:03d}.csv"
    filepath = os.path.join("fake_games", filename)

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["date", date])
        writer.writerow(["home_away", random.choice(["H", "A"])])
        writer.writerow(["win_loss", win_loss])
        writer.writerow(["your_team", your_team_name])
        writer.writerow(["your_score", your_score])
        writer.writerow(["opp_team", opp_team_name])
        writer.writerow(["opp_score", opp_score])
        writer.writerow(["---"])

        writer.writerow([
            "team", "player_name", "minutes", "points", "assists", "rebounds",
            "off_rebounds", "steals", "blocks", "turnovers", "fg_made", "fg_attempted",
            "three_made", "three_attempted", "ft_made", "ft_attempted",
            "fouls", "plus_minus", "points_responsible_for", "dunks"
        ])

        for player_name, template in roster.items():
            row = generate_player_row(your_team_name, player_name, template)
            writer.writerow(row)

        opp_positions = list(OPP_PLAYERS.items())
        for pos_name, template in opp_positions:
            player_display = f"{opp_team_name} {pos_name}"
            row = generate_player_row(opp_team_name, player_display, template)
            writer.writerow(row)

    return filepath

def generate_all_games(num_games=100):
    os.makedirs("fake_games", exist_ok=True)

    start_date = datetime(2024, 1, 1)

    for i in range(1, num_games + 1):
        your_team = random.choice(YOUR_TEAMS)
        roster = HEAT_0506 if "2005-06" in your_team else HEAT_1213
        opp_team = random.choice(OPP_TEAMS)

        win_loss = random.choice(["W", "W", "W", "L", "L"])  # slight win bias
        if win_loss == "W":
            your_score = random.randint(95, 118)
            opp_score = random.randint(85, your_score - 1)
        else:
            opp_score = random.randint(95, 118)
            your_score = random.randint(85, opp_score - 1)

        date = (start_date + timedelta(days=i * 3)).strftime("%Y-%m-%d")

        filepath = generate_game_csv(i, date, your_team, opp_team, win_loss, your_score, opp_score, roster)

        print(f"Game {i:03d}: {your_team} vs {opp_team} ({win_loss}) → importing...")
        subprocess.run(["python", "add_game.py", filepath], check=True)

    print(f"\n✓ {num_games} games generated and imported successfully!")

if __name__ == "__main__":
    generate_all_games(100)