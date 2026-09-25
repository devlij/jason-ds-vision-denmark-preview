#!/usr/bin/env python3
"""Bake DK-01-081 through DK-01-096 and rebuild the gallery from every manifest."""

from __future__ import annotations

import json
import math
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_denmark as bd

bd.LINEAGE = (
    "Text-prompt-only. No photographic reference pixels. "
    "The generator returned a 1280\u00d7720 JPEG for the wide frame and an 864\u00d71152 JPEG for the portrait frame; "
    "both were decoded to PNG without resampling. "
    "The 16:9 master is a uniform Lanczos resample from 1280\u00d7720 to 1920\u00d71080. "
    "The 4:5 master is a centered crop of the 864\u00d71152 frame to 864\u00d71080, with no upscale."
)

# Viewpoint coordinates used for the Open-Meteo request. Not surveyed cameras.
COORDS = {
    "DK-01-081": (55.65479, 12.64806),
    "DK-01-082": (55.68694, 12.57389),
    "DK-01-083": (55.69968, 12.54240),
    "DK-01-084": (55.67184, 12.52478),
    "DK-01-085": (55.75036, 12.58067),
    "DK-01-086": (55.65087, 12.08147),
    "DK-01-087": (55.68047, 11.08086),
    "DK-01-088": (55.72049, 11.71039),
    "DK-01-089": (55.23002, 11.75711),
    "DK-01-090": (55.00721, 11.91248),
    "DK-01-091": (54.77186, 11.86653),
    "DK-01-092": (55.50580, 9.73050),
    "DK-01-093": (55.26801, 9.88564),
    "DK-01-094": (55.73022, 9.11800),
    "DK-01-095": (55.48779, 8.41115),
    "DK-01-096": (55.27205, 8.53811),
}

# Sky bucket at the retrieval used to depict the frames.
GEN_BUCKET = {
    "DK-01-081": "overcast",
    "DK-01-082": "overcast",
    "DK-01-083": "overcast",
    "DK-01-084": "overcast",
    "DK-01-085": "overcast",
    "DK-01-086": "overcast",
    "DK-01-087": "overcast",
    "DK-01-088": "overcast",
    "DK-01-089": "overcast",
    "DK-01-090": "overcast",
    "DK-01-091": "overcast",
    "DK-01-092": "overcast",
    "DK-01-093": "overcast",
    "DK-01-094": "mainly",
    "DK-01-095": "mainly",
    "DK-01-096": "mainly",
}

MONTHS = {
    "01": "January", "02": "February", "03": "March", "04": "April",
    "05": "May", "06": "June", "07": "July", "08": "August",
    "09": "September", "10": "October", "11": "November", "12": "December",
}


def bucket(code: int) -> str:
    return {0: "clear", 1: "mainly", 2: "partly", 3: "overcast"}.get(code, "other")


def sky_word(code: int) -> str:
    return {
        0: "Clear",
        1: "Mainly clear",
        2: "Partly cloudy",
        3: "Overcast",
    }.get(code, f"Weather code {code}")


def nice_time(iso: str) -> str:
    y = iso[0:4]
    m = iso[5:7]
    d = iso[8:10]
    hhmm = iso[11:16]
    return f"{int(d)} {MONTHS[m]} {y} {hhmm}"


def moon_note(when: datetime) -> str:
    known = datetime(2000, 1, 6, 18, 14, tzinfo=timezone.utc)
    age = ((when.astimezone(timezone.utc) - known).total_seconds() / 86400.0) % 29.53058867
    illum = (1 - math.cos(2 * math.pi * age / 29.53058867)) / 2
    phase = "waxing" if age < 14.765 else "waning"
    kind = "gibbous" if illum >= 0.5 else "crescent"
    return (
        f"A {phase} {kind} moon near {illum * 100:.0f}% illumination was computed for "
        f"{when.astimezone(timezone.utc).strftime('%H:%M')} UTC, not observed on site."
    )


def sun_alt(lat: float, lon: float, dt_utc: datetime) -> float:
    n = (dt_utc - datetime(2000, 1, 1, 12, tzinfo=timezone.utc)).total_seconds() / 86400
    solar_long = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(solar_long + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    ra = math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam))
    dec = math.asin(math.sin(eps) * math.sin(lam))
    gmst = (18.697374558 + 24.06570982441908 * n) % 24
    lst = (gmst + lon / 15) % 24
    ha = math.radians(lst * 15 - math.degrees(ra))
    latr = math.radians(lat)
    alt = math.asin(math.sin(latr) * math.sin(dec) + math.cos(latr) * math.cos(dec) * math.cos(ha))
    return math.degrees(alt)


def twilight_phrase(alt: float) -> str:
    if alt >= -6:
        band = "civil twilight"
    elif alt >= -12:
        band = "nautical twilight"
    elif alt >= -18:
        band = "astronomical twilight"
    else:
        band = "full night, below astronomical twilight"
    return (
        f"A computed sun altitude of about {alt:.0f}\u00b0 ({band}), not an on-site observation."
    )


def fetch_weather() -> tuple[str, dict, str]:
    retrieved = datetime.now(bd.CPH)
    ids = list(COORDS)
    lats = ",".join(str(COORDS[i][0]) for i in ids)
    lons = ",".join(str(COORDS[i][1]) for i in ids)
    url = (
        "https://api.open-meteo.com/v1/forecast?"
        f"latitude={lats}&longitude={lons}"
        "&current=temperature_2m,cloud_cover,wind_speed_10m,precipitation,weather_code,is_day"
        "&daily=sunrise,sunset&timezone=" + urllib.parse.quote("Europe/Copenhagen") +
        "&past_days=1&forecast_days=1"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "jason-ds-vision-denmark/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read())
    if isinstance(data, dict):
        data = [data]
    if len(data) != len(ids):
        raise SystemExit(f"weather count {len(data)}")
    out = {}
    for entry, item in zip(ids, data):
        cur = item["current"]
        daily = item["daily"]
        if len(daily["sunset"]) < 2 or len(daily["sunrise"]) < 2:
            raise SystemExit(f"expected yesterday and today in daily for {entry}")
        offset = int(item["utc_offset_seconds"])
        local = datetime.fromisoformat(cur["time"]).replace(
            tzinfo=timezone(timedelta(seconds=offset))
        )
        code = int(cur["weather_code"])
        if bucket(code) != GEN_BUCKET[entry]:
            raise SystemExit(
                f"{entry} sky bucket changed from {GEN_BUCKET[entry]} to {bucket(code)}; "
                "the frames were depicted from the earlier bucket and were not regenerated"
            )
        temp = float(cur["temperature_2m"])
        cloud = int(cur["cloud_cover"])
        wind = float(cur["wind_speed_10m"])
        precip = float(cur["precipitation"])
        precip_words = "no precipitation" if precip == 0 else f"precipitation {precip} mm"
        word = sky_word(code)
        utc = local.astimezone(timezone.utc)
        alt = sun_alt(COORDS[entry][0], COORDS[entry][1], utc)
        out[entry] = {
            "word": word,
            "brief": f"{word.lower()}, {temp:.1f}\u00b0C",
            "detail": (
                f"{word}, {temp:.1f}\u00b0C, cloud cover {cloud}%, "
                f"wind {wind:.1f} km/h, {precip_words}."
            ),
            "temp": f"{temp:.1f}",
            "cloud": cloud,
            "wind": f"{wind:.1f}",
            "code": code,
            "is_day": cur.get("is_day"),
            "valid": cur["time"],
            "sunset_yesterday": daily["sunset"][0],
            "sunrise_today": daily["sunrise"][1],
            "sun_alt": alt,
        }
    stamp = retrieved.strftime("%-d %B %Y %H:%M")
    return stamp, out, moon_note(retrieved)


def prepare_raws() -> None:
    for n in range(81, 97):
        wide = bd.RAW / f"dk-01-{n:03d}-16x9.png"
        port = bd.RAW / f"dk-01-{n:03d}-45.png"
        imw = Image.open(wide)
        imp = Image.open(port)
        if imw.format != "JPEG" or imw.size != (1280, 720):
            raise SystemExit(f"bad wide {wide} {imw.format} {imw.size}")
        if imp.format != "JPEG" or imp.size != (864, 1152):
            raise SystemExit(f"bad portrait {port} {imp.format} {imp.size}")
        imw.convert("RGB").save(bd.RAW / f"dk-01-{n:03d}-16x9-raw.png", "PNG")
        imp.convert("RGB").save(bd.RAW / f"dk-01-{n:03d}-4x5-raw.png", "PNG")


def scenes(weather_stamp: str, wx: dict, moon: str) -> list:
    def pref(entry: str) -> str:
        row = wx[entry]
        valid = f"{nice_time(row['valid'])} Europe/Copenhagen"
        return (
            "Model data from Open-Meteo, retrieved "
            f"{weather_stamp} Europe/Copenhagen, valid {valid} "
            "\u2014 not a verified on-site observation."
        )

    def pack(entry: str) -> dict:
        row = wx[entry]
        return {
            "weather_prefix": pref(entry),
            "weather_detail": row["detail"],
            "weather_brief": row["brief"],
            "temp": row["temp"],
            "cloud": row["cloud"],
            "wind": row["wind"],
            "word": row["word"],
        }

    def clock(entry: str) -> str:
        row = wx[entry]
        text = (
            "Night. Sunset on "
            f"{nice_time(row['sunset_yesterday'])} Europe/Copenhagen and sunrise on "
            f"{nice_time(row['sunrise_today'])} Europe/Copenhagen. "
        )
        text += twilight_phrase(row["sun_alt"]) + " "
        text += f"Cloud cover {row['cloud']}%. "
        if row["cloud"] >= 80:
            text += "The cloud deck hides the moon. "
        else:
            text += moon + " "
        return text

    a = pack("DK-01-081")
    b = pack("DK-01-082")
    c = pack("DK-01-083")
    d = pack("DK-01-084")
    e = pack("DK-01-085")
    f = pack("DK-01-086")
    g = pack("DK-01-087")
    h = pack("DK-01-088")
    i = pack("DK-01-089")
    j = pack("DK-01-090")
    k = pack("DK-01-091")
    m = pack("DK-01-092")
    n = pack("DK-01-093")
    o = pack("DK-01-094")
    p = pack("DK-01-095")
    q = pack("DK-01-096")

    return [
        {
            "entry_id": "DK-01-081",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Amager Strandpark, Copenhagen",
            **a,
            "composition": "Lagoon, footbridge, and the island beach \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the city-side promenade, a low footbridge crosses the lagoon to the sandy island, with dunes and the Øresund beyond. "
                f"The night is {a['word'].lower()}, about {a['temp']}\u00b0C, with no rain, and the beach is empty. "
                "Promenade lamps light the sand. This is the 2005 island-and-lagoon park, not the older Helgoland sea bath."
            ),
            "alt_text": "AI-generated artistic interpretation of Amager Strandpark in Copenhagen at night, a lagoon and sandy island under cloud",
            "viewpoint": "City-side promenade at Amager Strandpark, looking east across the lagoon toward the artificial island and the Øresund. Approximate researched point 55.65479, 12.64806, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Amager_Strandpark",
                "https://www.visitcopenhagen.com/copenhagen/planning/amager-beach-park-gdk1123245",
            ],
            "anchors": [
                "A lagoon between the city shore and a low sandy island.",
                "One simple footbridge across the lagoon.",
                "Dunes and open water beyond, under thick cloud. No kiosk signs.",
            ],
            "solar": clock("DK-01-081") + "Promenade lamps. The overcast hides the sea horizon glow.",
            "independent": "Amager Strandpark is a public beach park on Amager. A park was founded in 1934, and in 2005 a roughly 2 km artificial island was added, separated from the original shore by a lagoon crossed by three bridges. The northern part is dunes and a more natural beach; the southern part is a city beach with a promenade. From the beach the Middelgrunden turbines and, farther south, the Øresund Bridge are reported views; this frame keeps to the lagoon, one bridge, and the sea, and does not treat a distant turbine as a required object.",
            "ip": "No kiosk or operator logos are intended. Internal review only, not a legal certification.",
            "visual": "Pass. Lagoon, footbridge, sand, and an overcast night. No readable signs.",
            "swap": "No swap. Amager Strandpark is not among DK-01-001 through DK-01-080.",
        },
        {
            "entry_id": "DK-01-082",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Palm House, Copenhagen",
            **b,
            "composition": "Iron-and-glass palm house, terrace, and basin \u00b7 AI-generated artistic interpretation",
            "description": (
                f"The Palm House is a long symmetrical iron-and-glass range, with a taller central bay, lower wings, a terrace, and a round basin in front. "
                f"The night is {b['word'].lower()}, about {b['temp']}\u00b0C, and the garden is closed, so the glass is mostly dark, with only a little path light. "
                "Late-September trees around it are still in leaf. No signboard is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of the Palm House in Copenhagen Botanical Garden at night, a dark iron-and-glass greenhouse",
            "viewpoint": "The garden axis in front of the Palm House terrace, looking at the glasshouse and the round basin. Garden point 55.68694, 12.57389, not a surveyed camera.",
            "refs": [
                "https://snm.dk/en/udstilling/palm-house",
                "https://en.wikipedia.org/wiki/University_of_Copenhagen_Botanical_Garden",
            ],
            "anchors": [
                "A tall central glass bay with lower glass wings.",
                "A terrace, central stair, and round basin in front.",
                "Mostly dark glass. Overcast night. No bright exhibition glow.",
            ],
            "solar": clock("DK-01-082") + "Path lamps only. Interior illumination at this hour was not verified, so the glasshouse is not shown as a lit display.",
            "independent": "The University of Copenhagen Botanical Garden has stood on this site since 1870. The Palm House, built 1872–74 in cast iron and glass for J.C. Jacobsen and designed by city architect Peter Christian Bønecke, is about 94 metres long, with a central bay about 16 metres tall. A terrace, stair, and round basin sit on the axis in front. The garden is not a night venue; a closed, dark exterior is the honest hour.",
            "ip": "Exterior architecture only. No readable museum name. Internal review only, not a legal certification.",
            "visual": "Pass. Symmetrical glasshouse, terrace, basin, dark overcast night.",
            "swap": "No swap. The caption is the Palm House exterior, not the garden as a whole and not an interior.",
        },
        {
            "entry_id": "DK-01-083",
            "region": "Capital Region",
            "city": "Copenhagen",
            "caption": "Superkilen, Copenhagen",
            **c,
            "composition": "Red paved wedge between Nørrebro blocks \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Superkilen's Red Square is a continuous red, pink, and orange paved wedge between ordinary apartment blocks, with a cycle path running through it. "
                f"The night is {c['word'].lower()}, about {c['temp']}\u00b0C, under street lamps. "
                "A few distant figures are small and not identifiable. There is no readable neon and no cemetery."
            ),
            "alt_text": "AI-generated artistic interpretation of Superkilen in Nørrebro at night, a red paved park between apartment blocks",
            "viewpoint": "On the red ground of Superkilen, looking along the wedge between the Nørrebro blocks. Approximate researched point 55.69968, 12.54240, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Superkilen",
                "https://www.visitcopenhagen.com/copenhagen/planning/superkilen-park-gdk707822",
            ],
            "anchors": [
                "A continuous red, pink, and orange paved surface.",
                "Apartment blocks along both sides of the wedge.",
                "No readable signs and no gravestones.",
            ],
            "solar": clock("DK-01-083") + "Street lamps on the red ground.",
            "independent": "Superkilen is a public park in Nørrebro, opened in 2012, designed by Superflex with Bjarke Ingels Group and Topotek1. It runs about 750 metres in three colour zones: the Red Square, the Black Market, and the Green Park. The red zone is the recreation surface. Objects borrowed from other cities include fountains and signs; this frame keeps the red ground and the blocks, and does not reproduce readable borrowed signage.",
            "ip": "No legible borrowed neon or brand marks are intended. Internal review only, not a legal certification.",
            "visual": "Pass. Red wedge, blocks, overcast night. Distant figures are not identifiable. No cemetery.",
            "swap": (
                "Swapped away from Assistens Cemetery. The catalogue allowed the cemetery or a Nørrebro street, and preferred Superkilen if the cemetery felt sensitive. "
                "Superkilen is the public park used here. No graves are depicted."
            ),
        },
        {
            "entry_id": "DK-01-084",
            "region": "Capital Region",
            "city": "Frederiksberg",
            "caption": "Frederiksberg Palace, Frederiksberg",
            **d,
            "composition": "Yellow Baroque palace above the garden axis \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the garden axis, the yellow-ochre Baroque palace sits uphill, symmetrical and three storeys, with a dark roof above a lawn and trees. "
                f"The night is {d['word'].lower()}, about {d['temp']}\u00b0C, and the park is empty. "
                "A few facade and path lights pick out the windows. The zoo next door is not in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Frederiksberg Palace at night, a yellow Baroque facade above a dark garden",
            "viewpoint": "On the axis in Frederiksberg Gardens, looking uphill at the palace facade. Approximate researched point 55.67184, 12.52478, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Frederiksberg_Palace",
                "https://dac.dk/en/knowledgebase/architecture/frederiksberg-palace-summer-serenity/",
            ],
            "anchors": [
                "A symmetrical yellow-ochre three-storey palace on the hill.",
                "A dark lawn and trees on the axis below.",
                "No zoo animals and no vehicles.",
            ],
            "solar": clock("DK-01-084") + "A few facade and path lights. Not a floodlit show.",
            "independent": "Frederiksberg Palace was begun in 1699 for Frederik IV as an Italian Baroque summer house and extended into the present H-shaped building by 1738. It stands on Valby Hill above Frederiksberg Gardens, which are public. Since 1869 it has housed the Royal Danish Military Academy. Frederiksberg is its own municipality, enclosed by Copenhagen. The zoo is next door; this view stays on the garden facade.",
            "ip": "No military signage and no zoo branding. Internal review only, not a legal certification.",
            "visual": "Pass. Yellow symmetrical palace, dark garden, overcast night, empty.",
            "swap": "No site swap. The city is Frederiksberg, the municipality of the palace, not Copenhagen.",
        },
        {
            "entry_id": "DK-01-085",
            "region": "Capital Region",
            "city": "Charlottenlund",
            "caption": "Charlottenlund Palace, Charlottenlund",
            **e,
            "composition": "Pale palace with a dome and lantern in a dark park \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Charlottenlund Palace stands alone on a gravel axis, a pale symmetrical house with a mansard roof and a central dome and lantern. "
                f"The night is {e['word'].lower()}, about {e['temp']}\u00b0C, with a few warm windows and an empty park. "
                "Lawns and trees close around it. There is no beach in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Charlottenlund Palace at night, a pale house with a dome in a dark park",
            "viewpoint": "Along the approach axis toward the garden front, with the dome on the centre line. Approximate researched point 55.75036, 12.58067, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Charlottenlund_Palace",
                "https://slks.dk/omraader/slotte-og-ejendomme/slotte-og-anlaeg/charlottenlund-slot-og-slotshave/",
            ],
            "anchors": [
                "A pale symmetrical palace with a mansard roof.",
                "A central dome and lantern.",
                "Dark lawns and trees. No beach and no readable signs.",
            ],
            "solar": clock("DK-01-085") + "A few warm windows. Park paths are dark.",
            "independent": "Charlottenlund Palace was built in 1731–33 for Princess Charlotte Amalie to designs by J.C. Krieger, using material from the demolished Copenhagen Castle. In 1880–81 Ferdinand Meldahl extended it in a French neo-renaissance manner and added the dome and lantern that mark the skyline now. The old Baroque garden became a romantic landscape park. The palace sits in Charlottenlund, Gentofte, between the forest and the Øresund; this frame is the park front, not the beach.",
            "ip": "No operator name on the building. Internal review only, not a legal certification.",
            "visual": "Pass. Dome and lantern, pale facade, dark overcast park, empty.",
            "swap": (
                "Swapped away from Ordrupgaard and from a beach-palace framing. "
                "The preferred exterior is Charlottenlund Palace itself. The beach is not in the frame."
            ),
        },
        {
            "entry_id": "DK-01-086",
            "region": "Zealand",
            "city": "Roskilde",
            "caption": "Viking Ship Museum, Roskilde",
            **f,
            "composition": "Concrete ship hall and moored wooden boats \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the museum harbour, a low concrete hall with a long glass wall and vertical fins faces Roskilde Fjord, and wooden boats lie at the quay. "
                f"The night is {f['word'].lower()}, about {f['temp']}\u00b0C, with a few quay lamps and no rain. "
                "No boat name is readable. Roskilde Cathedral is not in this frame."
            ),
            "alt_text": "AI-generated artistic interpretation of the Viking Ship Museum in Roskilde at night, a concrete hall and wooden boats",
            "viewpoint": "The museum harbour quay, looking at the fjord side of the Viking Ship Hall. Approximate researched point 55.65087, 12.08147, not a surveyed camera.",
            "refs": [
                "https://www.vikingeskibsmuseet.dk/en/visit-the-museum",
                "https://en.wikipedia.org/wiki/Viking_Ship_Museum_(Roskilde)",
            ],
            "anchors": [
                "A low concrete hall with a long glass wall and vertical fins.",
                "Wooden boats moored in the museum harbour.",
                "Dark fjord. No cathedral twin towers.",
            ],
            "solar": clock("DK-01-086") + "Quay lamps. No cathedral floodlight, because the cathedral is another site.",
            "independent": "The Viking Ship Museum at Vindeboder opened in 1969 to house the Skuldelev ships. Erik Christian Sørensen's hall is a concrete display case with a great window toward Roskilde Fjord. The museum island and harbour hold reconstructions; the museum says the boats are in the harbour from spring to autumn, and sailing on the fjord is published through 30 September, so moored wooden boats on 25 September are within that season. Which named ship was alongside this night was not checked. DK-01-006 is the cathedral, inland, and is not this waterfront.",
            "ip": "No readable boat names and no shop sign. Internal review only, not a legal certification.",
            "visual": "Pass. Concrete hall, fjord, moored wooden boats, overcast night. Distinct from the cathedral card.",
            "swap": "No city swap. The site is the museum exterior, kept separate from Roskilde Cathedral, DK-01-006.",
        },
        {
            "entry_id": "DK-01-087",
            "region": "Zealand",
            "city": "Kalundborg",
            "caption": "Church of Our Lady, Kalundborg",
            **g,
            "composition": "Five brick towers on the old-town hill \u00b7 AI-generated artistic interpretation",
            "description": (
                f"The Church of Our Lady rises on the hill above Kalundborg, red brick, with one taller square central tower and four shorter octagonal towers, each with a dark spire. "
                f"The night is {g['word'].lower()}, about {g['temp']}\u00b0C, and a little warm light sits on the brick. "
                "Low houses of the old town are at the foot. No sign is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of the five-towered Church of Our Lady in Kalundborg at night",
            "viewpoint": "From the old town below Højbyen, looking up at the five towers. Approximate researched point 55.68047, 11.08086, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Church_of_Our_Lady,_Kalundborg",
                "https://kirker.dk/kirke/vor-frue-kirke-kalundborg/",
            ],
            "anchors": [
                "Five towers: one taller central tower and four side towers.",
                "Red brick and dark pointed spires.",
                "The church on a hill, with lower houses beneath.",
            ],
            "solar": clock("DK-01-087") + "A little warm light on the brick. Not a measured lighting plot.",
            "independent": "Vor Frue Kirke in Kalundborg is a medieval brick church on a Greek-cross plan, begun around 1170 and unique for its five towers: a square central tower, Mary's tower, about 44 metres, and four octagonal towers about 34 metres at the ends of the arms. The central tower fell in 1827 and was rebuilt by 1871. It stands in Højbyen above the harbour and is the town's landmark.",
            "ip": "Church exterior only. No readable notice. Internal review only, not a legal certification.",
            "visual": "Pass. Five towers, red brick, overcast night, old town at the base.",
            "swap": "No swap. The five-tower church is the old-town landmark the catalogue asked for.",
        },
        {
            "entry_id": "DK-01-088",
            "region": "Zealand",
            "city": "Holbæk",
            "caption": "Holbæk Harbour, Holbæk",
            **h,
            "composition": "Wooden ships and the white bark-pot chimney \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Holbæk's old harbour holds several wooden ships with bare masts on the dark fjord, and a tall white square chimney stands on the quay. "
                f"The night is {h['word'].lower()}, about {h['temp']}\u00b0C, with quay lamps and no rain. "
                "The quay is empty, and no ship name is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Holbæk old harbour at night, wooden ships and a white chimney",
            "viewpoint": "The public quay at Holbæk Gammel Havn, looking across the moored wooden ships. Approximate researched point 55.72049, 11.71039, not a surveyed camera.",
            "refs": [
                "https://www.visitdenmark.com/denmark/plan-your-trip/historical-ships-harbour-holbaek-gdk1111670",
                "https://en.wikipedia.org/wiki/Holbæk",
            ],
            "anchors": [
                "A harbour basin on the fjord with wooden ships and bare masts.",
                "A tall white square chimney on the quay.",
                "Low sheds and quay lamps. No readable names.",
            ],
            "solar": clock("DK-01-088") + "Quay lamps on the water.",
            "independent": "Holbæk's old harbour, on the south side of Holbæk Fjord, is a lay-up for historic wooden ships. VisitDenmark describes about twenty galeases, cutters, and freighters, and a tall white chimney that is the old bark pot used to tan sails and nets. Not every ship is alongside at once; the frame shows several moored hulls, not a named muster. The Orø ferry uses the same harbour area and is not singled out.",
            "ip": "No readable ship names or yard brands. Internal review only, not a legal certification.",
            "visual": "Pass. Wooden ships, white chimney, dark fjord, overcast night, empty quay.",
            "swap": "No swap. The old harbour is the view, not the newer basin farther along the fjord.",
        },
        {
            "entry_id": "DK-01-089",
            "region": "Zealand",
            "city": "Næstved",
            "caption": "Næstved Old Town, Næstved",
            **i,
            "composition": "Red-brick Gothic church and one west tower \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Sankt Peders Kirke fills the old town: a red-brick Gothic church with one tall west tower, stepped gables, and pointed windows among low roofs. "
                f"The night is {i['word'].lower()}, about {i['temp']}\u00b0C, with street lamps and a quiet street. "
                "No shop sign is readable. This is the town church, not a market interior."
            ),
            "alt_text": "AI-generated artistic interpretation of Næstved old town at night, a red-brick Gothic church with one tower",
            "viewpoint": "The street by Sct. Peders Kirkeplads, looking at the west tower. Approximate researched point 55.23002, 11.75711, not a surveyed camera.",
            "refs": [
                "https://lex.dk/Sankt_Peders_Kirke_-_N%C3%A6stved",
                "https://www.sct.pederskirke.dk/om-kirken/kirkens-historie/",
            ],
            "anchors": [
                "One tall red-brick west tower.",
                "A Gothic brick body with stepped gables and pointed windows.",
                "Low old-town roofs around it. No readable shop signs.",
            ],
            "solar": clock("DK-01-089") + "Street lamps. The tower is not floodlit as a show.",
            "independent": "Sankt Peders Kirke stands in the middle of old Næstved, just north of the Suså. The present building is a Gothic brick rebuild, largely from the later 14th century, with a west tower raised around 1400 and heightened after 1500. It has one tower, not a pair. Axeltorv, the market, is nearby; the frame is the church in the old-town roofs rather than the square's shopfronts.",
            "ip": "No readable shop names. Church exterior only. Internal review only, not a legal certification.",
            "visual": "Pass. One brick tower, Gothic body, overcast night, quiet street.",
            "swap": "No swap. The old-town church is the landmark inside the catalogue's Næstved old town.",
        },
        {
            "entry_id": "DK-01-090",
            "region": "Zealand",
            "city": "Vordingborg",
            "caption": "Goose Tower, Vordingborg",
            **j,
            "composition": "Brick tower, copper spire, and a golden goose \u00b7 AI-generated artistic interpretation",
            "description": (
                f"The Goose Tower is a single red-brick shaft with a copper spire and a small golden goose at the tip, standing on grass with a low ruined curtain wall. "
                f"The night is {j['word'].lower()}, about {j['temp']}\u00b0C, with a little warm light on the brick. "
                "No museum sign is readable. The rest of the medieval castle is ruin, not a rebuilt palace."
            ),
            "alt_text": "AI-generated artistic interpretation of the Goose Tower in Vordingborg at night, a brick tower with a golden goose",
            "viewpoint": "The castle mound at Vordingborg, looking up at the Goose Tower. Approximate researched point 55.00721, 11.91248, not a surveyed camera.",
            "refs": [
                "https://en.wikipedia.org/wiki/Vordingborg_Castle",
                "https://da.wikipedia.org/wiki/G%C3%A5set%C3%A5rnet",
            ],
            "anchors": [
                "One brick tower, not a ring of towers.",
                "A copper spire with a small golden goose.",
                "A low ruined wall and grass. No readable sign.",
            ],
            "solar": clock("DK-01-090") + "A little warm light on the brick. Not a measured floodlight plot.",
            "independent": "Gåsetårnet is the only fully preserved tower of Vordingborg Castle. The brick shaft is about 26 metres, with a copper spire of about 10 metres from 1871. The golden goose on the spire is also the 1871 bird, later gilded; the medieval goose of the Valdemar story is not the one on the tower. Curtain-wall fragments remain. Danmarks Borgcenter, a modern museum, sits at the foot; it is not given a readable name or treated as the subject.",
            "ip": "No museum wordmark. The goose is a weather vane, not a brand. Internal review only, not a legal certification.",
            "visual": "Pass. One brick tower, copper spire, golden goose, ruined wall, overcast night.",
            "swap": "No swap. The Goose Tower is the subject, not a rebuilt castle.",
        },
        {
            "entry_id": "DK-01-091",
            "region": "Lolland-Falster",
            "city": "Nykøbing Falster",
            "caption": "Nykøbing Falster Harbour, Nykøbing Falster",
            **k,
            "composition": "Quay, moored boats, and the sound \u00b7 AI-generated artistic interpretation",
            "description": (
                f"The public quay at Nykøbing Falster faces the dark Guldborgsund, with a few moored boats and low town buildings under quay lamps. "
                f"The night is {k['word'].lower()}, about {k['temp']}\u00b0C, and the quay is empty. "
                "A low bridge sits farther down the sound. No boat name is readable, and the abbey interior is not shown."
            ),
            "alt_text": "AI-generated artistic interpretation of Nykøbing Falster harbour at night, boats on Guldborgsund",
            "viewpoint": "The public quay at Slotsbryggen, on the east shore of Guldborgsund, looking along the sound. Approximate researched point 54.77186, 11.86653, not a surveyed camera.",
            "refs": [
                "https://www.boatview.io/en/poi/20469/nykoebing-slotsbryggen",
                "https://en.wikipedia.org/wiki/Nyk%C3%B8bing_Falster",
            ],
            "anchors": [
                "A quay and moored boats on a narrow sound.",
                "Low town buildings and quay lamps.",
                "A distant low bridge. No abbey interior.",
            ],
            "solar": clock("DK-01-091") + "Quay lamps. The cloud hides any moon on the water.",
            "independent": "Nykøbing Falster sits on the east side of Guldborgsund. Slotsbryggen is a public marina quay on the north side of town. Kong Frederik IX's Bridge, a bascule, crosses the sound south of the commercial harbour. The frame shows the quay, boats, and a distant bridge in that direction; the bridge is not measured from the pixels. Klosterkirken, the Franciscan abbey church of 1419, is a short walk inland and is famous for an interior ancestral tablet, so it is not the picture.",
            "ip": "No readable boat names or bridge operator marks. Internal review only, not a legal certification.",
            "visual": "Pass. Quay, boats, sound, distant bridge, overcast night, empty.",
            "swap": (
                "Viewpoint choice, not a city swap. The catalogue allowed harbour or abbey. "
                "The harbour is used so the abbey's interior ancestral tablet is not the subject. "
                "The city remains Nykøbing Falster."
            ),
        },
        {
            "entry_id": "DK-01-092",
            "region": "Funen",
            "city": "Middelfart",
            "caption": "Little Belt Bridges, Middelfart",
            **m,
            "composition": "Steel truss bridge and a distant suspension bridge \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the Middelfart shore, the 1935 steel truss bridge crosses the Little Belt, and the 1970 suspension bridge stands farther along the strait. "
                f"The night is {m['word'].lower()}, about {m['temp']}\u00b0C, with bridge lights on the dark water. "
                "Wooded shores close the view. No sign is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of the Little Belt bridges at Middelfart at night, a truss bridge and a suspension bridge",
            "viewpoint": "The Middelfart shore south of the old bridge, looking across the Little Belt at both bridges. Approximate weather point 55.50580, 9.73050, not a surveyed camera.",
            "refs": [
                "https://www.visitmiddelfart.com/two-bridges-one-story",
                "https://www.visitmiddelfart.dk/turist/planlaeg-din-tur/den-gamle-lillebaeltsbro-gdk614471",
            ],
            "anchors": [
                "A steel truss bridge closer to the camera.",
                "A suspension bridge with towers and cables farther away.",
                "Dark water and wooded shores. No readable signs.",
            ],
            "solar": clock("DK-01-092") + "Bridge lights and their reflection. Not a fireworks display.",
            "independent": "Two bridges cross the Little Belt at Middelfart. The Old Little Belt Bridge, a steel truss opened in 1935, carries rail and local traffic and is about 1,178 metres long. The New Little Belt Bridge, a suspension bridge opened in 1970, is about 1,700 metres long with towers about 118 metres. From the Funen shore both are in one view: lattice steel nearer, cables farther north. Bridgewalking operates on the old bridge by day; no operator logo is the subject.",
            "ip": "No Bridgewalking wordmark and no vehicle brands as subjects. Internal review only, not a legal certification.",
            "visual": "Pass. Two different bridges, dark water, overcast night. A distant vehicle on the bridge is not the subject.",
            "swap": "No swap. Both bridges are the viewpoint the catalogue asked for, seen from Middelfart.",
        },
        {
            "entry_id": "DK-01-093",
            "region": "Funen",
            "city": "Assens",
            "caption": "Assens Harbour, Assens",
            **n,
            "composition": "Mole, harbour basin, and the town behind \u00b7 AI-generated artistic interpretation",
            "description": (
                f"From the outer mole, Assens harbour is a dark basin of moored boats, with low town roofs and one church tower behind the quay. "
                f"The night is {n['word'].lower()}, about {n['temp']}\u00b0C, and the Little Belt is open beyond the mole. "
                "The mole is quiet. No boat name or shop sign is readable."
            ),
            "alt_text": "AI-generated artistic interpretation of Assens harbour at night, boats and a church tower beyond the mole",
            "viewpoint": "The outer mole at Assens harbour, looking back toward the basin and the town. Approximate researched point 55.26801, 9.88564, not a surveyed camera.",
            "refs": [
                "https://www.visitassens.dk/assens/det-sker/molehovedet-ved-assens-gdk1093023",
                "https://en.wikipedia.org/wiki/Assens,_Denmark",
            ],
            "anchors": [
                "An outer mole and a harbour basin.",
                "Moored boats without readable names.",
                "Low town roofs and one church tower. Open water of the Little Belt.",
            ],
            "solar": clock("DK-01-093") + "Quay lamps. The overcast hides the far shore.",
            "independent": "Assens is a small harbour town on the west coast of Funen, facing the Little Belt, with the islands of Årø and Bågø offshore. VisitAssens describes the mole head as a public lookout over the harbour, the old town, and the belt. The town church tower is part of that roofscape. This is a night view back from the mole, not a daytime panorama with the far islands called out as identified shapes.",
            "ip": "No readable boat names or shop signs. Internal review only, not a legal certification.",
            "visual": "Pass. Mole, boats, town tower, overcast night. No featured logos.",
            "swap": "No swap. Assens harbour from the mole is the catalogue site.",
        },
        {
            "entry_id": "DK-01-094",
            "region": "Central Jutland",
            "city": "Billund",
            "caption": "Billund Church, Billund",
            **o,
            "composition": "Mocha-brick church and a freestanding bell tower \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Billund Church is a low modern complex of dark mocha brick, with offset volumes, glass, and a separate slender bell tower, on a quiet town street. "
                f"The night is {o['word'].lower()}, about {o['temp']}\u00b0C, with faint moonlight and no snow. "
                "There are no toy bricks and no readable wordmark."
            ),
            "alt_text": "AI-generated artistic interpretation of Billund Church at night, a dark brick building and a separate bell tower",
            "viewpoint": "The town-center street in front of Billund Church, looking at the brick volumes and the freestanding bell tower. Approximate researched point 55.73022, 9.11800, not a surveyed camera.",
            "refs": [
                "https://www.grenesogn.dk/kirkerne/billund-kirke",
                "https://trap.lex.dk/Kirker_i_Billund_Kommune",
            ],
            "anchors": [
                "Dark mocha brick in a modern, offset composition.",
                "A separate slender bell tower.",
                "An ordinary town street. No toy bricks and no wordmark.",
            ],
            "solar": clock("DK-01-094") + "Faint moonlight is plausible under this cloud cover. Street light is ordinary, not a theme-park wash.",
            "independent": "Billund Kirke was built in 1971–73 as part of Billund Centret, designed by Einar and Kuno Meilby, and opened on 15 April 1973. The walls are dark mocha brick in a herringbone bond, with glass bays, and a freestanding bell tower about 17 metres tall. The build was financed by Ole Kirks Fond and the Kirk Christiansen family. The theme park and the airport are elsewhere in town and are not in this frame. Jelling is already DK-01-052.",
            "ip": "No LEGO wordmark, no toy-brick pattern as a logo, and no foundation name on the facade. Internal review only, not a legal certification.",
            "visual": "Pass. Mocha-brick church, separate bell tower, mainly clear night, no snow and no brand mark.",
            "swap": (
                "Swapped away from LEGOLAND, from Givskud Zoo, from Billund Airport, from Jelling (already DK-01-052), and from Give. "
                "The scene is Billund Church in the town center. No LEGO mark is the subject."
            ),
        },
        {
            "entry_id": "DK-01-095",
            "region": "South Jutland",
            "city": "Esbjerg",
            "caption": "Men at Sea, Esbjerg",
            **p,
            "composition": "Four white seated figures facing the sea \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Four huge white seated figures sit in a row on the grass bank at Sædding Strand, all facing the dark North Sea, with the beach below. "
                f"The night is {p['word'].lower()}, about {p['temp']}\u00b0C, and faint moonlight is on the white concrete. "
                "They read as a monument, not as living people. No museum sign is in the frame."
            ),
            "alt_text": "AI-generated artistic interpretation of Men at Sea at Esbjerg at night, four white seated figures facing the water",
            "viewpoint": "The public grass bank at Sædding Strand, looking at the four figures and the sea. Approximate researched point 55.48779, 8.41115, not a surveyed camera.",
            "refs": [
                "https://www.rundtidanmark.dk/mennesket-ved-havet/",
                "https://en.wikipedia.org/wiki/Esbjerg",
            ],
            "anchors": [
                "Exactly four white seated figures in a row.",
                "A grass bank above a beach and the sea.",
                "No museum building and no readable sign.",
            ],
            "solar": clock("DK-01-095") + "Faint moonlight on the white concrete. A few distant path lamps.",
            "independent": "Mennesket ved Havet, Men at Sea, is four white concrete seated male figures, each about 9 metres tall, made by Svend Wiig Hansen and set up in 1995 on the bank above Sædding Strand, north of Esbjerg. They face the sea and can be seen from offshore. The Fisheries and Maritime Museum is nearby and is not the subject of this frame.",
            "ip": (
                "The sculpture is by Svend Wiig Hansen, who died in 1997. Copyright in the work may still sit with his heirs. "
                "This is an exterior public-landmark interpretation. Third-party rights are not waived. "
                "No museum logo. Internal review only, not a legal certification."
            ),
            "visual": "Pass. Four white seated figures, grass, sea, mainly clear night. No readable sign.",
            "swap": (
                "No swap. Men at Sea is the public sculpture the catalogue preferred. "
                "The harbour was the fallback and was not needed. Rights in the sculpture are noted under the IP gate."
            ),
        },
        {
            "entry_id": "DK-01-096",
            "region": "South Jutland",
            "city": "Mandø",
            "caption": "Mandø, Mandø",
            **q,
            "composition": "Brick church and a wooden bell frame on a marsh mound \u00b7 AI-generated artistic interpretation",
            "description": (
                f"Mandø's small red-brick church has no tower. It sits on a raised mound, with a separate dark wooden bell frame and a pyramidal roof just west of it. "
                f"The night is {q['word'].lower()}, about {q['temp']}\u00b0C, over flat marsh and dark tidal flats. "
                "A few warm windows mark the low houses. The causeway is not the subject, and the tide was not checked."
            ),
            "alt_text": "AI-generated artistic interpretation of Mandø at night, a brick church and wooden bell frame on a marsh mound",
            "viewpoint": "The village mound at Mandø, looking at the church and the bell frame, with the marsh beyond. Approximate researched point 55.27205, 8.53811, not a surveyed camera.",
            "refs": [
                "https://da.wikipedia.org/wiki/Mand%C3%B8_Kirke",
                "https://www.vadehavskysten.dk/ribe-esbjerg-fanoe/ribe-esbjerg-fanoe/mandoe-kirke-gdk775693",
            ],
            "anchors": [
                "A small red-brick church without a tower, on a raised mound.",
                "A separate dark wooden bell frame with a pyramidal roof to the west.",
                "Flat marsh and a dark tidal horizon. No causeway traffic.",
            ],
            "solar": clock("DK-01-096") + "Faint moonlight on the marsh. A few warm windows.",
            "independent": "Mandø is a hallig in the Wadden Sea, in Esbjerg Municipality, reached by a causeway that floods at high tide. The church of 1639, restored in 1727, is a brick longhouse without a tower, on a warft so it stays above storm water. The porch of 1792 has two doors, used according to the wind. A tarred bell frame west of the church dates from 1939. The postal town is Ribe; the settlement in the caption is Mandø. The Wadden Sea Centre at Ribe is a different building and is not shown. DK-01-013 is Ribe Cathedral.",
            "ip": "No centre logo and no readable road sign. Church exterior only. Internal review only, not a legal certification.",
            "visual": "Pass. Towerless brick church, separate bell frame, marsh, mainly clear night. No causeway traffic.",
            "swap": (
                "Swapped away from the Ribe Wadden Sea Centre. The scene is the village on Mandø. "
                "City is Mandø, the island settlement. 6760 Ribe is the postal town and is not used as the caption city."
            ),
        },
    ]


def load_all_scenes() -> list:
    found = []
    for path in sorted((bd.ROOT / "manifests").glob("DK-01-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        found.append({"_manifest": data})
    found.sort(key=lambda item: item["_manifest"]["entry_id"])
    return found


def verify_art50(paths: list[Path]) -> None:
    expected = {
        "Title": bd.ART50["Title"],
        "Description": bd.ART50["Description"],
        "Copyright": bd.ART50["Copyright"],
        "Software": bd.ART50["Software"],
        "Comment": bd.ART50["Comment"],
    }
    for path in paths:
        parsed = bd.read_text_chunks(path)
        for key, val in expected.items():
            if parsed.get(key) != val:
                raise SystemExit(f"art50 {path} {key}: {parsed.get(key)!r}")
        if "\u2019" in parsed["Title"] or "\u2019" in parsed["Copyright"]:
            raise SystemExit(f"curly apostrophe in metadata {path}")
        if "\u2014" not in parsed["Title"] or "\u2014" not in parsed["Copyright"]:
            raise SystemExit(f"missing em dash {path}")
        if "Denmark" not in parsed["Description"]:
            raise SystemExit(f"country {path}")
        im = Image.open(path)
        if path.name.endswith("-16x9.png") and im.size != (1920, 1080):
            raise SystemExit(f"size {path} {im.size}")
        if path.name.endswith("-4x5.png") and im.size != (864, 1080):
            raise SystemExit(f"size {path} {im.size}")


def main() -> None:
    prepare_raws()
    stamp, wx, moon = fetch_weather()
    print("moon", moon)
    if any(row["is_day"] != 0 for row in wx.values()):
        raise SystemExit(f"expected night, got { {k: v['is_day'] for k, v in wx.items()} }")
    batch = scenes(stamp, wx, moon)
    if len(batch) != 16:
        raise SystemExit(len(batch))
    lines = []
    masters: list[Path] = []
    for scene in batch:
        label = bd.scenario_label(scene["entry_id"])
        bd.write_outputs(scene, label)
        bd.manifest(scene, label)
        bd.approval(scene, label)
        masters.extend(scene["_files"].values())
        entry = scene["entry_id"].lower()
        city = scene["city"]
        lines.append(
            f"**{scene['entry_id']} \u2014 {scene['caption']}** \u00b7 Scenario: {label} \u00b7 "
            f"Weather: {scene['weather_prefix']} {scene['weather_detail']} \u00b7 "
            f"Masters: `Denmark/{city}/{entry}-16x9.png`, `Denmark/{city}/{entry}-4x5.png` \u00b7 Gates: 5/5 pass."
        )
        print(lines[-1])
    verify_art50(masters)
    all_scenes = load_all_scenes()
    if len(all_scenes) != 96:
        raise SystemExit(f"expected 96 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 97)]
    if ids != expected:
        raise SystemExit(ids)
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-081-096.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    for path in masters:
        subprocess.run(
            ["exiftool", "-Title", "-Description", "-Copyright", "-Software", "-Comment", str(path)],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    print("site written", len(all_scenes))
    print("exiftool checked", len(masters))


if __name__ == "__main__":
    main()
