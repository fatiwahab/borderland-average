# Run with: python3 -m pytest test_game.py   (or: python3 test_game.py)
import game


def play(players, picks):
    for player, number in picks.items():
        game.submit_number(players, player, number)
    return game.play_round(players)


def test_closest_number_wins_not_highest():
    # the original script made 90 win here
    players = game.create_game(["Arisu", "Usagi", "Karube"])
    result = play(players, {"Arisu": 10, "Usagi": 46, "Karube": 91})
    assert result["average"] == 49
    assert result["winners"] == ["Usagi"]
    assert players["Usagi"]["score"] == 4
    assert players["Arisu"]["score"] == 2
    assert players["Karube"]["score"] == 2


def test_average_uses_remaining_players():
    players = game.create_game(["Arisu", "Usagi", "Karube"])
    players["Karube"]["score"] = 1
    play(players, {"Arisu": 20, "Usagi": 30, "Karube": 100})
    assert "Karube" not in players
    # 2 players left: average of 0 and 60 is 30, not 20 (which dividing by 3 would give)
    result = play(players, {"Arisu": 0, "Usagi": 60})
    assert result["average"] == 30


def test_tie_means_everyone_loses_a_point():
    # average is 50, so A and C are both 10 away
    players = game.create_game(["A", "B", "C", "D"])
    result = play(players, {"A": 40, "B": 0, "C": 60, "D": 100})
    assert result["winners"] == []
    assert result["tied"] == ["A", "C"]
    for player in players:
        assert players[player]["score"] == 2


def test_ties_need_no_float_luck():
    # average is 100/3 = 33.33..., so 0 and 66.66... would tie; 10, 20 and 70 don't
    players = game.create_game(["A", "B", "C"])
    result = play(players, {"A": 10, "B": 20, "C": 70})
    assert result["winners"] == ["B"]


def test_two_players_always_tie_and_count_down():
    players = game.create_game(["A", "B"])
    players["A"]["score"] = 2
    result = play(players, {"A": 10, "B": 90})
    assert result["tied"] == ["A", "B"]
    result = play(players, {"A": 10, "B": 90})
    assert result["eliminated"] == ["A"]
    assert game.is_game_over(players)
    assert game.winner(players) == "B"


def test_last_two_eliminated_together_is_a_draw():
    players = game.create_game(["A", "B"])
    for _ in range(3):
        result = play(players, {"A": 50, "B": 50})
    assert result["eliminated"] == ["A", "B"]
    assert result["scores"] == {"A": 0, "B": 0}
    assert game.is_game_over(players)
    assert game.winner(players) is None


def test_elimination_and_winner():
    players = game.create_game(["A", "B", "C"])
    players["C"]["score"] = 1
    result = play(players, {"A": 40, "B": 100, "C": 0})
    assert result["winners"] == ["A"]
    assert result["eliminated"] == ["C"]
    assert result["scores"]["C"] == 0
    assert not game.is_game_over(players)


def test_duplicate_numbers_are_invalid():
    # 30 is picked twice, so only Karube's 90 is valid and wins, even though it's further away
    players = game.create_game(["Arisu", "Usagi", "Karube"])
    result = play(players, {"Arisu": 30, "Usagi": 30, "Karube": 90})
    assert result["duplicates"] == ["Arisu", "Usagi"]
    assert result["winners"] == ["Karube"]
    assert result["changes"] == {"Arisu": -1, "Usagi": -1, "Karube": 1}


def test_duplicate_on_the_average_does_not_count():
    # 50 is exactly the average but picked twice, so it's invalid; 20 and 80 tie
    players = game.create_game(["A", "B", "C", "D"])
    result = play(players, {"A": 50, "B": 50, "C": 20, "D": 80})
    assert result["duplicates"] == ["A", "B"]
    assert result["winners"] == []
    assert result["tied"] == ["C", "D"]
    assert not result["exact_hit"]
    for player in players:
        assert players[player]["score"] == 2


def test_every_number_duplicated_means_nobody_wins():
    players = game.create_game(["A", "B", "C"])
    result = play(players, {"A": 10, "B": 10, "C": 10})
    assert result["winners"] == [] and result["tied"] == []
    for player in players:
        assert players[player]["score"] == 2


def test_exact_hit_makes_everyone_else_lose_two():
    players = game.create_game(["A", "B", "C"])
    result = play(players, {"A": 50, "B": 100, "C": 0})
    assert result["exact_hit"]
    assert result["winners"] == ["A"]
    assert result["changes"] == {"A": 1, "B": -2, "C": -2}
    assert players["A"]["score"] == 4 and players["B"]["score"] == 1


def test_exact_hit_never_goes_below_zero():
    players = game.create_game(["A", "B", "C"])
    players["B"]["score"] = 1
    result = play(players, {"A": 50, "B": 100, "C": 0})
    assert result["scores"]["B"] == 0
    assert result["eliminated"] == ["B"]


def test_two_players_100_beats_0():
    for picks in ({"A": 0, "B": 100}, {"A": 100, "B": 0}):
        players = game.create_game(["A", "B"])
        result = play(players, picks)
        hundred = "B" if picks["B"] == 100 else "A"
        assert result["zero_vs_hundred"]
        assert result["winners"] == [hundred]
        assert not result["exact_hit"]
        assert players[hundred]["score"] == 4


def test_0_and_100_only_special_with_two_players():
    # 3 players: average 50, so 0 and 100 are both 50 away; 51 is closest
    players = game.create_game(["A", "B", "C"])
    result = play(players, {"A": 0, "B": 100, "C": 51})
    assert not result["zero_vs_hundred"]
    assert result["winners"] == ["C"]


def test_numbers_reset_each_round():
    players = game.create_game(["A", "B"])
    play(players, {"A": 1, "B": 2})
    assert not game.all_submitted(players)
    game.submit_number(players, "A", 5)
    assert not game.all_submitted(players)
    game.submit_number(players, "B", 5)
    assert game.all_submitted(players)


def test_rejects_bad_input():
    players = game.create_game(["A", "B"])
    for bad in (-1, 101, 2.5, "7"):
        try:
            game.submit_number(players, "A", bad)
            assert False, f'{bad!r} should be rejected'
        except ValueError:
            pass
    try:
        game.create_game(["A", "A"])
        assert False, 'duplicate names should be rejected'
    except ValueError:
        pass


def test_remove_player_mid_round():
    players = game.create_game(["A", "B", "C"])
    game.submit_number(players, "A", 5)
    game.submit_number(players, "B", 5)
    game.remove_player(players, "C")
    assert game.all_submitted(players)


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
            print("passed", name)
