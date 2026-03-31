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
import random   

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
# INSERT DATA 
# =================================================

def insert_energy_data():
    now = datetime.now()

    data = []

    for system in ALL_SYSTEM_NAMES:
        energy = round(random.uniform(5, 50), 2)

        data.append({
            "timestamp": now,
            "system": system,
            "energy_kwh": energy
        })

    df = pd.DataFrame(data)

    df.to_sql(
        "energy_data",
        engine,
        if_exists="append",
        index=False
    )

    print(f"Inserted data at {now}")

# =================================================
# KPI CARD
# =================================================

def kpi_card(title, value, unit, color="#1F4FD8"):
    return html.Div(
        className="kpi-card",
        style={
            "flex": "1",
            "background": "white",
            "padding": "20px",
            "borderRadius": "16px",
            "boxShadow": "0 6px 18px rgba(0,0,0,0.08)",
            "textAlign": "center",
            "transition": "all 0.2s ease",
            "cursor": "pointer"
        },
        children=[
            html.P(title, style={"margin": "0", "color": "#777"}),
            html.H2(f"{value:,.0f}" if isinstance(value,(int,float)) else value,
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

    if df.empty:
        print("No data available for daily report.")
        return

    df["report_date"] = today

    df = df[["report_date", "system", "energy_kwh", "carbon_kgco2"]]

    df.to_sql(
        "daily_reports",
        engine,
        if_exists="append",
        index=False
    )

    print(f"Daily report stored in database for {today}")

schedule.every().day.at("23:59").do(automated_daily_export)


schedule.every(14).minutes.do(insert_energy_data)

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
# ================================
# ADD THIS AFTER app = dash.Dash(...)
# ================================
app.index_string = '''
<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>EMS Dashboard</title>
        {%favicon%}
        {%css%}
        <style>
            body {
                background-color: #F4F6FB;
            }

            .graph-card {
                transition: transform 0.25s ease, box-shadow 0.25s ease;
                cursor: pointer;
            }

            .graph-card:hover {
                transform: scale(1.04);
                box-shadow: 0 12px 30px rgba(0,0,0,0.2);
                z-index: 10;
            }

            .kpi-card:hover {
                transform: translateY(-4px);
                box-shadow: 0 10px 25px rgba(0,0,0,0.15);
            }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>
'''
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
    Output("page-content","children"),
    Output("active-view","data"),
    Input("nav-overview","n_clicks"),
    *[Input(f"nav-{k}","n_clicks") for k in systems],
    Input("compare-a","value"),
    Input("compare-b","value"),
    Input("date-range","start_date"),
    Input("date-range","end_date"),
    Input("agg-level","value"),
    State("active-view","data"),
)

def render_page(_, *args):

    compare_a, compare_b, start, end, agg, active_view = args[-6:]

    ctx = dash.callback_context
    trigger = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

    if trigger == "nav-overview":
        active_view = "overview"

    elif trigger and trigger.startswith("nav-"):
        key = trigger.replace("nav-","")
        if key in systems:
            active_view = key

    elif compare_a and compare_b:
        active_view = "compare"

    # ================= COMPARISON =================
    if active_view == "compare" and compare_a and compare_b:

        df = fetch_data(start,end,[compare_a,compare_b],agg)

        trend = df.groupby(["date","system"],as_index=False).sum()

        fig = go.Figure()
        fig.update_layout(
            template="plotly_white",
            hovermode="x unified",
            transition=dict(duration=500, easing="cubic-in-out"),
            margin=dict(l=20, r=20, t=40, b=20),
            font=dict(size=14),
        )
        for s in [compare_a,compare_b]:
            s_df = trend[trend["system"]==s]

            fig.add_bar(
                x=s_df["date"],
                y=s_df["energy_kwh"],
                name=s
            )

        fig.update_layout(
            title="System Energy Comparison",
            yaxis_title="Energy (kWh)",
            barmode="group",
            template="plotly_white"
        )

        # KPI
        total_energy_a = df[df["system"]==compare_a]["energy_kwh"].sum()
        total_energy_b = df[df["system"]==compare_b]["energy_kwh"].sum()

        total_carbon_a = df[df["system"]==compare_a]["carbon_kgco2"].sum()
        total_carbon_b = df[df["system"]==compare_b]["carbon_kgco2"].sum()

        higher_system = compare_a if total_energy_a > total_energy_b else compare_b

        return html.Div([
            html.H3("System Comparison"),

            html.Div(
                style={"display":"flex","gap":"20px","marginBottom":"20px"},
                children=[
                    kpi_card(f"{compare_a} Energy", total_energy_a, "kWh"),
                    kpi_card(f"{compare_b} Energy", total_energy_b, "kWh"),
                    kpi_card(f"{compare_a} Carbon", total_carbon_a, "kgCO₂", "#E67E22"),
                    kpi_card(f"{compare_b} Carbon", total_carbon_b, "kgCO₂", "#E67E22"),
                    kpi_card("Higher Consumption", higher_system, "System", "#C0392B"),
                ]
            ),

            html.Div(
                className="graph-card",
                style={
                    "background": "white",
                    "padding": "15px",
                    "borderRadius": "16px",
                    "boxShadow": "0 6px 18px rgba(0,0,0,0.08)",
                },
                children=[
                    dcc.Graph(
                        figure=fig,
                        config={"displayModeBar": False},
                        style={"height": "450px"}  # BIGGER GRAPH
                    )
                ]
            )

        ]), active_view

    # ================= OVERVIEW =================

    if active_view == "overview":

        df = fetch_data(start,end,None,agg)

        total_energy = df["energy_kwh"].sum()
        total_carbon = df["carbon_kgco2"].sum()

        days = max((pd.to_datetime(end)-pd.to_datetime(start)).days,1)

        avg_energy = total_energy/days
        avg_carbon = total_carbon/days

        energy_pie = df.groupby("system",as_index=False)["energy_kwh"].sum()
        carbon_pie = df.groupby("system",as_index=False)["carbon_kgco2"].sum()

        top_system = energy_pie.sort_values("energy_kwh",ascending=False).iloc[0]

        prev_start = pd.to_datetime(start)-(pd.to_datetime(end)-pd.to_datetime(start))
        prev_end = pd.to_datetime(start)

        prev_df = fetch_data(prev_start,prev_end,None,agg)

        carbon_reduction = prev_df["carbon_kgco2"].sum()-total_carbon

        trend = df.groupby("date",as_index=False).sum()

        trend_fig = go.Figure()
        trend_fig.update_layout(
            template="plotly_white",
            hovermode="x unified",
            transition=dict(duration=500, easing="cubic-in-out"),
            margin=dict(l=20, r=20, t=40, b=20),
            font=dict(size=14),
        )
        trend_fig.add_bar(
            x=trend["date"],
            y=trend["energy_kwh"],
            name="Energy",
            hovertemplate="<b>%{x}</b><br>Energy: %{y:.2f} kWh<extra></extra>"
        )

        trend_fig.add_scatter(
            x=trend["date"],
            y=trend["carbon_kgco2"],
            yaxis="y2",
            name="Carbon",
            mode="lines+markers",
            line=dict(width=3),
            marker=dict(size=6),
            hovertemplate="<b>%{x}</b><br>Carbon: %{y:.2f} kgCO₂<extra></extra>"
        )

        trend_fig.update_layout(
            yaxis2=dict(overlaying="y",side="right"),
            template="plotly_white"
        )

        energy_pie_fig = go.Figure(
            data=[go.Pie(
                labels=energy_pie["system"],
                values=energy_pie["energy_kwh"],
                hole=0.5,
                textinfo="percent",
                textposition="inside",   # only % inside
                hoverinfo="label+value+percent",
                pull=[0.03]*len(energy_pie),
            )]
        )
        carbon_pie_fig = go.Figure(
            data=[go.Pie(
                labels=carbon_pie["system"],
                values=carbon_pie["carbon_kgco2"],
                hole=0.5,
                textinfo="percent",
                textposition="inside",   # only % inside
                hoverinfo="label+value+percent",
                pull=[0.03]*len(carbon_pie),
            )]
        )

        energy_pie_fig.update_layout(
            title={
                "text": "Energy Consumption by System",
                "x": 0.5,   # center title
                "xanchor": "center"
            },
            showlegend=True,
            margin=dict(t=50, b=20),
        )
        carbon_pie_fig.update_layout(
            title={
                "text": "Carbon by System",
                "x": 0.5,   # center title
                "xanchor": "center"
            },
            showlegend=True,
            margin=dict(t=50, b=20),
        )

        return html.Div([

            html.H3("EMS Overview & Carbon Reporting"),

            html.Div(
                style={"display":"flex","gap":"20px","marginBottom":"20px"},
                children=[
                    kpi_card("Total Energy",total_energy,"kWh"),
                    kpi_card("Total Carbon",total_carbon,"kgCO₂","#E67E22"),
                    kpi_card("Avg Daily Energy",avg_energy,"kWh/day","#27AE60"),
                    kpi_card("Avg Daily Carbon",avg_carbon,"kgCO₂/day","#8E44AD"),
                    kpi_card("Top Energy System",top_system["system"],"Highest Consumption","#C0392B"),
                    kpi_card("Carbon Reduction",carbon_reduction,"kgCO₂","#16A085"),
                ]
            ),

            html.Div(
                className="graph-card",
                style={
                    "background": "white",
                    "padding": "15px",
                    "borderRadius": "16px",
                    "boxShadow": "0 6px 18px rgba(0,0,0,0.08)",
                },
                children=[
                    dcc.Graph(
                        figure=trend_fig,
                        config={"displayModeBar": False},
                        style={"height": "450px"}  # BIGGER GRAPH
                    )
                ]
            ),

            html.Div(
                style={"display":"flex","gap":"20px"},
                children=[

                    html.Div(
                        style={"flex":"1","background":"white","padding":"15px","borderRadius":"12px"},
                        children=[dcc.Graph(figure=energy_pie_fig)]
                    ),

                    html.Div(
                        style={"flex":"1","background":"white","padding":"15px","borderRadius":"12px"},
                        children=[dcc.Graph(figure=carbon_pie_fig)]
                    )

                ]
            )

        ]), active_view

    # ================= SINGLE SYSTEM =================

    system = systems.get(active_view)

    if system:

        df = fetch_data(start,end,[system["name"]],agg)

        total_energy = df["energy_kwh"].sum()
        total_carbon = df["carbon_kgco2"].sum()

        days = max((pd.to_datetime(end)-pd.to_datetime(start)).days,1)

        avg_energy = total_energy/days
        avg_carbon = total_carbon/days

        trend = df.groupby("date",as_index=False).sum()

        fig = go.Figure()
        fig.update_layout(
            template="plotly_white",
            hovermode="x unified",
            transition=dict(duration=500, easing="cubic-in-out"),
            margin=dict(l=20, r=20, t=40, b=20),
            font=dict(size=14),
        )
        fig.add_bar(
            x=trend["date"],
            y=trend["energy_kwh"],
            name="Energy",
            hovertemplate="<b>%{x}</b><br>Energy: %{y:.2f} kWh<extra></extra>"
        )

        fig.add_scatter(
            x=trend["date"],
            y=trend["carbon_kgco2"],
            yaxis="y2",
            name="Carbon",
            mode="lines+markers",
            line=dict(width=3),
            marker=dict(size=6),
            hovertemplate="<b>%{x}</b><br>Carbon: %{y:.2f} kgCO₂<extra></extra>"
        )

        fig.update_layout(
            yaxis2=dict(overlaying="y",side="right"),
            template="plotly_white"
        )

        return html.Div([

            html.H3(system["name"]),
            html.P(system["scope"],style={"fontWeight":"bold","color":"#E67E22"}),

            html.Div(
                style={"display":"flex","gap":"20px","marginBottom":"20px"},
                children=[
                    kpi_card("Total Energy",total_energy,"kWh"),
                    kpi_card("Total Carbon",total_carbon,"kgCO₂","#E67E22"),
                    kpi_card("Avg Daily Energy",avg_energy,"kWh/day","#27AE60"),
                    kpi_card("Avg Daily Carbon",avg_carbon,"kgCO₂/day","#8E44AD"),
                ]
            ),

            html.Div(
                className="graph-card",
                style={
                    "background": "white",
                    "padding": "15px",
                    "borderRadius": "16px",
                    "boxShadow": "0 6px 18px rgba(0,0,0,0.08)",
                },
                children=[
                    dcc.Graph(
                        figure=fig,
                        config={"displayModeBar": False},
                        style={"height": "450px"}
                    )
                ]
            )

        ]), active_view

    return html.Div(), active_view

# =================================================
# RUN APP
# =================================================

if __name__ == "__main__":
    port = int(os.environ.get("PORT",8050))
    app.run_server(host="0.0.0.0",port=port)