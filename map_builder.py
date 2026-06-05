"""Interactive LA homeless encampment map served via Dash."""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import dash
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dcc, html

# --- constants ---

DATA_DIR = Path(__file__).parent / "data"
MYLA311_PATH = (
    DATA_DIR / "MyLA311" / "MyLA311_Service_Request_Homeless_Encampment_Combined_2025_20260524.csv"
)
MYLA311_REQUEST_TYPE = "Homeless Encampment"
LAHSA_PATH = DATA_DIR / "LAHSA" / "LA_County_Homeless_Encampment_Request_Forms_with_precinct.csv"
NIBRS_PATH = DATA_DIR / "LAPD" / "LAPD_NIBRS_Offenses_Dataset_2024_to_2025_20260526.csv"
PRECINCT_PATH = DATA_DIR / "LAPD" / "lapd_precincts_combined.csv"

START_DATE = date(2025, 1, 1)
END_DATE = date(2025, 12, 31)
DATE_RANGE = [
    START_DATE + timedelta(days=i)
    for i in range((END_DATE - START_DATE).days + 1)
]
LA_TZ = "America/Los_Angeles"
NA = "Not Available"

MAP_CENTER = {"lat": 34.05, "lon": -118.25}
MAP_ZOOM = 9
MARKER_SIZE = 16
MARKER_OPACITY = 0.55
MAP_STYLE = "open-street-map"

LAYER_COLORS = {
    "myla311": "#2563eb",
    "precincts": "#f59e0b",
}

LAHSA_ACTION_LAYERS = [
    {
        "action_type": "Full Encampment Protocol",
        "layer_id": "lahsa-protocol",
        "label": "Full Protocol",
        "color": "#dc2626",
    },
    {
        "action_type": "Immediate Action",
        "layer_id": "lahsa-immediate",
        "label": "Immediate Action",
        "color": "#0891b2",
    },
    {
        "action_type": "Non-Displacement",
        "layer_id": "lahsa-non-displacement",
        "label": "Non-Displacement",
        "color": "#7c3aed",
    },
]

LEGEND_ENTRIES = [
    {
        "marker": "Blue circle",
        "color": LAYER_COLORS["myla311"],
        "label": "MyLA311 reported encampments",
        "description": (
            "A 311 report filed on this date at this location. "
            "Shown only on the report date."
        ),
    },
    *[
        {
            "marker": f"{spec['label']} circle",
            "color": spec["color"],
            "label": f"LAHSA — {spec['label']}",
            "description": (
                "An active LAHSA outreach site from report date through the "
                "recorded action date."
            ),
        }
        for spec in LAHSA_ACTION_LAYERS
    ],
    {
        "marker": "Amber star",
        "color": LAYER_COLORS["precincts"],
        "label": "LAPD Precinct stations",
        "description": (
            "Daily count of NIBRS crimes with a homeless victim or homeless suspect "
            "in each precinct."
        ),
    },
]


# --- helpers ---


def fmt(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return NA
    text = str(value).strip()
    return text if text else NA


def to_la_date(value: object, *, utc: bool = False) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    ts = pd.to_datetime(value, format="mixed", utc=utc)
    if utc:
        ts = ts.tz_convert(LA_TZ)
    elif ts.tzinfo is None:
        ts = ts.tz_localize(LA_TZ, ambiguous=True, nonexistent="shift_forward")
    else:
        ts = ts.tz_convert(LA_TZ)
    return ts.date()


def clip_range(start: date, end: date) -> tuple[date, date]:
    if end < start:
        end = start
    visible_start = max(start, START_DATE)
    visible_end = min(end, END_DATE)
    return visible_start, visible_end


def _normalize_precinct(value: object, prec_lookup: dict[int, str]) -> str:
    """Map PolicePrecinct to a division name.

    MyLA311 encodes precincts as either a text name ('CENTRAL') or a numeric
    precinct number ('1.0'). Numeric values are resolved via the PREC→DIVISION
    lookup built from lapd_precincts_combined.csv.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return NA
    text = str(value).strip()
    if not text:
        return NA
    try:
        prec_num = int(float(text))
        # 0 is not a valid LAPD precinct number
        if prec_num == 0:
            return NA
        return prec_lookup.get(prec_num, text)
    except ValueError:
        return text


def hover_lines(people: str, precinct: str, scheduled: str) -> str:
    return (
        f"People: {people}<br>"
        f"Precinct: {precinct}<br>"
        f"Scheduled action: {scheduled}"
    )


# --- data model ---


@dataclass(frozen=True)
class Marker:
    lat: float
    lon: float
    opacity: float
    people: str
    precinct: str
    scheduled: str


@dataclass(frozen=True)
class PrecinctMarker:
    lat: float
    lon: float
    name: str
    area: float
    victim_count: int
    suspect_count: int
    yearly_victim: int
    yearly_suspect: int


class MapLayer(ABC):
    layer_id: str
    label: str
    color: str

    @abstractmethod
    def load(self, path: Path) -> None:
        ...

    @abstractmethod
    def markers_on(self, day: date) -> list[Marker]:
        ...


class MyLA311Layer(MapLayer):
    layer_id = "myla311"
    label = "MyLA311 reported encampments"
    color = LAYER_COLORS["myla311"]

    def __init__(self) -> None:
        self._by_date: dict[date, list[Marker]] = {}

    def load(self, path: Path) -> None:
        prec_df = pd.read_csv(PRECINCT_PATH, usecols=["PREC", "DIVISION"])
        prec_lookup: dict[int, str] = dict(
            zip(prec_df["PREC"].astype(int), prec_df["DIVISION"])
        )

        df = pd.read_csv(path, low_memory=False)
        df = df[df["RequestType"] == MYLA311_REQUEST_TYPE]
        df = df.dropna(subset=["Latitude", "Longitude", "CreatedDate"])
        for row in df.itertuples(index=False):
            day = to_la_date(row.CreatedDate)
            if day is None or day < START_DATE or day > END_DATE:
                continue
            scheduled = fmt(row.ServiceDate) if pd.notna(row.ServiceDate) else NA
            marker = Marker(
                lat=float(row.Latitude),
                lon=float(row.Longitude),
                opacity=MARKER_OPACITY,
                people=NA,
                precinct=_normalize_precinct(row.PolicePrecinct, prec_lookup),
                scheduled=scheduled,
            )
            self._by_date.setdefault(day, []).append(marker)

    def markers_on(self, day: date) -> list[Marker]:
        return self._by_date.get(day, [])


@dataclass(frozen=True)
class _LAHSARow:
    lat: float
    lon: float
    start: date
    action_date: date | None
    visible_end: date
    action_type: str
    people: str
    precinct: str
    scheduled: str


class LAHSALayer(MapLayer):
    def __init__(self, action_type: str, layer_id: str, label: str, color: str) -> None:
        self.action_type = action_type
        self.layer_id = layer_id
        self.label = label
        self.color = color
        self._rows: list[_LAHSARow] = []
        self._by_date: dict[date, list[Marker]] = {}

    def load(self, path: Path) -> None:
        df = pd.read_csv(path)
        df = df.dropna(subset=["X", "Y", "DATESUBMITTED"])
        for row in df.itertuples(index=False):
            row_action = fmt(row.REQUESTTYPENOTE)
            if row_action != self.action_type:
                continue
            start = to_la_date(row.DATESUBMITTED, utc=True)
            if start is None:
                continue
            completed = pd.notna(row.REQUESTCOMPLETEDDATE)
            action_date = (
                to_la_date(row.REQUESTCOMPLETEDDATE, utc=True)
                if completed
                else None
            )
            collab = to_la_date(row.COLLABORATORDATEAVAILABILITY, utc=True)
            action_type = fmt(row.REQUESTTYPENOTE)
            if collab is not None:
                scheduled = f"{collab.isoformat()} — {action_type}"
            else:
                scheduled = NA

            if completed:
                assert action_date is not None
                action_date = max(action_date, start)
                visible_end = action_date
            else:
                action_date = None
                visible_end = END_DATE

            self._rows.append(
                _LAHSARow(
                    lat=float(row.Y),
                    lon=float(row.X),
                    start=start,
                    action_date=action_date,
                    visible_end=visible_end,
                    action_type=row_action,
                    people=fmt(row.POSSIBLEDWELLERS),
                    precinct=fmt(row.PolicePrecinct),
                    scheduled=scheduled,
                )
            )
        self._build_daily()

    def _build_daily(self) -> None:
        for row in self._rows:
            visible_start, visible_end = clip_range(row.start, row.visible_end)
            if visible_start > visible_end:
                continue
            day = visible_start
            while day <= visible_end:
                self._by_date.setdefault(day, []).append(
                    Marker(
                        lat=row.lat,
                        lon=row.lon,
                        opacity=MARKER_OPACITY,
                        people=row.people,
                        precinct=row.precinct,
                        scheduled=row.scheduled,
                    )
                )
                day += timedelta(days=1)

    def markers_on(self, day: date) -> list[Marker]:
        return self._by_date.get(day, [])


class DailyMarkerIndex:
    def __init__(self, layers: list[MapLayer]) -> None:
        self._data: dict[date, dict[str, list[Marker]]] = {}
        for day in DATE_RANGE:
            self._data[day] = {layer.layer_id: layer.markers_on(day) for layer in layers}

    def get(self, day: date, layer_id: str) -> list[Marker]:
        return self._data.get(day, {}).get(layer_id, [])


class PrecinctLayer:
    layer_id = "precincts"
    label = "LAPD Precinct stations"
    color = LAYER_COLORS["precincts"]

    def __init__(self) -> None:
        self._by_date: dict[date, list[PrecinctMarker]] = {}

    def load(self, precinct_path: Path, nibrs_path: Path) -> None:
        precincts = pd.read_csv(precinct_path)
        loc: dict[int, tuple[float, float, str, float]] = {
            int(row.PREC): (float(row.lat), float(row.lon), str(row.DIVISION), float(row.Shape__Area))
            for row in precincts.itertuples(index=False)
        }

        nibrs = pd.read_csv(nibrs_path, low_memory=False)
        nibrs = nibrs.dropna(subset=["Date OCC", "AREA"])
        nibrs["_date"] = pd.to_datetime(
            nibrs["Date OCC"], format="%Y %b %d %I:%M:%S %p"
        ).dt.date
        nibrs["_area"] = pd.to_numeric(nibrs["AREA"], errors="coerce")
        nibrs = nibrs[
            nibrs["_date"].between(START_DATE, END_DATE) & nibrs["_area"].notna()
        ]
        nibrs["_area"] = nibrs["_area"].astype(int)
        nibrs["_victim"] = nibrs["Homeless-Victim Crime"] == "Yes"
        nibrs["_suspect"] = nibrs["Homeless-Suspect Crime"] == "Yes"

        grouped = (
            nibrs.groupby(["_date", "_area"])[["_victim", "_suspect"]]
            .sum()
            .rename(columns={"_victim": "v", "_suspect": "s"})
        )
        counts: dict[date, dict[int, tuple[int, int]]] = {}
        for (day, prec), row in grouped.iterrows():
            counts.setdefault(day, {})[int(prec)] = (int(row.v), int(row.s))

        yearly = (
            nibrs.groupby("_area")[["_victim", "_suspect"]]
            .sum()
            .rename(columns={"_victim": "v", "_suspect": "s"})
        )
        yearly_totals: dict[int, tuple[int, int]] = {
            int(prec): (int(row.v), int(row.s)) for prec, row in yearly.iterrows()
        }

        for day in DATE_RANGE:
            day_counts = counts.get(day, {})
            self._by_date[day] = [
                PrecinctMarker(
                    lat=lat,
                    lon=lon,
                    name=name,
                    area=area,
                    victim_count=day_counts.get(prec, (0, 0))[0],
                    suspect_count=day_counts.get(prec, (0, 0))[1],
                    yearly_victim=yearly_totals.get(prec, (0, 0))[0],
                    yearly_suspect=yearly_totals.get(prec, (0, 0))[1],
                )
                for prec, (lat, lon, name, area) in loc.items()
            ]

    def markers_on(self, day: date) -> list[PrecinctMarker]:
        return self._by_date.get(day, [])


def _traces_for_markers(
    markers: list[Marker], *, color: str, name: str
) -> list[go.Scattermap]:
    if not markers:
        return []
    return [
        go.Scattermap(
            lat=[m.lat for m in markers],
            lon=[m.lon for m in markers],
            mode="markers",
            name=name,
            showlegend=True,
            marker=dict(
                size=MARKER_SIZE,
                color=color,
                opacity=MARKER_OPACITY,
                symbol="circle",
            ),
            customdata=[[m.people, m.precinct, m.scheduled] for m in markers],
            hovertemplate=(
                "People: %{customdata[0]}<br>"
                "Precinct: %{customdata[1]}<br>"
                "Scheduled action: %{customdata[2]}<extra></extra>"
            ),
        )
    ]


def _circle_polygon(
    lat: float, lon: float, area_sqft: float, n: int = 64
) -> tuple[list[float], list[float]]:
    radius_m = math.sqrt(area_sqft * 0.0929 / math.pi)
    dlat = radius_m / 111_000
    dlon = radius_m / (111_000 * math.cos(math.radians(lat)))
    angles = [2 * math.pi * i / n for i in range(n + 1)]
    return (
        [lat + dlat * math.sin(a) for a in angles],
        [lon + dlon * math.cos(a) for a in angles],
    )


def _traces_for_precincts(markers: list[PrecinctMarker]) -> list[go.Scattermap]:
    if not markers:
        return []
    traces = []
    for i, m in enumerate(markers):
        lats, lons = _circle_polygon(m.lat, m.lon, m.area)
        traces.append(
            go.Scattermap(
                lat=lats,
                lon=lons,
                mode="lines",
                fill="toself",
                fillcolor="rgba(245, 158, 11, 0.25)",
                line=dict(color="#f59e0b", width=1),
                name=PrecinctLayer.label,
                showlegend=(i == 0),
                legendgroup="precincts",
                customdata=[[m.name, m.yearly_victim, m.yearly_suspect, m.victim_count + m.suspect_count]] * len(lats),
                hovertemplate=(
                    "Station: %{customdata[0]}<br>"
                    "Yearly homeless-victim crimes: %{customdata[1]}<br>"
                    "Yearly homeless-suspect crimes: %{customdata[2]}<br>"
                    "Homeless-related crimes today: %{customdata[3]}<extra></extra>"
                ),
            )
        )
        traces.append(
            go.Scattermap(
                lat=[m.lat],
                lon=[m.lon],
                mode="markers",
                marker=dict(size=6, color="#f59e0b", opacity=1.0),
                showlegend=False,
                legendgroup="precincts",
                customdata=[[m.name, m.yearly_victim, m.yearly_suspect, m.victim_count + m.suspect_count]],
                hovertemplate=(
                    "Station: %{customdata[0]}<br>"
                    "Yearly homeless-victim crimes: %{customdata[1]}<br>"
                    "Yearly homeless-suspect crimes: %{customdata[2]}<br>"
                    "Homeless-related crimes today: %{customdata[3]}<extra></extra>"
                ),
            )
        )
    return traces


def build_figure(
    index: DailyMarkerIndex,
    layers: list[MapLayer],
    day_idx: int,
    precinct_layer: PrecinctLayer,
) -> go.Figure:
    day = DATE_RANGE[day_idx]
    traces: list[go.Scattermap] = []
    for layer in layers:
        traces.extend(
            _traces_for_markers(
                index.get(day, layer.layer_id),
                color=layer.color,
                name=layer.label,
            )
        )
    precinct_traces = _traces_for_precincts(precinct_layer.markers_on(day))
    fig = go.Figure(precinct_traces + traces)
    fig.update_layout(
        map=dict(style=MAP_STYLE, center=MAP_CENTER, zoom=MAP_ZOOM),
        margin=dict(l=0, r=0, t=40, b=0),
        title=f"Encampment activity — {day.isoformat()}",
        showlegend=True,
    )
    return fig


# --- dash app ---


def _legend_entry_row(entry: dict) -> html.Div:
    marker_preview = html.Span(
        style={
            "display": "inline-block",
            "width": "14px",
            "height": "14px",
            "borderRadius": "50%",
            "backgroundColor": entry["color"],
            "opacity": MARKER_OPACITY,
        }
    )
    return html.Div(
        [
            html.Div(marker_preview, style={"width": "28px", "flexShrink": "0"}),
            html.Div(
                [
                    html.Strong(entry["label"]),
                    html.Span(f" ({entry['marker']})", style={"color": "#666"}),
                    html.Div(entry["description"], style={"color": "#444", "marginTop": "2px"}),
                ]
            ),
        ],
        style={"display": "flex", "gap": "12px", "alignItems": "flex-start"},
    )


def build_legend_dictionary() -> html.Div:
    return html.Div(
        [
            html.Div(
                "Legend",
                style={"fontWeight": "600", "marginBottom": "10px", "fontSize": "16px"},
            ),
            html.Div([_legend_entry_row(entry) for entry in LEGEND_ENTRIES], style={"display": "grid", "gap": "10px"}),
        ],
        style={
            "padding": "16px 20px",
            "borderTop": "1px solid #ddd",
            "backgroundColor": "#fafafa",
            "maxWidth": "900px",
            "margin": "0 auto",
        },
    )


def build_layers() -> list[MapLayer]:
    layers: list[MapLayer] = [MyLA311Layer()]
    layers[0].load(MYLA311_PATH)
    for spec in LAHSA_ACTION_LAYERS:
        layer = LAHSALayer(
            action_type=spec["action_type"],
            layer_id=spec["layer_id"],
            label=f"LAHSA — {spec['label']}",
            color=spec["color"],
        )
        layer.load(LAHSA_PATH)
        layers.append(layer)
    return layers


def build_app(
    index: DailyMarkerIndex, layers: list[MapLayer], precinct_layer: PrecinctLayer
) -> dash.Dash:
    app = dash.Dash(__name__)
    initial_figure = build_figure(index, layers, 0, precinct_layer)

    app.layout = html.Div(
        [
            dcc.Graph(
                id="map",
                figure=initial_figure,
                style={"height": "75vh"},
                config={"scrollZoom": True},
            ),
            html.Div(id="date-label", style={"textAlign": "center", "padding": "4px"}),
            dcc.Slider(
                id="day-slider",
                min=0,
                max=len(DATE_RANGE) - 1,
                step=1,
                value=0,
                tooltip=None,
                marks={
                    0: {
                        "label": "Jan 1, 2025",
                        "style": {"fontSize": "18px", "fontWeight": "600"},
                    },
                    len(DATE_RANGE) - 1: {
                        "label": "Dec 31, 2025",
                        "style": {"fontSize": "18px", "fontWeight": "600"},
                    },
                },
            ),
            html.Div(
                [
                    html.Button("◀ −1 day", id="day-prev", n_clicks=0),
                    html.Button("+1 day ▶", id="day-next", n_clicks=0),
                ],
                style={
                    "display": "flex",
                    "justifyContent": "center",
                    "gap": "16px",
                    "padding": "8px",
                },
            ),
            build_legend_dictionary(),
        ]
    )

    @callback(
        Output("day-slider", "value"),
        Input("day-prev", "n_clicks"),
        Input("day-next", "n_clicks"),
        State("day-slider", "value"),
        prevent_initial_call=True,
    )
    def step_day(prev_clicks: int, next_clicks: int, day_idx: int) -> int:
        triggered = dash.ctx.triggered_id
        if triggered == "day-prev":
            return max(0, day_idx - 1)
        if triggered == "day-next":
            return min(len(DATE_RANGE) - 1, day_idx + 1)
        return day_idx

    @callback(
        Output("map", "figure"),
        Output("date-label", "children"),
        Input("day-slider", "value"),
    )
    def update_map(day_idx: int) -> tuple[go.Figure, str]:
        day = DATE_RANGE[day_idx]
        fig = build_figure(index, layers, day_idx, precinct_layer)
        return fig, day.strftime("%B %d, %Y")

    return app


def main() -> None:
    layers = build_layers()
    index = DailyMarkerIndex(layers)
    precinct_layer = PrecinctLayer()
    precinct_layer.load(PRECINCT_PATH, NIBRS_PATH)
    app = build_app(index, layers, precinct_layer)
    print(f"Serving map at http://127.0.0.1:8050 ({len(DATE_RANGE)} days indexed)")
    app.run(host="127.0.0.1", port=8050, debug=False)


if __name__ == "__main__":
    main()
