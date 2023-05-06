# https://developer.riotgames.com/apis#summoner-v4
# https://developer.riotgames.com/apis#match-v5/
# Get new api key from https://developer.riotgames.com/

import datetime
import calendar
from tqdm import tqdm
import requests
from collections import Counter
import pdb

# Get new api key from https://developer.riotgames.com/
with open('apikey.txt') as infile:
    API_KEY = infile.read().strip()

USERNAME = 'muakasan'
TARGET_CHAMPION = None # "fiddlesticks"

# Start of the ranked season
DAY = 10
MONTH = 1
YEAR = 2023

# Number of possible duoqueue "partners" to print
NUM_PARTICIPANTS = 10
COUNT = 20

# https://static.developer.riotgames.com/docs/lol/queues.json
QUEUE_ID = 420 # 420 for ranked

def get_my_puuid(username):
    r = requests.get(f'https://na1.api.riotgames.com/lol/summoner/v4/summoners/by-name/{username}', params={
            'api_key': API_KEY,
        })
    my_puuid = r.json()['puuid']
    # print(my_puuid)
    return my_puuid

# Collects match data from API using pagination
def get_matches(puuid):
    # Convert the start of season to unix timestamp value
    t = datetime.datetime(YEAR, MONTH, DAY, 0, 0, 0)
    start_season_epoch = calendar.timegm(t.timetuple())
    print(start_season_epoch) # 1673308800 for 2023 season

    start_index = 0
    matches = []
    while True:
        r = requests.get(
            f'https://americas.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids',
            params={
                'api_key': API_KEY,
                'queue': QUEUE_ID,
                'startTime': start_season_epoch,
                'start': start_index,
                'count': COUNT,
            })
        start_index += COUNT
        new_matches = r.json()
        if len(new_matches) == 0:
            break
        matches.extend(new_matches)
    return matches

# Goes through fetched matches and updates dictionary mapping teammates to win loss counts
def aggregate_winlosses(my_puuid, matches):
    teammates_count = Counter()
    teammates_wl = Counter()

    num_matches = 0
    for m_id in tqdm(matches):
        r = requests.get(
        f'https://americas.api.riotgames.com/lol/match/v5/matches/{m_id}',
        params={
            'api_key': API_KEY,
        })
        
        j = r.json()
        if 'info' not in j:
            print(j)
            print('API Error?')
            continue
        info = j['info']

        # Ignores games which are shorter than 10 minutes
        # TODO: handle this? "Prior to patch 11.20, this field returns the game length in milliseconds calculated from gameEndTimestamp - gameStartTimestamp. Post patch 11.20, this field returns the max timePlayed of any participant in the game in seconds, which makes the behavior of this field consistent with that of match-v4. The best way to handling the change in this field is to treat the value as milliseconds if the gameEndTimestamp field isn't in the response and to treat the value as seconds if gameEndTimestamp is in the response."
        if info['gameDuration'] < 600: # 10 minutes in seconds
            continue
        num_matches += 1
        # gameCreation # unix timestamp
        participants = j['info']['participants']
        
        # Groups players by winning and losing team
        teams = {
            True: [],
            False: []
        }

        right_champion = True
        for p in participants:
            puuid = p['puuid']
            win = p['win'] # Whether or not "puuid" won the match
            if puuid == my_puuid:
                # Checks if the user's champion is the "filter" champion
                champion_name = p['championName']
                if (TARGET_CHAMPION is not None) and (champion_name.lower() != TARGET_CHAMPION.lower()):
                    right_champion = False
                    break
                i_won = win # i_won represents if the user won the match or not
            teams[win].append(puuid)

        # We skip the match if the user's champion is not the "filter" champion 
        if not right_champion:
            continue

        # Go through all the teammates of the user and updates the dictionary
        for p in teams[i_won]:
            teammates_wl[(p, i_won)] += 1
            teammates_count[p] += 1

    print(f'Found {num_matches} valid matches')
    return teammates_wl, teammates_count

# Fetches usernames from API and calculates winrate based on aggregated dictionaries
def generate_teammate_data(my_puuid, username, teammates_wl, teammates_count):
    duo_wins = 0
    duo_games = 0

    teammate_data = []
    for puuid, count in tqdm(teammates_count.most_common(NUM_PARTICIPANTS + 1)):
        r = requests.get(
            f'https://na1.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}',
            params={
                'api_key': API_KEY,
            })

        winrate = teammates_wl[(puuid, True)] / teammates_count[puuid]
        teammate_data.append((r.json()['name'], teammates_count[puuid], winrate))

        # Handle removing duoq games from soloq statistic
        if (teammates_count[puuid] > 1) and (puuid != my_puuid):
            duo_wins += teammates_wl[(puuid, True)]
            duo_games += teammates_count[puuid]

    # Compute solo statistics
    # NOTE: false-negative if you only duoq with someone once 
    # and false-positive if riot randomly matches you with the same random teammate more than once
    solo_wins = teammates_wl[(my_puuid, True)] - duo_wins
    solo_games = teammates_count[my_puuid] - duo_games
    solo_winrate = solo_wins / solo_games

    teammate_data.insert(1, (f'{username} "solo"', solo_games, solo_winrate))

    return teammate_data




def main():
    my_puuid = get_my_puuid(USERNAME)
    matches = get_matches(my_puuid)
    teammates_wl, teammates_count = aggregate_winlosses(my_puuid, matches)
    teammate_data = generate_teammate_data(my_puuid, USERNAME, teammates_wl, teammates_count)

    for row in teammate_data:
        print(row[0], row[1], row[2])

if __name__ == '__main__':
    main()
