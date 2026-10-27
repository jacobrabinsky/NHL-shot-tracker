# -------------------------
# PLAYER TABS
# -------------------------

st.subheader("Player shot trends")

st.caption(
    "★ identifies projected players. "
    "Starred Underperformers shows only players who are "
    "starred AND shot at least one below their season average."
)

# Keep the team filter selected above this section.
# The selected team applies to both tabs.

# Identify players who underperformed in their last game.
filtered = filtered.copy()

filtered["Below Avg"] = (
    filtered["Last Game"] - filtered["Season Avg"]
)

underperformers = filtered[
    filtered["Last Game"].notna()
    & (filtered["Last Game"] <= filtered["Season Avg"] - 1)
].copy()

# Starred underperformers must satisfy BOTH conditions.
starred_underperformers = underperformers[
    underperformers["⭐"] == "★"
].copy()

starred_underperformers = starred_underperformers.sort_values(
    "Hit Avg %",
    ascending=False,
)

# No separate star or Home/Away columns.
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

    # Put the star directly beside the player's name.
    original_names = data["Player"].astype(str)
    stars = data["⭐"].eq("★")

    table["Player"] = [
        f"★ {name}" if starred else name
        for name, starred in zip(original_names, stars)
    ]

    def highlight_underperformers(row):
        value = row.get("Last Game")
        avg = row.get("Season Avg")

        if (
            pd.notna(value)
            and pd.notna(avg)
            and value <= avg - 1
        ):
            return [
                (
                    "background-color: #7f1d1d; "
                    "color: #ffffff; font-weight: 600"
                )
                if col == "Last Game"
                else ""
                for col in row.index
            ]

        return [""] * len(row)

    styled = table.style.apply(
        highlight_underperformers,
        axis=1,
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
            "Logo": st.column_config.ImageColumn(
                "Logo",
                width="small",
            ),
            "Team": st.column_config.TextColumn(
                "Team",
                width="small",
            ),
            "Player": st.column_config.TextColumn(
                "Player",
                width="medium",
            ),
            "Hit Avg %": st.column_config.NumberColumn(
                "Chance to Hit Avg",
                help=(
                    "Heuristic estimate, not a calibrated "
                    "probability."
                ),
                format="%d%%",
            ),
        },
    )


# Two simple tabs.
all_tab, starred_tab = st.tabs(
    ["🏒 All Players", "⭐ Starred Underperformers"]
)

with all_tab:
    st.caption(
        "Use the Team dropdown above to filter players. "
        "Underperformers are grouped first."
    )

    all_players_sorted = filtered.sort_values(
        "Below Avg",
        ascending=True,
        na_position="last",
    )

    show_player_table(
        all_players_sorted,
        "all_players_table",
    )

with starred_tab:
    st.caption(
        "Only starred players who underperformed in their "
        "last game appear here."
    )

    st.metric(
        "Starred underperformers",
        len(starred_underperformers),
    )

    show_player_table(
        starred_underperformers,
        "starred_underperformers_table",
    )
