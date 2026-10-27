import base64
import time
from datetime import date

import pandas as pd
import requests
import streamlit as st

BASE = "https://api-web.nhle.com/v1"
LOGO_BASE = "https://assets.nhle.com/logos/nhl/svg"
BACKGROUND_FILE = "stanley_cup_money.jpg"

st.set_page_config(
    page_title="NHL Shot Tracker",
    page_icon="🏒",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def apply_design():
    background_css = ""

    try:
        with open(BACKGROUND_FILE, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode()

        background_css = f"""
        .stApp {{
            background-image:
                linear-gradient(
                    rgba(8, 12, 22, 0.90),
                    rgba(8, 12, 22, 0.94)
                ),
                url("data:image/jpeg;base64,{encoded}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        """
    except FileNotFoundError:
        pass

    st.markdown(
        f"""
        <style>
        {background_css}
        .block-container {{
            max-width: 1500px;
            padding: 1.5rem 1rem 2rem 1rem;
        }}
        div[data-testid="stDataFrame"] {{
            border: 1px solid rgba(150,160,180,0.22);
            border-radius: 10px;
            overflow: hidden;
        }}
        @media (max-width: 640px) {{
            .block-container {{
                padding: 0.75rem 0.65rem 2rem 0.65rem;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


apply_design()


@st.cache_data(ttl=900, show_spinner=False)
def safe_get(url):
    for attempt in range(3):
        try:
            response = requests.get(
                url,
                timeout=15,
                headers={"User-Agent": "NHLShotTracker/1.0"},
            )
            if response.status_code == 200:
                return response.json()
            if response.status_code == 429:
                time.sleep(2 * (attempt + 1))
            else:
                return None
        except requests.RequestException:
            time.sleep(attempt + 1)
    return None


@st.cache_data(ttl=900, show_spinner=False)
def get_teams():
    data = safe_get(f"{BASE}/standings/now") or {}
    return sorted({
        team.get("teamAbbrev", {}).get("default", "")
        for team in data.get("standings", [])
        if team.get("teamAbbrev", {}).get("default")
    })


@st.cache_data(ttl=3600, show_spinner=False)
def get_top_shooters(team, n=5):
    data = safe_get(f"{BASE}/club-stats/{team}/now") or {}
    players = data.get("skaters", [])
    results = []

    for player in sorted(
        players,
        key=lambda p: p.get("shots", 0),
        reverse=True,
    )[:n]:
        games_played = player.get("gamesPlayed") or 0
        if games_played == 0:
            continue

        first = player.get("firstName", {}).get("default", "")
        last = player.get("lastName", {}).get("default", "")

        results.append({
            "playerId": player.get("playerId"),
            "name": f"{first} {last}".strip(),
            "avg": player.get("shots", 0) / games_played,
        })

    return results


@st.cache_data(ttl=3600, show_spinner=False)
def get_player_log(player_id):
    data = safe_get(
        f"{BASE}/player/{player_id}/game-log/now"
    ) or {}
    return data.get("gameLog", [])


@st.cache_data(ttl=1800, show_spinner=False)
def get_next_game(team):
    data = safe_get(
        f"{BASE}/club-schedule-season/{team}/now"
    ) or {}
    games = data.get("games", [])

    upcoming = [
        game for game in games
        if game.get("gameDate", "") >= date.today().isoformat()
        and game.get("gameState", "") not in ("OFF", "FINAL")
    ]

    if not upcoming:
        return None

    upcoming.sort(key=lambda game: game.get("gameDate", "9999"))
    game = upcoming[0]
    home = game.get("homeTeam", {}).get("abbrev", "")
    away = game.get("awayTeam", {}).get("abbrev", "")

    if team not in (home, away):
        return None

    return {
        "date": game.get("gameDate", ""),
        "opponent": away if team == home else home,
        "venue": "Home" if team == home else "Away",
    }


def get_opponent(game):
    return (
        game.get("opponentAbbrev")
        or game.get("opponent", {}).get("abbrev")
        or game.get("opponentTeamAbbrev")
        or ""
    )


def is_home_game(game):
    venue = str(
        game.get("homeRoad", game.get("homeAway", ""))
    ).lower()

    if venue in ("h", "home"):
        return True
    if venue in ("r", "a", "away", "road"):
        return False
    return None


def analyze_player(player, team, next_game):
    season_avg = float(player["avg"])
    log = get_player_log(player["playerId"])

    recent = [
        game.get("shots")
        for game in log[:10]
        if game.get("shots") is not None
    ]
    last5 = [
        game.get("shots")
        for game in log[:5]
        if game.get("shots") is not None
    ]

    recent_avg = sum(recent) / len(recent) if recent else season_avg
    opponent = next_game["opponent"] if next_game else None
    venue = next_game["venue"] if next_game else None

    matchup_games = [
        game for game in log
        if opponent
        and get_opponent(game) == opponent
        and game.get("shots") is not None
    ]

    matchup_avg = (
        sum(game["shots"] for game in matchup_games) / len(matchup_games)
        if matchup_games else None
    )

    venue_games = [
        game for game in log
        if venue is not None
        and is_home_game(game) == (venue == "Home")
        and game.get("shots") is not None
    ]

    venue_avg = (
        sum(game["shots"] for game in venue_games) / len(venue_games)
        if venue_games else None
    )

    bounceback = []
    for i in range(len(log) - 1):
        previous_game = log[i + 1]
        following_game = log[i]
        before = previous_game.get("shots")
        after = following_game.get("shots")

        if before is None or after is None:
            continue
        if before < season_avg:
            bounceback.append(after)

    bounceback_avg = (
        sum(bounceback) / len(bounceback) if bounceback else None
    )

    if matchup_avg is not None:
        matchup_weight = min(0.20, 0.20 * len(matchup_games) / 5)
        components = [
            (season_avg, 0.45),
            (recent_avg, 0.35),
            (matchup_avg, matchup_weight),
        ]
    else:
        components = [(season_avg, 0.55), (recent_avg, 0.45)]

    if venue_avg is not None:
        components = [
            (value, weight * 0.85) for value, weight in components
        ]
        components.append((venue_avg, 0.15))

    projection = (
        sum(value * weight for value, weight in components)
        / sum(weight for _, weight in components)
    )

    if bounceback_avg is not None and len(bounceback) >= 3:
        adjustment = max(
            -0.5,
            min(0.5, (bounceback_avg - season_avg) * 0.15),
        )
        projection += adjustment

    threshold = int(season_avg)
    if season_avg > threshold:
        threshold += 1

    recent_hits = sum(shots >= threshold for shots in recent)
    recent_n = len(recent)
    recent_rate = (
        (recent_hits + 2) / (recent_n + 4) if recent_n else 0.5
    )

    if len(matchup_games) >= 2:
        matchup_hits = sum(
            game["shots"] >= threshold for game in matchup_games
        )
        matchup_rate = (
            (matchup_hits + 1) / (len(matchup_games) + 2)
        )
        probability = 0.75 * recent_rate + 0.25 * matchup_rate
    else:
        probability = recent_rate

    star = probability >= 0.60

    return {
        "Team": team,
        "Logo": f"{LOGO_BASE}/{team}.svg",
        "Player": player["name"],
        "Season Avg": round(season_avg, 2),
        "Last Game": last5[0] if last5 else None,
        "2 Games Ago": last5[1] if len(last5) > 1 else None,
        "3 Games Ago": last5[2] if len(last5) > 2 else None,
        "4 Games Ago": last5[3] if len(last5) > 3 else None,
        "5 Games Ago": last5[4] if len(last5) > 4 else None,
        "Next Opponent": opponent or "Unknown",
        "Projected Shots": round(max(0, projection), 2),
        "Hit Avg %": round(probability * 100),
        "⭐": "★" if star else "",
        "Games vs Opponent": len(matchup_games),
        "Bounce-back Games": len(bounceback),
        "Player ID": player["playerId"],
    }


@st.cache_data(ttl=900, show_spinner=False)
def build_tracker():
    rows = []
    for team in get_teams():
        players = get_top_shooters(team, n=5)
        upcoming = get_next_game(team)

        for player in players:
            try:
                rows.append(analyze_player(player, team, upcoming))
            except (TypeError, ValueError, KeyError):
                continue

    return pd.DataFrame(rows)


st.title("🏒 NHL Shot Tracker")
st.caption("Player shot trends · Underperformers · Next-game estimates")

refresh_col, note_col = st.columns([1, 3])

with refresh_col:
    if st.button("↻ Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

with note_col:
    st.caption("Projections are estimates, not guaranteed outcomes.")

with st.spinner("Loading NHL player data..."):
    df = build_tracker()

if df.empty:
    st.error("No player data could be loaded. Try refreshing the data.")
    st.stop()


# FILTERS
filter_col, sort_col = st.columns(2)

with filter_col:
    team_options = ["All teams"] + sorted(df["Team"].unique())
    selected_team = st.selectbox("Filter by team", team_options)

with sort_col:
    sort_mode = st.selectbox(
        "Sort players",
        [
            "Underperformers first",
            "Highest projected shots",
            "Lowest projected shots",
            "Player name",
        ],
    )

filtered = df.copy()

if selected_team != "All teams":
    filtered = filtered[filtered["Team"] == selected_team]

filtered["Below Avg"] = filtered["Last Game"] - filtered["Season Avg"]

if sort_mode == "Underperformers first":
    filtered = filtered.sort_values(
        "Below Avg", ascending=True, na_position="last"
    )
elif sort_mode == "Highest projected shots":
    filtered = filtered.sort_values("Projected Shots", ascending=False)
elif sort_mode == "Lowest projected shots":
    filtered = filtered.sort_values("Projected Shots", ascending=True)
else:
    filtered = filtered.sort_values("Player")


# SUMMARY
underperformers = filtered[
    filtered["Last Game"].notna()
    & (filtered["Last Game"] <= filtered["Season Avg"] - 1)
]

starred_underperformers = underperformers[
    underperformers["⭐"] == "★"
]

metric1, metric2, metric3 = st.columns(3)
metric1.metric("Players shown", len(filtered))
metric2.metric("Underperformers", len(underperformers))
metric3.metric("Starred underperformers", len(starred_underperformers))


# TABLES
st.subheader("Player shot trends")
st.caption(
    "Stars appear beside player names. The starred tab only shows "
    "starred players who underperformed in their last game."
)

display_columns = [
    "Logo",
    "Team",
    "Player",
    "Season Avg",
    "Last Game",
    "2 Games Ago",
    "3 Games Ago",
    "4 Games Ago",
    "5 Games Ago",
    "Next Opponent",
    "Projected Shots",
    "Hit Avg %",
]


def show_player_table(data, table_key):
    if data.empty:
        st.info("No players match these filters right now.")
        return

    table = data[display_columns].copy()
    table["Player"] = [
        f"★ {name}" if starred else name
        for name, starred in zip(data["Player"], data["⭐"].eq("★"))
    ]

    def highlight_underperformers(row):
        shots = row.get("Last Game")
        average = row.get("Season Avg")

        if (
            pd.notna(shots)
            and pd.notna(average)
            and shots <= average - 1
        ):
            return [
                "background-color: #7f1d1d; color: #ffffff; font-weight: 600"
                if column == "Last Game" else ""
                for column in row.index
            ]

        return [""] * len(row)

    styled = table.style.apply(
        highlight_underperformers, axis=1
    ).format(
        {
            "Season Avg": "{:.2f}",
            "Projected Shots": "{:.2f}",
            "Hit Avg %": "{}%",
        },
        na_rep="—",
    )

    st.dataframe(
        styled,
        key=table_key,
        use_container_width=True,
        hide_index=True,
        height=550,
        column_config={
            "Logo": st.column_config.ImageColumn("Logo", width="small"),
            "Team": st.column_config.TextColumn("Team", width="small"),
            "Player": st.column_config.TextColumn("Player", width="medium"),
            "Hit Avg %": st.column_config.NumberColumn(
                "Chance to Hit Avg",
                help="Heuristic estimate, not a calibrated probability.",
                format="%d%%",
            ),
        },
    )


all_tab, starred_tab = st.tabs(
    ["🏒 All Players", "⭐ Starred Underperformers"]
)

with all_tab:
    all_sorted = filtered.sort_values(
        "Below Avg", ascending=True, na_position="last"
    )
    show_player_table(all_sorted, "all_players_table")

with starred_tab:
    st.caption(
        "Only players who are starred AND had at least one fewer "
        "shot than their season average in their last game."
    )
    st.metric("Starred underperformers", len(starred_underperformers))

    starred_sorted = starred_underperformers.sort_values(
        "Hit Avg %", ascending=False
    )
    show_player_table(starred_sorted, "starred_underperformers_table")


# NEXT-GAME OUTLOOK
st.subheader("Next-game outlook")

if not filtered.empty:
    selected_player = st.selectbox(
        "View player details",
        filtered["Player"].tolist(),
        key="player_details",
    )

    player_row = filtered[
        filtered["Player"] == selected_player
    ].iloc[0]

    col1, col2, col3 = st.columns(3)
    col1.metric("Season shots/game", f"{player_row['Season Avg']:.2f}")
    col2.metric("Projected shots", f"{player_row['Projected Shots']:.2f}")
    col3.metric(
        "Estimated chance to hit average",
        f"{player_row['Hit Avg %']}%",
    )

    st.caption(
        f"Next matchup: {player_row['Team']} vs "
        f"{player_row['Next Opponent']}"
    )
    st.caption(
        f"Historical games vs opponent: {player_row['Games vs Opponent']} · "
        f"Bounce-back samples: {player_row['Bounce-back Games']}"
    )
    st.info(
        "Expected goalie data is not connected. These projections do not "
        "account for starting goalie quality and are preliminary estimates."
    )


# CSV DOWNLOAD
csv = filtered.drop(
    columns=["Logo", "Below Avg", "Player ID"],
    errors="ignore",
).to_csv(index=False)

st.download_button(
    "Download CSV",
    data=csv,
    file_name="nhl_shot_tracker.csv",
    mime="text/csv",
    use_container_width=True,
)
