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
# DATABASE CONFIG
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
            html.H2(f"{value:,.0f}" if isinstance(value,(int,float)) else value,
                    style={"margin": "5px 0", "color": color}),
            html.P(unit, style={"margin": "0", "color": "#999"}),
        ],
    )

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
# SIMULATED DATA GENERATOR (EVERY MINUTE)
# =================================================

def generate_energy_data():

    now = datetime.now()

    ranges = {
        "Boiler & Steam System (BSS)": (8,15),
        "Heat Pump System (HPS)": (6,12),
        "Pump System (PS)": (3,7),
        "Fan System (FS)": (2,5),
        "Air Compressor System (ACIACS)": (7,14),
        "Lighting System (LS)": (1,3),
    }

    records = []

    for system in ALL_SYSTEM_NAMES:

        low, high = ranges.get(system,(1,5))
        energy = round(random.uniform(low,high),2)

        records.append({
            "timestamp": now,
            "system": system,
            "energy_kwh": energy
        })

    df = pd.DataFrame(records)

    df.to_sql("energy_data",engine,if_exists="append",index=False)

    print("Simulated data inserted:",now)

# =================================================
# DAILY REPORT EXPORT (DATABASE)
# =================================================

def automated_daily_export():

    today = datetime.today().date()

    df = fetch_data(today,today,ALL_SYSTEM_NAMES,"daily")

    if df.empty:
        print("No data today.")
        return

    df["report_date"] = today
    df = df[["report_date","system","energy_kwh","carbon_kgco2"]]

    df.to_sql("daily_reports",engine,if_exists="append",index=False)

    print("Daily report saved.")

# =================================================
# SCHEDULER
# =================================================

schedule.every(1).minutes.do(generate_energy_data)
schedule.every().day.at("23:59").do(automated_daily_export)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)

threading.Thread(target=run_scheduler,daemon=True).start()

# =================================================
# DASH APP
# =================================================

app = dash.Dash(__name__, suppress_callback_exceptions=True)
server = app.server
app.title = "SIT Energy Management System"

# =================================================
# DATE RANGE
# =================================================

bounds = pd.read_sql(
"SELECT MIN(timestamp) AS min_d, MAX(timestamp) AS max_d FROM energy_data",
engine
)

MIN_DATE = bounds.loc[0,"min_d"]
MAX_DATE = bounds.loc[0,"max_d"]

# =================================================
# LAYOUT
# =================================================

app.layout = html.Div(

style={"display":"flex","fontFamily":"Segoe UI","background":"#F4F6FB"},

children=[

dcc.Store(id="active-view",data="overview"),

# SIDEBAR
html.Div(

style={
"width":"260px",
"background":"#1F4FD8",
"color":"white",
"padding":"20px",
"height":"100vh"
},

children=[

html.H3("EMS Dashboard"),
html.Hr(),

html.Button("Overview",id="nav-overview",style={"width":"100%"}),

html.Hr(),

html.P("Systems"),

*[
html.Button(v["label"],id=f"nav-{k}",style={"width":"100%"})
for k,v in systems.items()
],

html.Hr(),

html.Button("Daily Reports",id="nav-daily",style={"width":"100%"}),

html.Hr(),

dcc.Dropdown(id="compare-a",options=SYSTEM_OPTIONS,placeholder="System A"),

dcc.Dropdown(id="compare-b",options=SYSTEM_OPTIONS,placeholder="System B"),

]
),

# MAIN CONTENT
html.Div(
style={"flex":"1","padding":"25px"},
children=[

html.H2("Energy Management System"),

dcc.DatePickerRange(
id="date-range",
start_date=MIN_DATE,
end_date=MAX_DATE
),

dcc.RadioItems(
id="agg-level",
options=[
{"label":"Daily","value":"daily"},
{"label":"Monthly","value":"monthly"}
],
value="monthly",
inline=True
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
Input("nav-daily","n_clicks"),

*[Input(f"nav-{k}","n_clicks") for k in systems],

Input("compare-a","value"),
Input("compare-b","value"),

Input("date-range","start_date"),
Input("date-range","end_date"),
Input("agg-level","value"),

State("active-view","data")

)

def render_page(_,__ ,*args):

    compare_a,compare_b,start,end,agg,active_view=args[-6:]

    ctx=dash.callback_context
    trigger=ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else None

    if trigger=="nav-overview":
        active_view="overview"

    elif trigger=="nav-daily":
        active_view="daily"

    elif trigger and trigger.startswith("nav-"):
        key=trigger.replace("nav-","")
        if key in systems:
            active_view=key

    elif compare_a and compare_b:
        active_view="compare"

# =================================================
# COMPARISON PAGE
# =================================================

    if active_view=="compare" and compare_a and compare_b:

        df=fetch_data(start,end,[compare_a,compare_b],agg)

        trend=df.groupby(["date","system"],as_index=False).sum()

        fig=go.Figure()

        for s in [compare_a,compare_b]:

            s_df=trend[trend["system"]==s]

            fig.add_bar(x=s_df["date"],y=s_df["energy_kwh"],name=s)

        fig.update_layout(barmode="group",template="plotly_white")

        return html.Div([

            html.H3("System Comparison"),

            dcc.Graph(figure=fig)

        ]),active_view

# =================================================
# DAILY REPORT PAGE
# =================================================

    if active_view=="daily":

        df=pd.read_sql("""
        SELECT report_date,
        SUM(energy_kwh) energy,
        SUM(carbon_kgco2) carbon
        FROM daily_reports
        GROUP BY report_date
        ORDER BY report_date
        """,engine)

        if df.empty:
            return html.H3("No reports yet"),active_view

        fig=go.Figure()

        fig.add_bar(x=df["report_date"],y=df["energy"],name="Energy")

        fig.add_scatter(x=df["report_date"],y=df["carbon"],yaxis="y2",name="Carbon")

        fig.update_layout(yaxis2=dict(overlaying="y",side="right"))

        return html.Div([

        html.H3("Daily Reports"),

        dcc.Graph(figure=fig)

        ]),active_view

# =================================================
# OVERVIEW PAGE
# =================================================

    if active_view=="overview":

        df=fetch_data(start,end,None,agg)

        if df.empty:
            return html.H3("No data yet"),active_view

        total_energy=df["energy_kwh"].sum()
        total_carbon=df["carbon_kgco2"].sum()

        energy_pie=df.groupby("system")["energy_kwh"].sum()
        carbon_pie=df.groupby("system")["carbon_kgco2"].sum()

        trend=df.groupby("date",as_index=False).sum()

        fig=go.Figure()

        fig.add_bar(x=trend["date"],y=trend["energy_kwh"],name="Energy")

        fig.add_scatter(x=trend["date"],y=trend["carbon_kgco2"],yaxis="y2",name="Carbon")

        fig.update_layout(yaxis2=dict(overlaying="y",side="right"))

        energy_fig=go.Figure(data=[go.Pie(labels=energy_pie.index,values=energy_pie)])

        carbon_fig=go.Figure(data=[go.Pie(labels=carbon_pie.index,values=carbon_pie)])

        return html.Div([

        html.Div(style={"display":"flex","gap":"20px"},children=[

        kpi_card("Total Energy",total_energy,"kWh"),
        kpi_card("Total Carbon",total_carbon,"kgCO₂")

        ]),

        dcc.Graph(figure=fig),

        html.Div(style={"display":"flex"},children=[

        dcc.Graph(figure=energy_fig,style={"width":"50%"}),

        dcc.Graph(figure=carbon_fig,style={"width":"50%"})

        ])

        ]),active_view

# =================================================
# SYSTEM PAGE
# =================================================

    system=systems.get(active_view)

    if system:

        df=fetch_data(start,end,[system["name"]],agg)

        trend=df.groupby("date",as_index=False).sum()

        fig=go.Figure()

        fig.add_bar(x=trend["date"],y=trend["energy_kwh"])

        fig.add_scatter(x=trend["date"],y=trend["carbon_kgco2"],yaxis="y2")

        fig.update_layout(yaxis2=dict(overlaying="y",side="right"))

        return html.Div([

        html.H3(system["name"]),

        dcc.Graph(figure=fig)

        ]),active_view

    return html.Div(),active_view

# =================================================
# RUN APP
# =================================================

if __name__=="__main__":

    port=int(os.environ.get("PORT",8050))

    app.run_server(host="0.0.0.0",port=port)