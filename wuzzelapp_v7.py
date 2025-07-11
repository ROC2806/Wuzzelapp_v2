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
        #st.subheader("Aktuelles Turnier")
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
    #played_ko = 0
    #for ko_match in ko_matches:
        #if is_played(ko_match.get("score", "-")):
            #played_ko += 1
    #played_ko = sum(1 for m in ko_matches if is_played(m.get("score", "-")))
    #total_ko = len(ko_matches)
    #total_ko = 4
    #progress_ko = int((played_ko / total_ko) * 100) if total_ko > 0 else 0

    #st.markdown("---")

    st.markdown("Gruppenphase")
    st.progress(progress_group)
    st.markdown(f"          {played_group} / {total_group} Spiele gespielt")

    if ko_matches:
        played_ko = sum(1 for m in ko_matches if is_played(m.get("score", "-")))

        # Prüfe, ob Viertelfinale gespielt wird
        has_quarters = any("Viertelfinale" in m["round"] for m in ko_matches)

        if has_quarters:
            total_ko = 8  # 4 Viertelfinale + 2 Halbfinale + Finale + Spiel um Platz 3
        else:
            total_ko = 4  # 2 Halbfinale + Finale + Spiel um Platz 3

        progress_ko = int((played_ko / total_ko) * 100) if total_ko > 0 else 0

        st.markdown("KO-Runde")
        st.progress(progress_ko)
        st.markdown(f"          {played_ko} / {total_ko} Spiele gespielt")


if page in ["Teams", "Spielplan", "Gruppenphase", "KO-Runde"]:
    tournament_name = st.session_state.data.get("current_tournament", "Kein Turnier ausgewählt")
    #st.title(tournament_name)
    #st.image("logo.png", width=200)
    col1, col2 = st.columns([6, 1])
    with col1:
        st.title(tournament_name)
    with col2:
        st.image("logo.png", width=200)
else:
    #st.title("Wuzzel Turnier")
    col1, col2 = st.columns([6, 1])
    with col1:
        st.title("Wuzzel Turnier")
    with col2:
        st.image("logo.png", width=200)

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
                    
    with st.expander("Turnier Spielregeln"):
        st.markdown("""
            **Spielmodus:**  
            - 2 gegen 2  
            - Gruppenphase (jeder gegen jeden in der Gruppe) und KO-Phase (Viertelfinale, Halbfinale, Finale)
            - Es gibt 4 Gruppen, die vor Turnierbeginn ausgelost werden
            - Die jeweils besten zwei Teams jeder Gruppe steigen in die KO-Phase auf
            
            **Spielzeit:**  
            - Gruppenphase: 2 Halbzeiten à 4 Minuten  
            - KO-Phase: 2 Halbzeiten à 7 Minuten
            
            **Punktevergabe in Gruppenphase:**  
            - Sieg: 3 Punkte  
            - Unentschieden: 1 Punkt
            
            **Anstoß, Ballbesitz und Mitte:**
            - Team 1 ist im Spielplan die blaue Mannschaft
            - Anstoß zu Spielbeginn und zur zweiten Halbzeit hat Team Blau
            - Nach einem Tor: Gegner erhält den Ball   
            - Ball im Aus: Jeweilige Verteidigung erhält den Ball
            - Mitte zählt, aber nicht beim Anstoß 
            
            **Unentschieden in KO-Phase:**  
            - Bei Gleichstand entscheidet ein Golden Goal (Einwurf von Blau)
            """)
    def berechne_turnierzeit_und_spiele(anzahl_gruppen, anzahl_mannschaften, spielzeit_gruppenphase, spielzeit_kophase, viertelfinale):
        # Spiele pro Gruppe (Jeder gegen jeden)
        gesamt_spiele_gruppenphase = anzahl_mannschaften * (anzahl_mannschaften - 1) / 2 * anzahl_gruppen

        # KO-Spiele
        if viertelfinale:
            spiele_kophase = 8  # 4 Viertelfinale, 2 Halbfinale, Spiel um Platz 3, Finale
        else:
            spiele_kophase = 4  # 2 Halbfinale, Spiel um Platz 3, Finale

        gesamt_spiele = gesamt_spiele_gruppenphase + spiele_kophase
        gesamtzeit_minuten = gesamt_spiele_gruppenphase * spielzeit_gruppenphase + spiele_kophase * spielzeit_kophase

        return gesamtzeit_minuten, gesamt_spiele


    with st.expander("Turnierzeit Rechner"):
        anzahl_gruppen = st.number_input("Anzahl Gruppen", min_value=1, step=1, value=2)
        anzahl_mannschaften = st.number_input("Anzahl Mannschaften pro Gruppe", min_value=2, step=1, value=4)
        spielzeit_gruppenphase = st.number_input("Spielzeit Gruppenphase (Minuten)", min_value=1, step=1, value=8)
        spielzeit_kophase = st.number_input("Spielzeit KO-Phase (Minuten)", min_value=1, step=1, value=14)
        viertelfinale = st.radio("Mit Viertelfinale spielen?", ["Ja", "Nein"]) == "Ja"

        if st.button("Turnierzeit berechnen"):
            gesamtzeit_minuten, gesamt_spiele = berechne_turnierzeit_und_spiele(
                anzahl_gruppen,
                anzahl_mannschaften,
                spielzeit_gruppenphase,
                spielzeit_kophase,
                viertelfinale
            )
            gesamtzeit_stunden = gesamtzeit_minuten / 60
            st.success(f"Ungefähre Spielzeit: {gesamtzeit_stunden:.2f} Stunden")
            st.info(f"Gesamtanzahl der Spiele: {int(gesamt_spiele)}")

# --- Teams ---
elif page == "Teams":
    st.header("Teams")
 
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

            # Platzhalter für „keine Gruppe“
            selectbox_options = ["– Bitte auswählen –"] + group_names

            # Erstelle ein Mapping von Teamname zu Gruppe (zum Vorbefüllen)
            team_to_group = {}
            for g, t_list in groups.items():
                for t in t_list:
                    team_to_group[t["name"]] = g

            # Auswahl für jedes Team in welchem Gruppe
            new_groups = {g: [] for g in group_names}

            for team in teams:
                # default_group = team_to_group.get(team["name"], group_names[0])
                default_group = team_to_group.get(team["name"], "– Bitte auswählen –")
                #chosen_group = st.selectbox(f"Gruppe für Team '{team['name']}'", options=group_names, index=group_names.index(default_group))
                #new_groups[chosen_group].append(team)
                
                chosen_group = st.selectbox(
                    f"Gruppe für Team '{team['name']}'",
                    options=selectbox_options,
                    index=selectbox_options.index(default_group),
                    key=f"group_select_{team['name']}"
                )

                if chosen_group != "– Bitte auswählen –":
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
    st.header("Gruppenphase")
    #st.subheader("Timer")
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
        margin: 0 4px;
    }

    .timer-button:hover {
        background-color: #e53935;
    }

    .timer-display {
        font-size: 44px;
        font-weight: bold;
        margin-top: 10px;
    }

    .progress-bar-background {
        width: 100%;
        background-color: rgba(200, 200, 200, 0.2);
        height: 30px;
        border-radius: 15px;
        overflow: hidden;
        margin-top: 10px;
    }

    .progress-bar-fill {
        height: 100%;
        width: 100%;
        background-color: #f44336;
        transition: width 1s linear;
    }

    .time-input {
        margin-top: 10px;
    }

    .time-input label {
        font-size: 16px;
        margin-right: 8px;
    }

    input[type="range"] {
        width: 60%;
    }
</style>

<div class="timer-container">
    <div class="time-input">
        <span id="minutesDisplay">4</span>
        <input id="timeRange" type="range" min="1" max="10" value="4" />
    </div>

    <button class="timer-button" onclick="startTimer()">Start</button>
    <button class="timer-button" onclick="pauseTimer()">Pause</button>
    <button class="timer-button" onclick="resetTimer()">Reset</button>

    <div id="timer" class="timer-display">04:00</div>

    <div class="progress-bar-background">
        <div id="progress" class="progress-bar-fill"></div>
    </div>
</div>

<script>
    let totalSeconds = 240;
    let timeLeft = totalSeconds;
    let interval;
    let isPaused = false;

    const timeRange = document.getElementById('timeRange');
    const minutesDisplay = document.getElementById('minutesDisplay');

    // Update total time when slider changes
    timeRange.addEventListener('input', () => {
        const minutes = parseInt(timeRange.value, 10);
        minutesDisplay.textContent = minutes;
        totalSeconds = minutes * 60;
        resetTimer();
    });

    function startTimer() {
        if (interval || timeLeft <= 0) return;

        playSound();

        interval = setInterval(() => {
            if (!isPaused && timeLeft > 0) {
                timeLeft--;
                updateDisplay(timeLeft);
                updateProgress(timeLeft);
                if (timeLeft === 0) {
                    clearInterval(interval);
                    interval = null;
                    document.getElementById("timer").textContent = "Zeit abgelaufen!";
                    document.getElementById("progress").style.width = "0%";
                    playSound();
                }
            }
        }, 1000);
    }

    function pauseTimer() {
        isPaused = !isPaused;
    }

    function resetTimer() {
        clearInterval(interval);
        interval = null;
        timeLeft = totalSeconds;
        isPaused = false;
        updateDisplay(timeLeft);
        updateProgress(timeLeft);
    }

    function updateDisplay(seconds) {
        const m = String(Math.floor(seconds / 60)).padStart(2, '0');
        const s = String(seconds % 60).padStart(2, '0');
        document.getElementById("timer").textContent = m + ":" + s;
    }

    function updateProgress(seconds) {
        const percent = (seconds / totalSeconds) * 100;
        document.getElementById("progress").style.width = percent + "%";
    }

    function playSound() {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = ctx.createOscillator();
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(1000, ctx.currentTime);
        oscillator.connect(ctx.destination);
        oscillator.start();
        oscillator.stop(ctx.currentTime + 3);
    }

    // Initial
    updateDisplay(timeLeft);
    updateProgress(timeLeft);
</script>
    """, height=200)

    
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
            def zebra_stripes(row):
                return [
                    'background-color: #f9f9f9' if row.name % 2 == 0 else ''
                    for _ in row
                ]

            def render_table(df):
                # Neue Spalte berechnen
                df["Tordifferenz"] = df["goals_for"] - df["goals_against"]
                df = df.sort_values(by=["points", "Tordifferenz", "goals_for"], ascending=False).reset_index(drop=True)
                df["Rang"] = df.index + 1

                df_display = df[[
                    "Rang", "name", "games_played", "wins", "draws", "losses",
                    "goals_for", "goals_against", "points"
                ]].copy()

                df_display = df_display.rename(columns={
                    "name": "Team",
                    "games_played": "Spiele",
                    "wins": "S",
                    "draws": "U",
                    "losses": "N",
                    "goals_for": "TF",
                    "goals_against": "TG",
                    "points": "Punkte"
                })

                styled_df = (
                    df_display.style
                    .apply(zebra_stripes, axis=1)
                    #.highlight_max(subset=["Punkte"], color="lightgreen")
                    #.background_gradient(subset=["Punkte"], cmap="Greens")  # Farbverlauf für Punkte
                    .hide(axis="index")
                    .set_table_styles([
                        {'selector': 'thead th',
                        'props': [
                            ('background-color', '#FF4B4B'),
                            ('color', 'white'),
                            ('font-weight', 'bold'),
                            ('text-align', 'center')
                        ]},
                        {'selector': 'tbody td',
                        'props': [
                            ('text-align', 'center'),
                            ('font-family', 'Arial, sans-serif')
                        ]},
                        {'selector': '',
                        'props': [
                            ('border-collapse', 'collapse'),
                            ('border-radius', '10px'),
                            ('overflow', 'hidden')
                        ]},
                         {'selector': 'tbody td:nth-child(2), thead th:nth-child(2)',
                            'props': [
                                ('width', '200px'),
                                ('min-width', '200px'),
                                ('max-width', '200px'),
                                ('text-align', 'left')  # Team linksbündig, falls gewünscht
                            ]}
                    ])
                )

                st.markdown(
                    styled_df.to_html(),
                    unsafe_allow_html=True
                )

                #st.dataframe(styled_df, use_container_width=True)

            with st.expander("Tabellen", expanded=True):
                for g in groups.keys():
                    st.subheader(f"Gruppe {g}")
                    group_teams = groups[g]
                    matches = group_matches.get(g, [])
                    update_stats(group_teams, matches)
                    render_table(pd.DataFrame(group_teams))

# --- KO Phase ---
elif page == "KO-Runde":
    st.header("KO-Runde")

    # ===========================
    # TIMER (dein Original bleibt!)
    # ===========================
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
        margin: 0 4px;
    }

    .timer-button:hover {
        background-color: #e53935;
    }

    .timer-display {
        font-size: 44px;
        font-weight: bold;
        margin-top: 10px;
    }

    .progress-bar-background {
        width: 100%;
        background-color: rgba(200, 200, 200, 0.2);
        height: 30px;
        border-radius: 15px;
        overflow: hidden;
        margin-top: 10px;
    }

    .progress-bar-fill {
        height: 100%;
        width: 100%;
        background-color: #f44336;
        transition: width 1s linear;
    }

    .time-input {
        margin-top: 10px;
    }

    .time-input label {
        font-size: 16px;
        margin-right: 8px;
    }

    input[type="range"] {
        width: 60%;
    }
</style>

<div class="timer-container">
    <div class="time-input">
        <span id="minutesDisplay">7</span>
        <input id="timeRange" type="range" min="1" max="10" value="7" />
    </div>

    <button class="timer-button" onclick="startTimer()">Start</button>
    <button class="timer-button" onclick="pauseTimer()">Pause</button>
    <button class="timer-button" onclick="resetTimer()">Reset</button>

    <div id="timer" class="timer-display">07:00</div>

    <div class="progress-bar-background">
        <div id="progress" class="progress-bar-fill"></div>
    </div>
</div>

<script>
    let totalSeconds = 420;
    let timeLeft = totalSeconds;
    let interval;
    let isPaused = false;

    const timeRange = document.getElementById('timeRange');
    const minutesDisplay = document.getElementById('minutesDisplay');

    // Update total time when slider changes
    timeRange.addEventListener('input', () => {
        const minutes = parseInt(timeRange.value, 10);
        minutesDisplay.textContent = minutes;
        totalSeconds = minutes * 60;
        resetTimer();
    });

    function startTimer() {
        if (interval || timeLeft <= 0) return;

        playSound();

        interval = setInterval(() => {
            if (!isPaused && timeLeft > 0) {
                timeLeft--;
                updateDisplay(timeLeft);
                updateProgress(timeLeft);
                if (timeLeft === 0) {
                    clearInterval(interval);
                    interval = null;
                    document.getElementById("timer").textContent = "Zeit abgelaufen!";
                    document.getElementById("progress").style.width = "0%";
                    playSound();
                }
            }
        }, 1000);
    }

    function pauseTimer() {
        isPaused = !isPaused;
    }

    function resetTimer() {
        clearInterval(interval);
        interval = null;
        timeLeft = totalSeconds;
        isPaused = false;
        updateDisplay(timeLeft);
        updateProgress(timeLeft);
    }

    function updateDisplay(seconds) {
        const m = String(Math.floor(seconds / 60)).padStart(2, '0');
        const s = String(seconds % 60).padStart(2, '0');
        document.getElementById("timer").textContent = m + ":" + s;
    }

    function updateProgress(seconds) {
        const percent = (seconds / totalSeconds) * 100;
        document.getElementById("progress").style.width = percent + "%";
    }

    function playSound() {
        const ctx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = ctx.createOscillator();
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(1000, ctx.currentTime);
        oscillator.connect(ctx.destination);
        oscillator.start();
        oscillator.stop(ctx.currentTime + 3);
    }

    // Initial
    updateDisplay(timeLeft);
    updateProgress(timeLeft);
</script>
    """, height=200)

    # ===========================
    # TEAMS LADEN
    # ===========================
    teams = get_current("teams")
    if len(teams) < 4:
        st.error("Mindestens 4 Teams erforderlich.")
        st.stop()

    # ===========================
    # KO-RUNDE GENERIEREN
    # ===========================
    if not get_current("ko_round"):

        if get_current("group_phase"):
            groups = get_current("groups")
            group_names = list(groups.keys())

            group_stats = {
                g: pd.DataFrame(groups[g])
                    .assign(Tordifferenz=lambda x: x["goals_for"] - x["goals_against"])
                    .sort_values(by=["points", "Tordifferenz", "goals_for"], ascending=False)
                for g in group_names
            }

            num_groups = len(group_names)

            # Wie viele steigen auf?
            if num_groups == 1:
                qualified_teams = 8
                top_teams = group_stats[group_names[0]].head(8)
            elif num_groups == 2:
                qualified_teams = 8
                top_teams = pd.concat([group_stats[g].head(4) for g in group_names], ignore_index=True)
            elif num_groups == 4:
                qualified_teams = 8
                top_teams = pd.concat([group_stats[g].head(2) for g in group_names], ignore_index=True)
            else:
                st.error("Der Modus für diese Anzahl an Gruppen ist nicht definiert.")
                st.stop()

        else:
            num_groups = 0
            qualified_teams = len(teams)
            df = pd.DataFrame(teams)
            top_teams = df.sort_values(by=["points", "goals_for"], ascending=False).head(8)

        # Optionales Viertelfinale
        play_quarters = False
        if qualified_teams > 4:
            play_quarters = st.checkbox("Viertelfinale spielen?", value=True)

        if st.button("KO-Runde generieren"):
            ko_round = []

            if play_quarters:
                ko_round = [
                    {"round": "Viertelfinale 1", "team1": top_teams.iloc[0]["name"], "team2": top_teams.iloc[7]["name"], "score": "-"},
                    {"round": "Viertelfinale 2", "team1": top_teams.iloc[1]["name"], "team2": top_teams.iloc[6]["name"], "score": "-"},
                    {"round": "Viertelfinale 3", "team1": top_teams.iloc[2]["name"], "team2": top_teams.iloc[5]["name"], "score": "-"},
                    {"round": "Viertelfinale 4", "team1": top_teams.iloc[3]["name"], "team2": top_teams.iloc[4]["name"], "score": "-"}
                ]
            else:
               # Keine Viertelfinale => direkt die besten 4 Teams!
                if get_current("group_phase"):
                    # Kombiniere alle Gruppen, sortiere neu
                    group_stats_combined = pd.concat(group_stats.values(), ignore_index=True)
                    group_stats_combined = group_stats_combined.assign(Tordifferenz=lambda x: x["goals_for"] - x["goals_against"])
                    top4 = group_stats_combined.sort_values(by=["points", "Tordifferenz", "goals_for"], ascending=False).head(4)
                else:
                    top4 = top_teams.head(4)

                ko_round = [
                    {"round": "Halbfinale 1", "team1": top4.iloc[0]["name"], "team2": top4.iloc[3]["name"], "score": "-"},
                    {"round": "Halbfinale 2", "team1": top4.iloc[1]["name"], "team2": top4.iloc[2]["name"], "score": "-"}
                ]

            set_current("ko_round", ko_round)
            save_data(st.session_state.data)
            st.success("KO-Runde erstellt!")
            st.rerun()

    # ===========================
    # KO-SPIELE ANZEIGEN
    # ===========================

    ko_round_data = get_current("ko_round")
    if ko_round_data:

        # ---- VIERTELFINALE ----
        if any("Viertelfinale" in m["round"] for m in ko_round_data):
            st.subheader("Viertelfinale")
            new_scores = []

            for idx, match in enumerate([m for m in ko_round_data if "Viertelfinale" in m["round"]]):
                st.markdown(f"**{match['round']}**: {match['team1']} vs {match['team2']}")
                saved_score = match.get("score", "-")

                if saved_score == "-":
                    g1, g2 = "", ""
                else:
                    g1, g2 = saved_score.split(":")

                col1, col2 = st.columns(2)
                with col1:
                    goals1 = st.text_input(f"Tore {match['team1']}", value=g1, key=f"qf_{idx}_1")
                with col2:
                    goals2 = st.text_input(f"Tore {match['team2']}", value=g2, key=f"qf_{idx}_2")

                new_scores.append((ko_round_data.index(match), goals1.strip(), goals2.strip()))

            if st.button("Viertelfinale speichern"):
                winners = []
                for idx, g1_str, g2_str in new_scores:
                    # Nur speichern, wenn beide Tore eingegeben wurden
                    if g1_str != "" and g2_str != "":
                        try:
                            g1 = int(g1_str)
                            g2 = int(g2_str)
                            ko_round_data[idx]["score"] = f"{g1}:{g2}"

                            if g1 > g2:
                                winners.append(ko_round_data[idx]["team1"])
                            elif g2 > g1:
                                winners.append(ko_round_data[idx]["team2"])
                            else:
                                winners.append("n/a")
                        except ValueError:
                            st.warning(f"Ungültige Eingabe bei {ko_round_data[idx]['round']}.")
                            winners.append(None)
                    else:
                        # Kein Ergebnis gesetzt, Platzhalter None
                        winners.append(None)

                # Halbfinale nur erstellen, wenn alle Ergebnisse da sind
                if all(winners) and not any("Halbfinale" in m["round"] for m in ko_round_data):
                    ko_round_data += [
                        {"round": "Halbfinale 1", "team1": winners[0], "team2": winners[3], "score": "-"},
                        {"round": "Halbfinale 2", "team1": winners[1], "team2": winners[2], "score": "-"}
                    ]

                set_current("ko_round", ko_round_data)
                save_data(st.session_state.data)
                st.success("Viertelfinale gespeichert!")
                st.rerun()

        # ---- HALBFINALE ----
        if any("Halbfinale" in m["round"] for m in ko_round_data):
            st.subheader("Halbfinale")
            hf_matches = [m for m in ko_round_data if "Halbfinale" in m["round"]]
            new_scores = []

            for idx, match in enumerate(hf_matches):
                st.markdown(f"**{match['round']}**: {match['team1']} vs {match['team2']}")
                saved_score = match.get("score", "-")

                if saved_score == "-":
                    g1, g2 = "", ""
                else:
                    g1, g2 = saved_score.split(":")

                col1, col2 = st.columns(2)
                with col1:
                    goals1 = st.text_input(f"Tore {match['team1']}", value=g1, key=f"hf_{idx}_1")
                with col2:
                    goals2 = st.text_input(f"Tore {match['team2']}", value=g2, key=f"hf_{idx}_2")

                new_scores.append((ko_round_data.index(match), goals1.strip(), goals2.strip()))

            if st.button("Halbfinalrunde speichern"):
                winners, losers = [], []
                for idx, g1_str, g2_str in new_scores:
                    if g1_str != "" and g2_str != "":
                        try:
                            g1 = int(g1_str)
                            g2 = int(g2_str)
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
                        except ValueError:
                            st.warning(f"Ungültige Eingabe bei {ko_round_data[idx]['round']}.")
                            winners.append(None)
                            losers.append(None)
                    else:
                        winners.append(None)
                        losers.append(None)

                # Finale & Spiel um Platz 3 nur erstellen, wenn alle Ergebnisse da sind
                if all(winners) and not any(m["round"] in ["Finale", "Spiel um Platz 3"] for m in ko_round_data):
                    ko_round_data.append({"round": "Spiel um Platz 3", "team1": losers[0], "team2": losers[1], "score": "-"})
                    ko_round_data.append({"round": "Finale", "team1": winners[0], "team2": winners[1], "score": "-"})

                set_current("ko_round", ko_round_data)
                save_data(st.session_state.data)
                st.success("Halbfinale gespeichert!")
                st.rerun()

        # ---- FINALE + SPIEL UM PLATZ 3 ----
        if any(m["round"] == "Finale" for m in ko_round_data):
            st.subheader("Finalrunde")
            final_matches = [m for m in ko_round_data if m["round"] in ["Finale", "Spiel um Platz 3"]]
            final_scores = []

            for idx, match in enumerate(final_matches):
                st.markdown(f"**{match['round']}**: {match['team1']} vs {match['team2']}")
                saved_score = match.get("score", "-")

                if saved_score == "-":
                    g1, g2 = "", ""
                else:
                    g1, g2 = saved_score.split(":")

                col1, col2 = st.columns(2)
                with col1:
                    goals1 = st.text_input(f"Tore {match['team1']}", value=g1, key=f"final_{idx}_1")
                with col2:
                    goals2 = st.text_input(f"Tore {match['team2']}", value=g2, key=f"final_{idx}_2")

                final_scores.append((ko_round_data.index(match), goals1.strip(), goals2.strip()))

            if st.button("Finalrunde speichern"):
                for idx, g1_str, g2_str in final_scores:
                    if g1_str != "" and g2_str != "":
                        try:
                            g1 = int(g1_str)
                            g2 = int(g2_str)
                            ko_round_data[idx]["score"] = f"{g1}:{g2}"
                        except ValueError:
                            st.warning(f"Ungültige Eingabe bei Finale/Platz 3.")
                set_current("ko_round", ko_round_data)
                save_data(st.session_state.data)
                st.success("Finalrunde gespeichert!")
                st.rerun()



