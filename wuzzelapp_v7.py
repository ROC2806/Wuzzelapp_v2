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

# --- Helper Functions ---
def get_current(key):
    return st.session_state.data["tournaments"][st.session_state.data["current_tournament"]][key]

def set_current(key, value):
    st.session_state.data["tournaments"][st.session_state.data["current_tournament"]][key] = value

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

    def is_played(score):
        return score not in ["None:None", "-", None]

    # Beispiel: Daten holen (müsstest du an deine Datenquelle anpassen)
    group_matches = get_current("group_matches")  # dict mit Gruppen -> Liste Spiele
    ko_matches = get_current("ko_round")     # Liste KO-Spiele

    # Berechnung Gruppenphase Fortschritt
    played_group = 0
    total_group = 0
    for group, matches in group_matches.items():
        for match in matches:
            total_group += 1
            if is_played(match.get("score", "-")):
                played_group += 1

    progress_group = int((played_group / total_group) * 100) if total_group > 0 else 0

    # Berechnung KO-Runde Fortschritt
    played_ko = 0
    for ko_match in ko_matches:
        if is_played(ko_match.get("score", "-")):
            played_ko += 1
    #played_ko = sum(1 for m in ko_matches if is_played(m.get("score", "-")))
    #total_ko = len(ko_matches)
    total_ko = 4
    progress_ko = int((played_ko / total_ko) * 100) if total_ko > 0 else 0

    st.markdown("---")

    st.subheader("Gruppenphase")
    st.progress(progress_group)
    st.markdown(f"          {played_group} / {total_group} Spiele gespielt")

    st.subheader("KO-Runde")
    st.progress(progress_ko)
    st.markdown(f"          {played_ko} / {total_ko} Spiele gespielt")


if page in ["Teams", "Spielplan", "Gruppenphase", "KO-Runde"]:
    tournament_name = st.session_state.data.get("current_tournament", "Kein Turnier ausgewählt")
    st.title(tournament_name)
else:
    st.title("Wuzzel Turnier")

# --- Team Datenbank ---
if page == "Team Datenbank":
    st.header("Team Datenbank")

    db_config = st.secrets["mysql"]
    engine = f"mysql+mysqlconnector://{db_config['user']}:{db_config['password']}@{db_config['host']}/{db_config['database']}"
    query = "SELECT name, player_1, player_2, timestamp FROM teams"
    teams = pd.read_sql(query, engine)

    st.dataframe(teams)

# --- Turnierverwaltung ---
if page == "Turnierverwaltung":
    st.header("Turnierverwaltung")

    # Turnier erstellen
    with st.form("create_tournament"):
        name = st.text_input("Name des Turniers")
        date = st.date_input("Datum des Turniers")
        num_groups = st.selectbox("Anzahl der Gruppen in der Gruppenphase", options=[1, 2, 4], index=1)
        submitted = st.form_submit_button("Neues Turnier erstellen")
        if submitted and name:
            # Initialisiere Gruppen-Dict dynamisch nach Auswahl
            groups = {}
            group_names = ["A", "B", "C", "D"]
            for i in range(num_groups):
                groups[group_names[i]] = []

            st.session_state.data["tournaments"][name] = {
                "date": str(date),
                "players": [],
                "teams": [],
                "matches": [],
                "ko_round": [],
                "group_phase": True if num_groups > 0 else False,
                "num_groups": num_groups,
                "groups": groups,
                "group_matches": {k: [] for k in groups.keys()},
                "schedule_created": False   
            }
            st.session_state.data["current_tournament"] = name
            save_data(st.session_state.data)
            st.success(f"Turnier '{name}' erstellt und ausgewählt.")

    # Turnier auswählen
    with st.expander("Turnier laden"):
        #st.subheader("Existierende Turniere")
        if st.session_state.data["tournaments"]:
            selected = st.selectbox("Turnier auswählen", list(st.session_state.data["tournaments"].keys()))
            if st.button("Turnier laden"):
                st.session_state.data["current_tournament"] = selected
                save_data(st.session_state.data)
                st.success(f"Turnier '{selected}' geladen.")
                st.rerun()
        else:
            st.info("Noch keine Turniere vorhanden.")

    # Teams aus Datenbank übernehmen
    with st.expander("Teams laden"):
        if st.session_state.data.get("current_tournament"):
            st.subheader("Teams aus Datenbank übernehmen")

            engine = create_engine("mysql+mysqlconnector://d0437c1d:uguWe3RnmzqfaKRHmswU@kicker.kernlos.at/d0437c1d")
            query = "SELECT id, name, player_1, player_2 FROM teams"
            teams_db = pd.read_sql(query, engine)

            if get_current("schedule_created"):
                st.warning("Der Spielplan wurde bereits erstellt. Es können keine Teams mehr hinzugefügt werden.")
            else:
                selected_teams = st.multiselect(
                    "Wähle Teams aus der Datenbank aus:",
                    teams_db["name"].tolist()
                )

                if st.button("Teams übernehmen"):
                    teams = get_current("teams") or []
                    for team_name in selected_teams:
                        team_row = teams_db[teams_db["name"] == team_name].iloc[0]
                        team = {
                            "name": team_row["name"],
                            "players": [team_row["player_1"], team_row["player_2"]],
                            "player_ids": [str(uuid.uuid4()), str(uuid.uuid4())],
                            "points": 0,
                            "games_played": 0,
                            "wins": 0,
                            "draws": 0,
                            "losses": 0,
                            "goals_for": 0,
                            "goals_against": 0
                        }
                        teams.append(team)
                    set_current("teams", teams)
                    save_data(st.session_state.data)
                    st.success(f"{len(selected_teams)} Teams übernommen.")

    def berechne_turnierzeit_und_spiele(anzahl_gruppen, anzahl_mannschaften, spielzeit_gruppenphase, spielzeit_kophase):
        # Anzahl Spiele pro Gruppe (Jeder gegen jeden): n*(n-1)/2
        gesamt_spiele_gruppenphase = anzahl_mannschaften * (anzahl_mannschaften - 1) / 2 * anzahl_gruppen
        # Anzahl KO-Spiele (z.B. Halbfinale (2), Spiel um Platz 3 (1), Finale (1) = 4 Spiele insgesamt)
        spiele_kophase = 4
        
        gesamt_spiele = gesamt_spiele_gruppenphase + spiele_kophase
        
        gesamtzeit_minuten = gesamt_spiele_gruppenphase * spielzeit_gruppenphase + spiele_kophase * spielzeit_kophase
        return gesamtzeit_minuten, gesamt_spiele

    with st.expander("Turnierzeit Rechner"):
        anzahl_gruppen = st.number_input("Anzahl Gruppen", min_value=1, step=1, value=2)
        anzahl_mannschaften = st.number_input("Anzahl Mannschaften", min_value=2, step=1, value=4)
        spielzeit_gruppenphase = st.number_input("Spielzeit Gruppenphase (Minuten)", min_value=1, step=1, value=8)
        spielzeit_kophase = st.number_input("Spielzeit KO-Phase (Minuten)", min_value=1, step=1, value=14)

        if st.button("Turnierzeit berechnen"):
            gesamtzeit_minuten, gesamt_spiele = berechne_turnierzeit_und_spiele(anzahl_gruppen, anzahl_mannschaften, spielzeit_gruppenphase, spielzeit_kophase)
            gesamtzeit_stunden = gesamtzeit_minuten / 60
            st.success(f"Ungefähre Spielzeit: {gesamtzeit_stunden:.2f} Stunden")
            st.info(f"Gesamtanzahl der Spiele: {int(gesamt_spiele)}")

# --- Teams ---
elif page == "Teams":
    st.header("Bestehende Teams & Gruppenzuordnung")

    teams = get_current("teams") or []
    num_groups = get_current("num_groups") or 1
    groups = get_current("groups") or {}

    if not teams:
        st.info("Es wurden noch keine Teams erstellt.")
    else:
        with st.expander("Gruppenzuordnung"):
            # Gruppenzuordnung ermöglichen
            #st.subheader("Gruppenzuordnung der Teams")
            group_names = list(groups.keys())

            # Erstelle ein Mapping von Teamname zu Gruppe (zum Vorbefüllen)
            team_to_group = {}
            for g, t_list in groups.items():
                for t in t_list:
                    team_to_group[t["name"]] = g

            # Auswahl für jedes Team in welchem Gruppe
            new_groups = {g: [] for g in group_names}

            for team in teams:
                default_group = team_to_group.get(team["name"], group_names[0])
                chosen_group = st.selectbox(f"Gruppe für Team '{team['name']}'", options=group_names, index=group_names.index(default_group))
                new_groups[chosen_group].append(team)

        # Wenn Gruppe geändert, abspeichern
        if st.button("Gruppenzuordnung speichern"):
            set_current("groups", new_groups)
            save_data(st.session_state.data)
            st.success("Gruppenzuordnung gespeichert.")

        with st.expander("Übersicht"):
            # Liste der Teams anzeigen
            st.subheader("Teams Übersicht")
            for g in group_names:
                st.markdown(f"### Gruppe {g}")
                if new_groups[g]:
                    for t in new_groups[g]:
                        st.markdown(f"- **{t['name']}** ({t['players'][0]} & {t['players'][1]})")
                else:
                    st.markdown("_Keine Teams in dieser Gruppe_")

# --- Gruppenphase ---
elif page == "Gruppenphase":
    st.subheader("Gruppenphase")
    st.subheader("Timer")
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
                            background-color: #f44336;
                            color: white;
                            transition: background-color 0.3s;
                        }

                        .timer-button:hover {
                            background-color: #e53935;
                        }

                        .timer-display {
                            font-size: 24px;
                            font-weight: bold;
                            margin-top: 10px;
                            color: var(--timer-text-color, #fff);
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
                            background-color: #f44336;
                            transition: width 1s linear;
                        }

                        @media (prefers-color-scheme: dark) {
                            .timer-display {
                                color: #fff;
                            }

                            .progress-bar-fill {
                                background-color: #e57373;
                            }
                        }

                        @media (prefers-color-scheme: light) {
                            .timer-display {
                                color: #333;
                            }

                            .progress-bar-fill {
                                background-color: #f44336;
                            }
                        }
                    </style>

                    <div class="timer-container">
                        <button class="timer-button" onclick="startTimer()">Timer starten</button>
                        <div id="timer" class="timer-display">04:00</div>

                        <div class="progress-bar-background">
                            <div id="progress" class="progress-bar-fill"></div>
                        </div>
                    </div>

                    <script>
                        const totalSeconds = 240;
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
    
    teams = get_current("teams") or []
    groups = get_current("groups") or {}
    group_matches = get_current("group_matches") or {}
    schedule_created = get_current("schedule_created")
    num_groups = get_current("num_groups") or 1

    if len(teams) < 4:
        st.error("Mindestens 4 Teams erforderlich.")
    else:
        # Spielplan erstellen
        if not schedule_created:
            if st.button("Spielplan erstellen"):

                # Erstelle Spiele für jede Gruppe
                new_group_matches = {g: [] for g in groups.keys()}
                match_number = 1

                for g, t_list in groups.items():
                    # Für jede Gruppe alle Spiele aller Teams (jeder gegen jeden, 1x)
                    for i in range(len(t_list)):
                        for j in range(i + 1, len(t_list)):
                            t1 = t_list[i]["name"]
                            t2 = t_list[j]["name"]
                            new_group_matches[g].append({
                                "match_number": match_number,
                                "team1": t1,
                                "team2": t2,
                                "score": "-",
                                "color": "Rot vs Blau"
                            })
                            match_number += 1

                set_current("group_matches", new_group_matches)
                set_current("schedule_created", True)
                save_data(st.session_state.data)
                st.success("Spielplan wurde erfolgreich erstellt!")

        else:
            # Ergebnisse eingeben
            with st.expander("Gruppenspiele", expanded=True):
                for g in groups.keys():
                    st.subheader(f"Gruppe {g}")
                    matches = group_matches.get(g, [])
                    for idx, match in enumerate(matches):
                        col1, col2, col3 = st.columns([5, 1.5, 1.5])
                        with col1:
                            st.text(f"{match['match_number']}. {match['team1']} vs {match['team2']}")

                        saved_score = match.get('score', "-")
                        if saved_score != "-" and ":" in saved_score:
                            try:
                                goals_team1, goals_team2 = map(int, saved_score.split(":"))
                            except:
                                goals_team1, goals_team2 = "", ""
                        else:
                            goals_team1, goals_team2 = "", ""

                        with col2:
                            goals1 = st.number_input(f"Tore {match['team1']}", min_value=0, step=1,
                                                    value=goals_team1 if goals_team1 != "" else None,
                                                    key=f"group_{g}_{idx}_team1", label_visibility="collapsed")
                        with col3:
                            goals2 = st.number_input(f"Tore {match['team2']}", min_value=0, step=1,
                                                    value=goals_team2 if goals_team2 != "" else None,
                                                    key=f"group_{g}_{idx}_team2", label_visibility="collapsed")

                        match['new_score'] = f"{goals1}:{goals2}"

            # Ergebnisse speichern
            if st.button("Ergebnisse speichern"):
                for g in groups.keys():
                    matches = group_matches.get(g, [])
                    for match in matches:
                        match['score'] = match.get('new_score', match['score'])
                save_data(st.session_state.data)
                st.success("Ergebnisse gespeichert!")
                st.rerun()

            # Tabellen anzeigen
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

            with st.expander("Tabellen", expanded=True):
                for g in groups.keys():
                    st.subheader(f"Gruppe {g}")
                    group_teams = groups[g]
                    matches = group_matches.get(g, [])
                    update_stats(group_teams, matches)
                    render_table(pd.DataFrame(group_teams))


elif page == "KO-Runde":
    st.header("KO-Runde")

    st.subheader("Timer")
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
                        <div id="timer" class="timer-display">07:00</div>

                        <div class="progress-bar-background">
                            <div id="progress" class="progress-bar-fill"></div>
                        </div>
                    </div>

                    <script>
                        const totalSeconds = 420;
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

    # KO-Runde initialisieren
    if not get_current("ko_round") and st.button("KO-Runde generieren"):
        df = pd.DataFrame(teams)
        ko_round = []

        if get_current("group_phase"):
            groups = get_current("groups")
            group_names = list(groups.keys())

            group_stats = {
                g: pd.DataFrame(groups[g])
                    .assign(Tordifferenz=lambda x: x["goals_for"] - x["goals_against"])
                    .sort_values(by=["points", "Tordifferenz", "goals_for"], ascending=False)
                for g in group_names
            }

            if len(group_names) == 1:
                top4 = group_stats[group_names[0]].head(4)
                ko_round = [
                    {"round": "Halbfinale 1", "team1": top4.iloc[0]["name"], "team2": top4.iloc[3]["name"], "score": "-"},
                    {"round": "Halbfinale 2", "team1": top4.iloc[1]["name"], "team2": top4.iloc[2]["name"], "score": "-"}
                ]
            elif len(group_names) == 2:
                gA, gB = group_names[0], group_names[1]
                ko_round = [
                    {"round": "Halbfinale 1", "team1": group_stats[gA].iloc[0]["name"], "team2": group_stats[gB].iloc[1]["name"], "score": "-"},
                    {"round": "Halbfinale 2", "team1": group_stats[gB].iloc[0]["name"], "team2": group_stats[gA].iloc[1]["name"], "score": "-"}
                ]
            elif len(group_names) == 4:
                top4 = [group_stats[g].iloc[0]["name"] for g in group_names]
                ko_round = [
                    {"round": "Halbfinale 1", "team1": top4[0], "team2": top4[3], "score": "-"},
                    {"round": "Halbfinale 2", "team1": top4[1], "team2": top4[2], "score": "-"}
                ]
            else:
                st.error("Der Modus für diese Anzahl an Gruppen ist nicht definiert.")
                st.stop()
        else:
            top4 = df.sort_values(by=["points", "goals_for"], ascending=False).head(4)
            ko_round = [
                {"round": "Halbfinale 1", "team1": top4.iloc[0]["name"], "team2": top4.iloc[3]["name"], "score": "-"},
                {"round": "Halbfinale 2", "team1": top4.iloc[1]["name"], "team2": top4.iloc[2]["name"], "score": "-"}
            ]

        set_current("ko_round", ko_round)
        save_data(st.session_state.data)
        st.success("KO-Runde erstellt!")
        st.rerun()

    # KO-Spiele anzeigen und Ergebnisse erfassen
    ko_round_data = get_current("ko_round")
    if ko_round_data:
        new_scores = []

        st.subheader("Halbfinale")
        for idx, match in enumerate(ko_round_data[:2]):
            st.markdown(f"**{match['round']}**: {match['team1']} vs {match['team2']}")
            saved_score = match.get("score", "-")

            if saved_score != "-" and ":" in saved_score:
                try:
                    g1, g2 = map(int, saved_score.split(":")) if ":" in saved_score else (0, 0)
                except:
                    g1, g2 = "", ""
            else:
                g1, g2 = "", ""

            col1, col2 = st.columns(2)
            with col1:
                goals1 = st.number_input(f"Tore {match['team1']}", min_value=0, value=g1 if g1 != "" else None, key=f"hf_{idx}_1")
            with col2:
                goals2 = st.number_input(f"Tore {match['team2']}", min_value=0, value=g2 if g2 != "" else None, key=f"hf_{idx}_2")

            new_scores.append((idx, goals1, goals2))

        if st.button("Halbfinalrunde speichern"):
            winners, losers = [], []
            valid_games = 0
            for idx, g1, g2 in new_scores:
                if g1 is None or g2 is None:
                    all_scores_valid = False
                    ko_round_data[idx]["score"] = "-"
                    winners.append("n/a")
                    losers.append("n/a")
                    continue
                
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

                valid_games += 1

                if valid_games == 2 and len(ko_round_data) < 4 and "n/a" not in winners:
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
            st.rerun()

        # Finale und Spiel um Platz 3 anzeigen
        if len(ko_round_data) >= 4:
            st.subheader("Finalrunde")
            final_scores = []
            for idx, match in enumerate(ko_round_data[2:], start=2):
                st.markdown(f"**{match['round']}**: {match['team1']} vs {match['team2']}")
                saved_score = match.get("score", "-")
                
                if saved_score != "-" and ":" in saved_score:
                    try:
                        g1, g2 = map(int, saved_score.split(":")) if ":" in saved_score else (0, 0)
                    except:
                        g1, g2 = "", ""
                else: 
                    g1, g2 = "", ""

                col1, col2 = st.columns(2)
                with col1:
                    goals1 = st.number_input(f"Tore {match['team1']}", min_value=0, value=g1 if g1 != "" else None, key=f"final_{idx}_1")
                with col2:
                    goals2 = st.number_input(f"Tore {match['team2']}", min_value=0, value=g2 if g1 != "" else None, key=f"final_{idx}_2")

                final_scores.append((idx, goals1, goals2))
                #ko_round_data[idx]["score"] = f"{goals1}:{goals2}"

            if st.button("Finalrunde speichern"):
                for idx, g1, g2 in final_scores:
                    ko_round_data[idx]["score"] = f"{g1}:{g2}"
                set_current("ko_round", ko_round_data)
                save_data(st.session_state.data)
                st.success("Finalrunden-Ergebnisse gespeichert!")
                st.rerun()
