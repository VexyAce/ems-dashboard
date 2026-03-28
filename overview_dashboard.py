import dash
from dash import dcc, html, Input, Output, State
import plotly.graph_objects as go
import pandas as pd
from sqlalchemy import create_engine

# =================================================
# DATABASE CONFIG
# =================================================
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "ems_db"
DB_USER = "postgres"
DB_PASSWORD = "Limlimlimwee2#"   # change if needed

engine = create_engine(
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

CARBON_FACTOR = 0.408

# =================================================
# SYSTEM DEFINITIONS
# =================================================
systems = {
    "bss": {"label": "Boiler & Steam", "name": "Boiler & Steam System (BSS)", "scope": "Scope 1 – Direct Emissions"},
    "hps": {"label": "Heat Pump", "name": "Heat Pump System (HPS)", "scope": "Scope 2 – Electricity"},
    "ps":  {"label": "Pump System", "name": "Pump System (PS)", "scope": "Scope 2 – Electricity"},
    "fs":  {"label": "Fan System", "name": "Fan System (FS)", "scope": "Scope 2 – Electricity"},
    "ac":  {"label": "Air Compressor", "name": "Air Compressor System (ACIACS)", "scope": "Scope 2 – Electricity"},
    "ls":  {"label": "Lighting System", "name": "Lighting System (LS)", "scope": "Scope 2 – Electricity"},
}

SYSTEM_OPTIONS = [{"label": v["label"], "value": v["name"]} for v in systems.values()]
ALL_SYSTEM_NAMES = [v["name"] for v in systems.values()]

# =================================================
# DATE BOUNDS
# =================================================
bounds = pd.read_sql(
    "SELECT MIN(timestamp) AS min_d, MAX(timestamp) AS max_d FROM energy_data",
    engine
)
MIN_DATE = bounds.loc[0, "min_d"]
MAX_DATE = bounds.loc[0, "max_d"]

# =================================================
# SQL DATA FETCHER
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
# DASH APP
# =================================================
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "SIT Energy Management System"

# =================================================
# LAYOUT
# =================================================
app.layout = html.Div(
    style={"display": "flex", "fontFamily": "Segoe UI", "background": "#F4F6FB"},
    children=[

        dcc.Store(id="active-view", data="overview"),

        # ================= SIDEBAR =================
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
                    style={"marginBottom": "6px"}
                ),

                dcc.Dropdown(
                    id="compare-b",
                    options=SYSTEM_OPTIONS,
                    placeholder="Select System B",
                    style={"marginBottom": "10px"}
                ),

                html.Button(
                    "Export Current View (CSV)",
                    id="export-btn",
                    style={"width": "100%"}
                ),

                dcc.Download(id="download-report")
            ]
        ),

        # ================= MAIN =================
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
                        html.P(
                            "Energy Efficiency Technology Laboratory – Energy Management System",
                            style={"margin": "0", "color": "#555"}
                        )
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

    # ================= COMPARISON =================
    if active_view == "compare" and compare_a and compare_b:
        df = fetch_data(start, end, [compare_a, compare_b], agg)
        trend = df.groupby(["date", "system"], as_index=False).sum()

        fig = go.Figure()
        for s in [compare_a, compare_b]:
            s_df = trend[trend["system"] == s]
            fig.add_bar(x=s_df["date"], y=s_df["energy_kwh"], name=s)

        fig.update_layout(
            title="System Energy Comparison",
            yaxis_title="Energy (kWh)",
            template="plotly_white"
        )

        return html.Div([
            html.H3("System Comparison"),
            dcc.Graph(figure=fig)
        ]), active_view

    # ================= OVERVIEW =================
    if active_view == "overview":
        df = fetch_data(start, end, None, agg)

        trend = df.groupby("date", as_index=False).sum()
        energy_pie = df.groupby("system", as_index=False)["energy_kwh"].sum()
        carbon_pie = df.groupby("system", as_index=False)["carbon_kgco2"].sum()

        fig = go.Figure()
        fig.add_bar(x=trend["date"], y=trend["energy_kwh"], name="Energy (kWh)")
        fig.add_scatter(
            x=trend["date"],
            y=trend["carbon_kgco2"],
            yaxis="y2",
            name="Carbon (kgCO₂)"
        )
        fig.update_layout(
            yaxis=dict(title="Energy (kWh)"),
            yaxis2=dict(title="Carbon (kgCO₂)", overlaying="y", side="right"),
            template="plotly_white",
            height=420
        )

        return html.Div([

            html.H3("EMS Overview & Carbon Reporting"),

            # TOP – FULL WIDTH
            html.Div(
                style={"background": "white", "padding": "15px",
                       "borderRadius": "12px", "marginBottom": "20px"},
                children=[dcc.Graph(figure=fig)]
            ),

            # BOTTOM – 2 PIES FULL WIDTH
            html.Div(
                style={"display": "flex", "gap": "20px"},
                children=[
                    html.Div(
                        style={"flex": "1", "background": "white",
                               "padding": "15px", "borderRadius": "12px"},
                        children=[dcc.Graph(figure=go.Figure(
                            data=[go.Pie(labels=energy_pie["system"],
                                          values=energy_pie["energy_kwh"], hole=0.45)],
                            layout={"title": "Energy Share by System (%)"}
                        ))]
                    ),
                    html.Div(
                        style={"flex": "1", "background": "white",
                               "padding": "15px", "borderRadius": "12px"},
                        children=[dcc.Graph(figure=go.Figure(
                            data=[go.Pie(labels=carbon_pie["system"],
                                          values=carbon_pie["carbon_kgco2"], hole=0.45)],
                            layout={"title": "Carbon Emissions Share by System (%)"}
                        ))]
                    ),
                ]
            )
        ]), active_view

    # ================= SINGLE SYSTEM =================
    system = systems[active_view]
    df = fetch_data(start, end, [system["name"]], agg)
    trend = df.groupby("date", as_index=False).sum()

    fig = go.Figure()
    fig.add_bar(x=trend["date"], y=trend["energy_kwh"], name="Energy (kWh)")
    fig.add_scatter(
        x=trend["date"],
        y=trend["carbon_kgco2"],
        yaxis="y2",
        name="Carbon (kgCO₂)"
    )
    fig.update_layout(
        yaxis2=dict(overlaying="y", side="right"),
        template="plotly_white"
    )

    return html.Div([
        html.H3(system["name"]),
        html.P(system["scope"], style={"fontWeight": "bold", "color": "#E67E22"}),
        dcc.Graph(figure=fig)
    ]), active_view

# =================================================
# EXPORT CURRENT VIEW
# =================================================
@app.callback(
    Output("download-report", "data"),
    Input("export-btn", "n_clicks"),
    State("active-view", "data"),
    State("compare-a", "value"),
    State("compare-b", "value"),
    State("date-range", "start_date"),
    State("date-range", "end_date"),
    State("agg-level", "value"),
    prevent_initial_call=True
)
def export_current_view(_, active_view, a, b, start, end, agg):

    if active_view == "overview":
        systems_selected = ALL_SYSTEM_NAMES
    elif active_view == "compare":
        systems_selected = [s for s in [a, b] if s]
    else:
        systems_selected = [systems[active_view]["name"]]

    df = fetch_data(start, end, systems_selected, agg)

    return dcc.send_data_frame(
        df.to_csv,
        "ems_current_view_report.csv",
        index=False
    )

# =================================================
# RUN
# =================================================
if __name__ == "__main__":
    app.run(debug=True)