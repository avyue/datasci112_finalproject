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
from dash import Input, Output, Patch, State, callback, dcc, html

# --- constants ---

DATA_DIR = Path(__file__).parent / "data"
MYLA311_PATH = (
    DATA_DIR / "MyLA311" / "MyLA311_Service_Request_Homeless_Encampment_Combined_2025_20260524.csv"
)
MYLA311_REQUEST_TYPE = "Homeless Encampment"
LAHSA_PATH = DATA_DIR / "LAHSA" / "LA_County_Homeless_Encampment_Request_Forms_with_precinct.csv"
NIBRS_PATH = DATA_DIR / "LAPD" / "LAPD_NIBRS_Offenses_Dataset_2024_to_2025_20260526.csv"
PRECINCT_PATH = DATA_DIR / "LAPD" / "lapd_precincts_combined.csv"
QCT_BY_PREC_PATH = DATA_DIR / "census_indicators" / "qct_by_prec.csv"
SHELTER_PATH = DATA_DIR / "shelters" / "2025_HIC_All_Projects.csv"

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
    "shelters": "#000000",
}

# City-centroid lookup for shelter geocoding (HIC data has no lat/lon)
CITY_COORDS: dict[str, tuple[float, float] | None] = {
    "Alhambra": (34.0953, -118.1270),
    "Altadena": (34.1900, -118.1310),
    "Arcadia": (34.1397, -118.0353),
    "Azusa": (34.1336, -117.9076),
    "Baldwin Park": (34.0853, -117.9609),
    "Bell": (33.9775, -118.1870),
    "Bellflower": (33.8817, -118.1170),
    "Burbank": (34.1808, -118.3090),
    "Canoga Park": (34.2008, -118.5988),
    "Canyon Country": (34.4218, -118.4642),
    "Chatsworth": (34.2573, -118.6039),
    "CONFIDENTIAL": None,
    "Compton": (33.8958, -118.2201),
    "Covina": (34.0900, -117.8903),
    "Culver City": (34.0211, -118.3965),
    "Downey": (33.9401, -118.1331),
    "Duarte": (34.1392, -117.9776),
    "East Los Angeles CDP": (34.0239, -118.1717),
    "El Monte": (34.0686, -118.0276),
    "Gardena": (33.8883, -118.3089),
    "Hacienda Heights": (33.9931, -117.9690),
    "Harbor City": (33.7928, -118.2943),
    "Hawthorne": (33.9164, -118.3526),
    "Huntington Park": (33.9814, -118.2254),
    "Ingelwood": (33.9617, -118.3531),
    "Inglewood": (33.9617, -118.3531),
    "Irwindale": (34.1064, -117.9359),
    "La Puente": (34.0200, -117.9498),
    "La Verne": (34.1006, -117.7678),
    "Lancaster": (34.6868, -118.1542),
    "Lawndale": (33.8872, -118.3526),
    "Long Beach": (33.7701, -118.1937),
    "Los Angeles": (34.0522, -118.2437),
    "Los angeles": (34.0522, -118.2437),
    "los angeles": (34.0522, -118.2437),
    "Lynwood": (33.9303, -118.2112),
    "Marina Del Rey": (33.9802, -118.4517),
    "Mission HIlls": (34.2736, -118.4642),
    "Monrovia": (34.1442, -117.9995),
    "Montebello": (34.0153, -118.1137),
    "Newhall": (34.3842, -118.5301),
    "North Hills": (34.2342, -118.4842),
    "North Hollywood": (34.1872, -118.3830),
    "Northridge": (34.2289, -118.5342),
    "Norwalk": (33.9022, -118.0815),
    "Pacoima": (34.2597, -118.4087),
    "Palmadale": (34.5794, -118.1165),
    "Palmdale": (34.5794, -118.1165),
    "Panorama City": (34.2233, -118.4467),
    "Pomona": (34.0551, -117.7490),
    "Quartz Hills": (34.6489, -118.2154),
    "Redondo Beach": (33.8492, -118.3884),
    "Reseda": (34.2014, -118.5342),
    "Rosemead": (34.0803, -118.0728),
    "San Fernando": (34.2819, -118.4392),
    "San Gabriel": (34.0961, -118.1059),
    "San Pedro": (33.7367, -118.2912),
    "Santa Clarita": (34.3917, -118.5426),
    "Santa Fe Springs": (33.9428, -118.0687),
    "Santa Monica": (34.0195, -118.4912),
    "Sherman Oaks": (34.1511, -118.4494),
    "Signal Hill": (33.8042, -118.1665),
    "South El Monte": (34.0525, -118.0462),
    "South Gate": (33.9547, -118.2122),
    "Sun Valley": (34.2219, -118.3830),
    "Sunland": (34.2614, -118.3094),
    "Sylmar": (34.2994, -118.4442),
    "Tarzana": (34.1689, -118.5494),
    "Torrance": (33.8358, -118.3406),
    "Tujunga": (34.2494, -118.2894),
    "Van Nuys": (34.1897, -118.4494),
    "Venice": (33.9850, -118.4694),
    "West Athens CDP": (33.9058, -118.2965),
    "West Covina": (34.0686, -117.9390),
    "West Hollywood": (34.0900, -118.3614),
    "Whittier": (33.9792, -118.0326),
    "Wilmington": (33.7817, -118.2612),
    "Winnetka": (34.2139, -118.5694),
    "Woodland Hills": (34.1683, -118.5994),
}

LAHSA_ACTION_LAYERS = [
    {
        "action_type": "Full Encampment Protocol",
        "layer_id": "lahsa-protocol",
        "label": "Full Protocol",
        "color": "#dc2626",
        "description": (
            "Site assessment, intensive outreach, and individuals matched with housing solutions. "
            "The site is then cleared, cleaned, and secured to prevent future encampments."
        ),
        "link": "https://cd10.lacity.gov/sites/g/files/wph1986/files/2021-07/Best-Practices-for-Addressing-Street-Encampments-%E2%80%93-Final-Draft-3.pdf",
    },
    {
        "action_type": "Immediate Action",
        "layer_id": "lahsa-immediate",
        "label": "Immediate Action",
        "color": "#0891b2",
        "description": (
            "No information available, but presumably this protocol matches cases where all individuals "
            "and belongings are cleared from the site within three days due to health or safety hazards."
        ),
        "link": "https://www.hiltonfoundation.org/wp-content/uploads/2023/03/Encampments-Brief_Abt-Associates_3.28.23_FINAL-1.pdf",
    },
    {
        "action_type": "Non-Displacement",
        "layer_id": "lahsa-non-displacement",
        "label": "Non-Displacement",
        "color": "#7c3aed",
        "description": (
            "No intermediate housing available. Debris is cleared, and only personal property "
            "voluntarily relinquished is removed. Dwellings are not removed."
        ),
        "link": "https://file.lacounty.gov/SDSInter/lac/1183858_LACountyEncampmentResolutionGuidance.pdf",
    },
]

LEGEND_ENTRIES = [
    {
        "marker": "Blue circle",
        "color": LAYER_COLORS["myla311"],
        "label": "MyLA311 reported encampments",
        "link": "https://lacity.gov/myla311/myla311-frequently-asked-questions",
        "description": (
            "A report filed by a resident, business, or worker to MyLA311 to request city services "
            "to clear an encampment within the jurisdiction of the city of LA. "
            "Shown at the reported location and on the date filed."
        ),
    },
    *[
        {
            "marker": f"{spec['label']} circle",
            "color": spec["color"],
            "label": f"LAHSA \u2014 {spec['label']}",
            "link": spec["link"],
            "description": spec["description"],
        }
        for spec in LAHSA_ACTION_LAYERS
    ],
    {
        "marker": "Amber star",
        "color": LAYER_COLORS["precincts"],
        "label": "LAPD Precinct stations",
        "link": "https://lapdonlinestrgeacc.blob.core.usgovcloudapi.net/lapdonlinemedia/2021/12/LAPD-Area-Stations.pdf",
        "description": (
            "The location of the twenty-one police stations in LA county, and the area "
            "(represented as a circle) each covers."
        ),
    },
    {
        "marker": "Black triangle",
        "color": "#000000",
        "shape": "triangle",
        "label": "Homeless shelters (2025 HIC)",
        "link": "https://www.lahsa.org/documents?id=9369-housing-inventory-count-hic-.xlsx",
        "description": (
            "The location of all homeless shelters open during the 2025 Housing Inventory Count."
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
    created_date: str = ""
    closed_date: str = ""
    anonymous: str = ""


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
    qct_count: int = 0


@dataclass(frozen=True)
class ShelterMarker:
    lat: float
    lon: float
    name: str
    total_beds: str
    housing_type: str


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

        df = pd.read_csv(
            path,
            usecols=["RequestType", "Latitude", "Longitude", "CreatedDate", "ClosedDate", "Anonymous", "PolicePrecinct"],
            engine="python",
        )
        df = df[df["RequestType"] == MYLA311_REQUEST_TYPE]
        df = df.dropna(subset=["Latitude", "Longitude", "CreatedDate"])
        for row in df.itertuples(index=False):
            day = to_la_date(row.CreatedDate)
            if day is None or day < START_DATE or day > END_DATE:
                continue
            created = day.strftime("%m/%d/%Y")
            closed_raw = row.ClosedDate if pd.notna(row.ClosedDate) else None
            closed = to_la_date(closed_raw).strftime("%m/%d/%Y") if closed_raw else NA
            anon_val = str(row.Anonymous).strip().upper() if pd.notna(row.Anonymous) else "N"
            anonymous = "Yes" if anon_val in ("Y", "YES", "TRUE", "1") else "No"
            marker = Marker(
                lat=float(row.Latitude),
                lon=float(row.Longitude),
                opacity=MARKER_OPACITY,
                people=NA,
                precinct=_normalize_precinct(row.PolicePrecinct, prec_lookup),
                scheduled=NA,
                created_date=created,
                closed_date=closed,
                anonymous=anonymous,
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
            action = row.action_date.strftime("%m/%d/%Y") if row.action_date else NA
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
                        created_date=row.start.strftime("%m/%d/%Y"),
                        closed_date=action,
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
        qct_counts = _load_qct_counts()

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
                    qct_count=qct_counts.get(prec, 0),
                )
                for prec, (lat, lon, name, area) in loc.items()
            ]

    def markers_on(self, day: date) -> list[PrecinctMarker]:
        return self._by_date.get(day, [])


class ShelterLayer:
    layer_id = "shelters"
    label = "Homeless shelters (2025 HIC)"
    color = LAYER_COLORS["shelters"]

    def __init__(self) -> None:
        self._markers: list[ShelterMarker] = []

    def load(self, path: Path) -> None:
        df = pd.read_csv(path)
        df = df.dropna(subset=["Total Beds", "Project Name", "City"])
        for _, row in df.iterrows():
            city = str(row["City"]).strip()
            coords = CITY_COORDS.get(city)
            if coords is None:
                continue
            lat, lon = coords
            self._markers.append(
                ShelterMarker(
                    lat=lat,
                    lon=lon,
                    name=fmt(row["Project Name"]),
                    total_beds=str(int(row["Total Beds"])),
                    housing_type=fmt(row["Housing Type"]),
                )
            )

    @property
    def markers(self) -> list[ShelterMarker]:
        return self._markers


def _traces_for_shelters(markers: list[ShelterMarker]) -> list[go.Scattermap]:
    if not markers:
        return []
    return [
        go.Scattermap(
            lat=[m.lat for m in markers],
            lon=[m.lon for m in markers],
            mode="markers",
            name=ShelterLayer.label,
            showlegend=True,
            marker=dict(
                size=10,
                color=ShelterLayer.color,
                opacity=1.0,
                symbol="triangle",
            ),
            customdata=[[m.name, m.total_beds, m.housing_type] for m in markers],
            hovertemplate=(
                "Name: %{customdata[0]}<br>"
                "Total beds: %{customdata[1]}<br>"
                "Housing type: %{customdata[2]}<extra></extra>"
            ),
        )
    ]


def _traces_for_lahsa(markers: list[Marker], *, color: str, name: str) -> list[go.Scattermap]:
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
            customdata=[
                [m.created_date, m.closed_date, m.people, m.precinct]
                for m in markers
            ],
            hovertemplate=(
                "Created: %{customdata[0]}<br>"
                "Action date: %{customdata[1]}<br>"
                "Possible dwellers: %{customdata[2]}<br>"
                "Precinct: %{customdata[3]}<extra></extra>"
            ),
        )
    ]


def _traces_for_myla311(markers: list[Marker], *, color: str, name: str) -> list[go.Scattermap]:
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
            customdata=[[m.created_date, m.closed_date, m.precinct, m.anonymous] for m in markers],
            hovertemplate=(
                "%{customdata[0]} – %{customdata[1]}<br>"
                "Precinct: %{customdata[2]}<br>"
                "Anonymous: %{customdata[3]}<extra></extra>"
            ),
        )
    ]


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


def _load_qct_counts() -> dict[int, int]:
    df = pd.read_csv(QCT_BY_PREC_PATH)
    return dict(zip(df["PREC"].astype(int), df["qct_count"].astype(int)))


def _circle_polygon(
    lat: float, lon: float, area_sqft: float, n: int = 16
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
                hoverinfo="skip",
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
                customdata=[[m.name, m.yearly_victim, m.yearly_suspect, m.victim_count + m.suspect_count, m.qct_count]],
                hovertemplate=(
                    "Station: %{customdata[0]}<br>"
                    "Yearly homeless-victim crimes: %{customdata[1]}<br>"
                    "Yearly homeless-suspect crimes: %{customdata[2]}<br>"
                    "Homeless-related crimes today: %{customdata[3]}<br>"
                    "QCT households (poverty level): %{customdata[4]}<extra></extra>"
                ),
            )
        )
    return traces


DYNAMIC_LAYER_IDS = ["myla311", "lahsa-protocol", "lahsa-immediate", "lahsa-non-displacement"]
# Trace index layout (fixed), bottom → top:
#   0+j*2: precinct polygon fill for precinct j (shape static; hoverinfo=skip)
#   1+j*2: precinct center dot for precinct j (customdata updated every tick via Patch())
#   42   : shelter markers (fully static)
#   43–46: dynamic marker layers (myla311, 3×LAHSA) — updated every tick via Patch()
_PRECINCT_POLY_START = 0  # dot for precinct j is at j*2 + 1


def _empty_marker_trace(layer: MapLayer) -> go.Scattermap:
    """Placeholder trace for a dynamic layer, populated each tick via Patch()."""
    if layer.layer_id == "myla311":
        hovertemplate = (
            "%{customdata[0]} – %{customdata[1]}<br>"
            "Precinct: %{customdata[2]}<br>"
            "Anonymous: %{customdata[3]}<extra></extra>"
        )
    else:
        hovertemplate = (
            "Created: %{customdata[0]}<br>"
            "Action date: %{customdata[1]}<br>"
            "Possible dwellers: %{customdata[2]}<br>"
            "Precinct: %{customdata[3]}<extra></extra>"
        )
    return go.Scattermap(
        lat=[],
        lon=[],
        mode="markers",
        name=layer.label,
        showlegend=True,
        marker=dict(size=MARKER_SIZE, color=layer.color, opacity=MARKER_OPACITY, symbol="circle"),
        customdata=[],
        hovertemplate=hovertemplate,
    )


def build_base_figure(
    index: DailyMarkerIndex,
    layers: list[MapLayer],
    precinct_layer: PrecinctLayer,
    shelter_layer: ShelterLayer,
    initial_day_idx: int = 0,
) -> go.Figure:
    day = DATE_RANGE[initial_day_idx]
    dynamic_traces = []
    for layer in layers:
        t = _empty_marker_trace(layer)
        markers = index.get(day, layer.layer_id)
        t.lat = [m.lat for m in markers]
        t.lon = [m.lon for m in markers]
        if layer.layer_id == "myla311":
            t.customdata = [[m.created_date, m.closed_date, m.precinct, m.anonymous] for m in markers]
        else:
            t.customdata = [[m.created_date, m.closed_date, m.people, m.precinct] for m in markers]
        dynamic_traces.append(t)
    precinct_traces = _traces_for_precincts(precinct_layer.markers_on(day))
    shelter_traces = _traces_for_shelters(shelter_layer.markers)
    fig = go.Figure(precinct_traces + shelter_traces + dynamic_traces)
    fig.update_layout(
        map=dict(style=MAP_STYLE, center=MAP_CENTER, zoom=MAP_ZOOM),
        margin=dict(l=0, r=0, t=40, b=0),
        title=f"Encampment activity — {day.isoformat()}",
        showlegend=True,
        uirevision="constant",
    )
    return fig


# --- dash app ---


def _legend_entry_row(entry: dict) -> html.Div:
    if entry.get("shape") == "triangle":
        marker_preview = html.Span(
            style={
                "display": "inline-block",
                "width": "0",
                "height": "0",
                "borderLeft": "7px solid transparent",
                "borderRight": "7px solid transparent",
                "borderBottom": f"14px solid {entry['color']}",
            }
        )
    else:
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
                    html.Strong(
                        html.A(
                            entry["label"],
                            href=entry["link"],
                            target="_blank",
                            style={"color": "inherit", "textDecoration": "underline"},
                        )
                        if entry.get("link")
                        else entry["label"]
                    ),
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
    index: DailyMarkerIndex,
    layers: list[MapLayer],
    precinct_layer: PrecinctLayer,
    shelter_layer: ShelterLayer,
) -> dash.Dash:
    app = dash.Dash(__name__)
    initial_figure = build_base_figure(index, layers, precinct_layer, shelter_layer, initial_day_idx=0)

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

    # dynamic traces sit after all precinct traces (2 per station) + 1 shelter trace
    _dyn_start = len(precinct_layer.markers_on(DATE_RANGE[0])) * 2 + 1

    @callback(
        Output("map", "figure"),
        Output("date-label", "children"),
        Input("day-slider", "value"),
    )
    def update_map(day_idx: int) -> tuple[Patch, str]:
        day = DATE_RANGE[day_idx]
        p = Patch()
        for i, layer in enumerate(layers):
            idx = _dyn_start + i
            markers = index.get(day, layer.layer_id)
            p["data"][idx]["lat"] = [m.lat for m in markers]
            p["data"][idx]["lon"] = [m.lon for m in markers]
            if layer.layer_id == "myla311":
                p["data"][idx]["customdata"] = [
                    [m.created_date, m.closed_date, m.precinct, m.anonymous] for m in markers
                ]
            else:
                p["data"][idx]["customdata"] = [
                    [m.created_date, m.closed_date, m.people, m.precinct] for m in markers
                ]
        for j, pm in enumerate(precinct_layer.markers_on(day)):
            dot_idx = _PRECINCT_POLY_START + j * 2 + 1
            p["data"][dot_idx]["customdata"] = [
                [pm.name, pm.yearly_victim, pm.yearly_suspect, pm.victim_count + pm.suspect_count, pm.qct_count]
            ]
        p["layout"]["title"] = f"Encampment activity — {day.isoformat()}"
        return p, day.strftime("%B %d, %Y")

    return app


def main() -> None:
    layers = build_layers()
    index = DailyMarkerIndex(layers)
    precinct_layer = PrecinctLayer()
    precinct_layer.load(PRECINCT_PATH, NIBRS_PATH)
    shelter_layer = ShelterLayer()
    shelter_layer.load(SHELTER_PATH)
    app = build_app(index, layers, precinct_layer, shelter_layer)
    print(f"Serving map at http://127.0.0.1:8050 ({len(DATE_RANGE)} days indexed)")
    app.run(host="127.0.0.1", port=8050, debug=False)


if __name__ == "__main__":
    main()
