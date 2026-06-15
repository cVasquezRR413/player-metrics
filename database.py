import sqlite3

def get_connection():
    conn = sqlite3.connect("2k_stats.db")
    return conn

def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            game_id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            home_away TEXT NOT NULL,
            win_loss TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            team_id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            team_name TEXT NOT NULL,
            is_your_team INTEGER NOT NULL,
            score INTEGER NOT NULL,
            FOREIGN KEY (game_id) REFERENCES games(game_id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS player_stats (
            stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER NOT NULL,
            team_id INTEGER NOT NULL,
            player_name TEXT NOT NULL,
            minutes INTEGER,
            points INTEGER,
            assists INTEGER,
            rebounds INTEGER,
            off_rebounds INTEGER,
            steals INTEGER,
            blocks INTEGER,
            turnovers INTEGER,
            fg_made INTEGER,
            fg_attempted INTEGER,
            three_made INTEGER,
            three_attempted INTEGER,
            ft_made INTEGER,
            ft_attempted INTEGER,
            fouls INTEGER,
            plus_minus INTEGER,
            points_responsible_for INTEGER,
            dunks INTEGER,
            FOREIGN KEY (game_id) REFERENCES games(game_id),
            FOREIGN KEY (team_id) REFERENCES teams(team_id)
        )
    """)

    conn.commit()
    conn.close()
    print("Database ready.")

if __name__ == "__main__":
    create_tables()