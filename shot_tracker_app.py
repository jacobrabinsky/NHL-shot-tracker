import streamlit as st
import requests
import pandas as pd
import time

BASE = "https://api-web.nhle.com/v1"

def safe_get(url, retries=4):
    for attempt in range(retries):
        try:
            r = requests.get(url, timeout=25)
            if r.status_code == 200 and r.text.strip():
                return r.json()
        except:
            pass
        time.sleep(2)
    return None

def get_teams():
    data = safe_get(f"{BASE}/standings/now")
    if not data:
        return []
    return [t["teamAbbrev"]["default"] for t in data["standings"]]

def get_top_shooters(team, n=5):
    data = safe_get(f"{BASE}/club-stats/{team}/now")
    if not data:
        return []
    skaters = data.get("skaters", [])
    top = sorted(skaters, key=lambda x: x.get("shots", 0), reverse=True)[:n]
    result = []
    for p in top:
        shots = p.get("shots", 0)
        gp = p.get("gamesPlayed", 1) or 1
        first = p["firstName"]["default"]
        last = p["lastName"]["default"]
        result.append({
            "playerId": p["playerId"],
            "name": f"{first[0]}. {last}",
            "avg": round(shots / gp, 2)
        })
    return result

def get_last5_shots(player_id):
    data = safe_get(f"{BASE}/player/{player_id}/game-log/now")
    if not data:
        return [None] * 5
    games = data.get("gameLog", [])[:5]
    return [g.get("shots", 0) for g in games] + [None] * (5 - len(games))

def build_tracker():
    teams = get_teams()
    results = []
    progress = st.progress(0)
    status = st.empty()
    for i, team in enumerate(teams):
        status.text(f"Fetching {team}... ({i+1}/{len(teams)})")
        shooters = get_top_shooters(team, n=5)
        for s in shooters:
            last5 = get_last5_shots(s["playerId"])
            results.append({
                "Team": team,
                "Player": s["name"],
                "Season Avg": s["avg"],
                "Last Game": last5[0],
                "2 Games Ago": last5[1],
                "3 Games Ago": last5[2],
                "4 Games Ago": last5[3],
                "5 Games Ago": last5[4],
            })
        progress.progress((i + 1) / len(teams))
        time.sleep(1.5)  # slower to avoid rate limits
    status.text("Done!")
    return pd.DataFrame(results)

def style_last_game(row):
    styles = [""] * len(row)
    try:
        last_game_idx = row.index.get_loc("Last Game")
        season_avg = float(row["Season Avg"]) if row["Season Avg"] else None
        last_game = float(row["Last Game"]) if row["Last Game"] else None
        if last_game is not None and season_avg is not None and last_game <= season_avg - 1:
            styles[last_game_idx] = "background-color: #ffcccc"
    except:
        pass
    return styles

st.set_page_config(page_title="NHL Shot Tracker", layout="wide")
st.title("NHL Shot Tracker")
st.caption("Top 5 shot-takers • Last Game highlighted if ≥1 shot under season average")

if st.button("Refresh Data"):
    st.cache_data.clear()

df = build_tracker()

numeric_cols = ["Season Avg", "Last Game", "2 Games Ago", "3 Games Ago", "4 Games Ago", "5 Games Ago"]
for col in numeric_cols:
    df[col] = df[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "")

teams = ["All"] + sorted(df["Team"].unique())
selected_team = st.selectbox("Filter by team", teams)

if selected_team != "All":
    df = df[df["Team"] == selected_team]

styled = df.style.apply(style_last_game, axis=1)
st.dataframe(styled, use_container_width=True, hide_index=True)

st.download_button("Download CSV", df.to_csv(index=False), "nhl_shot_tracker.csv")