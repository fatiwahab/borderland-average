#Alice in borderlands - game logic
# Ported from the terminal version. No input(), print() or networking here,
# so the same code runs in the browser (main.py) and in the tests.
# Two fixes compared to the original:
#  - the difference is made positive with abs(), so the CLOSEST number wins
#    (before, the highest number always won)
#  - the average divides by the players still in the game, not the starting count
# Extra rules:
#  - a tie for closest means nobody wins and everyone loses a point
#  - a number picked by 2+ players is invalid, so those players can't win
#  - hitting the average exactly makes every other player lose 2 points
#  - with 2 players left, if one picks 0 and the other 100, the 100 wins

START_SCORE = 3
LOWEST_NUMBER = 0
HIGHEST_NUMBER = 100


def create_game(names):
    #populate dictionary with each player's name and game stats
    players = {}
    for player_name in names:
        if player_name in players:
            raise ValueError(f'Two players are called {player_name}')
        # number is None until the player has picked one this round
        players[player_name] = {"score": START_SCORE, "number": None, "difference": 0}
    return players


def submit_number(players, player, number):
    if player not in players:
        raise ValueError(f'{player} is not in the game')
    if not isinstance(number, int) or not LOWEST_NUMBER <= number <= HIGHEST_NUMBER:
        raise ValueError(f'Pick a whole number from {LOWEST_NUMBER} to {HIGHEST_NUMBER}')
    players[player]["number"] = number


def all_submitted(players):
    for player in players.keys():
        if players[player]["number"] is None:
            return False
    return True


def play_round(players):
    # find average of the numbers
    sum_num = 0
    for player in players.keys():
        sum_num += players[player]["number"]
    total_players = len(players)
    average = sum_num / total_players

    # find how far each number is from the average.
    # Ties are compared as whole numbers (|number * players - sum|) so two players
    # the same distance away always tie, with no floating-point rounding surprises.
    distances = {}
    times_picked = {}
    for player in players.keys():
        number = players[player]["number"]
        players[player]["difference"] = abs(number - average)
        distances[player] = abs(number * total_players - sum_num)
        times_picked[number] = times_picked.get(number, 0) + 1

    # a number picked by two or more players is invalid: they can't win the round.
    # (Invalid numbers still count towards the average.)
    duplicates = []
    valid = []
    for player in players.keys():
        if times_picked[players[player]["number"]] > 1:
            duplicates.append(player)
        else:
            valid.append(player)

    winners = []
    tied = []
    zero_vs_hundred = False
    if total_players == 2 and sorted(times_picked.keys()) == [LOWEST_NUMBER, HIGHEST_NUMBER]:
        # with 2 players left, 100 beats 0
        zero_vs_hundred = True
        for player in players.keys():
            if players[player]["number"] == HIGHEST_NUMBER:
                winners.append(player)
    elif valid:
        min_value = min(distances[player] for player in valid)
        closest = []
        for player in valid:
            if distances[player] == min_value:
                closest.append(player)
        # a tie for closest means nobody wins: the tied players lose a point too.
        if len(closest) == 1:
            winners = closest
        else:
            tied = closest

    # hitting the average exactly makes everyone else lose 2 points instead of 1
    exact_hit = len(winners) == 1 and not zero_vs_hundred and distances[winners[0]] == 0
    penalty = 2 if exact_hit else 1

    # update score for all players
    changes = {}
    for player in players.keys():
        if player in winners:
            changes[player] = 1
        else:
            changes[player] = -penalty
        players[player]["score"] = max(players[player]["score"] + changes[player], 0)

    result = {
        "average": average,
        "numbers": {},
        "differences": {},
        "changes": changes,
        "scores": {},
        "winners": winners,
        "tied": tied,
        "duplicates": duplicates,
        "exact_hit": exact_hit,
        "zero_vs_hundred": zero_vs_hundred,
    }
    for player in players.keys():
        result["numbers"][player] = players[player]["number"]
        result["differences"][player] = players[player]["difference"]
        result["scores"][player] = players[player]["score"]
        players[player]["number"] = None
    result["eliminated"] = eliminate_players(players)
    return result


def eliminate_players(players):
    eliminated_players = []
    for player in list(players.keys()):
        if players[player]["score"] <= 0:
            players.pop(player)
            eliminated_players.append(player)
    return eliminated_players


def remove_player(players, player):
    # used when someone disconnects in the middle of a game
    if player in players:
        players.pop(player)


def is_game_over(players):
    return len(players) <= 1


def winner(players):
    # None means the last players were eliminated together: a draw
    if len(players) == 1:
        return list(players.keys())[0]
    return None
