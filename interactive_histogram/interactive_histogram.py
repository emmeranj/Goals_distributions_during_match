from dash import Dash, html, dcc
from dash import html, dcc
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# Function to adjust goal times based on the period (half or extra time)
def adjust_minutes(row):
    if row['period'] == 2:
        return row['goal_time'] + 15  # Adjust by adding 15 minutes for second half
    else:
        return row['goal_time']  # No adjustment needed for first half

# Season and league IDs for fetching data from CSVs
season_id = 27
England_id = 2
Germany_id = 9
Spain_id = 11
France_id = 7
Italy_id = 12

# Load goal data for each league from CSV files, see goal_times.py for creating the datasets
df_england = pd.read_csv(f"goals_competition{England_id}_season{season_id}.csv")
df_germany = pd.read_csv(f"goals_competition{Germany_id}_season{season_id}.csv")
df_spain = pd.read_csv(f"goals_competition{Spain_id}_season{season_id}.csv")
df_france = pd.read_csv(f"goals_competition{France_id}_season{season_id}.csv")
df_italy = pd.read_csv(f"goals_competition{Italy_id}_season{season_id}.csv")

# Create a dictionary mapping league names to their respective dataframes
league_data = {
    'England': df_england,
    'Germany': df_germany,
    'Spain': df_spain,
    'France': df_france,
    'Italy': df_italy
}

# Dictionary to map bin widths to corresponding y-axis range (for goals per match)
YAXIS = {
    1: dict(range=[0, 0.063]),
    3: dict(range=[0, 0.2]),
    5: dict(range=[0, 0.25]),
    15: dict(range=[0, 0.6]),
    45: dict(range=[0, 2]),
}

# Dictionary to map bin widths to corresponding y-axis range (for total goals)
YAXIS_total = {
    1: dict(range=[0, 25]),
    3: dict(range=[0, 60]),
    5: dict(range=[0, 100]),
    15: dict(range=[0, 210]),
    45: dict(range=[0, 600]),
}


#########################################################
############ CREATING THE INTERACTIVE PLOT ##############
#########################################################

# Initialize the Dash app
app = Dash(__name__)
server = app.server  # For deploying the app later

# Define the layout of the app
app.layout = html.Div([
    # Graph to display the histogram
    dcc.Graph(id="graph"),
    
    # Slider to select the bin width for the histogram
    html.P("Select Bin Width:"),
    dcc.Slider(
        id="bin-width-slider",  # ID for callback
        value=15, step=None,  # Default value 15, no intermediate steps
        marks={1: '1', 3: '3', 5: '5', 15: '15', 45: '45'},  # Discrete options
    ),

    # RadioItems for selecting which league's data to show
    html.Div([
        html.Label('Select League:'),
        dcc.RadioItems(
            id='league-selector',  # ID for callback
            options=[{'label': country, 'value': country} for country in league_data.keys()],  # List of leagues
            value='England',  # Default selected league
            labelStyle={'display': 'block'}  # Display options vertically
        ),
    ], style={'paddingTop': '20px', 'paddingLeft': '20px'}),  # Styling for padding

    # RadioItems for toggling between weighted (goals per match) and non-weighted (total goals) histograms
    html.Div([
        html.Label('Y-axis:'),
        dcc.RadioItems(
            id='weight-toggle',  # ID for callback
            options=[
                {'label': 'Total goals', 'value': 'not_weighted'},  # Option for total goals
                {'label': 'Goals / match', 'value': 'weighted'}  # Option for goals per match
            ],
            value='weighted'  # Default to weighted histogram
        ),
    ], style={'paddingTop': '20px', 'paddingLeft': '20px'}),  # Styling for padding
])

# Callback to update the graph based on user input
@app.callback(
    Output("graph", "figure"),  # Output: Update the 'figure' of the graph
    [Input("league-selector", "value"),  # Input: Selected league
     Input("bin-width-slider", "value"),  # Input: Selected bin width
     Input("weight-toggle", "value")]  # Input: Weighted or not
)
def update_histogram(selected_league, bin_width, weight_toggle):
    # Filter data for the selected league
    filtered_df = league_data[selected_league]
    filtered_df['adjusted_goal_time'] = filtered_df.apply(adjust_minutes, axis=1)  # Adjust goal times
    n_matches = league_data[selected_league]['n_matches'][0]  # Get the number of matches in the league
    
    # Extract goal times after adjustment
    data = filtered_df['adjusted_goal_time']
    
    # Define bin edges based on the selected bin width
    bin_edge_H1 = list(range(0, 46, bin_width))  # First half bins
    bin_edge_H2 = list(range(60, 105, bin_width))  # Second half bins
    if bin_width == 1:
        bin_edges = list(range(0, 121, 1))  # Special case for 1-minute bins
    else:
        bin_edges = bin_edge_H1 + bin_edge_H2 + [105, 120]  # Combine half bins and extra time

    # Initialize an empty figure
    fig = go.Figure()
    
    # Add histogram trace depending on whether weighted or not
    if weight_toggle == 'weighted':
        # Weighted histogram (goals per match)
        hist_data, hist_edges = np.histogram(data, bins=bin_edges, weights=[1/n_matches] * len(data))
        yaxis_title = 'Goals per match'
        yaxis = YAXIS[bin_width]  # Use predefined y-axis range for goals per match
    else:
        # Non-weighted histogram (total goals)
        hist_data, hist_edges = np.histogram(data, bins=bin_edges)
        yaxis_title = 'Total Goals'
        yaxis = YAXIS_total[bin_width]  # Use predefined y-axis range for total goals

    # Create hover text for each bin (showing interval)
    if bin_width == 1:
        # For 1-minute bins, show precise intervals
        hover_text = [f'{bin_edges[i]} - {bin_edges[i+1]}' for i in range(60)]
        hover_text += [f'{bin_edges[i] - 15} - {bin_edges[i+1] - 15}' for i in range(60, len(bin_edges) - 1)]
    else:
        # For larger bins, show general intervals (with adjustments for injury time)
        hover_text = [f'{bin_edge_H1[i]} - {bin_edge_H1[i+1]}' for i in range(len(bin_edge_H1) - 1)]
        hover_text += ["45+"]
        hover_text += [f'{bin_edge_H2[i] - 15} - {bin_edge_H2[i+1] - 15}' for i in range(len(bin_edge_H2) - 1)]
        hover_text += [f'{bin_edge_H2[-1] - 15} - 90']
        hover_text += ["90+"]

    # Add the bar trace for the histogram
    fig.add_trace(go.Bar(
        x=[(bin_edges[i] + bin_edges[i+1]) / 2 for i in range(len(bin_edges) - 1)],  # Center of each bin
        y=hist_data,  # Heights of the bars (histogram counts)
        width=[bin_edges[i+1] - bin_edges[i] for i in range(len(bin_edges) - 1)],  # Width of each bin
        marker_color='#6096BA',  # Bar color
        hovertemplate='<b>Interval:</b> %{text}<br>' +  # Custom hover text format
                      '<b>Count:</b> %{y}<br>' +
                      '<extra></extra>',
        text=hover_text  # Text for hover
    ))

    # Update the layout of the figure (title, axis labels, tick marks, etc.)
    fig.update_layout(
        title=f'Goals Distribution - {selected_league}',  # Title of the plot
        xaxis_title='Minute of Goal',  # X-axis label
        yaxis_title=yaxis_title,  # Y-axis label (either "Goals per match" or "Total Goals")
        xaxis=dict(
            range=[0, 120],  # Set the range for the x-axis (minutes)
            title='Minute of Goal',  # Title for x-axis
            tickvals=[0, 15, 30, 45, 52.5, 60, 75, 90, 105, 112.5],  # Custom tick values for halves and extra time
            ticktext=['0', '15', '30', '45', '45+', '45', '60', '75', '90', '90+'],  # Custom tick labels
        ),
        yaxis=yaxis  # Set the y-axis limits based on the bin width
    )
    
    return fig  # Return the updated figure for display

# Run the app
if __name__ == '__main__':
    app.run_server(debug=True)  # Start the server for the Dash app in debug mode
