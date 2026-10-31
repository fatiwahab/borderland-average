#Alice in borderlands - browser version
# One player creates a room and becomes the host. The host's browser runs the
# game (game.py) and publishes what everyone is allowed to see to Firebase at
# rooms/CODE/state. Guests write their name and number to their own slot at
# rooms/CODE/inbox/THEIR_ID. The database rules (database.rules.json) only let
# the host read the inbox, so nobody can peek at anyone else's number.
import json

from pyscript import document, window, when
from pyscript.ffi import create_proxy

import game

CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I or O, they look like 1 and 0
MAX_PLAYERS = 12
JOIN_TIMEOUT_MS = 15000
SESSION_KEY = "borderland-session"
SCREENS = ["loading", "home", "lobby", "pick", "reveal"]

net = None
my_uid = ""
my_name = ""
is_host = False
room_code = ""
in_room = False
listeners = []       # functions that stop a Firebase listener
last_round_shown = 0
current_round = 0

# guest only
join_attempt = ""    # a fresh id for every join, so old rejections are ignored
joined = False
seen_state = False

# host only
names = {}           # guest id -> player name
online = {}          # guest id -> is their browser connected
attempts = {}        # guest id -> their join attempt id
rejected_attempts = []
attempts_made = [""]  # id of the room-creation attempt in progress, so old timers do nothing
lobby = []
players = {}
spectators = []
phase = "lobby"
round_number = 0
last_result = None
notice = ""


# ---------- small helpers ----------

def el(element_id):
    return document.getElementById(element_id)


def show_screen(name):
    for screen in SCREENS:
        el(screen).hidden = screen != name


def esc(text):
    # player names go into the page, so make sure they can't inject HTML
    text = str(text)
    for old, new in (("&", "&amp;"), ("<", "&lt;"), (">", "&gt;"), ('"', "&quot;")):
        text = text.replace(old, new)
    return text


def fmt(number):
    number = round(number, 2)
    if number == int(number):
        return str(int(number))
    return str(number)


def lives(score):
    return "&#9830;" * max(score, 0)


def clean_name(name):
    # Firebase can't store these characters in keys, and names are used as keys
    name = str(name).strip()
    for bad in ".#$[]/":
        name = name.replace(bad, "")
    return name[:20]


def new_id(length, letters):
    text = ""
    for _ in range(length):
        text += letters[int(window.Math.random() * len(letters))]
    return text


def later(function, ms):
    window.setTimeout(create_proxy(function), ms)


def room_path(child=""):
    path = f'rooms/{room_code}'
    if child:
        path += "/" + child
    return path


def parse(text):
    text = str(text)
    if not text:
        return None
    return json.loads(text)


# ---------- talking to Firebase (see net.js) ----------

def proxy(function):
    return create_proxy(function) if function else None


def connection_problem(code):
    code = str(code)
    if "PERMISSION_DENIED" in code.upper() or "permission" in code:
        go_home("The game's database refused that. The room may have closed.")
    else:
        go_home(f'Connection problem ({code}). Check your internet and try again.')


def db_set(path, value, done=None, fail=connection_problem):
    net.set(path, json.dumps(value), proxy(done), proxy(fail))


def db_update(path, value, done=None, fail=connection_problem):
    net.update(path, json.dumps(value), proxy(done), proxy(fail))


def db_remove(path, done=None, fail=None):
    net.remove(path, proxy(done), proxy(fail))


def db_listen(path, changed):
    listeners.append(net.listen(path, create_proxy(changed), create_proxy(connection_problem)))


def stop_listening():
    while listeners:
        stop = listeners.pop()
        stop()


def my_presence_path():
    return room_path("host") if is_host else room_path("inbox/" + my_uid)


def on_connected(connected):
    # Firebase forgets onDisconnect after a reconnect, so set it up again each time
    if not (connected and in_room):
        return
    path = my_presence_path()
    net.onDisconnectUpdate(path, json.dumps({"online": False}))
    db_update(path, {"online": True}, fail=lambda code: None)


# ---------- remembering the room, so a reload can rejoin ----------

def save_session():
    try:
        window.localStorage.setItem(SESSION_KEY, json.dumps({"room": room_code, "name": my_name, "host": is_host}))
    except Exception:
        pass


def load_session():
    try:
        return parse(window.localStorage.getItem(SESSION_KEY) or "")
    except Exception:
        return None


def clear_session():
    try:
        window.localStorage.removeItem(SESSION_KEY)
    except Exception:
        pass


def show_rejoin():
    session = load_session()
    rejoin = el("rejoin-btn")
    rejoin.hidden = not session
    if session:
        rejoin.textContent = f'Rejoin room {session["room"]} as {session["name"]}'


# ---------- home screen ----------

def set_home_busy(busy, message=""):
    el("create-btn").disabled = busy
    el("join-btn").disabled = busy
    el("rejoin-btn").disabled = busy
    el("home-message").textContent = message


def go_home(message):
    global in_room, is_host, joined
    if in_room:
        net.cancelOnDisconnect(my_presence_path())
    stop_listening()
    in_room = False
    is_host = False
    joined = False
    el("whoami").textContent = ""
    el("away-notice").textContent = ""
    el("leave-btn").hidden = True
    show_rejoin()
    set_home_busy(not my_uid, message)
    show_screen("home")


def read_name():
    global my_name
    name = clean_name(el("name-input").value)
    if not name:
        el("home-message").textContent = "Enter your name first."
        return False
    my_name = name
    return True


@when("click", "#create-btn")
def on_create(event):
    if read_name():
        start_host()


@when("click", "#join-btn")
def on_join(event):
    global room_code
    if not read_name():
        return
    code = el("code-input").value.strip().upper()
    if len(code) != 4:
        el("home-message").textContent = "Room codes are 4 letters."
        return
    room_code = code
    start_guest()


@when("click", "#rejoin-btn")
def on_rejoin(event):
    global my_name, room_code
    session = load_session()
    if not session:
        return
    my_name = session["name"]
    room_code = session["room"]
    if session["host"]:
        resume_host()
    else:
        start_guest()


@when("click", "#leave-btn")
def on_leave(event):
    if is_host:
        if not window.confirm("Leave and close the room for everyone?"):
            return
        db_remove(room_path())
    else:
        db_remove(room_path("inbox/" + my_uid))
    clear_session()
    go_home("")


# ---------- host side ----------

def start_host(tries=0):
    global room_code, is_host
    is_host = True
    room_code = new_id(4, CODE_LETTERS)
    set_home_busy(True, "Creating a room...")
    room = {"host": {"uid": my_uid, "name": my_name, "online": True, "created": {".sv": "timestamp"}}}

    def taken(code):
        # the database rules refuse a code another host is using, so try another one
        if tries < 5:
            start_host(tries + 1)
        else:
            connection_problem(code)

    db_set(room_path(), room, done=lambda *args: host_ready(True), fail=taken)

    def give_up():
        # Firebase waits forever if it can't reach the database, so don't leave people stuck
        if is_host and not in_room and token == attempts_made[0]:
            go_home("Couldn't reach the game server. Check your internet, turn off any ad or "
                    "tracker blocker for this page, and try again.")

    token = new_id(8, CODE_LETTERS)
    attempts_made[0] = token
    later(give_up, JOIN_TIMEOUT_MS)


def host_ready(fresh):
    global in_room, lobby, players, spectators, phase, round_number, last_result, notice
    if fresh:
        lobby = [my_name]
        players = {}
        spectators = []
        phase = "lobby"
        round_number = 0
        last_result = None
        notice = ""
        names.clear()
        online.clear()
        attempts.clear()
        rejected_attempts.clear()
    in_room = True
    save_session()
    on_connected(True)
    db_listen(room_path("inbox"), on_inbox)
    publish()


def resume_host():
    global is_host
    is_host = True
    set_home_busy(True, f'Rejoining room {room_code}...')

    def restore(text):
        global lobby, players, spectators, phase, round_number, last_result, notice
        saved = parse(text)
        if not saved:
            clear_session()
            go_home(f'Room {room_code} has ended.')
            return
        # Firebase drops empty lists and None values, so fill them back in
        lobby = saved.get("lobby", [])
        players = saved.get("players", {})
        for name in players.keys():
            if "number" not in players[name]:
                players[name]["number"] = None
        spectators = saved.get("spectators", [])
        phase = saved.get("phase", "lobby")
        round_number = saved.get("round", 0)
        last_result = complete_result(saved.get("result"))
        notice = saved.get("notice", "")
        names.clear()
        names.update(saved.get("names", {}))
        attempts.clear()
        attempts.update(saved.get("attempts", {}))
        rejected_attempts.clear()
        rejected_attempts.extend(saved.get("rejected", []))
        online.clear()
        host_ready(False)

    net.get(room_path("private"), create_proxy(restore),
            create_proxy(lambda code: (clear_session(), go_home(f'Room {room_code} has ended.'))))


def on_inbox(text):
    inbox = parse(text) or {}
    changed = False
    # a guest whose slot has gone has left the room
    for uid in list(names.keys()):
        if uid not in inbox:
            changed = player_left(uid, f'{names[uid]} left the room.') or changed
    for uid in inbox.keys():
        entry = inbox[uid]
        if uid in names:
            is_online = entry.get("online", True) is not False
            if online.get(uid) != is_online:
                online[uid] = is_online
                changed = True
            name = names[uid]
            number = entry.get("number")
            if (phase == "pick" and entry.get("round") == round_number and number is not None
                    and name in players and players[name]["number"] is None):
                try:
                    game.submit_number(players, name, number)
                    changed = True
                except ValueError:
                    pass
        elif entry.get("attempt", "") not in rejected_attempts:
            changed = handle_join(uid, entry) or changed
    if phase == "pick" and players and game.all_submitted(players):
        finish_round()
    elif changed:
        publish()


def reject(uid, attempt, reason):
    rejected_attempts.append(attempt)
    db_set(room_path("rejected/" + uid), {"attempt": attempt, "reason": reason}, fail=lambda code: None)


def handle_join(uid, entry):
    global notice
    name = clean_name(entry.get("name", ""))
    attempt = entry.get("attempt", "")
    if phase != "lobby":
        reject(uid, attempt, "That game has already started. Ask the host to start a new one.")
    elif not name:
        reject(uid, attempt, "Enter your name first.")
    elif name in lobby:
        reject(uid, attempt, f'Someone in that room is already called {name}. Pick another name.')
    elif len(lobby) >= MAX_PLAYERS:
        reject(uid, attempt, f'That room is full ({MAX_PLAYERS} players).')
    else:
        names[uid] = name
        attempts[uid] = attempt
        online[uid] = entry.get("online", True) is not False
        lobby.append(name)
        notice = ""
        return True
    return False


def player_left(uid, message):
    global phase, notice
    name = names.pop(uid, None)
    online.pop(uid, None)
    attempts.pop(uid, None)
    if name is None:
        return False
    notice = message
    if name in lobby:
        lobby.remove(name)
    if name in spectators:
        spectators.remove(name)
    if name in players:
        game.remove_player(players, name)
        if phase in ("pick", "reveal") and game.is_game_over(players):
            phase = "over"
    return True


def remove_player(uid):
    # the host can remove someone, e.g. a player whose phone died mid-round
    name = names.get(uid)
    if name is None:
        return
    reject(uid, attempts.get(uid, ""), "The host removed you from the game.")
    player_left(uid, f'{name} was removed.')
    db_remove(room_path("inbox/" + uid))
    if phase == "pick" and players and game.all_submitted(players):
        finish_round()
    else:
        publish()


def handle_number(name, number):
    if phase != "pick" or name not in players:
        return
    try:
        game.submit_number(players, name, number)
    except ValueError:
        return
    if game.all_submitted(players):
        finish_round()
    else:
        publish()


def finish_round():
    global phase, last_result, notice
    last_result = game.play_round(players)
    for name in last_result["eliminated"]:
        spectators.append(name)
    notice = ""
    if game.is_game_over(players):
        phase = "over"
    else:
        phase = "reveal"
    publish()


@when("click", "#start-btn")
def on_start(event):
    global players, spectators, round_number, last_result, phase, notice
    if not is_host or len(lobby) < game.MIN_PLAYERS:
        return
    players = game.create_game(lobby)
    spectators = []
    round_number = 1
    last_result = None
    notice = ""
    phase = "pick"
    publish()


@when("click", "#next-btn")
def on_next(event):
    global round_number, phase, lobby, notice
    if not is_host:
        return
    notice = ""
    if phase == "reveal":
        round_number += 1
        phase = "pick"
    elif phase == "over":
        # new game with everyone who is still in the room
        lobby = [my_name]
        for name in names.values():
            lobby.append(name)
        phase = "lobby"
    publish()


def on_remove_click(event):
    uid = event.target.getAttribute("data-remove")
    if is_host and uid:
        remove_player(str(uid))


el("lobby-players").addEventListener("click", create_proxy(on_remove_click))
el("pick-players").addEventListener("click", create_proxy(on_remove_click))


def uid_of(name):
    for uid in names.keys():
        if names[uid] == name:
            return uid
    return None


def is_away(name):
    uid = uid_of(name)
    return uid is not None and online.get(uid) is False


def public_state():
    # what everyone is allowed to see: never the numbers of the round in progress
    rows = []
    if phase == "lobby":
        for name in lobby:
            rows.append({"name": name, "score": game.START_SCORE, "picked": False, "away": is_away(name)})
    else:
        for name in players.keys():
            rows.append({"name": name, "score": players[name]["score"],
                         "picked": players[name]["number"] is not None, "away": is_away(name)})
    return {
        "phase": phase,
        "room": room_code,
        "host": my_name,
        "round": round_number,
        "players": rows,
        "spectators": spectators,
        "result": last_result if phase in ("reveal", "over") else None,
        "winner": game.winner(players) if phase == "over" else None,
        "notice": notice,
    }


def private_state():
    # only the host can read this; it lets the host reload the page without ending the game
    return {
        "lobby": lobby,
        "players": players,
        "spectators": spectators,
        "phase": phase,
        "round": round_number,
        "result": last_result,
        "notice": notice,
        "names": names,
        "attempts": attempts,
        "rejected": rejected_attempts,
    }


def publish():
    state = public_state()
    db_update(room_path(), {"state": state, "private": private_state()})
    render(state)


# ---------- guest side ----------

def start_guest():
    global is_host, joined, seen_state
    is_host = False
    joined = False
    seen_state = False
    set_home_busy(True, f'Joining room {room_code}...')

    def checked(text):
        host = parse(text)
        if not host:
            clear_session()
            go_home(f'No room with the code {room_code}. Check the code and try again.')
        else:
            send_join()

    net.get(room_path("host"), create_proxy(checked), create_proxy(connection_problem))


def send_join():
    global join_attempt, in_room
    join_attempt = new_id(8, CODE_LETTERS)
    attempt = join_attempt
    in_room = True
    db_set(room_path("inbox/" + my_uid), {"name": my_name, "attempt": attempt, "online": True})
    on_connected(True)
    db_listen(room_path("state"), on_state)
    db_listen(room_path("rejected/" + my_uid), on_rejected)
    db_listen(room_path("host/online"), on_host_online)
    el("home-message").textContent = f'Joining room {room_code}... waiting for the host.'

    def give_up():
        if in_room and not joined and join_attempt == attempt:
            db_remove(room_path("inbox/" + my_uid))
            go_home("The host's page isn't responding. Ask them to keep the game open, then try again.")

    later(give_up, JOIN_TIMEOUT_MS)


def on_rejected(text):
    rejection = parse(text)
    if rejection and rejection.get("attempt") == join_attempt:
        db_remove(room_path("inbox/" + my_uid))
        clear_session()
        go_home(rejection.get("reason", "Couldn't join that room."))


def on_host_online(text):
    away = parse(text) is False
    el("away-notice").textContent = "The host's connection dropped. Waiting for them to come back..." if away else ""


def on_state(text):
    global joined, seen_state
    state = parse(text)
    if state is None:
        if seen_state:
            clear_session()
            go_home("The host closed the room.")
        return
    seen_state = True
    state = complete_state(state)
    in_game = my_name in state["spectators"]
    for row in state["players"]:
        if row["name"] == my_name:
            in_game = True
    if not joined:
        if not in_game:
            return  # the host hasn't let us in yet
        joined = True
        save_session()
    render(state)


def complete_result(result):
    # Firebase drops empty lists, so put them back
    if result:
        for key in ("winners", "tied", "duplicates", "eliminated"):
            result[key] = result.get(key, [])
    return result


def complete_state(state):
    state["players"] = state.get("players", [])
    state["spectators"] = state.get("spectators", [])
    state["result"] = complete_result(state.get("result"))
    state["winner"] = state.get("winner")
    state["notice"] = state.get("notice", "")
    return state


# ---------- drawing the screens (same for host and guests) ----------

def render(state):
    global current_round
    current_round = state["round"]
    el("whoami").textContent = f'Room {state["room"]} · playing as {my_name}'
    el("leave-btn").hidden = False
    if state["phase"] == "lobby":
        render_lobby(state)
    elif state["phase"] == "pick":
        render_pick(state)
    else:
        render_reveal(state)


def player_extras(row):
    # "away" tag for everyone, plus a remove button the host can use
    html = ' <span class="away">away</span>' if row.get("away") else ""
    uid = uid_of(row["name"]) if is_host else None
    if uid:
        html += f'<button class="remove" data-remove="{esc(uid)}">remove</button>'
    return html


def render_lobby(state):
    el("lobby-code").textContent = state["room"]
    html = ""
    for row in state["players"]:
        tags = []
        if row["name"] == state["host"]:
            tags.append("host")
        if row["name"] == my_name:
            tags.append("you")
        html += (f'<li><span>{esc(row["name"])}{player_extras(row)}</span>'
                 f'<span class="tag">{", ".join(tags)}</span></li>')
    el("lobby-players").innerHTML = html
    count = len(state["players"])
    start = el("start-btn")
    start.hidden = not is_host
    start.disabled = count < game.MIN_PLAYERS
    if is_host:
        needed = game.MIN_PLAYERS - count
        if needed > 0:
            more = "1 more player" if needed == 1 else f'{needed} more players'
            el("lobby-wait").textContent = f'Waiting for {more}. The game needs at least {game.MIN_PLAYERS}.'
        else:
            el("lobby-wait").textContent = f'{count} players ready.'
    else:
        el("lobby-wait").textContent = f'Waiting for {state["host"]} to start the game.'
    show_screen("lobby")


def render_pick(state):
    global last_round_shown
    el("pick-title").textContent = f'Round {state["round"]}'
    if state["round"] != last_round_shown:
        # a new round: clear last round's number
        last_round_shown = state["round"]
        el("number-input").value = ""
        el("pick-message").textContent = ""

    me = None
    for row in state["players"]:
        if row["name"] == my_name:
            me = row
    waiting = el("pick-waiting")
    if me is None:
        el("pick-form").hidden = True
        waiting.hidden = False
        waiting.textContent = "You've been eliminated. Watching the rest of the game."
    elif me["picked"]:
        el("pick-form").hidden = True
        waiting.hidden = False
        waiting.textContent = "Locked in. Waiting for the others..."
    else:
        el("pick-form").hidden = False
        el("submit-btn").disabled = False
        waiting.hidden = True

    html = ""
    for row in state["players"]:
        status = '<span class="done">locked in</span>' if row["picked"] else '<span class="tag">thinking...</span>'
        html += (f'<li><span>{esc(row["name"])} <span class="lives">{lives(row["score"])}</span>'
                 f'{player_extras(row)}</span>{status}</li>')
    for name in state["spectators"]:
        html += f'<li><span class="out">{esc(name)}</span><span class="tag">out</span></li>'
    el("pick-players").innerHTML = html
    el("pick-notice").textContent = state["notice"]
    show_screen("pick")


@when("submit", "#pick-form")
def on_submit_number(event):
    event.preventDefault()
    text = el("number-input").value.strip()
    if not text.isdigit() or int(text) > game.HIGHEST_NUMBER:
        el("pick-message").textContent = f'Pick a whole number from {game.LOWEST_NUMBER} to {game.HIGHEST_NUMBER}.'
        return
    el("pick-message").textContent = ""
    el("submit-btn").disabled = True
    if is_host:
        handle_number(my_name, int(text))
    else:
        db_update(room_path("inbox/" + my_uid), {"number": int(text), "round": current_round})


def render_reveal(state):
    result = state["result"]
    over = state["phase"] == "over"
    el("reveal-title").textContent = "Game over" if over else f'Round {state["round"]} results'

    if over:
        if state["winner"]:
            headline = f'{state["winner"]} wins the game!'
            if result and result["exact_hit"] and state["winner"] in result["winners"]:
                headline += " (Hit the average exactly in the last round.)"
            elif result and result["zero_vs_hundred"] and state["winner"] in result["winners"]:
                headline += " (100 beat 0 in the last round.)"
        elif result and len(result["eliminated"]) > 1:
            headline = "Draw! The last players were eliminated together."
        else:
            headline = "Nobody is left in the game."
    elif result["zero_vs_hundred"]:
        headline = f'{result["winners"][0]} picked 100 against 0 and wins the round.'
    elif result["exact_hit"]:
        headline = f'{result["winners"][0]} hit the average exactly! Everyone else loses 2 points.'
    elif result["winners"] and result["duplicates"]:
        headline = f'{result["winners"][0]} was closest with a valid number and wins the round.'
    elif result["winners"]:
        headline = f'{result["winners"][0]} was closest and wins the round.'
    elif result["tied"]:
        headline = f'{" and ".join(result["tied"])} tied, so nobody wins. Everyone loses a point.'
    else:
        headline = "Every number was picked more than once, so nobody wins. Everyone loses a point."
    el("reveal-headline").textContent = headline

    table = ""
    rule = ""
    if result:
        el("reveal-average").textContent = f'Average: {fmt(result["average"])}'
        if result["duplicates"]:
            picked_twice = []
            for name in result["duplicates"]:
                number = str(result["numbers"][name])
                if number not in picked_twice:
                    picked_twice.append(number)
            rule = f'Invalid (picked more than once): {", ".join(picked_twice)}'
        table = "<tr><th>Player</th><th>Picked</th><th>Off by</th><th></th><th>Points</th></tr>"
        order = sorted(result["numbers"].keys(), key=lambda name: result["differences"][name])
        for name in order:
            change = result["changes"][name]
            if change > 0:
                change_html = f'<span class="plus">+{change}</span>'
            else:
                change_html = f'<span class="minus">&minus;{-change}</span>'
            picked = str(result["numbers"][name])
            if name in result["duplicates"]:
                picked = f'<span class="out">{picked}</span>'
            score = result["scores"][name]
            points = '<span class="tag">out</span>' if name in result["eliminated"] else f'<span class="lives">{lives(score)}</span>'
            row_class = ' class="me"' if name == my_name else ""
            table += (f'<tr{row_class}><td>{esc(name)}</td><td class="num">{picked}</td>'
                      f'<td class="num">{fmt(result["differences"][name])}</td><td>{change_html}</td><td>{points}</td></tr>')
    else:
        el("reveal-average").textContent = ""
    el("reveal-rule").textContent = rule
    el("reveal-table").innerHTML = table
    el("reveal-notice").textContent = state["notice"]

    next_btn = el("next-btn")
    next_btn.hidden = not is_host
    next_btn.textContent = "New game" if over else "Next round"
    if is_host:
        el("reveal-wait").textContent = ""
    elif over:
        el("reveal-wait").textContent = f'Waiting for {state["host"]} to start a new game.'
    else:
        el("reveal-wait").textContent = f'Waiting for {state["host"]} to start the next round.'
    show_screen("reveal")


# ---------- start up ----------

def on_signed_in(uid):
    global my_uid
    my_uid = str(uid)
    net.onConnected(create_proxy(on_connected))
    set_home_busy(False)
    show_rejoin()


def start():
    global net
    status = str(window.netStatus)
    show_screen("home")
    if status == "not-configured":
        set_home_busy(True, "This copy of the game isn't connected to Firebase yet (see web/firebase-config.js).")
    elif status != "ready":
        set_home_busy(True, "Couldn't load the connection service. Check your internet and reload the page.")
    else:
        net = window.net
        set_home_busy(True, "Connecting...")
        net.signIn(create_proxy(on_signed_in),
                   create_proxy(lambda code: set_home_busy(True, f'Couldn\'t connect ({code}). Reload to try again.')))


start()
