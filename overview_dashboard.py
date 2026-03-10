import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import create_engine
import schedule
import threading
import time
from datetime import datetime
import os

# =================================================
# SUPABASE DATABASE CONFIG
# =================================================

DATABASE_URL = "postgresql://postgres.vgffglhsnxdfygtgyepu:Limlimlimwee2@aws-1-ap-southeast-1.pooler.supabase.com:5432/postgres"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)

CARBON_FACTOR = 0.408

# =================================================
# SYSTEM DEFINITIONS
# =================================================

systems = {
    "bss": {"label": "Boiler & Steam", "name": "Boiler & Steam System (BSS)", "scope": "Scope 1 – Direct Emissions"},
    "hps": {"label": "Heat Pump", "name": "Heat Pump System (HPS)", "scope": "Scope 2 – Electricity"},
    "ps": {"label": "Pump System", "name": "Pump System (PS)", "scope": "Scope 2 – Electricity"},
    "fs": {"label": "Fan System", "name": "Fan System (FS)", "scope": "Scope 2 – Electricity"},
    "ac": {"label": "Air Compressor", "name": "Air Compressor System (ACIACS)", "scope": "Scope 2 – Electricity"},
    "ls": {"label": "Lighting System", "name": "Lighting System (LS)", "scope": "Scope 2 – Electricity"},
}

SYSTEM_OPTIONS = [{"label": v["label"], "value": v["name"]} for v in systems.values()]
ALL_SYSTEM_NAMES = [v["name"] for v in systems.values()]

# =================================================
# KPI CARD
# =================================================

def kpi_card(title, value, unit, color="#1F4FD8"):
    return html.Div(
        style={
            "flex": "1",
            "background": "white",
            "padding": "18px",
            "borderRadius": "12px",
            "boxShadow": "0 4px 10px rgba(0,0,0,0.08)",
            "textAlign": "center",
        },
        children=[
            html.P(title, style={"margin": "0", "color": "#777"}),
            html.H2(f"{value:,.0f}" if isinstance(value, (int, float)) else value,
                    style={"margin": "5px 0", "color": color}),
            html.P(unit, style={"margin": "0", "color": "#999"}),
        ],
    )

# =================================================
# DATE RANGE
# =================================================

bounds = pd.read_sql(
    "SELECT MIN(timestamp) AS min_d, MAX(timestamp) AS max_d FROM energy_data",
    engine
)

MIN_DATE = bounds.loc[0, "min_d"]
MAX_DATE = bounds.loc[0, "max_d"]

# =================================================
# FETCH DATA
# =================================================

def fetch_data(start_date, end_date, system_list, agg_level):

    trunc_unit = "day" if agg_level == "daily" else "month"

    sql = f"""
    SELECT
        date_trunc('{trunc_unit}', timestamp)::date AS date,
        system,
        SUM(energy_kwh) AS energy_kwh,
        SUM(energy_kwh) * {CARBON_FACTOR} AS carbon_kgco2
    FROM energy_data
    WHERE timestamp BETWEEN %(start)s AND %(end)s
    """

    params = {"start": start_date, "end": end_date}

    if system_list:
        sql += " AND system = ANY(%(systems)s)"
        params["systems"] = system_list

    sql += """
    GROUP BY date, system
    ORDER BY date;
    """

    return pd.read_sql(sql, engine, params=params)

# =================================================
# AUTOMATED DAILY EXPORT
# =================================================

def automated_daily_export():

    today = datetime.today().date()
    df = fetch_data(today, today, ALL_SYSTEM_NAMES, "daily")

    filename = f"ems_daily_report_{today}.csv"
    df.to_csv(filename, index=False)

    print(f"Daily EMS report exported: {filename}")

schedule.every().day.at("23:59").do(automated_daily_export)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(60)

threading.Thread(target=run_scheduler, daemon=True).start()

# =================================================
# DASH APP
# =================================================

app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server
app.title = "SIT Energy Management System"

# =================================================
# LAYOUT
# =================================================

app.layout = html.Div(
    style={"display": "flex", "fontFamily": "Segoe UI", "background": "#F4F6FB"},
    children=[

        dcc.Store(id="active-view", data="overview"),

        # SIDEBAR
        html.Div(
            style={
                "width": "260px",
                "background": "#1F4FD8",
                "color": "white",
                "padding": "20px",
                "height": "100vh",
                "overflowY": "auto"
            },
            children=[
                html.H3("EMS Dashboard"),
                html.P("System-Based Reporting"),
                html.Hr(),

                html.Button("Overview", id="nav-overview",
                            style={"width": "100%", "marginBottom": "10px"}),

                html.Hr(),
                html.P("Systems", style={"fontWeight": "bold"}),

                *[
                    html.Button(v["label"], id=f"nav-{k}",
                                style={"width": "100%", "marginBottom": "6px"})
                    for k, v in systems.items()
                ],

                html.Hr(),
                html.P("System Comparison", style={"fontWeight": "bold"}),

                dcc.Dropdown(
                    id="compare-a",
                    options=SYSTEM_OPTIONS,
                    placeholder="Select System A",
                    style={"marginBottom": "6px", "color": "black"}
                ),

                dcc.Dropdown(
                    id="compare-b",
                    options=SYSTEM_OPTIONS,
                    placeholder="Select System B",
                    style={"marginBottom": "10px", "color": "black"}
                ),

                html.Button("Export Current View (CSV)", id="export-btn", style={"width": "100%"}),
                dcc.Download(id="download-report")
            ]
        ),

        # MAIN
        html.Div(
            style={"flex": "1", "padding": "25px"},
            children=[

                html.Div(
                    style={
                        "background": "white",
                        "padding": "15px",
                        "borderRadius": "12px",
                        "boxShadow": "0 4px 10px rgba(0,0,0,0.08)"
                    },
                    children=[
                        html.H2("Singapore Institute of Technology",
                                style={"margin": "0", "color": "#1F4FD8"}),
                        html.P("Energy Efficiency Technology Laboratory – Energy Management System",
                               style={"margin": "0", "color": "#555"})
                    ]
                ),

                html.Br(),

                html.Div(
                    style={"display": "flex", "gap": "20px"},
                    children=[
                        dcc.DatePickerRange(
                            id="date-range",
                            min_date_allowed=MIN_DATE,
                            max_date_allowed=MAX_DATE,
                            start_date=MIN_DATE,
                            end_date=MAX_DATE
                        ),

                        dcc.RadioItems(
                            id="agg-level",
                            options=[
                                {"label": "Daily", "value": "daily"},
                                {"label": "Monthly", "value": "monthly"}
                            ],
                            value="monthly",
                            inline=True
                        )
                    ]
                ),

                html.Br(),
                html.Div(id="page-content")
            ]
        )
    ]
)

# =================================================
# MAIN CALLBACK
# =================================================

@app.callback(
    Output("page-content", "children"),
    Output("active-view", "data"),
    Input("nav-overview", "n_clicks"),
    *[Input(f"nav-{k}", "n_clicks") for k in systems],
    Input("compare-a", "value"),
    Input("compare-b", "value"),
    Input("date-range", "start_date"),
    Input("date-range", "end_date"),
    Input("agg-level", "value"),
    State("active-view", "data"),
)

def render_page(_, *args):

    compare_a, compare_b, start, end, agg, active_view = args[-6:]

    ctx = dash.callback_context
    trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

    if trigger == "nav-overview":
        active_view = "overview"
    elif trigger and trigger.startswith("nav-"):
        key = trigger.replace("nav-", "")
        if key in systems:
            active_view = key
    elif compare_a and compare_b:
        active_view = "compare"

    # ================= OVERVIEW =================

    if active_view == "overview":

        df = fetch_data(start, end, None, agg)

        total_energy = df["energy_kwh"].sum()
        total_carbon = df["carbon_kgco2"].sum()

        days = max((pd.to_datetime(end) - pd.to_datetime(start)).days, 1)

        avg_energy = total_energy / days
        avg_carbon = total_carbon / days

        energy_pie = df.groupby("system", as_index=False)["energy_kwh"].sum()
        carbon_pie = df.groupby("system", as_index=False)["carbon_kgco2"].sum()

        # Top system
        top_system = energy_pie.sort_values("energy_kwh", ascending=False).iloc[0]

        # Carbon reduction calculation
        prev_start = pd.to_datetime(start) - (pd.to_datetime(end) - pd.to_datetime(start))
        prev_end = pd.to_datetime(start)

        prev_df = fetch_data(prev_start, prev_end, None, agg)

        carbon_reduction = prev_df["carbon_kgco2"].sum() - total_carbon

        trend = df.groupby("date", as_index=False).sum()

        trend_fig = go.Figure()

        trend_fig.add_bar(x=trend["date"], y=trend["energy_kwh"], name="Energy")

        trend_fig.add_scatter(
            x=trend["date"],
            y=trend["carbon_kgco2"],
            yaxis="y2",
            name="Carbon"
        )

        trend_fig.update_layout(
            yaxis2=dict(overlaying="y", side="right"),
            template="plotly_white"
        )

        energy_pie_fig = go.Figure(
            data=[go.Pie(labels=energy_pie["system"], values=energy_pie["energy_kwh"], hole=0.3)]
        )

        carbon_pie_fig = go.Figure(
            data=[go.Pie(labels=carbon_pie["system"], values=carbon_pie["carbon_kgco2"], hole=0.3)]
        )

        return html.Div([

            html.H3("EMS Overview & Carbon Reporting"),

            html.Div(
                style={"display": "flex", "gap": "20px", "marginBottom": "20px"},
                children=[
                    kpi_card("Total Energy", total_energy, "kWh"),
                    kpi_card("Total Carbon", total_carbon, "kgCO₂", "#E67E22"),
                    kpi_card("Avg Daily Energy", avg_energy, "kWh/day", "#27AE60"),
                    kpi_card("Avg Daily Carbon", avg_carbon, "kgCO₂/day", "#8E44AD"),
                    kpi_card("Top Energy System", top_system["system"], "Highest Consumption", "#C0392B"),
                    kpi_card("Carbon Reduction", carbon_reduction, "kgCO₂", "#16A085"),
                ]
            ),

            html.Div(
                style={"background": "white", "padding": "15px", "borderRadius": "12px", "marginBottom": "20px"},
                children=[dcc.Graph(figure=trend_fig)]
            ),

            html.Div(
                style={"display": "flex", "gap": "20px"},
                children=[

                    html.Div(
                        style={"flex": "1", "background": "white", "padding": "15px", "borderRadius": "12px"},
                        children=[dcc.Graph(figure=energy_pie_fig)]
                    ),

                    html.Div(
                        style={"flex": "1", "background": "white", "padding": "15px", "borderRadius": "12px"},
                        children=[dcc.Graph(figure=carbon_pie_fig)]
                    ),

                ]
            )

        ]), active_view

    # ================= SINGLE SYSTEM =================

    system = systems.get(active_view)

    if system:

        df = fetch_data(start, end, [system["name"]], agg)

        total_energy = df["energy_kwh"].sum()
        total_carbon = df["carbon_kgco2"].sum()

        days = max((pd.to_datetime(end) - pd.to_datetime(start)).days, 1)

        avg_energy = total_energy / days
        avg_carbon = total_carbon / days

        trend = df.groupby("date", as_index=False).sum()

        fig = go.Figure()

        fig.add_bar(x=trend["date"], y=trend["energy_kwh"], name="Energy")

        fig.add_scatter(
            x=trend["date"],
            y=trend["carbon_kgco2"],
            yaxis="y2",
            name="Carbon"
        )

        fig.update_layout(
            yaxis2=dict(overlaying="y", side="right"),
            template="plotly_white"
        )

        return html.Div([

            html.H3(system["name"]),
            html.P(system["scope"], style={"fontWeight": "bold", "color": "#E67E22"}),

            html.Div(
                style={"display": "flex", "gap": "20px", "marginBottom": "20px"},
                children=[
                    kpi_card("Total Energy", total_energy, "kWh"),
                    kpi_card("Total Carbon", total_carbon, "kgCO₂", "#E67E22"),
                    kpi_card("Avg Daily Energy", avg_energy, "kWh/day", "#27AE60"),
                    kpi_card("Avg Daily Carbon", avg_carbon, "kgCO₂/day", "#8E44AD"),
                ]
            ),

            html.Div(
                style={"background": "white", "padding": "15px", "borderRadius": "12px"},
                children=[dcc.Graph(figure=fig)]
            )

        ]), active_view

    return html.Div(), active_view

# =================================================
# RUN APP
# =================================================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8050))
    app.run_server(host="0.0.0.0", port=port)