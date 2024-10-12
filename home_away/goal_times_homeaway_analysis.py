from statsbombpy import sb
import pandas as pd
import warnings
import matplotlib.pyplot as plt
import sys

from scipy.stats import norm
import numpy as np
from scipy.stats import mannwhitneyu

# Suppress the specific NoAuthWarning from statsbombpy
warnings.filterwarnings("ignore", message="credentials were not supplied. open data access only")

def make_df(competition_id, season_id):
    csv_name = f"goal-distribution/goals_competition{competition_id}_season{season_id}.csv"

    # get the data for all matches from considered competition and season
    matches = sb.matches(competition_id=competition_id, season_id=season_id)
    n_matches = matches.shape[0]
    goals_data = []
    # print(matches.columns)
    # print(matches.iloc[0,:])

    # Loop through each match to get the event data and filter for goals
    for i, match_id in enumerate(matches['match_id']):
        if i % 10 == 0:
            print(i, " / ", len(matches['match_id']))
        events = sb.events(match_id=match_id)
        home_team = matches['home_team'][i]
        away_team = matches['away_team'][i]

        # Filter for goals - either a shot with outcome goal or an own-goal
        # Check if 'shot_outcome' exists in the DataFrame columns
        if 'shot_outcome' in events.columns:
            goals = events[
                (events['shot_outcome'] == 'Goal') |
                (events['type'] == 'Own Goal For')            
            ]
        else:
            goals = events[
                (events['type'] == 'Own Goal For')            
            ]            

        for _, goal in goals.iterrows():
            goal_time = goal['minute']
            period = goal['period']
            if home_team == goal['team']:
                home = 1
            elif away_team == goal['team']:
                home = 0
            else:
                home = 2
            goals_data.append({
                'match_id': match_id,
                'period': period,
                'n_matches': n_matches,
                'goal_time': goal_time,
                'home': home,
            })
    # Convert the list to a DataFrame and save it as a csv
    goals_df = pd.DataFrame(goals_data)
    goals_df.to_csv(csv_name, index=False)

def make_df_tournament(competition_id, season_id):
    csv_name = f"goals_competition{competition_id}_season{season_id}.csv"

    # get the data for all matches from considered competition and season
    matches = sb.matches(competition_id=competition_id, season_id=season_id)
    goals_data = []

    # filter for group stage and knockout-games
    n_matches_group =  matches[matches['competition_stage'] == 'Group Stage'].shape[0]
    n_matches_ko =  matches[matches['competition_stage'] != 'Group Stage'].shape[0]
    # initialise a variable counting the number of matches going to extra-time:
    n_ET = 0

    # Loop through each match to get the event data and filter for goals
    for i, match in matches.iterrows():        
        if i % 10 == 0:
            print(i, " / ", len(matches['match_id']))
        
        match_id = match['match_id']
        events = sb.events(match_id=match_id)

        # indicator for match going to extra-time (period 3 is first half of extra-time)
        ET = (events[events['period'] == 3].shape[0] > 0)
        # increment counter for number of matches going to extra-time
        n_ET += ET

        # Filter for goals - either a shot with outcome goal or an own-goal
        # Check if 'shot_outcome' exists in the DataFrame columns
        if 'shot_outcome' in events.columns:
            goals = events[
                (events['shot_outcome'] == 'Goal') |
                (events['type'] == 'Own Goal For')
            ]
        else:
            goals = events[
                (events['type'] == 'Own Goal For')          
            ]   
        # remove penalty shoot-outs from goals
        goals = goals[goals['period'] < 5]

        for _, goal in goals.iterrows():
            goal_time = goal['minute']
            period = goal['period']
            stage = match['competition_stage']
            goals_data.append({
                'match_id': match_id,
                'period': period,
                'stage': stage,
                'goal_time': goal_time,
                'n_matches_group': n_matches_group,
                'n_matches_ko': n_matches_ko,
                'n_matches_ET': n_ET,
                'ET_match': ET
            })

    # Convert the list to a DataFrame and save it as a csv
    goals_df = pd.DataFrame(goals_data)
    goals_df.to_csv(csv_name, index=False)

def adjust_minutes(row):
    if row['period'] == 2:
        return row['goal_time'] + 15 
    elif row['period'] == 3:
        return row['goal_time'] + 30 
    elif row['period'] == 4:
        return row['goal_time'] + 45
    else:
        return row['goal_time']

# Make and save the data
season_id = 27
England_id = 2
Germany_id = 9
Spain_id = 11
France_id = 7
Italy_id = 12

# World Cups:
World_cup_id = 43
season_22 = 106
season_18 = 3
Euros_id = 55
season_20 = 43

CREATE_DATA = False

if CREATE_DATA:
    make_df(England_id, season_id)
    make_df(Germany_id, season_id)
    make_df(Spain_id, season_id)
    make_df(France_id, season_id)
    make_df(Italy_id, season_id)

    # make_df_tournament(World_cup_id, season_22)
    # make_df_tournament(World_cup_id, season_18)
    # make_df_tournament(Euros_id, season_20)

# load and join data
df_england = pd.read_csv(f"goal-distribution/goals_competition{England_id}_season{season_id}.csv")
df_germany = pd.read_csv(f"goal-distribution/goals_competition{Germany_id}_season{season_id}.csv")
df_spain = pd.read_csv(f"goal-distribution/goals_competition{Spain_id}_season{season_id}.csv")
df_france = pd.read_csv(f"goal-distribution/goals_competition{France_id}_season{season_id}.csv")
df_italy = pd.read_csv(f"goal-distribution/goals_competition{Italy_id}_season{season_id}.csv")
goals_clubs = pd.concat([df_england, df_germany, df_spain, df_france, df_italy])

# use the adjust_minutes fct to be able to appropriately plot the injury-time at the end of halves
goals_clubs['adjusted_goal_time'] = goals_clubs.apply(adjust_minutes, axis=1)

# compute number of matches for group stage, knockout, extra-time
n_matches = df_england['n_matches'][0]
n_matches += df_germany['n_matches'][0]
n_matches += df_spain['n_matches'][0]
n_matches += df_france['n_matches'][0]
n_matches += df_italy['n_matches'][0]

home_goals_df = goals_clubs[goals_clubs['home'] == 1]['goal_time'] 
away_goals_df = goals_clubs[goals_clubs['home'] == 0]['goal_time']

############## POISSON RATE TEST ##############

def poisson_rate_test(rate1, n1, rate2, n2):
    """
    Perform a two-sample Z-test for comparing two Poisson rates.
    
    rate1: Poisson rate (goals per match) for group 1 (e.g., home team)
    n1: Number of observations (matches) for group 1
    rate2: Poisson rate (goals per match) for group 2 (e.g., away team)
    n2: Number of observations (matches) for group 2
    
    Returns:
    Z-statistic and two-tailed p-value.
    """
    # Calculate the difference in rates and standard error of the difference
    diff_rate = rate1 - rate2
    std_error = np.sqrt(rate1 / n1 + rate2 / n2)
    
    # Calculate the Z-statistic
    z = diff_rate / std_error
    
    # Two-tailed p-value from Z-distribution
    p_value = 2 * norm.sf(np.abs(z))
    return z, p_value

# Calculate Poisson rates
rate_home = home_goals_df.shape[0] / n_matches
rate_away = away_goals_df.shape[0] / n_matches
# Perform the Poisson rate test
z_stat, p_value = poisson_rate_test(rate_home, n_matches, rate_away, n_matches)

print(f"Z-statistic: {z_stat:.4f}, p-value: {p_value}")

############## MANN-WHITNEY TEST ##############

# Perform Mann-Whitney U test
stat, p_value = mannwhitneyu(home_goals_df, away_goals_df, alternative='two-sided')

print(f'U Statistic: {stat}')
print(f'P-value: {p_value}')




