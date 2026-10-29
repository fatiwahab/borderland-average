#Alice in borderlands - Complete Game
print("Players are eliminated when their score reaches 0. All players start with a score of 3")
players = {}
total_players = int(input(f'Enter the number of players: '))

def create_game():
    #populate dictionary with each player's name and game stats
    for i in range (1, total_players+1):
        player_name = input(f'Enter a name for player {i}: ')
        score = 3
        number = 0
        difference = 0
        players[player_name] = { "score":score, "number":number, "difference":difference}

def game_round():
    #get number from each player 
    num = 0
    sum_num = 0
    diff_list = []
    for player in players.keys():
        num = int(input(f'Enter a number for {player}: '))
        players[player]["number"] = num
    #find average of the numbers
        i = players[player]["number"]
        sum_num += i
    average = sum_num / total_players
    # find difference between number and average and save to list
    for player in players.keys():
        j = average - (players[player]["number"])
        diff_list.append(j)
        players[player]["difference"] = j
    # find smallest value in list
    min_value = min(diff_list)
    # update score for all players
    for player in players.keys():
        if min_value == players[player]["difference"]:
            print(f'{player} wins this round!')
            players[player]["score"] += 1
        elif min_value != players[player]["difference"]:
            players[player]["score"] -= 1
        #show current score for all players after the score has been updated
    for player in players.keys():
        print(f'Current Score is: {player}: {players[player]["score"]}')
    eliminate_players()

def eliminate_players():
# Update score of players
    eliminated_players = 0
    for player in list(players.keys()):
        if players[player]["score"] == 0:
            eliminated = players.pop(player)
            print(f'{player} has been eliminated')
            eliminated_players +=1
    if eliminated_players == 0:
        print(f'No players have been eliminated in this round')
        print(f'Number of players left {len(players)}')
    if len(players) == 1:
        print(f'{list(players.keys())[0]} wins the game')
    

create_game()
while len(players) > 1:
    game_round()
#game_round()

