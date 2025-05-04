import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import uuid
import random
from streamlit_option_menu import option_menu
from sqlalchemy import create_engine
from mongo_v1 import load_data, save_data

# --- Session State Setup ---
if "data" not in st.session_state:
    st.session_state.data = load_data()

# --- Seiten-Navigation ---
with st.sidebar:
    page = option_menu(
        "Wuzzel Turnier",
        ["Team Datenbank", "Turnierverwaltung", "Teams", "Gruppenphase", "KO-Runde"],
        icons=["database", "clipboard", "trophy", "bar-chart", "award"],
        menu_icon="cast",
        default_index=0
    )

    # Turniername unter dem Menü anzeigen
    current_tournament = st.session_state.data.get("current_tournament")
    if current_tournament:
        st.markdown("---")
        st.subheader("Aktuelles Turnier")
        st.write(f"**{current_tournament}**")
    else:
        st.markdown("---")
        st.write("Kein Turnier ausgewählt.")

if page in ["Teams", "Spielplan", "Gruppenphase", "KO-Runde"]:
    tournament_name = st.session_state.data.get("current_tournament", "Kein Turnier ausgewählt")
    st.title(tournament_name)
else:
    st.title("Wuzzel Turnier")

# --- Helper Functions ---
def get_current(key):
    return st.session_state.data["tournaments"][st.session_state.data["current_tournament"]][key]

def set_current(key, value):
    st.session_state.data["tournaments"][st.session_state.data["current_tournament"]][key] = value

# --- Team Datenbank ---
if page == "Team Datenbank":
    st.header("Team Datenbank")

    db_config = st.secrets["mysql"]
    engine = f"mysql+mysqlconnector://{db_config['user']}:{db_config['password']}@{db_config['host']}/{db_config['database']}"
    query = "SELECT id, name, player_1, player_2, timestamp FROM teams"
    teams = pd.read_sql(query, engine)

    st.dataframe(teams)

# --- Turnierverwaltung ---
elif page == "Turnierverwaltung":
    st.header("Turnier erstellen oder auswählen")

    # Turnier erstellen
    with st.form("create_tournament"):
        name = st.text_input("Name des Turniers")
        date = st.date_input("Datum des Turniers")
        is_group_phase = st.checkbox("Gruppenphase mit zwei Gruppen")
        submitted = st.form_submit_button("Neues Turnier erstellen")
        if submitted and name:
            st.session_state.data["tournaments"][name] = {
                "date": str(date),
                "players": [],
                "teams": [],
                "matches": [],
                "ko_round": [],
                "group_phase": is_group_phase,
                "groups": {"A": [], "B": []},
                "group_matches": {"A": [], "B": []},
                "schedule_created": False   
            }
            st.session_state.data["current_tournament"] = name
            save_data(st.session_state.data)
            st.success(f"Turnier '{name}' erstellt und ausgewählt.")

    # Turnier auswählen
    st.subheader("Existierende Turniere")
    if st.session_state.data["tournaments"]:
        selected = st.selectbox("Turnier auswählen", list(st.session_state.data["tournaments"].keys()))
        if st.button("Turnier laden"):
            st.session_state.data["current_tournament"] = selected
            save_data(st.session_state.data)
            st.success(f"Turnier '{selected}' geladen.")
    else:
        st.info("Noch keine Turniere vorhanden.")

    # Teams übernehmen
    if st.session_state.data["current_tournament"]:
        st.subheader("Teams aus Datenbank übernehmen")

        # Verbindung zur Teamdatenbank
        engine = create_engine("mysql+mysqlconnector://d0437c1d:uguWe3RnmzqfaKRHmswU@kicker.kernlos.at/d0437c1d")
        query = "SELECT id, name, player_1, player_2 FROM teams"
        teams_db = pd.read_sql(query, engine)

        # Zeige Info, falls Spielplan schon erstellt wurde
        if get_current("schedule_created"):
            st.warning("Der Spielplan wurde bereits erstellt. Es können keine Teams mehr hinzugefügt werden.")
        else:
            selected_teams = st.multiselect(
                "Wähle Teams aus der Datenbank aus:",
                teams_db["name"].tolist()
            )

            if st.button("Teams übernehmen"):
                for team_name in selected_teams:
                    team_row = teams_db[teams_db["name"] == team_name].iloc[0]
                    team = {
                        "name": team_row["name"],
                        "players": [team_row["player_1"], team_row["player_2"]],
                        "player_ids": [str(uuid.uuid4()), str(uuid.uuid4())],  # neue UUIDs generieren
                        "points": 0,
                        "games_played": 0,
                        "wins": 0,
                        "draws": 0,
                        "losses": 0,
                        "goals_for": 0,
                        "goals_against": 0
                    }
                    get_current("teams").append(team)
                save_data(st.session_state.data)
                st.success(f"{len(selected_teams)} Teams übernommen.")

# --- Teams ---
elif page == "Teams":
    with st.expander("Teammodus anzeigen"):
        st.markdown("""
        **Teamzusammensetzung:**  
        - Standardmäßig treten Mixed-Teams an  
        - In begründeten Ausnahmefällen sind auch reine Damen- oder Herren-Teams möglich
        """)
    st.header("Bestehende Teams")

    teams = get_current("teams")

    if not teams:
        st.info("Es wurden noch keine Teams erstellt.")
    else:
        for t in teams:
            st.markdown(f"- **{t['name']}** ({t['players'][0]} & {t['players'][1]})")

# --- Gruppenphase ---
elif page == "Gruppenphase":
    st.subheader("Gruppenspiele & Tabelle")
    with st.expander("Modus Gruppenphase anzeigen"):
        st.markdown("""
        **Modus bei einer Gruppe:**  
        - Alle Teams spielen gemeinsam in einer einzigen Gruppe.             
        - Jedes Team tritt zweimal gegen jedes andere Team an.
                    
        **Modus bei zwei Gruppen:**  
        - Die Teams werden per Zufall auf zwei Gruppen aufgeteilt.
        - Innerhalb jeder Gruppe spielt jedes Team zweimal gegen jedes andere Team der Gruppe.
                    
        **Spiele**  
        - Ein Spiel besteht aus **10 Bällen**. 
                    
        **Aufstieg ins Halbfinale**  
        - Die vier besten Teams der Gruppenphase qualifizieren sich für das Halbfinale.
        - Bei Punktgleichheit und identischem Torverhältnis entscheidet ein Entscheidungstor über den Aufstieg.

        """)

    components.html("""
                    <style>
                        :root {
                            color-scheme: light dark;
                        }

                        .timer-container {
                            font-family: sans-serif;
                            text-align: center;
                            padding: 10px;
                        }

                        .timer-button {
                            font-size: 16px;
                            padding: 6px 12px;
                            border: none;
                            border-radius: 8px;
                            cursor: pointer;
                            background-color: #f44336; /* Helles Rot */
                            color: white;
                            transition: background-color 0.3s;
                        }

                        .timer-button:hover {
                            background-color: #e53935; /* Dunkleres Rot beim Hover */
                        }

                        .timer-display {
                            font-size: 24px;
                            font-weight: bold;
                            margin-top: 10px;
                            color: var(--timer-text-color, #fff);  /* Dynamische Textfarbe */
                        }

                        .progress-bar-background {
                            width: 100%;
                            background-color: rgba(200, 200, 200, 0.2);
                            height: 20px;
                            border-radius: 10px;
                            overflow: hidden;
                            margin-top: 10px;
                        }

                        .progress-bar-fill {
                            height: 100%;
                            width: 100%;
                            background-color: #f44336; /* Helles Rot für den Fortschrittsbalken */
                            transition: width 1s linear;
                        }

                        /* Anpassung für Dark Mode */
                        @media (prefers-color-scheme: dark) {
                            .timer-display {
                                color: #fff; /* Helle Schrift im Dark Mode */
                            }

                            .progress-bar-fill {
                                background-color: #e57373; /* Helles Rot im Dark Mode */
                            }
                        }

                        /* Anpassung für Light Mode */
                        @media (prefers-color-scheme: light) {
                            .timer-display {
                                color: #333; /* Dunkle Schrift im Light Mode */
                            }

                            .progress-bar-fill {
                                background-color: #f44336; /* Helles Rot im Light Mode */
                            }
                        }
                    </style>

                    <div class="timer-container">
                        <button class="timer-button" onclick="startTimer()">Timer starten</button>
                        <div id="timer" class="timer-display">05:00</div>

                        <div class="progress-bar-background">
                            <div id="progress" class="progress-bar-fill"></div>
                        </div>
                    </div>

                    <script>
                        const totalSeconds = 30;
                        let interval;

                        function startTimer() {
                            clearInterval(interval);
                            let timeLeft = totalSeconds;
                            updateDisplay(timeLeft);
                            updateProgress(timeLeft);
                            
                            interval = setInterval(() => {
                                timeLeft--;
                                if (timeLeft >= 0) {
                                    updateDisplay(timeLeft);
                                    updateProgress(timeLeft);
                                } else {
                                    clearInterval(interval);
                                    document.getElementById("timer").textContent = "Zeit abgelaufen!";
                                    document.getElementById("progress").style.width = "0%";
                                    playSound();
                                }
                            }, 1000);
                        }

                        function updateDisplay(seconds) {
                            const m = String(Math.floor(seconds / 60)).padStart(2, '0');
                            const s = String(seconds % 60).padStart(2, '0');
                            document.getElementById("timer").textContent = `${m}:${s}`;
                        }

                        function updateProgress(seconds) {
                            const percent = (seconds / totalSeconds) * 100;
                            document.getElementById("progress").style.width = `${percent}%`;
                        }

                        function playSound() {
                            const ctx = new (window.AudioContext || window.webkitAudioContext)();
                            const oscillator = ctx.createOscillator();
                            oscillator.type = 'sine';
                            oscillator.frequency.setValueAtTime(1000, ctx.currentTime);
                            oscillator.connect(ctx.destination);
                            oscillator.start();
                            oscillator.stop(ctx.currentTime + 1.5);
                        }
                    </script>
                """, height=170)
    
    teams = get_current("teams")
    group_mode = get_current("group_phase")
    schedule_created = get_current("schedule_created")

    if len(teams) < 4:
        st.error("Mindestens 4 Teams erforderlich.")
    else:
        if not schedule_created:
            if st.button("Spielplan erstellen"):
                if group_mode:
                    random.shuffle(teams)
                    midpoint = len(teams) // 2
                    set_current("groups", {"A": teams[:midpoint], "B": teams[midpoint:]})

                    group_matches = {"A": [], "B": []}
                    match_number = 1
                    for group in ["A", "B"]:
                        g_teams = get_current("groups")[group]
                        for i in range(len(g_teams)):
                            for j in range(i+1, len(g_teams)):
                                for reverse in [False, True]:
                                    t1 = g_teams[i if not reverse else j]["name"]
                                    t2 = g_teams[j if not reverse else i]["name"]
                                    group_matches[group].append({
                                        "match_number": match_number,
                                        "team1": t1, "team2": t2, "score": "-",
                                        "color": "Rot vs Blau"
                                    })
                                    match_number += 1
                    set_current("group_matches", group_matches)
                else:
                    matches = []
                    match_number = 1
                    for i in range(len(teams)):
                        for j in range(i+1, len(teams)):
                            for reverse in [False, True]:
                                t1 = teams[i if not reverse else j]["name"]
                                t2 = teams[j if not reverse else i]["name"]
                                matches.append({
                                    "match_number": match_number,
                                    "team1": t1, "team2": t2, "score": "-",
                                    "color": "Rot vs Blau"
                                })
                                match_number += 1
                    set_current("matches", matches)

                set_current("schedule_created", True)
                save_data(st.session_state.data)
                st.success("Spielplan wurde erfolgreich erstellt!")
        else:
           # --- Ergebnisse eingeben ---
            if group_mode:
                with st.expander("Gruppenspiele (Rot vs. Blau)", expanded=True):
                    for group in ["A", "B"]:
                        st.subheader(f"Gruppe {group}")
                        for idx, match in enumerate(get_current("group_matches")[group]):
                            col1, col2, col3 = st.columns([5, 1.5, 1.5])
                            with col1:
                                st.text(f"{match['match_number']}. {match['team1']} vs {match['team2']}")
                            # Lade gespeichertes Ergebnis
                            saved_score = match.get('score', "-")
                            if saved_score != "-" and ":" in saved_score:
                                try:
                                    goals_team1, goals_team2 = map(int, saved_score.split(":"))
                                except:
                                    goals_team1, goals_team2 = "", ""  # Bei Fehlern keine Tore
                            else:
                                goals_team1, goals_team2 = "", ""  # Kein gespeichertes Ergebnis, also leer

                            with col2:
                                goals1 = st.number_input(f"Tore {match['team1']}", min_value=0, max_value=10, step=1, value=goals_team1 if goals_team1 != "" else None,
                                                        key=f"group_{group}_{idx}_team1", label_visibility="collapsed")
                            with col3:
                                goals2 = st.number_input(f"Tore {match['team2']}", min_value=0, max_value=10, step=1, value=goals_team2 if goals_team2 != "" else None,
                                                        key=f"group_{group}_{idx}_team2", label_visibility="collapsed")
                            match['new_score'] = f"{goals1}:{goals2}"

            else:
                with st.expander("Gruppenspiele (Rot vs. Blau)", expanded=True):
                    for idx, match in enumerate(get_current("matches")):
                        col1, col2, col3 = st.columns([5, 1.5, 1.5])
                        with col1:
                            st.text(f"{match['match_number']}. {match['team1']} vs {match['team2']}")
                        saved_score = match.get('score', "-")
                        if saved_score != "-" and ":" in saved_score:
                            try:
                                goals_team1, goals_team2 = map(int, saved_score.split(":"))
                            except:
                                goals_team1, goals_team2 = "", ""  # Bei Fehlern keine Tore
                        else:
                            goals_team1, goals_team2 = "", ""  # Kein gespeichertes Ergebnis, also leer

                        with col2:
                            goals1 = st.number_input(f"Tore {match['team1']}", min_value=0, max_value=10, step=1, value=goals_team1 if goals_team1 != "" else None,
                                                    key=f"match_{idx}_team1", label_visibility="collapsed")
                        with col3:
                            goals2 = st.number_input(f"Tore {match['team2']}", min_value=0, max_value=10, step=1, value=goals_team2 if goals_team2 != "" else None,
                                                    key=f"match_{idx}_team2", label_visibility="collapsed")
                        match['new_score'] = f"{goals1}:{goals2}"

            # --- Ergebnisse speichern ---
            if st.button("Ergebnisse speichern"):
                if group_mode:
                    for group in ["A", "B"]:
                        for idx, match in enumerate(get_current("group_matches")[group]):
                            match['score'] = match.get('new_score', match['score'])
                else:
                    for idx, match in enumerate(get_current("matches")):
                        match['score'] = match.get('new_score', match['score'])
                save_data(st.session_state.data)
                st.success("Ergebnisse gespeichert!")

            # --- Tabellen anzeigen ---
            def update_stats(teams, matches):
                for team in teams:
                    team.update({
                        "points": 0,
                        "games_played": 0,
                        "wins": 0,
                        "draws": 0,
                        "losses": 0,
                        "goals_for": 0,
                        "goals_against": 0
                    })
                team_lookup = {team["name"]: team for team in teams}
                for match in matches:
                    score = match["score"]
                    if score != "-" and ":" in score:
                        try:
                            s1, s2 = map(int, score.split(":"))
                            t1 = team_lookup.get(match["team1"])
                            t2 = team_lookup.get(match["team2"])
                            if not t1 or not t2:
                                continue
                            t1["games_played"] += 1
                            t2["games_played"] += 1
                            t1["goals_for"] += s1
                            t1["goals_against"] += s2
                            t2["goals_for"] += s2
                            t2["goals_against"] += s1
                            if s1 > s2:
                                t1["points"] += 3
                                t1["wins"] += 1
                                t2["losses"] += 1
                            elif s2 > s1:
                                t2["points"] += 3
                                t2["wins"] += 1
                                t1["losses"] += 1
                            else:
                                t1["points"] += 1
                                t2["points"] += 1
                                t1["draws"] += 1
                                t2["draws"] += 1
                        except:
                            continue

            def render_table(df):
                df["Tordifferenz"] = df["goals_for"] - df["goals_against"]
                df = df.sort_values(by=["points", "Tordifferenz", "goals_for"], ascending=False).reset_index(drop=True)
                df["Rang"] = df.index + 1
                st.dataframe(df[["Rang", "name", "games_played", "wins", "draws", "losses", "goals_for", "goals_against", "points"]]
                             .rename(columns={
                                 "name": "Team", "games_played": "Spiele", "wins": "S", "draws": "U", "losses": "N", 
                                 "goals_for": "Tore", "goals_against": "Gegentore", "points": "Punkte"
                             }),
                             use_container_width=True)

            #st.subheader("Tabelle")
            with st.expander("Tabelle", expanded=True):
                if group_mode:
                    for group in ["A", "B"]:
                        st.subheader(f"Gruppe {group}")
                        group_teams = get_current("groups")[group]
                        group_matches = get_current("group_matches")[group]
                        update_stats(group_teams, group_matches)
                        render_table(pd.DataFrame(group_teams))
                else:
                    update_stats(teams, get_current("matches"))
                    render_table(pd.DataFrame(teams))

elif page == "KO-Runde":
    st.header("KO-Runde")

    with st.expander("Modus KO-Runde anzeigen"):
        st.markdown("""
        **Halbfinale:**  
        - Gespielt werden **20 Bälle**  
        - Je Team jeweils **10 blaue** und **10 rote** Bälle
        
        **Spiel um Platz 3:**  
        - Gespielt werden **10 Bälle**  
        - Je Team jeweils **5 blaue** und **5 rote** Bälle

        **Finale:**  
        - Gespielt werden **20 Bälle**  
        - Je Team jeweils **10 blaue** und **10 rote** Bälle
                    
        **Umgang mit Unentschieden in der KO-Runde**
        - Bei Unentschieden wird auf ein Tor Unterschied gespielt
        - Seitenwechsel erfolgt nicht mehr
        - Nur Damen Spielen Golden Goal aus
        """)

    components.html("""
                    <style>
                        :root {
                            color-scheme: light dark;
                        }

                        .timer-container {
                            font-family: sans-serif;
                            text-align: center;
                            padding: 10px;
                        }

                        .timer-button {
                            font-size: 16px;
                            padding: 6px 12px;
                            border: none;
                            border-radius: 8px;
                            cursor: pointer;
                            background-color: #f44336; /* Helles Rot */
                            color: white;
                            transition: background-color 0.3s;
                        }

                        .timer-button:hover {
                            background-color: #e53935; /* Dunkleres Rot beim Hover */
                        }

                        .timer-display {
                            font-size: 24px;
                            font-weight: bold;
                            margin-top: 10px;
                            color: var(--timer-text-color, #fff);  /* Dynamische Textfarbe */
                        }

                        .progress-bar-background {
                            width: 100%;
                            background-color: rgba(200, 200, 200, 0.2);
                            height: 20px;
                            border-radius: 10px;
                            overflow: hidden;
                            margin-top: 10px;
                        }

                        .progress-bar-fill {
                            height: 100%;
                            width: 100%;
                            background-color: #f44336; /* Helles Rot für den Fortschrittsbalken */
                            transition: width 1s linear;
                        }

                        /* Anpassung für Dark Mode */
                        @media (prefers-color-scheme: dark) {
                            .timer-display {
                                color: #fff; /* Helle Schrift im Dark Mode */
                            }

                            .progress-bar-fill {
                                background-color: #e57373; /* Helles Rot im Dark Mode */
                            }
                        }

                        /* Anpassung für Light Mode */
                        @media (prefers-color-scheme: light) {
                            .timer-display {
                                color: #333; /* Dunkle Schrift im Light Mode */
                            }

                            .progress-bar-fill {
                                background-color: #f44336; /* Helles Rot im Light Mode */
                            }
                        }
                    </style>

                    <div class="timer-container">
                        <button class="timer-button" onclick="startTimer()">Timer starten</button>
                        <div id="timer" class="timer-display">05:00</div>

                        <div class="progress-bar-background">
                            <div id="progress" class="progress-bar-fill"></div>
                        </div>
                    </div>

                    <script>
                        const totalSeconds = 30;
                        let interval;

                        function startTimer() {
                            clearInterval(interval);
                            let timeLeft = totalSeconds;
                            updateDisplay(timeLeft);
                            updateProgress(timeLeft);
                            
                            interval = setInterval(() => {
                                timeLeft--;
                                if (timeLeft >= 0) {
                                    updateDisplay(timeLeft);
                                    updateProgress(timeLeft);
                                } else {
                                    clearInterval(interval);
                                    document.getElementById("timer").textContent = "Zeit abgelaufen!";
                                    document.getElementById("progress").style.width = "0%";
                                    playSound();
                                }
                            }, 1000);
                        }

                        function updateDisplay(seconds) {
                            const m = String(Math.floor(seconds / 60)).padStart(2, '0');
                            const s = String(seconds % 60).padStart(2, '0');
                            document.getElementById("timer").textContent = `${m}:${s}`;
                        }

                        function updateProgress(seconds) {
                            const percent = (seconds / totalSeconds) * 100;
                            document.getElementById("progress").style.width = `${percent}%`;
                        }

                        function playSound() {
                            const ctx = new (window.AudioContext || window.webkitAudioContext)();
                            const oscillator = ctx.createOscillator();
                            oscillator.type = 'sine';
                            oscillator.frequency.setValueAtTime(1000, ctx.currentTime);
                            oscillator.connect(ctx.destination);
                            oscillator.start();
                            oscillator.stop(ctx.currentTime + 1.5);
                        }
                    </script>
                """, height=170)
    
    teams = get_current("teams")

    if len(teams) < 4:
        st.error("Mindestens 4 Teams erforderlich.")
        st.stop()

    # Initialisiere KO-Runde
    if not get_current("ko_round") and st.button("KO-Runde generieren"):
        df = pd.DataFrame(teams)
        ko_round = []

        if get_current("group_phase"):
            group_stats = {
                g: pd.DataFrame(get_current("groups")[g])
                      .assign(Tordifferenz=lambda x: x["goals_for"] - x["goals_against"])
                      .sort_values(by=["points", "Tordifferenz", "goals_for"], ascending=False)
                      .head(2)
                for g in ["A", "B"]
            }
            ko_round = [
                {"round": "Halbfinale 1", "team1": group_stats["A"].iloc[0]["name"], "team2": group_stats["B"].iloc[1]["name"], "score": "-"},
                {"round": "Halbfinale 2", "team1": group_stats["B"].iloc[0]["name"], "team2": group_stats["A"].iloc[1]["name"], "score": "-"}
            ]
        else:
            top4 = df.sort_values(by=["points", "goals_for"], ascending=False).head(4)
            ko_round = [
                {"round": "Halbfinale 1", "team1": top4.iloc[0]["name"], "team2": top4.iloc[3]["name"], "score": "-"},
                {"round": "Halbfinale 2", "team1": top4.iloc[1]["name"], "team2": top4.iloc[2]["name"], "score": "-"}
            ]

        set_current("ko_round", ko_round)
        save_data(st.session_state.data)
        st.success("KO-Runde erstellt!")

    # KO-Spiele anzeigen
    ko_round_data = get_current("ko_round")
    if ko_round_data:
        new_scores = []

        st.subheader("Halbfinale")
        for idx, match in enumerate(ko_round_data[:2]):
            st.markdown(f"**{match['round']}**: {match['team1']} vs {match['team2']}")

            saved_score = match.get("score", "-")
            if saved_score != "-" and ":" in saved_score:
                try:
                    g1, g2 = map(int, saved_score.split(":"))
                except:
                    g1, g2 = 0, 0
            else:
                g1, g2 = 0, 0

            col1, col2 = st.columns(2)
            with col1:
                goals1 = st.number_input(f"Tore {match['team1']}", min_value=0, max_value=20, value=g1, key=f"hf_{idx}_1")
            with col2:
                goals2 = st.number_input(f"Tore {match['team2']}", min_value=0, max_value=20, value=g2, key=f"hf_{idx}_2")

            new_scores.append((idx, goals1, goals2))

        if st.button("Halbfinal-Ergebnisse speichern"):
            winners, losers = [], []
            for idx, g1, g2 in new_scores:
                ko_round_data[idx]["score"] = f"{g1}:{g2}"
                if g1 > g2:
                    winners.append(ko_round_data[idx]["team1"])
                    losers.append(ko_round_data[idx]["team2"])
                elif g2 > g1:
                    winners.append(ko_round_data[idx]["team2"])
                    losers.append(ko_round_data[idx]["team1"])
                else:
                    winners.append("n/a")
                    losers.append("n/a")

            # Finale & Spiel um Platz 3 hinzufügen, falls noch nicht vorhanden
            if len(ko_round_data) < 4 and "n/a" not in winners:
                ko_round_data.append({
                    "round": "Spiel um Platz 3",
                    "team1": losers[0],
                    "team2": losers[1],
                    "score": "-"
                })
                ko_round_data.append({
                    "round": "Finale",
                    "team1": winners[0],
                    "team2": winners[1],
                    "score": "-"
                })
            set_current("ko_round", ko_round_data)
            save_data(st.session_state.data)
            st.success("Ergebnisse gespeichert und nächste Runde erstellt!")

        # Zeige Finale und Spiel um Platz 3, wenn vorhanden
        if len(ko_round_data) >= 4:
            st.subheader("Finalrunde")
            for idx, match in enumerate(ko_round_data[2:], start=2):
                st.markdown(f"**{match['round']}**: {match['team1']} vs {match['team2']}")
                saved_score = match.get("score", "-")
                if saved_score != "-" and ":" in saved_score:
                    try:
                        g1, g2 = map(int, saved_score.split(":"))
                    except:
                        g1, g2 = 0, 0
                else:
                    g1, g2 = 0, 0

                col1, col2 = st.columns(2)
                with col1:
                    goals1 = st.number_input(f"Tore {match['team1']}", min_value=0, max_value=20, value=g1, key=f"final_{idx}_1")
                with col2:
                    goals2 = st.number_input(f"Tore {match['team2']}", min_value=0, max_value=20, value=g2, key=f"final_{idx}_2")

                ko_round_data[idx]["score"] = f"{goals1}:{goals2}"

            if st.button("Finalrunde speichern"):
                set_current("ko_round", ko_round_data)
                save_data(st.session_state.data)
                st.success("Finalrunden-Ergebnisse gespeichert!")












