# Borderland Average

A multiplayer number game inspired by *Alice in Borderland*, playable in the browser.

**Play:** https://fatiwahab.github.io/borderland-average/

One player creates a room and shares the 4-letter code. Everyone else joins from their own phone or computer.

## Rules

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
- Multiplayer uses [PeerJS](https://peerjs.com): browsers connect directly to the host's browser, so there's no server.
- `#Alice in borderlands - Complete Game.py`: the original terminal version.

## Running it locally

```
cd web
python3 test_game.py        # run the tests
python3 -m http.server      # then open http://localhost:8000 in two windows
```

## Deploying

Every push runs the tests with GitHub Actions. When they pass on `main`, the site is published to GitHub Pages automatically.
