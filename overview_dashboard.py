import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import create_engine

# =================================================
# SUPABASE DATABASE CONNECTION
# =================================================

DATABASE_URL = "postgresql://postgres:Limlimlimwee2#@db.vgffglhsnxfdygtygepu.supabase.co:5432/postgres"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)

# =================================================
# DASH APP
# =================================================

app = dash.Dash(__name__)
server = app.server

# =================================================
# LOAD DATA FUNCTION
# =================================================

def load_data():
    query = "SELECT * FROM energy_data"
    df = pd.read_sql(query, engine)
    return df

# =================================================
# SYSTEM LIST
# =================================================

systems = [
    "Boiler & Steam System (BSS)",
    "Heat Pump System (HPS)",
    "Pump System (PS)",
    "Fan System (FS)",
    "Air Compressor System (ACIACS)",
    "Lighting System (LS)"
]

# =================================================
# LAYOUT
# =================================================

app.layout = html.Div([

    html.H2("Energy System Dashboard"),

    html.Div([
        html.Div([
            html.H4("Total Energy"),
            html.H2(id="total-energy"),
            html.P("kWh")
        ], style={"width":"40%", "display":"inline-block"}),

        html.Div([
            html.H4("Total Carbon"),
            html.H2(id="total-carbon"),
            html.P("kgCO₂")
        ], style={"width":"40%", "display":"inline-block"})
    ]),

    dcc.Graph(id="energy-chart"),

    dcc.Interval(
        id="refresh",
        interval=5*1000,
        n_intervals=0
    )
])

# =================================================
# CALLBACK
# =================================================

@app.callback(
    Output("total-energy","children"),
    Output("total-carbon","children"),
    Output("energy-chart","figure"),
    Input("refresh","n_intervals")
)

def update_dashboard(n):

    df = load_data()

    if df.empty:
        return 0,0,go.Figure()

    total_energy = df["energy_kwh"].sum()

    # Carbon factor example
    carbon_factor = 0.408
    total_carbon = total_energy * carbon_factor

    # System breakdown
    system_energy = df.groupby("system")["energy_kwh"].sum()

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=system_energy.index,
        y=system_energy.values,
        name="Energy (kWh)"
    ))

    fig.update_layout(
        title="Energy Consumption by System",
        xaxis_title="System",
        yaxis_title="Energy (kWh)"
    )

    return round(total_energy,2), round(total_carbon,2), fig


# =================================================
# RUN SERVER
# =================================================

if __name__ == "__main__":
    app.run_server(debug=True)