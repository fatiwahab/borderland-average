#Alice in borderlands - browser version
# One player creates a room and becomes the host. The host's browser runs the
# game (game.py) and sends the current state to everyone after every change.
# Guests only send two kinds of message to the host: their name and their number.
# Numbers never leave the host until everyone has picked, so nobody can peek.
import json

from pyscript import document, window, when
from pyscript.ffi import create_proxy

import game

ROOM_PREFIX = "borderland-average-"
CODE_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # no I or O, they look like 1 and 0
MAX_PLAYERS = 12
SCREENS = ["loading", "home", "lobby", "pick", "reveal"]

my_name = ""
is_host = False
room_code = ""
peer = None
leaving = False      # True when we chose to disconnect, so it isn't shown as an error
last_round_shown = 0

# guest only
host_conn = None

# host only
conns = {}           # peer id -> connection
names = {}           # peer id -> player name, once they have joined
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


def send(conn, message):
    if conn is not None and conn.open:
        conn.send(json.dumps(message))


def later(function, ms):
    window.setTimeout(create_proxy(function), ms)


def go_home(message):
    global peer, host_conn, is_host, leaving
    leaving = True
    if peer is not None:
        peer.destroy()
    peer = None
    host_conn = None
    is_host = False
    el("whoami").textContent = ""
    el("home-message").textContent = message
    el("create-btn").disabled = False
    el("join-btn").disabled = False
    show_screen("home")


def read_name():
    global my_name
    name = el("name-input").value.strip()
    if not name:
        el("home-message").textContent = "Enter your name first."
        return False
    my_name = name
    return True


def connection_error(err):
    kind = str(err.type)
    if kind == "peer-unavailable":
        return f'No room with the code {room_code}. Check the code and try again.'
    if kind in ("network", "server-error", "socket-error", "socket-closed"):
        return "Couldn't reach the connection server. Check your internet and try again."
    if kind == "browser-incompatible":
        return "This browser can't make peer-to-peer connections. Try Chrome, Firefox or Safari."
    return f'Connection problem ({kind}). Try again.'


# ---------- home screen ----------

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


# ---------- host side ----------

def new_code():
    code = ""
    for _ in range(4):
        code += CODE_LETTERS[int(window.Math.random() * len(CODE_LETTERS))]
    return code


def start_host():
    global peer, is_host, room_code, leaving, phase, lobby, players, spectators, notice
    is_host = True
    leaving = False
    room_code = new_code()
    phase = "lobby"
    lobby = [my_name]
    players = {}
    spectators = []
    notice = ""
    conns.clear()
    names.clear()
    el("create-btn").disabled = True
    el("join-btn").disabled = True
    el("home-message").textContent = "Creating a room..."
    peer = window.makePeer(ROOM_PREFIX + room_code)
    peer.on("open", create_proxy(lambda peer_id: broadcast()))
    peer.on("connection", create_proxy(on_guest_connected))
    peer.on("error", create_proxy(on_host_error))


def on_host_error(err):
    if str(err.type) == "unavailable-id":
        # someone else is already using this room code, so pick another one
        peer.destroy()
        start_host()
    elif str(err.type) == "peer-unavailable":
        pass  # a guest vanished before we could reach them; their close event cleans up
    else:
        go_home(connection_error(err))


def on_guest_connected(conn):
    peer_id = str(conn.peer)
    conns[peer_id] = conn
    conn.on("data", create_proxy(lambda data: on_guest_message(peer_id, data)))
    conn.on("close", create_proxy(lambda *args: on_guest_left(peer_id)))


def on_guest_message(peer_id, data):
    try:
        message = json.loads(str(data))
    except ValueError:
        return
    if message.get("type") == "join":
        handle_join(peer_id, str(message.get("name", "")).strip()[:20])
    elif message.get("type") == "guess" and peer_id in names:
        handle_number(names[peer_id], message.get("number"))


def reject(peer_id, reason):
    conn = conns.pop(peer_id, None)
    send(conn, {"type": "error", "message": reason})
    later(lambda: conn.close(), 1000)


def handle_join(peer_id, name):
    if phase != "lobby":
        reject(peer_id, "That game has already started. Ask the host to start a new one.")
    elif not name:
        reject(peer_id, "Enter your name first.")
    elif name in lobby:
        reject(peer_id, f'Someone in that room is already called {name}. Pick another name.')
    elif len(lobby) >= MAX_PLAYERS:
        reject(peer_id, f'That room is full ({MAX_PLAYERS} players).')
    else:
        names[peer_id] = name
        lobby.append(name)
        broadcast()


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
        broadcast()


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
    broadcast()


def on_guest_left(peer_id):
    global phase, notice
    conns.pop(peer_id, None)
    name = names.pop(peer_id, None)
    if name is None or leaving:
        return
    notice = f'{name} left the game.'
    if name in lobby:
        lobby.remove(name)
    if name in spectators:
        spectators.remove(name)
    if name in players:
        game.remove_player(players, name)
        if phase in ("pick", "reveal") and game.is_game_over(players):
            phase = "over"
        elif phase == "pick" and game.all_submitted(players):
            finish_round()
            return
    broadcast()


@when("click", "#start-btn")
def on_start(event):
    global players, spectators, round_number, last_result, phase, notice
    if not is_host or len(lobby) < 2:
        return
    players = game.create_game(lobby)
    spectators = []
    round_number = 1
    last_result = None
    notice = ""
    phase = "pick"
    broadcast()


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
        # new game with everyone who is still connected
        lobby = [my_name]
        for name in names.values():
            lobby.append(name)
        phase = "lobby"
    broadcast()


def public_state():
    # what everyone is allowed to see: never the numbers of the round in progress
    rows = []
    if phase == "lobby":
        for name in lobby:
            rows.append({"name": name, "score": game.START_SCORE, "picked": False})
    else:
        for name in players.keys():
            rows.append({"name": name, "score": players[name]["score"],
                         "picked": players[name]["number"] is not None})
    return {
        "type": "state",
        "phase": phase,
        "room": room_code,
        "host": lobby[0] if lobby else my_name,
        "round": round_number,
        "players": rows,
        "spectators": spectators,
        "result": last_result if phase in ("reveal", "over") else None,
        "winner": game.winner(players) if phase == "over" else None,
        "notice": notice,
    }


def broadcast():
    state = public_state()
    text = json.dumps(state)
    for peer_id in names.keys():
        conn = conns.get(peer_id)
        if conn is not None and conn.open:
            conn.send(text)
    render(state)


# ---------- guest side ----------

def start_guest():
    global peer, is_host, leaving
    is_host = False
    leaving = False
    el("create-btn").disabled = True
    el("join-btn").disabled = True
    el("home-message").textContent = f'Joining room {room_code}...'
    peer = window.makePeer(None)
    peer.on("open", create_proxy(lambda peer_id: connect_to_host()))
    peer.on("error", create_proxy(lambda err: go_home(connection_error(err))))


def connect_to_host():
    global host_conn
    host_conn = peer.connect(ROOM_PREFIX + room_code)
    host_conn.on("open", create_proxy(lambda *args: send(host_conn, {"type": "join", "name": my_name})))
    host_conn.on("data", create_proxy(on_host_message))
    host_conn.on("close", create_proxy(on_host_left))


def on_host_message(data):
    try:
        message = json.loads(str(data))
    except ValueError:
        return
    if message.get("type") == "state":
        render(message)
    elif message.get("type") == "error":
        go_home(message.get("message", "Couldn't join that room."))


def on_host_left(*args):
    if not leaving:
        go_home("The host left, so the game ended.")


# ---------- drawing the screens (same for host and guests) ----------

def render(state):
    el("whoami").textContent = f'Room {state["room"]} · playing as {my_name}'
    if state["phase"] == "lobby":
        render_lobby(state)
    elif state["phase"] == "pick":
        render_pick(state)
    else:
        render_reveal(state)


def render_lobby(state):
    el("lobby-code").textContent = state["room"]
    html = ""
    for row in state["players"]:
        tags = []
        if row["name"] == state["host"]:
            tags.append("host")
        if row["name"] == my_name:
            tags.append("you")
        html += f'<li><span>{esc(row["name"])}</span><span class="tag">{", ".join(tags)}</span></li>'
    el("lobby-players").innerHTML = html
    count = len(state["players"])
    start = el("start-btn")
    start.hidden = not is_host
    start.disabled = count < 2
    if is_host:
        el("lobby-wait").textContent = "Waiting for at least one more player." if count < 2 else f'{count} players ready.'
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
        html += f'<li><span>{esc(row["name"])} <span class="lives">{lives(row["score"])}</span></span>{status}</li>'
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
        send(host_conn, {"type": "guess", "number": int(text)})


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


def on_page_closed(event):
    # closing the tab doesn't always tell the other browsers, so say goodbye properly
    global leaving
    leaving = True
    if peer is not None:
        peer.destroy()


window.addEventListener("pagehide", create_proxy(on_page_closed))
show_screen("home")
