# Borderland Average

A multiplayer number game inspired by *Alice in Borderland*, playable in the browser.

**Play:** https://fatiwahab.github.io/borderland-average/

One player creates a room and shares the 4-letter code. Everyone else joins from their own phone or computer.

## Rules

- You need at least 4 players to start.
- Everyone secretly picks a whole number from 0 to 100.
- The number closest to the average wins the round: +1. Everyone else: −1.
- If two or more players tie for closest, nobody wins and everyone loses a point.
- A number picked by more than one player is invalid: those players can't win and lose a point.
- Hit the average exactly and everyone else loses 2 points.
- With two players left, if one picks 0, the other wins by picking 100.
- Everyone starts with 3 points. Reach 0 and you're out. Last one standing wins.

## How it's built

- `web/game.py`: the game rules, in plain Python.
- `web/main.py`: the screens and multiplayer, running in the browser with [PyScript](https://pyscript.net) (MicroPython).
- Multiplayer goes through a free [Firebase Realtime Database](https://firebase.google.com/docs/database). The host's browser runs the game; guests send their name and number to it through Firebase. `web/net.js` wraps Firebase, `web/firebase-config.js` holds the project settings, and `database.rules.json` makes sure only the host can read players' numbers.
- `#Alice in borderlands - Complete Game.py`: the original terminal version.

## Running it locally

```
cd web
python3 test_game.py        # run the tests
python3 -m http.server      # then open http://localhost:8000
```

To play locally without touching the real database, start the Firebase emulator from the project folder (needs Java) and add `?emulator` to the URL:

```
npx firebase-tools emulators:start --only auth,database --project demo-borderland
```

Open `http://localhost:8000/?emulator` in two different browsers (or a normal and a private window), because each player needs their own sign-in.

## Deploying

Every push runs the tests with GitHub Actions. When they pass on `main`, the site is published to GitHub Pages automatically.
