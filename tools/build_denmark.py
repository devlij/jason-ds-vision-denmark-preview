#!/usr/bin/env python3
"""Bake Denmark masters, Art. 50 PNG text, approvals, manifests, and the gallery."""

from __future__ import annotations

import hashlib
import json
import os
import struct
import zlib
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

ROOT = Path("/workspace")
RAW = Path("/opt/cursor/artifacts/assets")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
CPH = ZoneInfo("Europe/Copenhagen")
SIG = "Jason D\u2019s Vision"
DISCLOSURE = "AI-generated artistic interpretation \u00b7 Not a photograph."

ART50 = {
    "Title": "Jason D's Vision \u2014 AI-generated artistic interpretation",
    "Description": "AI-generated artistic interpretation from the Jason D's Vision Denmark gallery. Created with generative AI; not a photograph.",
    "Copyright": "Jason D's Vision \u2014 AI-generated content",
    "Software": "Jason D's Vision library pipeline",
    "Comment": "EU AI Act Art. 50 transparency note: this image is AI-generated content. Machine-readable disclosure embedded 2026-09-24.",
}
ITXT_KEYS = {"Title", "Copyright"}

EARLY = (
    "Model data from Open-Meteo, retrieved 24 September 2026 23:52 Europe/Copenhagen, "
    "valid 24 September 2026 23:45 Europe/Copenhagen \u2014 not a verified on-site observation."
)
LATE = (
    "Model data from Open-Meteo, retrieved 25 September 2026 00:02 Europe/Copenhagen, "
    "valid 25 September 2026 00:00 Europe/Copenhagen \u2014 not a verified on-site observation."
)
LATE_FAROE = (
    "Model data from Open-Meteo, retrieved 25 September 2026 00:02 Europe/Copenhagen, "
    "valid 24 September 2026 23:00 Atlantic/Faroe (the same instant as 25 September 2026 00:00 Europe/Copenhagen) "
    "\u2014 not a verified on-site observation."
)
LATE_GREENLAND = (
    "Model data from Open-Meteo, retrieved 25 September 2026 00:02 Europe/Copenhagen, "
    "valid 24 September 2026 21:00 America/Nuuk (the same instant as 25 September 2026 00:00 Europe/Copenhagen) "
    "\u2014 not a verified on-site observation."
)

LINEAGE = (
    "Text-prompt-only. No photographic reference pixels. "
    "The 16:9 master is a uniform Lanczos resample from the generated 1280\u00d7720 frame to 1920\u00d71080. "
    "The 4:5 master is a centered crop of the generated 864\u00d71152 frame to 864\u00d71080, with no upscale."
)

SCENES = [
    {
        "entry_id": "DK-01-001",
        "region": "Capital Region",
        "city": "Copenhagen",
        "caption": "Nyhavn, Copenhagen",
        "weather_prefix": EARLY,
        "weather_detail": "Mainly clear, 14.0\u00b0C, cloud cover 34%, wind 5.0 km/h, no precipitation.",
        "weather_brief": "mainly clear, 14.0\u00b0C",
        "composition": "North-bank townhouses along the Nyhavn canal, looking east \u00b7 AI-generated artistic interpretation",
        "description": "From the quay at the Kongens Nytorv end, the view looks east down Nyhavn. The narrow gabled townhouses stand along the north bank, with moored wooden boats in the canal and the lower south quay to the right. It is a mainly clear night, about 14.0\u00b0C, with warm window and lamp light on the water. The harbor mouth is in the distance; fine shopfront lettering is not treated as real signage.",
        "alt_text": "AI-generated artistic interpretation of Nyhavn in Copenhagen at night, with gabled townhouses reflected in the canal",
        "viewpoint": "Cobbled quay at the Kongens Nytorv end of Nyhavn, looking east toward the harbor mouth. Approximate researched point 55.6798, 12.5876, not a surveyed camera.",
        "refs": [
            "https://www.visitcopenhagen.com/copenhagen/planning/nyhavn-gdk474735",
            "https://en.wikipedia.org/wiki/Nyhavn",
        ],
        "anchors": [
            "Continuous row of narrow gabled townhouses along the north bank, left of frame when looking east.",
            "Canal water and moored traditional boats in the center.",
            "Lower south quay on the right, with the harbor mouth in the distance.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:03 Europe/Copenhagen at this site. A waxing gibbous moon near 96% illumination was computed for 21:45 UTC, not observed on site. Cloud cover 34%, so some moonlight is plausible.",
        "independent": "Nyhavn is the 17th-century canal from Kongens Nytorv to the harbor. The postcard view is the colorful north-bank houses, masts, and reflections.",
        "ip": "No featured logos. Internal review only, not a legal certification.",
        "visual": "Pass. Canal, north-bank gables, and moored boats match the Kongens Nytorv viewpoint. No second bridge invented across the canal.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-002",
        "region": "Capital Region",
        "city": "Copenhagen",
        "caption": "The Little Mermaid, Copenhagen",
        "weather_prefix": EARLY,
        "weather_detail": "Mainly clear, 13.7\u00b0C, cloud cover 32%, wind 5.8 km/h, no precipitation.",
        "weather_brief": "mainly clear, 13.7\u00b0C",
        "composition": "Bronze mermaid on the Langelinie rock, harbor behind \u00b7 AI-generated artistic interpretation",
        "description": "From the Langelinie promenade, Edvard Eriksen's small bronze mermaid sits on the granite rock at the water, tail and bowed head reading as the sculpture rather than a living figure. Harbor water and distant shore lights fill the background under a mainly clear night sky, about 13.7\u00b0C. The promenade is empty at this hour. A distant light structure in the generated frame is not identified as a named lighthouse.",
        "alt_text": "AI-generated artistic interpretation of the Little Mermaid bronze statue at Langelinie in Copenhagen at night",
        "viewpoint": "Langelinie promenade immediately beside the statue, looking across the rock toward the harbor. Approximate researched point 55.6929, 12.5993, not a surveyed camera.",
        "refs": [
            "https://www.visitcopenhagen.com/copenhagen/planning/little-mermaid-gdk586951",
            "https://en.wikipedia.org/wiki/The_Little_Mermaid_(statue)",
        ],
        "anchors": [
            "Small bronze seated figure with a fish tail on a rock at the waterline.",
            "Stone promenade in the foreground.",
            "Open harbor water and distant lights behind the rock.",
        ],
        "solar": "Night. Local sunset 19:03 Europe/Copenhagen. Mainly clear, so moonlight and promenade lamps both contribute. Not an on-site light survey.",
        "independent": "The 1913 bronze sits on a rock off Langelinie, small in the frame, with the harbor behind it.",
        "ip": "The sculpture is by Edvard Eriksen, who died in 1959; the heirs have historically asserted rights in the statue. This is an exterior landmark interpretation requested for the gallery. Third-party rights are not waived. Internal review only, not a legal certification.",
        "visual": "Pass. The subject is the small bronze on the rock at Langelinie, not a living mermaid and not a cartoon.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-003",
        "region": "Capital Region",
        "city": "Copenhagen",
        "caption": "Amalienborg, Copenhagen",
        "weather_prefix": EARLY,
        "weather_detail": "Mainly clear, 13.7\u00b0C, cloud cover 34%, wind 5.0 km/h, no precipitation.",
        "weather_brief": "mainly clear, 13.7\u00b0C",
        "composition": "Palace square, equestrian statue, and the Marble Church dome \u00b7 AI-generated artistic interpretation",
        "description": "The octagonal palace square is framed by the pale rococo wings, with Saly's equestrian statue of Frederik V in the middle. Along the Frederiksgade axis the copper dome of Frederik's Church, the Marble Church, rises behind the palaces. It is a mainly clear night, about 13.7\u00b0C, with warm light on the facades and an empty square. Whether a Dannebrog was flying because the monarch was in residence was not verified for this hour.",
        "alt_text": "AI-generated artistic interpretation of Amalienborg palace square in Copenhagen at night, with the Marble Church dome beyond",
        "viewpoint": "On Amalienborg Slotsplads, looking along Frederiksgade toward the Marble Church. Approximate researched point 55.6841, 12.5930, not a surveyed camera.",
        "refs": [
            "https://www.visitcopenhagen.com/copenhagen/planning/amalienborg-palace-gdk492887",
            "https://en.wikipedia.org/wiki/Amalienborg",
        ],
        "anchors": [
            "Four matching rococo palace facades around an octagonal square.",
            "Equestrian statue on a pedestal at the center.",
            "Marble Church dome centered on the axis beyond the palaces.",
        ],
        "solar": "Night. Sunset 19:03 Europe/Copenhagen. Mainly clear. Facade light is the ordinary city-night appearance, not a verified lighting plot.",
        "independent": "Amalienborg is four identical rococo palaces around Frederik V's statue, with the Marble Church dome on the Frederiksgade axis.",
        "ip": "No featured commercial logos. Royal emblems, if present, are architectural. Internal review only, not a legal certification.",
        "visual": "Pass. Square, central rider, rococo wings, and the dome on axis are all present.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-004",
        "region": "Capital Region",
        "city": "Helsing\u00f8r",
        "caption": "Kronborg Castle, Helsing\u00f8r",
        "weather_prefix": EARLY,
        "weather_detail": "Mainly clear, 14.8\u00b0C, cloud cover 40%, wind 10.4 km/h, no precipitation.",
        "weather_brief": "mainly clear, 14.8\u00b0C",
        "composition": "Seaward sandstone facade and copper spires across the \u00d8resund \u00b7 AI-generated artistic interpretation",
        "description": "From the seaward side, Kronborg's pale sandstone walls and green copper spires stand above the \u00d8resund, with the square tower in the silhouette. A thin band of lights on the far shore is Helsingborg across the strait. The night is mainly clear, about 14.8\u00b0C, with a moderate breeze and only a little chop. The castle is moonlit, with a few warm windows, not a floodlight show; after-dark visits here are flashlight tours rather than a published facade-lighting scheme.",
        "alt_text": "AI-generated artistic interpretation of Kronborg Castle in Helsing\u00f8r at night, moonlit above the \u00d8resund",
        "viewpoint": "Seaward rampart or beach side, looking at the \u00d8resund facade with Sweden beyond. Approximate researched point 56.0394, 12.6220, not a surveyed camera.",
        "refs": [
            "https://kronborg.dk/en",
            "https://en.wikipedia.org/wiki/Kronborg",
        ],
        "anchors": [
            "Pale sandstone Renaissance castle with green copper spires.",
            "Square tower in the silhouette.",
            "\u00d8resund in front and a distant band of lights on the Swedish shore.",
        ],
        "solar": "Night. Sunset 19:03 Europe/Copenhagen. Cloud cover 40%. Moonlight on the stone is consistent with the computed bright moon and was not surveyed.",
        "independent": "Kronborg stands on the \u00d8resund at Helsing\u00f8r, with Helsingborg visible across the narrow strait.",
        "ip": "No featured logos. Internal review only, not a legal certification.",
        "visual": "Pass. Sandstone castle, copper roofs, water, and a distant opposite shore. No theme-park lighting.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-005",
        "region": "Capital Region",
        "city": "Hiller\u00f8d",
        "caption": "Frederiksborg Castle, Hiller\u00f8d",
        "weather_prefix": EARLY,
        "weather_detail": "Partly cloudy, 12.0\u00b0C, cloud cover 50%, wind 3.2 km/h, no precipitation.",
        "weather_brief": "partly cloudy, 12.0\u00b0C",
        "composition": "Red-brick castle and copper spires across Slotss\u00f8en \u00b7 AI-generated artistic interpretation",
        "description": "From the shore of the castle lake, Frederiksborg's red-brick Renaissance ranges and copper-green spires sit on the islets, with the dark water in the foreground. The night is partly cloudy, about 12.0\u00b0C, and the light wind only ripples the reflection. A few windows are warm. The baroque garden on the far side of the complex is not the subject of this lake view.",
        "alt_text": "AI-generated artistic interpretation of Frederiksborg Castle in Hiller\u00f8d at night, seen across the castle lake",
        "viewpoint": "Public shore of Slotss\u00f8en looking toward the castle. Approximate researched point 55.9336, 12.3006, not a surveyed camera.",
        "refs": [
            "https://frederiksborg.dk/en/frederiksborg-castle/",
            "https://en.wikipedia.org/wiki/Frederiksborg_Castle",
        ],
        "anchors": [
            "Red-brick Dutch Renaissance palace with many copper spires.",
            "Castle standing in the lake, water in the foreground.",
            "Broken reflection under partial cloud.",
        ],
        "solar": "Night. Sunset 19:04 Europe/Copenhagen. Cloud cover 50%, so the moon is partly veiled.",
        "independent": "Christian IV's Frederiksborg stands on three islets in the castle lake at Hiller\u00f8d.",
        "ip": "No featured logos. Internal review only, not a legal certification.",
        "visual": "Pass. Brick palace, copper towers, and lake reflection match the south-shore view.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-006",
        "region": "Zealand",
        "city": "Roskilde",
        "caption": "Roskilde Cathedral, Roskilde",
        "weather_prefix": EARLY,
        "weather_detail": "Partly cloudy, 12.0\u00b0C, cloud cover 76%, wind 8.3 km/h, no precipitation.",
        "weather_brief": "partly cloudy, 12.0\u00b0C",
        "composition": "West front and the pair of slender spires \u00b7 AI-generated artistic interpretation",
        "description": "From the cathedral close, the west front of Roskilde Cathedral shows its pair of tall pointed spires above the brick Gothic body. The night is partly cloudy with cloud cover about 76%, about 12.0\u00b0C, so the moon is mostly hidden and the brick reads by street lamps. The square is empty. Later royal burial chapels are not claimed as part of this west-front frame.",
        "alt_text": "AI-generated artistic interpretation of Roskilde Cathedral at night, with its two slender spires",
        "viewpoint": "Cathedral close, looking at the west front. Approximate researched point 55.6425, 12.0799, not a surveyed camera.",
        "refs": [
            "https://roskildedomkirke.dk/",
            "https://en.wikipedia.org/wiki/Roskilde_Cathedral",
        ],
        "anchors": [
            "Two tall slender spires, a pair, not a single square tower.",
            "Red-brick Gothic west front.",
            "Open close in the foreground, empty at night.",
        ],
        "solar": "Night. Sunset 19:05 Europe/Copenhagen. High cloud cover, so lamp light dominates over moonlight.",
        "independent": "Roskilde Cathedral's west front is known by its twin slender spires. It is a different silhouette from Ribe's single square tower.",
        "ip": "No featured logos. Internal review only, not a legal certification.",
        "visual": "Pass. Twin spires and brick west front, not Ribe's square tower.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-007",
        "region": "Lolland-Falster",
        "city": "Borre",
        "caption": "M\u00f8ns Klint, Borre",
        "weather_prefix": EARLY,
        "weather_detail": "Clear, 12.7\u00b0C, cloud cover 18%, wind 6.5 km/h, no precipitation.",
        "weather_brief": "clear, 12.7\u00b0C",
        "composition": "White chalk cliffs and the Baltic from the cliff-top path \u00b7 AI-generated artistic interpretation",
        "description": "From the cliff-top path, the white chalk face of M\u00f8ns Klint drops to a narrow beach and the Baltic, with beech trees along the edge. Leaves are still mostly green in late September, with only a little early yellow. The night is clear, about 12.7\u00b0C, and the chalk takes the moonlight. The portrait includes the wooden stair that visitors use on this cliff; the wide frame is the cliff line itself.",
        "alt_text": "AI-generated artistic interpretation of the white chalk cliffs at M\u00f8ns Klint under a clear night sky",
        "viewpoint": "Cliff-top path above the chalk face, near the main M\u00f8ns Klint lookout beyond GeoCenter M\u00f8ns Klint (Steng\u00e5rdsvej 8, 4791 Borre). Approximate researched point 54.9645, 12.5483, not a surveyed camera.",
        "refs": [
            "https://moensklint.dk/en/plan-your-visit/",
            "https://eng.naturstyrelsen.dk/experience-nature/explore-denmark-s-nature-with-our-guides/moens-klint/practical",
        ],
        "anchors": [
            "Sheer white chalk cliff falling to a dark beach and the Baltic.",
            "Beech trees on the cliff edge, still mostly green.",
            "Clear moonlit sky, no resort buildings in the view.",
        ],
        "solar": "Night. Sunset 19:03 Europe/Copenhagen. Cloud cover 18% and a bright computed moon, so the cliffs are moonlit. Not surveyed on site.",
        "independent": "M\u00f8ns Klint is the chalk cliff on eastern M\u00f8n. The postal address of the GeoCenter is 4791 Borre.",
        "ip": "No featured logos. Internal review only, not a legal certification.",
        "visual": "Pass. White chalk, beech edge, beach, and sea. No invented resort skyline.",
        "swap": "Kit place-name was M\u00f8n. Honest city is Borre: GeoCenter M\u00f8ns Klint is at Steng\u00e5rdsvej 8, 4791 Borre, in Vordingborg Municipality. The town of Vordingborg is on Zealand, and Stege is the island's main town several kilometres west of the cliffs, so neither is the site's own town. Gallery region follows the kit coverage row Lolland-Falster. Administratively the municipality sits in Region Zealand.",
    },
    {
        "entry_id": "DK-01-008",
        "region": "Funen",
        "city": "Odense",
        "caption": "H.C. Andersen Quarter, Odense",
        "weather_prefix": LATE,
        "weather_detail": "Overcast, 13.4\u00b0C, cloud cover 100%, wind 16.2 km/h, no precipitation.",
        "weather_brief": "overcast, 13.4\u00b0C",
        "composition": "Ochre corner house and half-timbered lane in the birthplace quarter \u00b7 AI-generated artistic interpretation",
        "description": "The frame is the narrow cobbled lane of the H.C. Andersen birthplace quarter: a low ochre corner house with a red tile roof and warm windows, and half-timbered neighbours. The sky is overcast, about 13.4\u00b0C, with a fresh wind and no rain, so the moon is hidden and the street lamps carry the light. The lane is empty. Facade joints are a generated interpretation of the quarter, not a measured survey of the birthplace elevation. The new museum building is outside this frame.",
        "alt_text": "AI-generated artistic interpretation of the H.C. Andersen birthplace quarter in Odense on an overcast night",
        "viewpoint": "The cobbled lane at the birthplace quarter, Hans Jensens Str\u00e6de / Bangs Boder area. Approximate researched point 55.3978, 10.3890, not a surveyed camera. Exact facade geometry was not measured.",
        "refs": [
            "https://hcandersenshus.dk/en/",
            "https://en.wikipedia.org/wiki/Hans_Christian_Andersen",
        ],
        "anchors": [
            "Low ochre corner house with a red tile roof.",
            "Half-timbered neighbours and cobbles.",
            "No modern glass block in the frame.",
        ],
        "solar": "Night, just after midnight Europe/Copenhagen. Overcast, so no moon disk. Sunset the previous evening was 19:12 Europe/Copenhagen at this site.",
        "independent": "Andersen's birthplace quarter is the low old houses around the yellow corner house in central Odense, beside the newer museum.",
        "ip": "No featured logos or readable shop names intended. Internal review only, not a legal certification.",
        "visual": "Pass. Old quarter only. A first wide frame that invented a glass tower behind the lane was replaced before publish.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-009",
        "region": "Funen",
        "city": "Kv\u00e6rndrup",
        "caption": "Egeskov Castle, Kv\u00e6rndrup",
        "weather_prefix": EARLY,
        "weather_detail": "Overcast, 12.1\u00b0C, cloud cover 100%, wind 14.0 km/h, no precipitation.",
        "weather_brief": "overcast, 12.1\u00b0C",
        "composition": "Moated red-brick castle with copper spires \u00b7 AI-generated artistic interpretation",
        "description": "From the west bank, Egeskov's red-brick Renaissance walls and copper spires stand in the dark moat, with a rippled reflection rather than a mirror. The night is overcast, about 12.1\u00b0C, with a breeze near 14 km/h and no rain. A few windows are lit. Late-September lawns are dark; this is not a summer flower show, and the vehicle museum is not in the frame.",
        "alt_text": "AI-generated artistic interpretation of Egeskov Castle at Kv\u00e6rndrup at night, standing in its moat",
        "viewpoint": "West bank of the moat, the usual visitor view of the castle in the water. Address Egeskov Gade 22, 5772 Kv\u00e6rndrup. Approximate researched point 55.1786, 10.4885, not a surveyed camera.",
        "refs": [
            "https://egeskov.dk/en/",
            "https://en.wikipedia.org/wiki/Egeskov_Castle",
        ],
        "anchors": [
            "Red-brick castle with towers and copper spires sitting in a moat.",
            "Water in the foreground with a broken reflection.",
            "Dark lawn, overcast sky, no car museum.",
        ],
        "solar": "Night. Sunset 19:12 Europe/Copenhagen. Full cloud cover, so window light and a dark sky, not moonlight.",
        "independent": "Egeskov is the moated Renaissance castle at Kv\u00e6rndrup. The official visitor address is Egeskov Gade 22, 5772 Kv\u00e6rndrup, in Faaborg-Midtfyn Municipality.",
        "ip": "No vintage-car badges or other featured logos. Internal review only, not a legal certification.",
        "visual": "Pass. Moated brick castle under an overcast night sky.",
        "swap": "Kit city was Kerteminde. Egeskov is not in Kerteminde. The castle's own address is Egeskov Gade 22, 5772 Kv\u00e6rndrup, Faaborg-Midtfyn Municipality, on southern Funen. Caption and city folder use Kv\u00e6rndrup. Region stays Funen, as in the kit coverage row.",
    },
    {
        "entry_id": "DK-01-010",
        "region": "Central Jutland",
        "city": "Aarhus",
        "caption": "Den Gamle By, Aarhus",
        "weather_prefix": EARLY,
        "weather_detail": "Overcast, 13.5\u00b0C, cloud cover 100%, wind 16.2 km/h, no precipitation.",
        "weather_brief": "overcast, 13.5\u00b0C",
        "composition": "Cobbled museum square of half-timbered houses after closing \u00b7 AI-generated artistic interpretation",
        "description": "Inside Den Gamle By, the cobbled square is lined with half-timbered merchant houses, red tile roofs, and small-paned windows. It is an overcast night, about 13.5\u00b0C, with wind near 16 km/h and historic-style lamps still on. The museum is not on a late-evening summer schedule in late September, so the square is empty and there are no modern cars. Individual house identities in the generated square were not matched beam by beam to the museum plan.",
        "alt_text": "AI-generated artistic interpretation of the old-town square at Den Gamle By in Aarhus on an overcast night",
        "viewpoint": "The open-air museum's old-town square. Museum address Viborgvej 2, 8000 Aarhus C. Approximate researched point 56.1587, 10.1913, not a surveyed camera.",
        "refs": [
            "https://www.dengamleby.dk/en",
            "https://en.wikipedia.org/wiki/Den_Gamle_By",
        ],
        "anchors": [
            "Half-timbered houses around a cobbled square.",
            "Warm lamps, overcast sky.",
            "No modern cars and no crowd, consistent with after-hours.",
        ],
        "solar": "Night. Sunset 19:13 Europe/Copenhagen. Overcast, so lamp light only.",
        "independent": "Den Gamle By is the open-air old town at Viborgvej 2 in Aarhus. Its streets are a museum, not a living commercial high street.",
        "ip": "No readable brand signs intended. Internal review only, not a legal certification.",
        "visual": "Pass. Half-timbered museum town, empty, overcast night.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-011",
        "region": "Central Jutland",
        "city": "Aarhus",
        "caption": "ARoS, Aarhus",
        "weather_prefix": EARLY,
        "weather_detail": "Overcast, 13.6\u00b0C, cloud cover 100%, wind 16.2 km/h, no precipitation.",
        "weather_brief": "overcast, 13.6\u00b0C",
        "composition": "Street-level exterior of the brick cube and rainbow roof ring \u00b7 AI-generated artistic interpretation",
        "description": "From the plaza on Aros All\u00e9, the dark brick cube of ARoS fills the frame and the circular glass walkway on the roof reads as a rainbow ring against an overcast sky. It is about 13.6\u00b0C, with wind near 16 km/h and no rain. This is an exterior tourist view only; no gallery interior is shown. Weekday public hours end at 21:00, and whether the ring stays lit after closing on this night was not confirmed. The depiction follows the documented night beacon of the rooftop ring.",
        "alt_text": "AI-generated artistic interpretation of the ARoS museum exterior in Aarhus at night, with the rainbow ring on the roof",
        "viewpoint": "Street plaza outside ARoS, Aros All\u00e9 2, 8000 Aarhus, looking up at the cube and roof ring. Approximate researched point 56.1537, 10.1997, not a surveyed camera.",
        "refs": [
            "https://www.aros.dk/en/",
            "https://en.wikipedia.org/wiki/ARoS_Aarhus_Kunstmuseum",
        ],
        "anchors": [
            "Cubic dark brick museum, seen from street level.",
            "Circular rainbow glass ring on the roof, spanning the cube.",
            "Overcast night sky, no interior galleries.",
        ],
        "solar": "Night. Sunset 19:13 Europe/Copenhagen. Overcast. The ring is the light source in the frame.",
        "independent": "ARoS is the cubic brick museum on Aros All\u00e9. The rooftop circle is Olafur Eliasson's Your rainbow panorama, a glass walkway visitors see from the street.",
        "ip": "Your rainbow panorama is an artwork by Olafur Eliasson. Only the exterior tourists see from the plaza is depicted, not interior works. Third-party rights are not waived. Internal review only, not a legal certification.",
        "visual": "Pass. Exterior cube and roof ring only.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-012",
        "region": "North Jutland",
        "city": "Skagen",
        "caption": "Grenen, Skagen",
        "weather_prefix": LATE,
        "weather_detail": "Overcast, 14.2\u00b0C, cloud cover 100%, wind 14.8 km/h, no precipitation.",
        "weather_brief": "overcast, 14.2\u00b0C",
        "composition": "Sand spit where two wave trains meet \u00b7 AI-generated artistic interpretation",
        "description": "The pale sand of Grenen runs into dark water, and waves arrive from two directions and break where the seas meet. The sky is overcast, about 14.2\u00b0C, with wind near 15 km/h and no rain, so there is no moon disk. The spit is empty. The seasonal tractor shuttle is not running at this hour, and no buildings are in the frame. The exact tip of the sandbar shifts with the sea; this is the meeting of the waves, not a surveyed coordinate on the sand.",
        "alt_text": "AI-generated artistic interpretation of Grenen at Skagen at night, where two wave patterns meet around the sand spit",
        "viewpoint": "On the sand at the tip of Grenen, looking along the point. Approximate researched point 57.7455, 10.6465. The standing point on the moving spit was not surveyed.",
        "refs": [
            "https://en.wikipedia.org/wiki/Grenen",
            "https://en.wikipedia.org/wiki/Skagen",
        ],
        "anchors": [
            "Narrow pale sand point surrounded by sea.",
            "Two different wave directions meeting in broken surf.",
            "Overcast sky, no buildings and no people.",
        ],
        "solar": "Night, just after midnight. Sunset the previous evening was 19:11 Europe/Copenhagen. Full cloud cover.",
        "independent": "Grenen is the sandy tip at Skagen where the Skagerrak and Kattegat meet, visible as waves coming from two directions.",
        "ip": "No logos. Internal review only, not a legal certification.",
        "visual": "Pass. Sand tip and two wave trains under cloud. No shuttle vehicle.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-013",
        "region": "South Jutland",
        "city": "Ribe",
        "caption": "Ribe Cathedral, Ribe",
        "weather_prefix": LATE,
        "weather_detail": "Overcast, 12.2\u00b0C, cloud cover 95%, wind 9.4 km/h, no precipitation.",
        "weather_brief": "overcast, 12.2\u00b0C",
        "composition": "Single square Romanesque tower from the cathedral square \u00b7 AI-generated artistic interpretation",
        "description": "From the cathedral square, Ribe Cathedral is dominated by one massive square tower, the Commoner's Tower, in pale stone with rounded Romanesque arches and a low top. It does not have Roskilde's twin spires. Half-timbered eaves sit at the edge of the square. The night is overcast, about 12.2\u00b0C, and the stone is lit by street lamps. The square is empty. Ribe remains the town name; the municipality since 2007 is Esbjerg.",
        "alt_text": "AI-generated artistic interpretation of Ribe Cathedral at night, with its single square Romanesque tower",
        "viewpoint": "Cathedral square, looking at the west end and the square tower. Approximate researched point 55.3281, 8.7616, not a surveyed camera.",
        "refs": [
            "https://www.ribe-domkirke.dk/",
            "https://en.wikipedia.org/wiki/Ribe_Cathedral",
        ],
        "anchors": [
            "One massive square tower, not a pair of spires.",
            "Romanesque rounded arches in pale stone.",
            "Half-timbered town edges and an empty square.",
        ],
        "solar": "Night, just after midnight. Previous sunset 19:16 Europe/Copenhagen. Cloud cover 95%.",
        "independent": "Ribe Cathedral is Denmark's Romanesque cathedral with the large square Commoner's Tower, in the old town of Ribe.",
        "ip": "No featured logos. Internal review only, not a legal certification.",
        "visual": "Pass. Square tower chosen as the single scene for Ribe, not a split old-town-and-cathedral collage.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-014",
        "region": "Bornholm",
        "city": "Allinge",
        "caption": "Hammershus, Allinge",
        "weather_prefix": LATE,
        "weather_detail": "Overcast, 13.9\u00b0C, cloud cover 100%, wind 12.6 km/h, no precipitation.",
        "weather_brief": "overcast, 13.9\u00b0C",
        "composition": "Granite ring-wall ruin above the Baltic \u00b7 AI-generated artistic interpretation",
        "description": "Hammershus is a broken granite ring wall on the rocky headland, with the Baltic below the cliff. The night is fully overcast, about 13.9\u00b0C, with a breeze, so the ruin is dim rather than floodlit. No visitors are in the frame, and the visitor center is not used as the subject. The stones read as a medieval curtain wall, not an intact palace.",
        "alt_text": "AI-generated artistic interpretation of the Hammershus ruins above the Baltic on an overcast night",
        "viewpoint": "Approach view of the ring wall with the sea behind, near the Hammershus visitor center at Slotslyngvej 9, 3770 Allinge. Approximate researched point 55.2712, 14.7552, not a surveyed camera.",
        "refs": [
            "https://bornholm.info/en/hammershus/",
            "https://en.wikipedia.org/wiki/Hammershus",
        ],
        "anchors": [
            "Broken dark granite curtain wall on a headland.",
            "Baltic Sea below and behind the ruin.",
            "Overcast sky and no floodlight wash.",
        ],
        "solar": "Night, just after midnight. Previous sunset 18:52 Europe/Copenhagen. Full cloud cover, so no moonlight on the stone.",
        "independent": "Hammershus is the large medieval ruin on northern Bornholm. The visitor address is 3770 Allinge.",
        "ip": "No logos. Internal review only, not a legal certification.",
        "visual": "Pass. Dark ruin, sea, overcast sky. Not a restored castle and not floodlit.",
        "swap": "Kit place-name was Bornholm, the island. Honest city is Allinge: the visitor center is Slotslyngvej 9, 3770 Allinge, and Allinge-Sandvig is the nearest town. Gallery region is Bornholm, matching the kit coverage row. Bornholm Regional Municipality is administratively inside the Capital Region of Denmark; the gallery does not file this scene under Copenhagen's region label.",
    },
    {
        "entry_id": "DK-01-015",
        "region": "Faroe Islands",
        "city": "G\u00e1sadalur",
        "caption": "M\u00falafossur, G\u00e1sadalur",
        "weather_prefix": LATE_FAROE,
        "weather_detail": "Overcast, 10.7\u00b0C, cloud cover 100%, wind 55.8 km/h, no precipitation.",
        "weather_brief": "overcast, 10.7\u00b0C, wind 55.8 km/h",
        "composition": "Turf-roofed houses and the cliff waterfall into the Atlantic \u00b7 AI-generated artistic interpretation",
        "description": "At the edge of G\u00e1sadalur, a few black wooden houses with green turf roofs sit on the cliff, and M\u00falafossur drops off that cliff into the Atlantic. The local hour is overcast, about 10.7\u00b0C, with a gale near 56 km/h, so the grass is flattened and the fall is torn into spray. No moon is visible. The scenario clock on the image is Europe/Copenhagen, one hour ahead of Atlantic/Faroe. A small boat in the portrait was not verified as present.",
        "alt_text": "AI-generated artistic interpretation of M\u00falafossur at G\u00e1sadalur at night, with turf-roofed houses and a gale",
        "viewpoint": "Village edge at G\u00e1sadalur, looking toward the waterfall and the sea. Approximate researched point 62.1120, -7.4342, not a surveyed camera.",
        "refs": [
            "https://en.wikipedia.org/wiki/G%C3%A1sadalur",
            "https://www.openstreetmap.org/#map=16/62.1120/-7.4342",
        ],
        "anchors": [
            "Turf-roofed houses on the cliff top.",
            "Waterfall leaving the cliff edge and falling to the sea.",
            "Rough water and gale-blown spray under full cloud.",
        ],
        "solar": "Local night in the Faroe Islands (about 23:04 Atlantic/Faroe when the masters were made). Overcast. The printed scenario time is Europe/Copenhagen, as the kit requires for every scene.",
        "independent": "M\u00falafossur falls off the cliff beside the turf-roofed village of G\u00e1sadalur on V\u00e1gar.",
        "ip": "No signs or logos. Internal review only, not a legal certification.",
        "visual": "Pass. Village, cliff fall, and rough sea. An earlier pair showed moonlight under the previous hour's broken cloud and was replaced after the 23:00 Atlantic/Faroe model hour went fully overcast.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-016",
        "region": "Greenland",
        "city": "Ilulissat",
        "caption": "Ilulissat Icefjord, Ilulissat",
        "weather_prefix": LATE_GREENLAND,
        "weather_detail": "Clear, 0.1\u00b0C, cloud cover 1%, wind 6.6 km/h, no precipitation. Local sunset 20:18 America/Nuuk.",
        "weather_brief": "clear, 0.1\u00b0C, civil twilight",
        "composition": "Icebergs in the fjord during local twilight \u00b7 AI-generated artistic interpretation",
        "description": "From the rocky shore south of town, white and blue icebergs fill Ilulissat Icefjord. Local time is about 21:00 America/Nuuk, roughly forty minutes after the 20:18 sunset, so the sky is still clear twilight with an amber glow on the horizon rather than midnight black. It is about 0.1\u00b0C, with almost no cloud. The autumn shore is rock and low rust-colored tundra. The clock printed on the image is Europe/Copenhagen, which is three hours ahead of Nuuk at this date; the light follows Ilulissat, not Copenhagen.",
        "alt_text": "AI-generated artistic interpretation of Ilulissat Icefjord in clear twilight, with icebergs and an amber horizon",
        "viewpoint": "Rocky icefjord shore south of Ilulissat, the usual tourist view over the bergs. Approximate researched area 69.21, -51.10. The exact boardwalk camera point was not surveyed.",
        "refs": [
            "https://visitgreenland.com/destinations/ilulissat/",
            "https://en.wikipedia.org/wiki/Ilulissat_Icefjord",
        ],
        "anchors": [
            "Many large icebergs in a dark fjord.",
            "Clear sky with twilight color still on the horizon, not a noon sky and not full night.",
            "Low rocky autumn shore in the foreground, no town skyline.",
        ],
        "solar": "Local sun set at 20:18 America/Nuuk. The build instant is about 21:00 America/Nuuk, is_day 0, clear. Twilight length is long at 69\u00b0N, so a remaining horizon glow is the honest light. Scenario label remains Europe/Copenhagen.",
        "independent": "Ilulissat Icefjord is the iceberg-filled fjord at the mouth of Sermeq Kujalleq, seen from the shore south of Ilulissat.",
        "ip": "No logos. Internal review only, not a legal certification.",
        "visual": "Pass. Bergs, clear twilight, cold shore. Not a summer midnight-sun scene and not a black midnight.",
        "swap": None,
    },
]


def scenario_label(entry_id: str) -> str:
    times = []
    for kind in ("16x9", "4x5"):
        path = RAW / f"{entry_id.lower()}-{kind}-raw.png"
        times.append(os.path.getmtime(path))
    dt = datetime.fromtimestamp(max(times), CPH)
    month = dt.strftime("%B")
    return f"{dt.day} {month} {dt.year} \u00b7 {dt.strftime('%H:%M')} Europe/Copenhagen"


def cover(im: Image.Image, tw: int, th: int) -> Image.Image:
    im = im.convert("RGB")
    sw, sh = im.size
    scale = max(tw / sw, th / sh)
    nw, nh = round(sw * scale), round(sh * scale)
    im = im.resize((nw, nh), Image.Resampling.LANCZOS)
    left = max(0, (nw - tw) // 2)
    top = max(0, (nh - th) // 2)
    return im.crop((left, top, left + tw, top + th))


def bake_text(im: Image.Image, caption: str, label: str) -> Image.Image:
    w, h = im.size
    im = im.convert("RGBA")
    start = int(h * 0.70)
    grad = Image.new("L", (1, h), 0)
    gp = grad.load()
    span = max(1, h - start)
    for y in range(start, h):
        t = (y - start) / span
        gp[0, y] = int(215 * (t ** 1.05))
    veil = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    veil.putalpha(grad.resize((w, h)))
    im = Image.alpha_composite(im, veil)
    draw = ImageDraw.Draw(im)
    fonts = {
        "c": ImageFont.truetype(FONT, max(1, round(w * 0.016))),
        "s": ImageFont.truetype(FONT, max(1, round(w * 0.012))),
        "d": ImageFont.truetype(FONT, max(1, round(w * 0.010))),
        "g": ImageFont.truetype(FONT, max(1, round(w * 0.018))),
    }
    scenario = f"Scenario: {label}"
    pad_x = round(w * 0.028)
    pad_b = round(h * 0.030)
    gap = max(2, round(w * 0.004))

    def height(text: str, font: ImageFont.FreeTypeFont) -> int:
        box = draw.textbbox((0, 0), text, font=font)
        return box[3] - box[1]

    hd = height(DISCLOSURE, fonts["d"])
    hs = height(scenario, fonts["s"])
    y_d = h - pad_b
    y_s = y_d - hd - gap
    y_c = y_s - hs - gap

    def shadow(xy, text, font, anchor):
        x, y = xy
        draw.text((x + 1, y + 1), text, font=font, fill=(0, 0, 0, 170), anchor=anchor)
        draw.text((x, y), text, font=font, fill=(255, 255, 255, 235), anchor=anchor)

    shadow((pad_x, y_c), caption, fonts["c"], "ls")
    shadow((pad_x, y_s), scenario, fonts["s"], "ls")
    shadow((pad_x, y_d), DISCLOSURE, fonts["d"], "ls")
    shadow((w - pad_x, y_c), SIG, fonts["g"], "rs")
    cap_w = draw.textbbox((0, 0), caption, font=fonts["c"])[2]
    sig_w = draw.textbbox((0, 0), SIG, font=fonts["g"])[2]
    if pad_x + cap_w + 12 > w - pad_x - sig_w:
        raise SystemExit(f"text overlap: {caption}")
    return im.convert("RGB")


def png_chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def tEXt(keyword: str, text: str) -> bytes:
    data = keyword.encode("latin-1") + b"\x00" + text.encode("latin-1")
    return png_chunk(b"tEXt", data)


def iTXt(keyword: str, text: str) -> bytes:
    data = keyword.encode("latin-1") + b"\x00\x00\x00\x00\x00" + text.encode("utf-8")
    return png_chunk(b"iTXt", data)


def embed_art50(path: Path) -> str:
    raw = path.read_bytes()
    sig = b"\x89PNG\r\n\x1a\n"
    if not raw.startswith(sig):
        raise SystemExit(f"not png: {path}")
    before = hashlib.sha256(Image.open(path).tobytes()).hexdigest()
    iend = raw.rfind(b"IEND")
    if iend < 8:
        raise SystemExit(f"no IEND: {path}")
    pos = iend - 4
    extra = b""
    for key, val in ART50.items():
        extra += iTXt(key, val) if key in ITXT_KEYS else tEXt(key, val)
    path.write_bytes(raw[:pos] + extra + raw[pos:])
    after = hashlib.sha256(Image.open(path).tobytes()).hexdigest()
    if before != after:
        raise SystemExit(f"pixels changed: {path}")
    parsed = read_text_chunks(path)
    for key, val in ART50.items():
        got = parsed.get(key)
        if got != val:
            raise SystemExit(f"chunk mismatch {path} {key!r}: {got!r}")
    return before


def read_text_chunks(path: Path) -> dict:
    data = path.read_bytes()
    pos = 8
    found = {}
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        tag = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if tag == b"tEXt":
            key, text = chunk.split(b"\x00", 1)
            found[key.decode("latin-1")] = text.decode("latin-1")
        elif tag == b"iTXt":
            key, rest = chunk.split(b"\x00", 1)
            # flag, method, then lang\0 trans\0 text
            rest = rest[2:]
            _lang, rest = rest.split(b"\x00", 1)
            _trans, text = rest.split(b"\x00", 1)
            found[key.decode("latin-1")] = text.decode("utf-8")
        if tag == b"IEND":
            break
    return found


def write_outputs(scene: dict, label: str) -> None:
    entry = scene["entry_id"]
    city = scene["city"]
    folder = ROOT / "library" / "world" / "Denmark" / city
    folder.mkdir(parents=True, exist_ok=True)
    specs = {
        "16x9": (1920, 1080),
        "4x5": (864, 1080),
    }
    for kind, (tw, th) in specs.items():
        src = RAW / f"{entry.lower()}-{kind}-raw.png"
        im = Image.open(src)
        if kind == "16x9" and im.size != (1280, 720):
            raise SystemExit(f"unexpected 16:9 source {src} {im.size}")
        if kind == "4x5" and im.size != (864, 1152):
            raise SystemExit(f"unexpected 4:5 source {src} {im.size}")
        out = cover(im, tw, th)
        if out.size != (tw, th):
            raise SystemExit(f"bad size {out.size}")
        out = bake_text(out, scene["caption"], label)
        dest = folder / f"{entry.lower()}-{kind}.png"
        out.save(dest, "PNG", optimize=False)
        embed_art50(dest)
        scene.setdefault("_files", {})[kind] = dest


def manifest(scene: dict, label: str) -> None:
    entry = scene["entry_id"]
    city = scene["city"]
    rel16 = f"Denmark/{city}/{entry.lower()}-16x9.png"
    rel45 = f"Denmark/{city}/{entry.lower()}-4x5.png"
    data = {
        "entry_id": entry,
        "country": "Denmark",
        "region": scene["region"],
        "city": city,
        "caption": scene["caption"],
        "scenario_label": label,
        "composition": scene["composition"],
        "description": scene["description"],
        "alt_text": scene["alt_text"],
        "file_16x9": rel16,
        "file_4x5": rel45,
        "license_badge": "Free \u00b7 no credit needed",
        "license_anchor": "#license",
    }
    path = ROOT / "manifests" / f"{entry}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    scene["_manifest"] = data


def approval(scene: dict, label: str) -> None:
    entry = scene["entry_id"]
    swap = scene["swap"] or "No swap. The kit city is the town used in the caption."
    refs = "\n".join(f"  {i}. {url}" for i, url in enumerate(scene["refs"], 1))
    anchors = "\n".join(f"  {i}. {item}" for i, item in enumerate(scene["anchors"], 1))
    weather = f"{scene['weather_prefix']} {scene['weather_detail']}"
    text = f"""# {entry} \u2014 {scene['caption']}

**Status:** Candidate. Not Approved. Awaiting independent QC.

## Evidence card

- **Location / caption:** {scene['caption']}
- **Region:** {scene['region']}
- **City:** {scene['city']}
- **Camera viewpoint:** {scene['viewpoint']}
- **Reference links:**
{refs}
- **Geometry anchors:**
{anchors}
- **Weather:** {weather}
- **Solar direction / time of day:** {scene['solar']}
- **Independent description:** {scene['independent']}
- **Source-use notes:** {LINEAGE} Sources above were consulted for place, viewpoint, and what belongs in the frame. They were not image prompts and no reference pixels were supplied. Commercial use of the finished interpretation is the gallery license; third-party rights, if any, remain with their owners.

## Caption decision

{swap}

## Scenario

`Scenario: {label}`

The scenario clock is the Europe/Copenhagen minute when the later of the two generated frames was written. It labels the depicted scenario. It is not a verified on-site capture.

## Gates

1. **Visual/location:** {scene['visual']}
2. **Technical:** Pass. Masters are 1920\u00d71080 and 864\u00d71080. Caption, scenario, disclosure, and signature are baked on a bottom gradient. Font sizes are 0.016, 0.012, 0.010, and 0.018 of image width.
3. **Originality/provenance:** Pass. {LINEAGE}
4. **Commercial/IP:** Pass as an internal editorial note, not a legal certification. {scene['ip']}
5. **Publication readiness:** Pass. Caption, scenario, disclosure, and the curly-apostrophe signature are present. EU AI Act Art. 50 text chunks were appended after the pixels were written and the pixel hash was unchanged.

## Art. 50

Both masters carry Title (iTXt, UTF-8), Description (tEXt), Copyright (iTXt, UTF-8), Software (tEXt), and Comment (tEXt), character-for-character as specified, including the straight apostrophe and em dash in Title and Copyright. Embedded 2026-09-24. Verified by reading the PNG chunks back.
"""
    path = ROOT / "approvals" / f"{entry}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


DK_SVG = (
    '<svg viewBox="0 0 37 28" xmlns="http://www.w3.org/2000/svg">'
    '<rect width="37" height="28" fill="#C8102E"/>'
    '<rect x="11" width="4" height="28" fill="#fff"/>'
    '<rect y="12" width="37" height="4" fill="#fff"/></svg>'
)

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<!-- Google tag (gtag.js) -->
<script async src="https://www.googletagmanager.com/gtag/js?id=G-PDJ4WSS725"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-PDJ4WSS725');
</script>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Jason D’s Vision — Denmark</title>
<link rel="canonical" href="https://devlij.github.io/jason-ds-vision-denmark-preview/"/>
<meta name="description" content="AI-generated artistic interpretations of Denmark, the Faroe Islands and Greenland. Free to use, no credit required."/>
<meta name="robots" content="index, follow"/>
<meta property="og:type" content="website"/>
<meta property="og:site_name" content="Jason D's Vision"/>
<meta property="og:title" content="Jason D's Vision — Denmark"/>
<meta property="og:description" content="AI-generated artistic interpretations of Denmark, the Faroe Islands and Greenland. Free to use, no credit required."/>
<meta property="og:image" content="__ASSET_BASE__library/world/Denmark/Copenhagen/dk-01-001-16x9.png"/>
<meta property="og:url" content="https://devlij.github.io/jason-ds-vision-denmark-preview/"/>
<meta name="twitter:card" content="summary_large_image"/>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "ImageGallery",
  "name": "Jason D's Vision \u2014 Denmark",
  "url": "https://devlij.github.io/jason-ds-vision-denmark-preview/",
  "description": "AI-generated artistic interpretations of Denmark, the Faroe Islands and Greenland. Free to use, no credit required.",
  "inLanguage": "en",
  "creator": {
    "@type": "Organization",
    "name": "Jason D's Vision"
  }
}
</script>
<style>
    :root {
      --bg:#0f1418; --card:#17202a; --text:#f0f3f6; --muted:#9fb0c0; --accent:#e05260; --line:#26313d;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.5;
    }
    a { color: var(--accent); }
    header, main, footer, .promise, #license {
      max-width: 1100px;
      margin: 0 auto;
      padding: 1.25rem 1.25rem;
    }
    .pointer {
      font-size: 0.95rem;
      color: var(--muted);
      border-bottom: 1px solid var(--line);
      padding-bottom: 1rem;
    }
    h1 {
      font-size: 1.75rem;
      font-weight: 650;
      margin: 1.25rem 0 0.35rem;
      letter-spacing: 0.01em;
    }
    .country-switch {
      margin: 0.15rem 0 0.85rem;
      font-size: 0.95rem;
      color: var(--muted);
      letter-spacing: 0.01em;
    }
    .country-switch .home-link { font-weight: 700; }
    .country-switch a { color: var(--accent); text-decoration: none; }
    .country-switch a:hover { text-decoration: underline; }
    .country-switch [aria-current="page"] { color: var(--text); font-weight: 600; }
    .country-switch .sep { margin: 0 0.45rem; color: var(--line); }
    .sub { color: var(--muted); margin: 0 0 1.5rem; }
    .promise h2, #license h2 { font-size: 1.2rem; margin-top: 2rem; }
    .promise p, #license p { color: var(--muted); max-width: 70ch; }
    .toolbar {
      display: flex; flex-wrap: wrap; gap: 0.75rem; align-items: center; margin: 1.5rem 0 1rem;
    }
    .toolbar input, .toolbar select {
      background: var(--card); color: var(--text); border: 1px solid var(--line);
      border-radius: 8px; padding: 0.55rem 0.75rem; font: inherit;
    }
    .toolbar input { flex: 1 1 220px; min-width: 180px; }
    .toolbar button {
      background: transparent; color: var(--muted); border: 1px solid var(--line);
      border-radius: 8px; padding: 0.55rem 0.9rem; cursor: pointer; font: inherit;
    }
    .toolbar button:hover { color: var(--text); border-color: var(--muted); }
    #result-count { color: var(--muted); font-size: 0.9rem; }
    #no-results { display: none; color: var(--muted); padding: 2rem 0; text-align: center; }
    .grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
      gap: 1.25rem; margin-bottom: 2rem;
    }
    .card {
      background: var(--card); border: 1px solid var(--line); border-radius: 14px;
      overflow: hidden; display: flex; flex-direction: column; scroll-margin-top: 1rem;
    }
    .preview { position: relative; }
    .fmt-tabs { display: flex; gap: 6px; padding: 0.75rem 1.05rem 0; line-height: 1.4; }
    .day-row { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; padding: 0.5rem 1.05rem 0; }
    .fmt-tab {
      background: rgba(23, 32, 42, 0.85); color: var(--text); border: 1px solid var(--line);
      border-radius: 8px; padding: 5px 10px; font: inherit; font-size: 12px; line-height: 1.2; cursor: pointer;
    }
    .fmt-tab:hover { border-color: var(--muted); }
    .fmt-tab.is-active {
      background: var(--accent); border-color: var(--accent); color: var(--bg); font-weight: 700;
    }
    .fmt-tab:disabled, .fmt-tab.is-disabled { opacity: 0.4; cursor: default; }
    .day-row button.day-tab {
      display: inline-block; background: #243049; color: var(--text);
      border-radius: 8px; padding: 0.4rem 0.7rem; font-size: 0.85rem; border: 1px solid var(--line);
      cursor: pointer;
    }
    .day-row button.day-tab:hover { border-color: var(--accent); }
    .day-row button.day-tab.is-active {
      background: #e8b23a; border-color: #e8b23a; color: #1a1405; font-weight: 700;
    }
    .day-row button.day-tab.pc-tab.is-active {
      background: #1f6b4a; border-color: #1f6b4a; color: #f4fff8; font-weight: 700;
    }
    .thumb {
      display: block; padding: 0.65rem 0.65rem 0; background: #12151c; line-height: 0;
    }
    .thumb img {
      width: 100%; height: auto; display: block; border-radius: 8px; background: #000;
      aspect-ratio: 16 / 9; object-fit: contain;
    }
    .thumb.tall img { aspect-ratio: 4 / 5; }
    .thumb.tall916 img { aspect-ratio: 9 / 16; }
    .card-body { padding: 1rem 1rem 1.15rem; display: flex; flex-direction: column; gap: 0.35rem; flex: 1; }
    .entry-id { font-size: 0.75rem; letter-spacing: 0.06em; text-transform: uppercase; color: var(--accent); }
    .status-row { display: flex; flex-wrap: wrap; gap: 0.45rem; align-items: center; }
    .status {
      display: inline-block; font-size: 0.72rem; letter-spacing: 0.04em; text-transform: uppercase;
      border-radius: 999px; padding: 0.2rem 0.55rem; border: 1px solid var(--line); color: var(--muted);
    }
    .status.approved { color: var(--accent); border-color: var(--accent); }
    .qc-count { font-size: 0.85rem; color: var(--muted); margin: 0.3rem 0 0; }
    .caption { font-size: 1.05rem; font-weight: 600; margin: 0; }
    .scenario, .composition, .detail { font-size: 0.85rem; color: var(--muted); margin: 0; }
    .detail { font-size: 0.92rem; color: #d7dde8; margin: 0.35rem 0 0; }
    .actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.85rem; align-items: center; }
    .actions a.download {
      display: inline-block; text-decoration: none; background: #243049; color: var(--text);
      border-radius: 8px; padding: 0.4rem 0.7rem; font-size: 0.85rem; border: 1px solid var(--line);
    }
    .actions a.download:hover { border-color: var(--accent); }
    .actions button.narrate {
      display: inline-block; background: #243049; color: var(--text);
      border-radius: 8px; padding: 0.4rem 0.7rem; font-size: 0.85rem; border: 1px solid var(--line);
      cursor: pointer;
    }
    .actions button.narrate:hover { border-color: var(--accent); }
    .actions button.narrate.playing { border-color: var(--accent); color: var(--accent); }
    .badge {
      display: inline-block; font-size: 0.75rem; color: var(--bg); background: var(--accent);
      border-radius: 999px; padding: 0.25rem 0.6rem; text-decoration: none; font-weight: 600;
    }
    footer {
      border-top: 1px solid var(--line); color: var(--muted); font-size: 0.9rem; padding-bottom: 2.5rem;
    }
    footer .sig { color: var(--text); font-weight: 600; }
    .flag-band{height:6px;background:linear-gradient(to bottom,transparent 38%,#ffffff 38%,#ffffff 62%,transparent 62%),linear-gradient(to right,transparent 28%,#ffffff 28%,#ffffff 40%,transparent 40%),#C8102E}
    .flag{display:inline-block;width:46px;height:35px;border-radius:4px;vertical-align:-6px;margin-right:12px;box-shadow:0 0 0 1px rgba(255,255,255,.25);overflow:hidden}
    .flag svg{display:block;width:100%;height:100%}
    .flag-chip{display:inline-block;width:22px;height:15px;border-radius:2px;vertical-align:-2px;margin-right:6px;box-shadow:0 0 0 1px rgba(255,255,255,.2);overflow:hidden}
    .flag-chip svg{display:block;width:100%;height:100%}
    .flag-chip.flag-de{background:linear-gradient(to bottom,#000 0 33.34%,#DD0000 0 66.67%,#FFCE00 0)}
    .flag-chip.flag-it{background:linear-gradient(to right,#009246 0 33.34%,#fff 0 66.67%,#CE2B37 0)}
    .flag-chip.flag-fr{background:linear-gradient(to right,#0055A4 0 33.34%,#fff 0 66.67%,#EF4135 0)}
    .flag-chip.flag-es{background:linear-gradient(to bottom,#AA151B 0 25%,#F1BF00 0 75%,#AA151B 0)}
    .flag-chip.flag-gr{background:repeating-linear-gradient(to bottom,#0D5EAF 0 3px,#fff 0 6px)}
    .flag-chip.flag-nl{background:linear-gradient(to bottom,#AE1C28 0 33.34%,#fff 0 66.67%,#21468B 0)}
    .flag-chip.flag-ch{background:linear-gradient(#fff,#fff) center/45% 22% no-repeat,linear-gradient(#fff,#fff) center/22% 65% no-repeat,#DA291C}
    .flag-chip.flag-dk{background:linear-gradient(to bottom,transparent 38%,#fff 38%,#fff 62%,transparent 62%),linear-gradient(to right,transparent 28%,#fff 28%,#fff 44%,transparent 44%),#C8102E}.flag-chip.flag-no,.flag-no{background:linear-gradient(to bottom,transparent 35%,#00205B 35%,#00205B 65%,transparent 65%),linear-gradient(to bottom,transparent 25%,#fff 25%,#fff 75%,transparent 75%),linear-gradient(to right,transparent 25%,#00205B 25%,#00205B 45%,transparent 45%),linear-gradient(to right,transparent 15%,#fff 15%,#fff 55%,transparent 55%),#BA0C2F}
    .lb{position:fixed;inset:0;z-index:60;display:none;align-items:center;justify-content:center;background:rgba(13,18,24,.93)}
.lb.open{display:flex}
.lb figure{margin:0;max-width:94vw;display:flex;flex-direction:column;align-items:center}
.lb img{max-width:94vw;max-height:72vh;display:block;border-radius:6px}
.lb figcaption{align-self:stretch;color:#f0f3f6;font-size:14px;padding:10px 2px 0}
.lb-nav{display:flex;align-items:center;justify-content:center;gap:20px;margin-bottom:12px}
.lb-count{color:#9fb0c0;white-space:nowrap;font-size:15px;min-width:90px;text-align:center}
.lb-controls{display:flex;justify-content:center;margin-top:12px;gap:10px}
.lb-prev,.lb-next,.lb-play,.lb-narrate{background:rgba(23,32,42,.85);color:#f0f3f6;border:1px solid #26313d;border-radius:999px;width:46px;height:46px;font-size:20px;cursor:pointer;line-height:1}
.lb-play.playing,.lb-narrate.playing{background:#e05260;border-color:#e05260;color:#0f1418}
.lb-play.playing{background:#e05260;border-color:#e05260;color:#0f1418}
.lb-close{position:absolute;top:14px;right:14px;background:rgba(23,32,42,.85);color:#f0f3f6;border:1px solid #26313d;border-radius:999px;width:46px;height:46px;font-size:20px;cursor:pointer;line-height:1}}
.wotd{border-top:1px solid rgba(255,255,255,.12);border-bottom:1px solid rgba(255,255,255,.12);background:#141419;padding:10px 24px;display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;font-size:14px;line-height:1.5}
.wotd .kicker{font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:#8f8a7d;font-weight:600;white-space:nowrap}
.wotd .word{font-weight:700;font-size:15px;color:#f2f0e9}
.wotd .gloss{color:#a8a294}
.wotd .sep{color:#5a564c}
.wotd .phrase{font-style:italic;color:#f2f0e9}
.wotd .day{margin-left:auto;font-size:11px;color:#8f8a7d;white-space:nowrap}
.wotd .translit{color:#8f8a7d;font-size:12.5px}
@media (max-width:520px){.wotd .day{margin-left:0;width:100%}}

  /* Phase 1 competitive features (ported from the Spain pilot, 2026-09-26):
     advanced filters (day/night, mood), related-scenes rows, copy-link. */
  .related { border-top: 1px solid var(--line); padding-top: 12px; margin-top: 0.5rem; }
  .related-h { font-size: 12px; letter-spacing: .12em; text-transform: uppercase;
               color: var(--muted); margin: 0 0 10px; }
  .related-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
  .related-link { display: block; text-decoration: none; }
  .related-link img { width: 100%; aspect-ratio: 16/9; object-fit: cover; display: block;
                      border: 1px solid var(--line); border-radius: 6px; }
  .related-link span { display: block; font-size: 12px; color: var(--muted); padding: 6px 0; }
  .related-link:hover span { color: var(--text); }
  .copy-link { display: inline-block; background: #243049; color: var(--text);
               border: 1px solid var(--line); border-radius: 8px; padding: 0.4rem 0.7rem;
               font-size: 0.85rem; cursor: pointer; font: inherit; }
  .copy-link:hover { border-color: var(--muted); }
  @media(max-width: 760px) { .related-row { grid-template-columns: repeat(2, 1fr); } }
</style>
</head>
<body>
  <div class="flag-band" aria-hidden="true"></div>
  <header>
    <p class="pointer">Every image is free to use — no credit required. See <a href="#license">license</a> below.</p>
    <h1><span class="flag" aria-hidden="true">DK_SVG</span>Jason D’s Vision — Denmark</h1>
    <p class="qc-count" id="qc-count"></p>
    <nav class="country-switch" aria-label="Country galleries">
      <a class="home-link" href="https://jdvision.org/">&#8962; Home</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://germany.jdvision.org/"><span class="flag-chip flag-de" aria-hidden="true"></span>Germany</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://italy.jdvision.org/"><span class="flag-chip flag-it" aria-hidden="true"></span>Italy</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://france.jdvision.org/"><span class="flag-chip flag-fr" aria-hidden="true"></span>France</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://greece.jdvision.org/"><span class="flag-chip flag-gr" aria-hidden="true"></span>Greece</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://spain.jdvision.org/"><span class="flag-chip flag-es" aria-hidden="true"></span>Spain</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://devlij.github.io/jason-ds-vision-norway-preview/"><span class="flag-chip flag-no" aria-hidden="true"></span>Norway</a>
      <span class="sep" aria-hidden="true">|</span>
      <span aria-current="page"><span class="flag-chip" aria-hidden="true">DK_SVG</span>Denmark</span>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://devlij.github.io/jason-ds-vision-switzerland-preview/"><span class="flag-chip flag-ch" aria-hidden="true"></span>Switzerland</a>
    </nav>
    <p class="sub">Denmark, the Faroe Islands and Greenland · Candidate scenes until an independent QC pass</p>
  </header>
<div class="wotd" id="wotd" lang="da">
  <span class="kicker">Dagens ord · Word of the day</span>
  <span class="wotd-body" aria-live="polite"></span>
  <span class="day" id="wotd-day"></span>
</div>
<script type="application/json" id="wotd-data">[{"phrase":"Tænd et lys i mørket","phrase_en":"Light a candle in the darkness","word":"et lys","word_en":"light, candle"},{"phrase":"Solen skinner i dag","phrase_en":"The sun is shining today","word":"en sol","word_en":"sun"},{"phrase":"Vi nyder solskinnet","phrase_en":"We are enjoying the sunshine","word":"et solskin","word_en":"sunshine"},{"phrase":"Månen står højt på himlen","phrase_en":"The moon is high in the sky","word":"en måne","word_en":"moon"},{"phrase":"Måneskinnet glitrer på vandet","phrase_en":"The moonlight glitters on the water","word":"et måneskin","word_en":"moonlight"},{"phrase":"Stjernerne funkler i nat","phrase_en":"The stars are twinkling tonight","word":"en stjerne","word_en":"star"},{"phrase":"Himlen er skyfri","phrase_en":"The sky is cloudless","word":"en himmel","word_en":"sky"},{"phrase":"Skyerne driver langsomt forbi","phrase_en":"The clouds drift slowly by","word":"en sky","word_en":"cloud"},{"phrase":"Det regner i dag","phrase_en":"It is raining today","word":"en regn","word_en":"rain"},{"phrase":"Se regnbuen efter regnen","phrase_en":"Look at the rainbow after the rain","word":"en regnbue","word_en":"rainbow"},{"phrase":"Sneen falder blidt","phrase_en":"The snow is falling gently","word":"en sne","word_en":"snow"},{"phrase":"Hvert snefnug er unikt","phrase_en":"Every snowflake is unique","word":"et snefnug","word_en":"snowflake"},{"phrase":"Vinden suser i træerne","phrase_en":"The wind is rushing through the trees","word":"en vind","word_en":"wind"},{"phrase":"Stormen raser udenfor","phrase_en":"The storm is raging outside","word":"en storm","word_en":"storm"},{"phrase":"Tågen letter ved middagstid","phrase_en":"The fog lifts around noon","word":"en tåge","word_en":"fog"},{"phrase":"Duggen glimter på græsset","phrase_en":"The dew sparkles on the grass","word":"en dug","word_en":"dew"},{"phrase":"Frosten bider i kinderne","phrase_en":"The frost nips at our cheeks","word":"en frost","word_en":"frost"},{"phrase":"Lynet oplyser natten","phrase_en":"The lightning lights up the night","word":"et lyn","word_en":"lightning"},{"phrase":"Tordenen ruller i det fjerne","phrase_en":"The thunder rumbles in the distance","word":"en torden","word_en":"thunder"},{"phrase":"Vi søger skygge under træet","phrase_en":"We seek shade under the tree","word":"en skygge","word_en":"shadow"},{"phrase":"En solstråle rammer gulvet","phrase_en":"A sunbeam hits the floor","word":"en stråle","word_en":"ray, beam"},{"phrase":"Vi står op ved daggry","phrase_en":"We get up at dawn","word":"et daggry","word_en":"dawn"},{"phrase":"Skumringen falder på","phrase_en":"Dusk is falling","word":"en skumring","word_en":"twilight, dusk"},{"phrase":"Solopgangen er smuk i dag","phrase_en":"The sunrise is beautiful today","word":"en solopgang","word_en":"sunrise"},{"phrase":"Vi ser solnedgangen fra stranden","phrase_en":"We watch the sunset from the beach","word":"en solnedgang","word_en":"sunset"},{"phrase":"En let dis hænger over marken","phrase_en":"A light haze hangs over the field","word":"en dis","word_en":"haze, mist"},{"phrase":"Vi nyder varmen fra solen","phrase_en":"We enjoy the warmth of the sun","word":"en varme","word_en":"warmth, heat"},{"phrase":"Kulden bider i næsen","phrase_en":"The cold bites our noses","word":"en kulde","word_en":"cold"},{"phrase":"Blæsten rusker i håret","phrase_en":"The wind tousles our hair","word":"en blæst","word_en":"gale, strong wind"},{"phrase":"Der kommer opklaring i eftermiddag","phrase_en":"It will clear up this afternoon","word":"en opklaring","word_en":"clearing of weather"},{"phrase":"Havet er stille i dag","phrase_en":"The sea is calm today","word":"et hav","word_en":"sea, ocean"},{"phrase":"Bølgerne ruller ind mod kysten","phrase_en":"The waves roll toward the coast","word":"en bølge","word_en":"wave"},{"phrase":"Vi vandrer langs kysten","phrase_en":"We hike along the coast","word":"en kyst","word_en":"coast"},{"phrase":"Børnene leger på stranden","phrase_en":"The children are playing on the beach","word":"en strand","word_en":"beach"},{"phrase":"Sandet er varmt under fødderne","phrase_en":"The sand is warm under our feet","word":"et sand","word_en":"sand"},{"phrase":"Klinten rejser sig over havet","phrase_en":"The cliff rises above the sea","word":"en klint","word_en":"cliff"},{"phrase":"Fjorden snor sig ind i landet","phrase_en":"The fjord winds into the country","word":"en fjord","word_en":"fjord"},{"phrase":"Bugten er læ for vinden","phrase_en":"The bay is sheltered from the wind","word":"en bugt","word_en":"bay"},{"phrase":"Øen ligger langt til havs","phrase_en":"The island lies far out at sea","word":"en ø","word_en":"island"},{"phrase":"En lille holm dukker op i disen","phrase_en":"A small islet appears in the haze","word":"en holm","word_en":"islet"},{"phrase":"Bådene ligger trygt i havnen","phrase_en":"The boats lie safely in the harbor","word":"en havn","word_en":"harbor"},{"phrase":"Færgen sejler hver time","phrase_en":"The ferry sails every hour","word":"en færge","word_en":"ferry"},{"phrase":"Sejlbåden glider over vandet","phrase_en":"The sailboat glides across the water","word":"en sejlbåd","word_en":"sailboat"},{"phrase":"Vi kaster anker i bugten","phrase_en":"We drop anchor in the bay","word":"et anker","word_en":"anchor"},{"phrase":"Fyrtårnet blinker i natten","phrase_en":"The lighthouse blinks in the night","word":"et fyrtårn","word_en":"lighthouse"},{"phrase":"Tangen skyller op på stranden","phrase_en":"The seaweed washes up on the beach","word":"en tang","word_en":"seaweed"},{"phrase":"Vi samler muslinger på stranden","phrase_en":"We collect mussels on the beach","word":"en musling","word_en":"mussel, clam"},{"phrase":"En søstjerne ligger i vandkanten","phrase_en":"A starfish lies at the water's edge","word":"en søstjerne","word_en":"starfish"},{"phrase":"Mågerne skriger over havnen","phrase_en":"The seagulls cry over the harbor","word":"en måge","word_en":"seagull"},{"phrase":"Sælen soler sig på stenen","phrase_en":"The seal is sunbathing on the rock","word":"en sæl","word_en":"seal"},{"phrase":"Dønningen løfter båden","phrase_en":"The swell lifts the boat","word":"en dønning","word_en":"swell"},{"phrase":"Brændingen bruser mod klipperne","phrase_en":"The surf roars against the rocks","word":"en brænding","word_en":"surf, breakers"},{"phrase":"Vi går tur langs vandkanten","phrase_en":"We walk along the water's edge","word":"en vandkant","word_en":"water's edge"},{"phrase":"Skibet forsvinder i horisonten","phrase_en":"The ship disappears over the horizon","word":"en horisont","word_en":"horizon"},{"phrase":"I dybet bor mange fisk","phrase_en":"Many fish live in the deep","word":"et dyb","word_en":"the deep"},{"phrase":"Strømmen er stærk i dag","phrase_en":"The current is strong today","word":"en strøm","word_en":"current"},{"phrase":"Tidevandet skifter to gange dagligt","phrase_en":"The tide changes twice daily","word":"et tidevand","word_en":"tide"},{"phrase":"Saltvandet svaler på en varm dag","phrase_en":"The salt water cools on a hot day","word":"et saltvand","word_en":"salt water"},{"phrase":"Vi samler rullesten på stranden","phrase_en":"We collect pebbles on the beach","word":"en rullesten","word_en":"pebble"},{"phrase":"Skallen glimter i solen","phrase_en":"The shell glitters in the sun","word":"en skal","word_en":"shell"},{"phrase":"Landskabet er storslået","phrase_en":"The landscape is magnificent","word":"et landskab","word_en":"landscape"},{"phrase":"Vi værner om naturen","phrase_en":"We protect nature","word":"en natur","word_en":"nature"},{"phrase":"Marken er grøn og frodig","phrase_en":"The field is green and lush","word":"en mark","word_en":"field"},{"phrase":"Køerne græsser på engen","phrase_en":"The cows graze in the meadow","word":"en eng","word_en":"meadow"},{"phrase":"Vi løber op ad bakken","phrase_en":"We run up the hill","word":"en bakke","word_en":"hill"},{"phrase":"Dalen ligger i læ","phrase_en":"The valley lies sheltered","word":"en dal","word_en":"valley"},{"phrase":"Bjerget tårner sig op","phrase_en":"The mountain towers up","word":"et bjerg","word_en":"mountain"},{"phrase":"Åen risler gennem engen","phrase_en":"The stream ripples through the meadow","word":"en å","word_en":"stream"},{"phrase":"Søen ligger spejlblank","phrase_en":"The lake is mirror-calm","word":"en sø","word_en":"lake"},{"phrase":"Mosen damper i morgensolen","phrase_en":"The bog steams in the morning sun","word":"en mose","word_en":"bog, marsh"},{"phrase":"Lyngen blomstrer på heden","phrase_en":"The heather blooms on the heath","word":"en hede","word_en":"heath"},{"phrase":"Lyngen står i fuldt flor","phrase_en":"The heather is in full bloom","word":"en lyng","word_en":"heather"},{"phrase":"Stenen er glat af vandet","phrase_en":"The stone is smooth from the water","word":"en sten","word_en":"stone"},{"phrase":"Vi klatrer op på klippen","phrase_en":"We climb up on the rock","word":"en klippe","word_en":"rock"},{"phrase":"Jorden dufter af regn","phrase_en":"The soil smells of rain","word":"en jord","word_en":"earth, soil"},{"phrase":"Stien er dækket af grus","phrase_en":"The path is covered with gravel","word":"et grus","word_en":"gravel"},{"phrase":"Huset ligger på skrænten","phrase_en":"The house sits on the slope","word":"en skrænt","word_en":"slope"},{"phrase":"Kløften er dyb og smal","phrase_en":"The ravine is deep and narrow","word":"en kløft","word_en":"ravine, gorge"},{"phrase":"Sletten strækker sig mod horisonten","phrase_en":"The plain stretches to the horizon","word":"en slette","word_en":"plain"},{"phrase":"En grøn oase midt i byen","phrase_en":"A green oasis in the middle of the city","word":"en oase","word_en":"oasis"},{"phrase":"Udsigten er betagende","phrase_en":"The view is breathtaking","word":"en udsigt","word_en":"view"},{"phrase":"Panoramaet tager vejret fra os","phrase_en":"The panorama takes our breath away","word":"et panorama","word_en":"panorama"},{"phrase":"Stilheden sænker sig","phrase_en":"Silence descends","word":"en stilhed","word_en":"silence, stillness"},{"phrase":"Ekkoet svarer fra klipperne","phrase_en":"The echo answers from the rocks","word":"et ekko","word_en":"echo"},{"phrase":"Duften af hav hænger i luften","phrase_en":"The scent of sea hangs in the air","word":"en duft","word_en":"scent"},{"phrase":"Efterårets farver er smukke","phrase_en":"Autumn's colors are beautiful","word":"en farve","word_en":"color"},{"phrase":"Bjergets kontur tegner sig mod himlen","phrase_en":"The mountain's outline stands out against the sky","word":"en kontur","word_en":"contour, outline"},{"phrase":"Vidden åbner sig foran os","phrase_en":"The expanse opens before us","word":"en vidde","word_en":"expanse"},{"phrase":"En stille afkrog i skoven","phrase_en":"A quiet nook in the forest","word":"en afkrog","word_en":"nook, remote corner"},{"phrase":"Det er en sand idyl","phrase_en":"It is a true idyll","word":"en idyl","word_en":"idyll"},{"phrase":"Vildmarken kalder på os","phrase_en":"The wilderness calls to us","word":"en vildmark","word_en":"wilderness"},{"phrase":"Haven er mit fristed","phrase_en":"The garden is my sanctuary","word":"et fristed","word_en":"sanctuary, refuge"},{"phrase":"Bornholm er Østersøens perle","phrase_en":"Bornholm is the pearl of the Baltic Sea","word":"en perle","word_en":"pearl, gem"},{"phrase":"Naturen er en skat","phrase_en":"Nature is a treasure","word":"en skat","word_en":"treasure"},{"phrase":"Et sandt naturvidunder","phrase_en":"A true natural wonder","word":"et vidunder","word_en":"wonder"},{"phrase":"Skoven dufter af gran","phrase_en":"The forest smells of spruce","word":"en skov","word_en":"forest"},{"phrase":"Træet er hundrede år gammelt","phrase_en":"The tree is a hundred years old","word":"et træ","word_en":"tree"},{"phrase":"Fuglen sidder på grenen","phrase_en":"The bird sits on the branch","word":"en gren","word_en":"branch"},{"phrase":"Rødderne går dybt","phrase_en":"The roots go deep","word":"en rod","word_en":"root"},{"phrase":"Stammen er tyk og ru","phrase_en":"The trunk is thick and rough","word":"en stamme","word_en":"trunk"},{"phrase":"Barken er ru at røre ved","phrase_en":"The bark is rough to touch","word":"en bark","word_en":"bark"},{"phrase":"Bladene rasler i vinden","phrase_en":"The leaves rustle in the wind","word":"et blad","word_en":"leaf"},{"phrase":"Blomsten springer ud","phrase_en":"The flower blooms","word":"en blomst","word_en":"flower"},{"phrase":"Knopperne brister i foråret","phrase_en":"The buds burst in spring","word":"en knop","word_en":"bud"},{"phrase":"Græsset er grønt og saftigt","phrase_en":"The grass is green and lush","word":"et græs","word_en":"grass"},{"phrase":"Urterne dufter dejligt","phrase_en":"The herbs smell lovely","word":"en urt","word_en":"herb"},{"phrase":"Vi finder svampe i skoven","phrase_en":"We find mushrooms in the forest","word":"en svamp","word_en":"mushroom"},{"phrase":"Mosset er blødt som fløjl","phrase_en":"The moss is soft as velvet","word":"et mos","word_en":"moss"},{"phrase":"Bregnerne vokser i skyggen","phrase_en":"The ferns grow in the shade","word":"en bregne","word_en":"fern"},{"phrase":"Egen er Danmarks nationaltræ","phrase_en":"The oak is Denmark's national tree","word":"en eg","word_en":"oak"},{"phrase":"Bøgen springer ud i maj","phrase_en":"The beech comes into leaf in May","word":"en bøg","word_en":"beech"},{"phrase":"Birkens blade er lysegrønne","phrase_en":"The birch leaves are light green","word":"en birk","word_en":"birch"},{"phrase":"Granen dufter af jul","phrase_en":"The spruce smells of Christmas","word":"en gran","word_en":"spruce"},{"phrase":"Fyrren står rank på klippen","phrase_en":"The pine stands tall on the rock","word":"en fyr","word_en":"pine"},{"phrase":"Æbletræet bugner af frugt","phrase_en":"The apple tree is laden with fruit","word":"et æbletræ","word_en":"apple tree"},{"phrase":"Rosen dufter sødt","phrase_en":"The rose smells sweet","word":"en rose","word_en":"rose"},{"phrase":"Tulipanerne står i rækker","phrase_en":"The tulips stand in rows","word":"en tulipan","word_en":"tulip"},{"phrase":"Solsikken vender sig mod solen","phrase_en":"The sunflower turns toward the sun","word":"en solsikke","word_en":"sunflower"},{"phrase":"Åkanderne flyder på søen","phrase_en":"The water lilies float on the lake","word":"en åkande","word_en":"water lily"},{"phrase":"Af et lille frø vokser et træ","phrase_en":"From a small seed grows a tree","word":"et frø","word_en":"seed"},{"phrase":"Fuglen synger ved daggry","phrase_en":"The bird sings at dawn","word":"en fugl","word_en":"bird"},{"phrase":"Svanen glider over søen","phrase_en":"The swan glides across the lake","word":"en svane","word_en":"swan"},{"phrase":"Ænderne svømmer i åen","phrase_en":"The ducks swim in the stream","word":"en and","word_en":"duck"},{"phrase":"Uglen tuder i natten","phrase_en":"The owl hoots in the night","word":"en ugle","word_en":"owl"},{"phrase":"Ravnen kredser over marken","phrase_en":"The raven circles over the field","word":"en ravn","word_en":"raven"},{"phrase":"Storken er vendt tilbage","phrase_en":"The stork has returned","word":"en stork","word_en":"stork"},{"phrase":"Hesten galoperer over engen","phrase_en":"The horse gallops across the meadow","word":"en hest","word_en":"horse"},{"phrase":"Koen gumler græs","phrase_en":"The cow chews grass","word":"en ko","word_en":"cow"},{"phrase":"Fårene græsser på heden","phrase_en":"The sheep graze on the heath","word":"et får","word_en":"sheep"},{"phrase":"Geden klatrer på klippen","phrase_en":"The goat climbs on the rock","word":"en ged","word_en":"goat"},{"phrase":"Grisen tryner i mudderet","phrase_en":"The pig roots in the mud","word":"en gris","word_en":"pig"},{"phrase":"Hunden logrer med halen","phrase_en":"The dog wags its tail","word":"en hund","word_en":"dog"},{"phrase":"Katten spinder i solen","phrase_en":"The cat purrs in the sun","word":"en kat","word_en":"cat"},{"phrase":"Haren hopper over marken","phrase_en":"The hare hops across the field","word":"en hare","word_en":"hare"},{"phrase":"Rådyret græsser i skovbrynet","phrase_en":"The roe deer grazes at the forest edge","word":"et rådyr","word_en":"roe deer"},{"phrase":"Hjorten står stille i lysningen","phrase_en":"The stag stands still in the clearing","word":"en hjort","word_en":"deer, stag"},{"phrase":"Ræven lister gennem skoven","phrase_en":"The fox slinks through the forest","word":"en ræv","word_en":"fox"},{"phrase":"Egernet samler nødder","phrase_en":"The squirrel gathers nuts","word":"et egern","word_en":"squirrel"},{"phrase":"Pindsvinet putter sig i løvet","phrase_en":"The hedgehog nestles in the leaves","word":"et pindsvin","word_en":"hedgehog"},{"phrase":"Musen piler over gulvet","phrase_en":"The mouse darts across the floor","word":"en mus","word_en":"mouse"},{"phrase":"Sommerfuglen flagrer i haven","phrase_en":"The butterfly flutters in the garden","word":"en sommerfugl","word_en":"butterfly"},{"phrase":"Bien summer om blomsterne","phrase_en":"The bee buzzes around the flowers","word":"en bi","word_en":"bee"},{"phrase":"Mariehønen kravler på bladet","phrase_en":"The ladybug crawls on the leaf","word":"en mariehøne","word_en":"ladybug"},{"phrase":"Edderkoppen spinder sit net","phrase_en":"The spider spins its web","word":"en edderkop","word_en":"spider"},{"phrase":"Fisken springer i åen","phrase_en":"The fish leaps in the stream","word":"en fisk","word_en":"fish"},{"phrase":"Foråret er på vej","phrase_en":"Spring is on its way","word":"et forår","word_en":"spring"},{"phrase":"Sommeren er årets højdepunkt","phrase_en":"Summer is the highlight of the year","word":"en sommer","word_en":"summer"},{"phrase":"Efteråret maler skoven gul","phrase_en":"Autumn paints the forest yellow","word":"et efterår","word_en":"autumn, fall"},{"phrase":"Vinteren er kold og klar","phrase_en":"Winter is cold and crisp","word":"en vinter","word_en":"winter"},{"phrase":"Hver årstid har sin charme","phrase_en":"Every season has its charm","word":"en årstid","word_en":"season"},{"phrase":"Glædelig jul!","phrase_en":"Merry Christmas!","word":"en jul","word_en":"Christmas"},{"phrase":"Vi fejrer juleaften sammen","phrase_en":"We celebrate Christmas Eve together","word":"en juleaften","word_en":"Christmas Eve"},{"phrase":"Godt nytår!","phrase_en":"Happy New Year!","word":"et nytår","word_en":"New Year"},{"phrase":"God påske!","phrase_en":"Happy Easter!","word":"en påske","word_en":"Easter"},{"phrase":"I pinsen er dagene lange","phrase_en":"At Whitsun the days are long","word":"en pinse","word_en":"Whitsun, Pentecost"},{"phrase":"Vi tænder bål sankthansaften","phrase_en":"We light a bonfire on Midsummer's Eve","word":"en sankthansaften","word_en":"Midsummer's Eve"},{"phrase":"Bålet knitrer i natten","phrase_en":"The bonfire crackles in the night","word":"et bål","word_en":"bonfire"},{"phrase":"Børnene slår katten af tønden til fastelavn","phrase_en":"The children hit the barrel at Shrovetide","word":"en fastelavn","word_en":"Shrovetide, Danish carnival"},{"phrase":"Tillykke med fødselsdagen!","phrase_en":"Happy birthday!","word":"en fødselsdag","word_en":"birthday"},{"phrase":"Brylluppet holdes i juni","phrase_en":"The wedding takes place in June","word":"et bryllup","word_en":"wedding"},{"phrase":"Konfirmationen fejres om foråret","phrase_en":"The confirmation is celebrated in spring","word":"en konfirmation","word_en":"confirmation"},{"phrase":"Høsten er i fuld gang","phrase_en":"The harvest is in full swing","word":"en høst","word_en":"harvest"},{"phrase":"Forårssolen varmer kinderne","phrase_en":"The spring sun warms our cheeks","word":"en forårssol","word_en":"spring sun"},{"phrase":"Sommernatten er lys og mild","phrase_en":"The summer night is bright and mild","word":"en sommernat","word_en":"summer night"},{"phrase":"Efterårsstormen rusker i træerne","phrase_en":"The autumn storm shakes the trees","word":"en efterårsstorm","word_en":"autumn storm"},{"phrase":"Vintergækken er forårets budbringer","phrase_en":"The snowdrop is spring's messenger","word":"en vintergæk","word_en":"snowdrop"},{"note":"Traditional Danish paper Christmas decoration","phrase":"Vi fletter julehjerter","phrase_en":"We weave Christmas hearts","word":"et julehjerte","word_en":"woven Christmas heart"},{"phrase":"Nissen driller til jul","phrase_en":"The elf plays tricks at Christmas","word":"en nisse","word_en":"elf, gnome"},{"note":"Traditional Danish birthday cake shaped like a man","phrase":"Kagemanden pyntes til fødselsdagen","phrase_en":"The cake man is decorated for the birthday","word":"en kagemand","word_en":"cake man"},{"note":"Dannebrog is the Danish national flag","phrase":"Dannebrog vajer i vinden","phrase_en":"The Dannebrog waves in the wind","word":"et flag","word_en":"flag"},{"phrase":"Byen summer af liv","phrase_en":"The city buzzes with life","word":"en by","word_en":"town, city"},{"phrase":"Gaden er fyldt med mennesker","phrase_en":"The street is full of people","word":"en gade","word_en":"street"},{"phrase":"Vi mødes på torvet","phrase_en":"We meet at the square","word":"et torv","word_en":"square, marketplace"},{"phrase":"Kirken ringer til gudstjeneste","phrase_en":"The church bells ring for service","word":"en kirke","word_en":"church"},{"phrase":"Kirketårnet ses langvejsfra","phrase_en":"The church tower is visible from afar","word":"et kirketårn","word_en":"church tower"},{"phrase":"Slottet troner over byen","phrase_en":"The castle towers over the town","word":"et slot","word_en":"castle, palace"},{"phrase":"Rådhusklokkerne slår tolv","phrase_en":"The city-hall bells strike twelve","word":"et rådhus","word_en":"city hall"},{"phrase":"Butikken åbner klokken ni","phrase_en":"The shop opens at nine","word":"en butik","word_en":"shop"},{"phrase":"Vi drikker kaffe på caféen","phrase_en":"We drink coffee at the café","word":"en café","word_en":"café"},{"phrase":"Bageren bager frisk brød","phrase_en":"The baker bakes fresh bread","word":"en bager","word_en":"baker"},{"phrase":"Vi cykler til arbejde","phrase_en":"We bike to work","word":"en cykel","word_en":"bicycle"},{"phrase":"Toget kører til tiden","phrase_en":"The train runs on time","word":"et tog","word_en":"train"},{"phrase":"Vi mødes på stationen","phrase_en":"We meet at the station","word":"en station","word_en":"station"},{"phrase":"Bussen kommer om fem minutter","phrase_en":"The bus comes in five minutes","word":"en bus","word_en":"bus"},{"phrase":"Bilen holder ved kantstenen","phrase_en":"The car is parked at the curb","word":"en bil","word_en":"car"},{"phrase":"Broen forbinder øerne","phrase_en":"The bridge connects the islands","word":"en bro","word_en":"bridge"},{"phrase":"Havnefronten er nyrenoveret","phrase_en":"The waterfront is newly renovated","word":"en havnefront","word_en":"waterfront"},{"phrase":"Parken er fuld af blomster","phrase_en":"The park is full of flowers","word":"en park","word_en":"park"},{"phrase":"Børnene leger på legepladsen","phrase_en":"The children play at the playground","word":"en legeplads","word_en":"playground"},{"phrase":"Skolen begynder i august","phrase_en":"School starts in August","word":"en skole","word_en":"school"},{"phrase":"Biblioteket er åbent til klokken 18","phrase_en":"The library is open until 6 pm","word":"et bibliotek","word_en":"library"},{"phrase":"Museet viser dansk kunst","phrase_en":"The museum shows Danish art","word":"et museum","word_en":"museum"},{"phrase":"Vi skal i teatret i aften","phrase_en":"We are going to the theatre tonight","word":"et teater","word_en":"theatre"},{"phrase":"Biografen viser en ny film","phrase_en":"The cinema shows a new film","word":"en biograf","word_en":"cinema"},{"phrase":"Markedet bugner af grønt","phrase_en":"The market overflows with produce","word":"et marked","word_en":"market"},{"phrase":"Vi gør et kup på loppemarkedet","phrase_en":"We find a bargain at the flea market","word":"et loppemarked","word_en":"flea market"},{"phrase":"Værtshuset er hyggeligt","phrase_en":"The pub is cozy","word":"et værtshus","word_en":"pub, tavern"},{"phrase":"Restauranten serverer smørrebrød","phrase_en":"The restaurant serves smørrebrød","word":"en restaurant","word_en":"restaurant"},{"phrase":"Hotellet ligger ved havnen","phrase_en":"The hotel is by the harbor","word":"et hotel","word_en":"hotel"},{"phrase":"Naboen hilser venligt","phrase_en":"The neighbor greets us kindly","word":"en nabo","word_en":"neighbor"},{"phrase":"Fællesskabet er stærkt her","phrase_en":"The community is strong here","word":"et fællesskab","word_en":"community"},{"phrase":"Hverdagen går sin vante gang","phrase_en":"Everyday life goes on as usual","word":"en hverdag","word_en":"weekday, everyday life"},{"phrase":"I weekenden slapper vi af","phrase_en":"On the weekend we relax","word":"en weekend","word_en":"weekend"},{"phrase":"Morgentrafikken er tæt","phrase_en":"The morning traffic is heavy","word":"en morgentrafik","word_en":"morning traffic"},{"phrase":"Gadelamperne tændes ved skumringstid","phrase_en":"The street lamps come on at dusk","word":"en gadelampe","word_en":"street lamp"},{"note":"Untranslatable Danish concept of cozy contentment","phrase":"Hygge er svært at oversætte","phrase_en":"Hygge is hard to translate","word":"en hygge","word_en":"coziness"},{"phrase":"Kaffen er varm og stærk","phrase_en":"The coffee is hot and strong","word":"en kaffe","word_en":"coffee"},{"phrase":"Vi drikker te om eftermiddagen","phrase_en":"We drink tea in the afternoon","word":"en te","word_en":"tea"},{"phrase":"Kagen smager af chokolade","phrase_en":"The cake tastes of chocolate","word":"en kage","word_en":"cake"},{"phrase":"Brødet er nybagt","phrase_en":"The bread is freshly baked","word":"et brød","word_en":"bread"},{"phrase":"Rundstykker til morgenmad","phrase_en":"Bread rolls for breakfast","word":"et rundstykke","word_en":"bread roll"},{"phrase":"Smørrebrødet pyntes med dild","phrase_en":"The open sandwich is garnished with dill","word":"et smørrebrød","word_en":"open sandwich"},{"phrase":"Øllen er kold","phrase_en":"The beer is cold","word":"en øl","word_en":"beer"},{"phrase":"Vinen passer til maden","phrase_en":"The wine goes with the food","word":"en vin","word_en":"wine"},{"phrase":"Maden dufter dejligt","phrase_en":"The food smells lovely","word":"en mad","word_en":"food"},{"phrase":"Morgenmaden er dagens vigtigste måltid","phrase_en":"Breakfast is the most important meal of the day","word":"en morgenmad","word_en":"breakfast"},{"phrase":"Vi spiser frokost klokken tolv","phrase_en":"We eat lunch at twelve","word":"en frokost","word_en":"lunch"},{"phrase":"Middagen serveres klokken 18","phrase_en":"Dinner is served at 6","word":"en middag","word_en":"dinner"},{"phrase":"Desserten er sød og lækker","phrase_en":"The dessert is sweet and delicious","word":"en dessert","word_en":"dessert"},{"phrase":"Isen smelter i solen","phrase_en":"The ice cream melts in the sun","word":"en is","word_en":"ice cream"},{"phrase":"Æblet er sprødt","phrase_en":"The apple is crisp","word":"et æble","word_en":"apple"},{"phrase":"Jordbærrene er søde i juni","phrase_en":"The strawberries are sweet in June","word":"et jordbær","word_en":"strawberry"},{"phrase":"Kartoflerne koges møre","phrase_en":"The potatoes are boiled tender","word":"en kartoffel","word_en":"potato"},{"phrase":"Osten lagres i kælderen","phrase_en":"The cheese matures in the cellar","word":"en ost","word_en":"cheese"},{"phrase":"Silden serveres med rugbrød","phrase_en":"The herring is served with rye bread","word":"en sild","word_en":"herring"},{"phrase":"Laksen er røget over bøg","phrase_en":"The salmon is smoked over beech","word":"en laks","word_en":"salmon"},{"phrase":"Rejerne pilles ved bordet","phrase_en":"The shrimp are peeled at the table","word":"en reje","word_en":"shrimp"},{"phrase":"Suppen varmer i vinterkulden","phrase_en":"The soup warms in the winter cold","word":"en suppe","word_en":"soup"},{"phrase":"Pandekager med sukker og citron","phrase_en":"Pancakes with sugar and lemon","word":"en pandekage","word_en":"pancake"},{"phrase":"Kanelsneglen er blød og sød","phrase_en":"The cinnamon roll is soft and sweet","word":"en kanelsnegl","word_en":"cinnamon roll"},{"phrase":"Vi deler et honninghjerte på julemarkedet","phrase_en":"We share a honey-cake heart at the Christmas market","word":"et honninghjerte","word_en":"honey-cake heart"},{"phrase":"Mælken er frisk fra gården","phrase_en":"The milk is fresh from the farm","word":"en mælk","word_en":"milk"},{"phrase":"Saften er lavet på hyldeblomst","phrase_en":"The cordial is made from elderflower","word":"en saft","word_en":"juice, cordial"},{"phrase":"Pejsen knitrer hyggeligt","phrase_en":"The fireplace crackles cozily","word":"en pejs","word_en":"fireplace"},{"phrase":"Vi putter os under tæppet","phrase_en":"We snuggle under the blanket","word":"et tæppe","word_en":"blanket"},{"phrase":"Rejsen går til Bornholm","phrase_en":"The journey goes to Bornholm","word":"en rejse","word_en":"journey, trip"},{"phrase":"Eventyret venter forude","phrase_en":"The adventure awaits ahead","word":"et eventyr","word_en":"adventure, fairy tale"},{"phrase":"Ferien står for døren","phrase_en":"The holiday is just around the corner","word":"en ferie","word_en":"holiday, vacation"},{"phrase":"Udflugten går til Møns Klint","phrase_en":"The excursion goes to Møns Klint","word":"en udflugt","word_en":"excursion"},{"phrase":"Vandringen tager fire timer","phrase_en":"The hike takes four hours","word":"en vandring","word_en":"hike"},{"phrase":"Cykelturen går gennem landskabet","phrase_en":"The bike ride goes through the countryside","word":"en cykeltur","word_en":"bike ride"},{"phrase":"Sejlturen byder på smukke udsigter","phrase_en":"The sailing trip offers beautiful views","word":"en sejltur","word_en":"sailing trip"},{"phrase":"Bilturen langs kysten er skøn","phrase_en":"The drive along the coast is lovely","word":"en biltur","word_en":"road trip, drive"},{"phrase":"Rygsækken er pakket og klar","phrase_en":"The backpack is packed and ready","word":"en rygsæk","word_en":"backpack"},{"phrase":"Kortet viser vejen","phrase_en":"The map shows the way","word":"et kort","word_en":"map"},{"phrase":"Kompasset peger mod nord","phrase_en":"The compass points north","word":"et kompas","word_en":"compass"},{"phrase":"Med kikkerten ser vi sælerne","phrase_en":"With the binoculars we see the seals","word":"en kikkert","word_en":"binoculars"},{"phrase":"Kameraet fanger øjeblikket","phrase_en":"The camera captures the moment","word":"et kamera","word_en":"camera"},{"phrase":"Billedet hænger på væggen","phrase_en":"The picture hangs on the wall","word":"et billede","word_en":"picture"},{"phrase":"Mindet varmer endnu","phrase_en":"The memory still warms","word":"et minde","word_en":"memory"},{"phrase":"Oplevelsen glemmer vi aldrig","phrase_en":"We will never forget the experience","word":"en oplevelse","word_en":"experience"},{"phrase":"Hver dag byder på en ny opdagelse","phrase_en":"Each day brings a new discovery","word":"en opdagelse","word_en":"discovery"},{"phrase":"Udsigten var en stor overraskelse","phrase_en":"The view was a great surprise","word":"en overraskelse","word_en":"surprise"},{"phrase":"Destinationen er ukendt","phrase_en":"The destination is unknown","word":"en destination","word_en":"destination"},{"phrase":"Afgangen er klokken otte","phrase_en":"The departure is at eight","word":"en afgang","word_en":"departure"},{"phrase":"Vi glæder os til ankomsten","phrase_en":"We look forward to the arrival","word":"en ankomst","word_en":"arrival"},{"phrase":"Billetten gælder hele dagen","phrase_en":"The ticket is valid all day","word":"en billet","word_en":"ticket"},{"phrase":"Husk passet!","phrase_en":"Remember your passport!","word":"et pas","word_en":"passport"},{"phrase":"Kufferten er tung","phrase_en":"The suitcase is heavy","word":"en kuffert","word_en":"suitcase"},{"phrase":"Overnatningen er booket","phrase_en":"The overnight stay is booked","word":"en overnatning","word_en":"overnight stay"},{"phrase":"Vandrehjemmet ligger ved søen","phrase_en":"The hostel is by the lake","word":"et vandrehjem","word_en":"youth hostel"},{"phrase":"Campingpladsen er fuld i juli","phrase_en":"The campsite is full in July","word":"en campingplads","word_en":"campsite"},{"note":"Open wooden shelter, a staple of Danish outdoor life","phrase":"Vi sover i shelter ved skoven","phrase_en":"We sleep in a shelter by the forest","word":"et shelter","word_en":"shelter, lean-to"},{"phrase":"Bålpladsen ligger ved vandet","phrase_en":"The campfire site is by the water","word":"en bålplads","word_en":"campfire site"},{"phrase":"Hjemrejsen går over Fyn","phrase_en":"The journey home goes via Funen","word":"en hjemrejse","word_en":"journey home"},{"phrase":"Tiden flyver af sted","phrase_en":"Time flies","word":"en tid","word_en":"time"},{"phrase":"Nyd øjeblikket","phrase_en":"Enjoy the moment","word":"et øjeblik","word_en":"moment"},{"phrase":"Godmorgen og velkommen","phrase_en":"Good morning and welcome","word":"en morgen","word_en":"morning"},{"phrase":"Formiddagen er til arbejde","phrase_en":"The forenoon is for work","word":"en formiddag","word_en":"forenoon, late morning"},{"phrase":"Vi drikker kaffe om eftermiddagen","phrase_en":"We drink coffee in the afternoon","word":"en eftermiddag","word_en":"afternoon"},{"phrase":"Godaften!","phrase_en":"Good evening!","word":"en aften","word_en":"evening"},{"phrase":"Godnat og sov godt","phrase_en":"Good night and sleep well","word":"en nat","word_en":"night"},{"phrase":"Klokken slår midnat","phrase_en":"The clock strikes midnight","word":"en midnat","word_en":"midnight"},{"phrase":"Hav en dejlig dag!","phrase_en":"Have a lovely day!","word":"en dag","word_en":"day"},{"phrase":"Åbent hele døgnet","phrase_en":"Open around the clock","word":"et døgn","word_en":"24 hours, day and night"},{"phrase":"Vi ses i næste uge","phrase_en":"See you next week","word":"en uge","word_en":"week"},{"phrase":"Måneden er gået hurtigt","phrase_en":"The month went by fast","word":"en måned","word_en":"month"},{"phrase":"Året går på hæld","phrase_en":"The year is drawing to a close","word":"et år","word_en":"year"},{"phrase":"Et århundrede med historie","phrase_en":"A century of history","word":"et århundrede","word_en":"century"},{"phrase":"Et sekund ad gangen","phrase_en":"One second at a time","word":"et sekund","word_en":"second"},{"phrase":"Giv mig et minut","phrase_en":"Give me a minute","word":"et minut","word_en":"minute"},{"phrase":"Vi mødes om en time","phrase_en":"We meet in an hour","word":"en time","word_en":"hour"},{"note":"Danish proverb: the morning hour has gold in its mouth","phrase":"Morgenstund har guld i mund","phrase_en":"The early bird catches the worm","word":"en morgenstund","word_en":"early morning hour"},{"phrase":"I nattetimerne er byen stille","phrase_en":"In the night hours the city is quiet","word":"en nattetime","word_en":"night hour"},{"phrase":"Fremtiden ser lys ud","phrase_en":"The future looks bright","word":"en fremtid","word_en":"future"},{"phrase":"Lykken smiler til os","phrase_en":"Fortune smiles on us","word":"en lykke","word_en":"happiness, luck"},{"phrase":"Glæden er stor","phrase_en":"The joy is great","word":"en glæde","word_en":"joy"},{"phrase":"Kærligheden overvinder alt","phrase_en":"Love conquers all","word":"en kærlighed","word_en":"love"},{"phrase":"Fred i sindet","phrase_en":"Peace of mind","word":"en fred","word_en":"peace"},{"phrase":"Harmoni i naturen","phrase_en":"Harmony in nature","word":"en harmoni","word_en":"harmony"},{"phrase":"Håbet lever endnu","phrase_en":"Hope still lives","word":"et håb","word_en":"hope"},{"phrase":"Drømmen går i opfyldelse","phrase_en":"The dream comes true","word":"en drøm","word_en":"dream"},{"phrase":"Længslen mod fjerne kyster","phrase_en":"The longing for distant shores","word":"en længsel","word_en":"longing"},{"phrase":"Savnet er stort","phrase_en":"The sense of loss is great","word":"et savn","word_en":"missing, sense of loss"},{"phrase":"Mod til at drage af sted","phrase_en":"Courage to set off","word":"et mod","word_en":"courage"},{"phrase":"Tålmodighed er en dyd","phrase_en":"Patience is a virtue","word":"en tålmodighed","word_en":"patience"},{"phrase":"Vi føler stor taknemmelighed","phrase_en":"We feel great gratitude","word":"en taknemmelighed","word_en":"gratitude"},{"phrase":"Forundring over naturens kræfter","phrase_en":"Amazement at nature's forces","word":"en forundring","word_en":"wonder, amazement"},{"phrase":"Nysgerrigheden driver os videre","phrase_en":"Curiosity drives us on","word":"en nysgerrighed","word_en":"curiosity"},{"phrase":"Friheden til at vandre","phrase_en":"The freedom to roam","word":"en frihed","word_en":"freedom"},{"phrase":"Tryghed i hverdagen","phrase_en":"A sense of security in everyday life","word":"en tryghed","word_en":"security, sense of safety"},{"phrase":"Venskabet holder hele livet","phrase_en":"Friendship lasts a lifetime","word":"et venskab","word_en":"friendship"},{"phrase":"Et smil smitter","phrase_en":"A smile is contagious","word":"et smil","word_en":"smile"},{"phrase":"Latteren runger i rummet","phrase_en":"Laughter resounds in the room","word":"en latter","word_en":"laughter"},{"phrase":"En tåre af glæde","phrase_en":"A tear of joy","word":"en tåre","word_en":"tear"},{"phrase":"Tid til eftertanke","phrase_en":"Time for reflection","word":"en eftertanke","word_en":"reflection, afterthought"},{"phrase":"Nostalgien melder sig","phrase_en":"Nostalgia sets in","word":"en nostalgi","word_en":"nostalgia"},{"phrase":"Velvære i krop og sjæl","phrase_en":"Well-being in body and soul","word":"et velvære","word_en":"well-being"},{"phrase":"Livsglæden smitter","phrase_en":"The zest for life is contagious","word":"en livsglæde","word_en":"joy of life, zest for life"},{"phrase":"Eventyrlysten vækkes","phrase_en":"The sense of adventure awakens","word":"en eventyrlyst","word_en":"sense of adventure"},{"phrase":"Vi rejser til Jylland","phrase_en":"We travel to Jutland","word":"at rejse","word_en":"to travel"},{"phrase":"Vi vandrer i Mols Bjerge","phrase_en":"We hike in the Mols Hills","word":"at vandre","word_en":"to hike, wander"},{"phrase":"Vi opdager nye steder","phrase_en":"We discover new places","word":"at opdage","word_en":"to discover"},{"phrase":"Vi udforsker kysten","phrase_en":"We explore the coast","word":"at udforske","word_en":"to explore"},{"phrase":"Vi sejler til Sverige","phrase_en":"We sail to Sweden","word":"at sejle","word_en":"to sail"},{"phrase":"Vi cykler gennem byen","phrase_en":"We cycle through the city","word":"at cykle","word_en":"to cycle"},{"phrase":"Vi svømmer i havet","phrase_en":"We swim in the sea","word":"at svømme","word_en":"to swim"},{"phrase":"Vi går en tur","phrase_en":"We go for a walk","word":"at gå","word_en":"to walk, go"},{"phrase":"Vi løber på stranden","phrase_en":"We run on the beach","word":"at løbe","word_en":"to run"},{"phrase":"Vi klatrer op ad klinten","phrase_en":"We climb up the cliff","word":"at klatre","word_en":"to climb"},{"phrase":"Se udsigten!","phrase_en":"Look at the view!","word":"at se","word_en":"to see"},{"phrase":"Vi betragter solnedgangen","phrase_en":"We contemplate the sunset","word":"at betragte","word_en":"to observe, contemplate"},{"phrase":"Lyt til bølgerne","phrase_en":"Listen to the waves","word":"at lytte","word_en":"to listen"},{"phrase":"Kan du dufte havet?","phrase_en":"Can you smell the sea?","word":"at dufte","word_en":"to smell"},{"phrase":"Smag på osten","phrase_en":"Taste the cheese","word":"at smage","word_en":"to taste"},{"phrase":"Nyd aftenen","phrase_en":"Enjoy the evening","word":"at nyde","word_en":"to enjoy"},{"phrase":"Vi slapper af i solen","phrase_en":"We relax in the sun","word":"at slappe af","word_en":"to relax"},{"phrase":"Drøm stort","phrase_en":"Dream big","word":"at drømme","word_en":"to dream"},{"phrase":"Smil til verden","phrase_en":"Smile at the world","word":"at smile","word_en":"to smile"},{"phrase":"Vi ler sammen","phrase_en":"We laugh together","word":"at le","word_en":"to laugh"},{"phrase":"Vi elsker Danmark","phrase_en":"We love Denmark","word":"at elske","word_en":"to love"},{"phrase":"Vi savner sommeren","phrase_en":"We miss the summer","word":"at savne","word_en":"to miss"},{"phrase":"Vi glæder os til ferien","phrase_en":"We look forward to the holiday","word":"at glæde sig","word_en":"to look forward to, rejoice"},{"phrase":"Vi venter på færgen","phrase_en":"We wait for the ferry","word":"at vente","word_en":"to wait"},{"phrase":"Vi finder vej","phrase_en":"We find our way","word":"at finde","word_en":"to find"},{"phrase":"Vi samler sten på stranden","phrase_en":"We collect stones on the beach","word":"at samle","word_en":"to gather, collect"},{"phrase":"Børnene bygger sandslotte","phrase_en":"The children build sandcastles","word":"at bygge","word_en":"to build"},{"phrase":"Hun maler landskaber","phrase_en":"She paints landscapes","word":"at male","word_en":"to paint"},{"phrase":"Vi fotograferer solnedgangen","phrase_en":"We photograph the sunset","word":"at fotografere","word_en":"to photograph"},{"phrase":"Fortæl om din rejse","phrase_en":"Tell about your journey","word":"at fortælle","word_en":"to tell"},{"phrase":"En smuk udsigt","phrase_en":"A beautiful view","word":"smuk","word_en":"beautiful"},{"phrase":"En dejlig dag","phrase_en":"A lovely day","word":"dejlig","word_en":"lovely, delightful"},{"phrase":"En vidunderlig aften","phrase_en":"A wonderful evening","word":"vidunderlig","word_en":"wonderful"},{"phrase":"Et fantastisk landskab","phrase_en":"A fantastic landscape","word":"fantastisk","word_en":"fantastic"},{"phrase":"En betagende solnedgang","phrase_en":"A breathtaking sunset","word":"betagende","word_en":"breathtaking"},{"phrase":"Et storslået syn","phrase_en":"A magnificent sight","word":"storslået","word_en":"magnificent, grand"},{"phrase":"En malerisk landsby","phrase_en":"A picturesque village","word":"malerisk","word_en":"picturesque"},{"phrase":"Et idyllisk sted","phrase_en":"An idyllic place","word":"idyllisk","word_en":"idyllic"},{"phrase":"En stille morgen","phrase_en":"A quiet morning","word":"stille","word_en":"quiet, still"},{"phrase":"Et roligt hav","phrase_en":"A calm sea","word":"rolig","word_en":"calm"},{"phrase":"En fredelig aften","phrase_en":"A peaceful evening","word":"fredelig","word_en":"peaceful"},{"phrase":"En vild kyst","phrase_en":"A wild coast","word":"vild","word_en":"wild"},{"phrase":"En uberørt natur","phrase_en":"Pristine nature","word":"uberørt","word_en":"untouched, pristine"},{"phrase":"En gammel bydel","phrase_en":"An old town district","word":"gammel","word_en":"old"},{"phrase":"Et historisk slot","phrase_en":"A historic castle","word":"historisk","word_en":"historic"},{"phrase":"En moderne havnefront","phrase_en":"A modern waterfront","word":"moderne","word_en":"modern"},{"phrase":"Et skinnende hav","phrase_en":"A sparkling sea","word":"skinnende","word_en":"shining, sparkling"},{"phrase":"En mørk vinternat","phrase_en":"A dark winter night","word":"mørk","word_en":"dark"},{"phrase":"Et farverigt efterår","phrase_en":"A colorful autumn","word":"farverig","word_en":"colorful"},{"phrase":"Et gyldent lys","phrase_en":"A golden light","word":"gylden","word_en":"golden"},{"phrase":"En klar dag","phrase_en":"A clear day","word":"klar","word_en":"clear"},{"phrase":"En frisk morgenluft","phrase_en":"Fresh morning air","word":"frisk","word_en":"fresh"},{"phrase":"En kølig brise","phrase_en":"A cool breeze","word":"kølig","word_en":"cool"},{"phrase":"En lun sommeraften","phrase_en":"A mild summer evening","word":"lun","word_en":"mild"},{"phrase":"Et vindstille hav","phrase_en":"A windless sea","word":"vindstille","word_en":"windless, calm"}]</script>

  <section class="promise">
    <h2>Our promise to creators</h2>
    <p>Beautiful, realistic imagery should never stand between a creator and their work. Everything in this gallery is free to use — for any purpose, forever, with no credit required. We make these images so the people doing the work always have something stunning to build on.</p>
    <p><a href="#license">Read the full license</a></p>
  </section>

  <main>
    <div class="toolbar" role="search">
      <input id="q" type="search" placeholder="Search by city, site, or region" aria-label="Search by city, site, or region" />
      <select id="region" aria-label="Filter by region">
        <option value="">All regions</option>
      </select>
      
      <select id="f-daynight" aria-label="Filter by time of day">
        <option value="">Day or night</option><option value="day">Day</option><option value="night">Night</option>
      </select>
      <select id="f-mood" aria-label="Filter by scene mood">
        <option value="">All moods</option><option value="coastal">Coastal</option><option value="mountain">Mountain</option><option value="urban">Urban</option><option value="historic">Historic</option>
      </select>
      <button type="button" id="clear" aria-label="Clear all filters">Clear</button>
      <span id="result-count"></span>
    </div>
    <div id="no-results">No scenes match that search.</div>
    <div class="grid" id="grid"></div>
  </main>

  <section id="license">
    <h2>License</h2>
    <p>Every image in Jason D's Vision is free to use for any purpose — personal or commercial. No credit is required. If you'd like to credit, 'Jason D's Vision' is appreciated, but it's entirely your choice.</p>
    <p>Jason D's Vision waives its own rights in these images. This doesn't waive anyone else's rights: if an image happens to include a trademark, logo, or other third-party material, those rights still belong to their owners. All images are AI-generated artistic interpretations, not photographs, and use of an image doesn't imply endorsement by Jason D's Vision.</p>
  </section>

  <footer>
    <p>AI-generated artistic interpretations · <span class="sig">Jason D’s Vision</span> &middot; <a href="https://jdvision.org/transparency.html">How our images are made</a></p>
  </footer>

<script>
const DENMARK_META = __DENMARK_META__;
</script>
  <script>
    const SCENES = __SCENES__;

    const ASSET_BASE = "__ASSET_BASE__";

    const grid = document.getElementById('grid');
    const q = document.getElementById('q');
    const region = document.getElementById('region');
    const fdn = document.getElementById('f-daynight');
    const fmood = document.getElementById('f-mood');
    const clearBtn = document.getElementById('clear');
    const countEl = document.getElementById('result-count');
    const noResults = document.getElementById('no-results');

    const regions = [...new Set(SCENES.map(s => s.region))].sort();
    for (const r of regions) {
      const opt = document.createElement('option');
      opt.value = r; opt.textContent = r; region.appendChild(opt);
    }

    function esc(value) {
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
      }[ch]));
    }
    function fileName(url) {
      const path = String(url).split("?")[0];
      const slash = path.lastIndexOf("/");
      return slash >= 0 ? path.slice(slash + 1) : path;
    }
    /* Gallery site name (same string as the page title). Image alts are
       "{caption} — {site}, {City}". */
    const SITE_NAME = "Jason D\u2019s Vision";
    function sceneById(id) {
      for (var i = 0; i < SCENES.length; i++) {
        if (SCENES[i].entry_id === id) return SCENES[i];
      }
      return null;
    }
    function sceneAlt(caption, city) {
      return caption + " \u2014 " + SITE_NAME + ", " + city;
    }

    /* Phase 1: related scenes (Spain algorithm, DENMARK_META substituted). */
    /* Same-region first, then more shared mood tags, then entry id. Skip a scene with no master. */
    function relatedFor(id) {
      if (typeof DENMARK_META === 'undefined') return [];
      var me = DENMARK_META[id]; if (!me) return [];
      var mm = (me[2] || '').split(',').filter(Boolean); var out = [];
      for (var oid in DENMARK_META) {
        if (oid === id) continue;
        var o = DENMARK_META[oid];
        if (!o || !o[3]) continue;
        var om = ',' + (o[2] || '') + ',', shared = 0;
        for (var i = 0; i < mm.length; i++) { if (om.indexOf(',' + mm[i] + ',') >= 0) shared++; }
        if (o[0] === me[0] || shared > 0) out.push([(o[0] === me[0] ? 0 : 1), -shared, oid]);
      }
      out.sort(function(a,b){ return a[0]-b[0] || a[1]-b[1] || (a[2]<b[2] ? -1 : 1); });
      /* Per-card rotation (2026-10-01): the sorted candidate list is the same
         for every same-region card, so slice(0,4) repeated the same four scenes
         on every card. Rotate the 4-window by a hash of this card's own id so
         each card shows a different but still related set. */
      var start = 0;
      if (out.length > 4) {
        var hh = 0;
        for (var k = 0; k < id.length; k++) { hh = ((hh * 31) + id.charCodeAt(k)) >>> 0; }
        hh ^= hh >>> 16; hh = Math.imul(hh, 0x7feb352d); hh ^= hh >>> 15;
        hh = Math.imul(hh, 0x846ca68b); hh ^= hh >>> 16; hh >>>= 0;
        start = hh % out.length;
      }
      var rel = [];
      for (var j = 0; j < 4 && j < out.length; j++) { rel.push(out[(start + j) % out.length][2]); }
      return rel;
    }
    function relatedHTML(id) {
      if (typeof DENMARK_META === 'undefined') return '';
      var rel = relatedFor(id);
      if (!rel.length) return '';
      var items = rel.map(function(rid) {
        var m = DENMARK_META[rid];
        if (!m || !m[3]) return '';
        var scene = sceneById(rid);
        var alt = scene ? sceneAlt(scene.caption, scene.city) : m[4];
        return '<a class="related-link" href="#' + rid + '"><img loading="lazy" src="' +
               esc(m[3]) + '" alt="' + esc(alt) + '"><span>' + esc(m[4]) + '</span></a>';
      }).filter(Boolean).join('');
      if (!items) return '';
      return '<div class="related"><p class="related-h">Related scenes</p>' +
             '<div class="related-row">' + items + '</div></div>';
    }

    function variantKey(fmt, mode) {
      if (mode === 'postcard') {
        return fmt === '4x5' ? 'data-src-45-pc' : fmt === '9x16' ? 'data-src-916-pc' : 'data-src-16-pc';
      }
      if (mode === 'day') {
        return fmt === '4x5' ? 'data-src-45-day' : fmt === '9x16' ? 'data-src-916-day' : 'data-src-16-day';
      }
      return fmt === '4x5' ? 'data-src-45' : fmt === '9x16' ? 'data-src-916' : 'data-src-16';
    }
    function ownSrc(img, fmt, mode) {
      return (img && img.getAttribute(variantKey(fmt, mode))) || '';
    }
    function variantSrc(img, fmt, mode) {
      const own = ownSrc(img, fmt, mode);
      if (own) return own;
      if (mode === 'day') return ownSrc(img, fmt, 'scene');
      return '';
    }
    function cardMode(card) {
      if (card.querySelector('.pc-tab.is-active')) return 'postcard';
      const day = card.querySelector('.day-tab:not(.pc-tab).is-active');
      if (day && day.getAttribute('data-daynight') === 'day') return 'day';
      return 'scene';
    }
    function applyVariant(card, mode) {
      const link = card.querySelector('a.thumb');
      const img = link && link.querySelector('img');
      let fmt = '16x9';
      const active = card.querySelector('.fmt-tab.is-active');
      if (active) fmt = active.getAttribute('data-format') || '16x9';
      const t916 = card.querySelector('.fmt-tab[data-format="9x16"]');
      if (t916 && img) {
        const ok = !!ownSrc(img, '9x16', mode);
        t916.disabled = !ok;
        t916.classList.toggle('is-disabled', !ok);
        if (!ok && t916.classList.contains('is-active')) {
          const fallback = card.querySelector('.fmt-tab[data-format="16x9"]') || card.querySelector('.fmt-tab[data-format="4x5"]');
          if (fallback) {
            card.querySelectorAll('.fmt-tab').forEach((item) => {
              const on = item === fallback;
              item.classList.toggle('is-active', on);
              item.setAttribute('aria-pressed', on ? 'true' : 'false');
            });
            fmt = fallback.getAttribute('data-format') || '16x9';
          }
        }
      }
      if (img && link) {
        const next = variantSrc(img, fmt, mode);
        if (next) { img.src = next; link.href = next; }
        link.classList.toggle('tall', fmt === '4x5');
        link.classList.toggle('tall916', fmt === '9x16');
      }
      card.querySelectorAll('a.download').forEach((a) => {
        const f = a.getAttribute('data-dl');
        const u = variantSrc(img, f, mode);
        if (u) { a.href = u; a.hidden = false; a.setAttribute('download', fileName(u)); }
        else a.hidden = true;
      });
      const sc = card.querySelector('p.scenario');
      if (sc) {
        if (mode === 'postcard') sc.textContent = 'Postcard collection';
        else if (mode === 'day') sc.textContent = '\u2600 Daylight variant \u00b7 derived from the night interpretation';
        else sc.textContent = 'Scenario: ' + (sc.getAttribute('data-scenario') || '');
      }
    }
    const preDay916 = new WeakMap();
    function snapshot916(card) {
      const t916 = card.querySelector('.fmt-tab[data-format="9x16"]');
      const dl = card.querySelector('a.download[data-dl="9x16"]');
      if (!t916 && !dl) return null;
      return {
        href: dl ? (dl.getAttribute('href') || '') : '',
        download: dl ? (dl.getAttribute('download') || '') : '',
        hidden: dl ? dl.hidden : false,
        disabled: t916 ? t916.disabled : false,
        pressed: t916 ? (t916.getAttribute('aria-pressed') || 'false') : 'false',
        active: t916 ? t916.classList.contains('is-active') : false,
        disabledClass: t916 ? t916.classList.contains('is-disabled') : false
      };
    }
    function restore916(card) {
      const snap = preDay916.get(card);
      if (!snap) return;
      preDay916.delete(card);
      const dl = card.querySelector('a.download[data-dl="9x16"]');
      if (dl && snap.href) {
        dl.setAttribute('href', snap.href);
        if (snap.download) dl.setAttribute('download', snap.download);
        dl.hidden = snap.hidden;
      }
      const t916 = card.querySelector('.fmt-tab[data-format="9x16"]');
      if (!t916) return;
      t916.disabled = snap.disabled;
      t916.classList.toggle('is-disabled', snap.disabledClass);
      t916.classList.toggle('is-active', snap.active);
      t916.setAttribute('aria-pressed', snap.pressed || 'false');
      if (!snap.active) return;
      card.querySelectorAll('.fmt-tab').forEach((item) => {
        if (item === t916) return;
        item.classList.remove('is-active');
        item.setAttribute('aria-pressed', 'false');
      });
      const link = card.querySelector('a.thumb');
      const img = link && link.querySelector('img');
      if (link && img) {
        img.src = snap.href;
        link.href = snap.href;
        link.classList.remove('tall');
        link.classList.add('tall916');
      }
    }
    function render() {
      const query = q.value.trim().toLowerCase();
      const reg = region.value;
      const dn = fdn ? fdn.value : '';
      const mo = fmood ? fmood.value : '';
      const filtered = SCENES.filter(s => {
        if (reg && s.region !== reg) return false;
        const pm = (typeof DENMARK_META !== 'undefined') ? DENMARK_META[s.entry_id] : null;
        if (dn && pm && pm[1] !== dn) return false;
        if (mo && pm && ((',' + (pm[2] || '') + ',').indexOf(',' + mo + ',') < 0)) return false;
        if (!query) return true;
        const hay = (s.city + ' ' + s.caption + ' ' + s.region + ' ' + s.entry_id + ' ' + (s.description || '')).toLowerCase();
        return hay.includes(query);
      });
      grid.innerHTML = '';
      noResults.style.display = filtered.length ? 'none' : 'block';
      countEl.textContent = filtered.length + ' scene' + (filtered.length === 1 ? '' : 's');
      const approvedN = SCENES.filter(function (x) { return x.approval_status === "Approved"; }).length;
      const qcCountEl = document.getElementById("qc-count");
      if (qcCountEl) { qcCountEl.textContent = approvedN + " of " + SCENES.length + " independently approved \u00b7 " + (SCENES.length - approvedN) + " awaiting QC"; }
      for (const s of filtered) {
        const card = document.createElement('article');
        card.className = 'card';
        card.id = s.entry_id;
        if (s.audio) card.setAttribute('data-audio', s.audio);
        const file16 = s.file_16x9 ? (ASSET_BASE + 'library/world/' + s.file_16x9) : '';
        const file45 = s.file_4x5 ? (ASSET_BASE + 'library/world/' + s.file_4x5) : '';
        const file916 = s.file_9x16 ? (ASSET_BASE + 'library/world/' + s.file_9x16) : '';
        const day16 = s.file_16x9_day ? (ASSET_BASE + 'library/world/' + s.file_16x9_day) : '';
        const day45 = s.file_4x5_day ? (ASSET_BASE + 'library/world/' + s.file_4x5_day) : '';
        const day916 = s.file_9x16_day ? (ASSET_BASE + 'library/world/' + s.file_9x16_day) : '';
        const pc16 = s.file_16x9_postcard ? (ASSET_BASE + 'library/world/' + s.file_16x9_postcard) : '';
        const pc45 = s.file_4x5_postcard ? (ASSET_BASE + 'library/world/' + s.file_4x5_postcard) : '';
        const pc916 = s.file_9x16_postcard ? (ASSET_BASE + 'library/world/' + s.file_9x16_postcard) : '';
        const hasPc = !!(pc16 || pc45 || pc916);
        const sceneHero = file16 || file45 || file916;
        const hero = hasPc ? (pc16 || pc45 || pc916) : sceneHero;
        const activeFmt = (file16 || pc16) ? '16x9' : ((file45 || pc45) ? '4x5' : ((file916 || pc916) ? '9x16' : ''));
        const imgAttrs = (file16 ? ` data-src-16="${esc(file16)}"` : '')
          + (file45 ? ` data-src-45="${esc(file45)}"` : '')
          + (day16 ? ` data-src-16-day="${esc(day16)}"` : '')
          + (day45 ? ` data-src-45-day="${esc(day45)}"` : '')
          + (file916 ? ` data-src-916="${esc(file916)}"` : '')
          + (day916 ? ` data-src-916-day="${esc(day916)}"` : '')
          + (pc16 ? ` data-src-16-pc="${esc(pc16)}"` : '')
          + (pc45 ? ` data-src-45-pc="${esc(pc45)}"` : '')
          + (pc916 ? ` data-src-916-pc="${esc(pc916)}"` : '');
        const thumb = hero ? `
            <a class="thumb${activeFmt === '4x5' ? ' tall' : ''}${activeFmt === '9x16' ? ' tall916' : ''}" href="${esc(hero)}" target="_blank" rel="noopener">
              <img src="${esc(hero)}" alt="${esc(sceneAlt(s.caption, s.city))}" loading="lazy"${imgAttrs} />
            </a>` : '';
        const show16 = !!(file16 || pc16);
        const show45 = !!(file45 || pc45);
        const show916 = !!(file916 || pc916);
        const tab = (fmt, label) => {
          const on = fmt === activeFmt;
          return `<button type="button" class="fmt-tab${on ? ' is-active' : ''}" data-format="${fmt}" aria-pressed="${on ? 'true' : 'false'}">${label}</button>`;
        };
        const tabs = (show16 ? tab('16x9', '16:9') : '') + (show45 ? tab('4x5', '4:5') : '') + (show916 ? tab('9x16', '9:16') : '');
        const dl16 = (hasPc && pc16) ? pc16 : file16;
        const dl45 = (hasPc && pc45) ? pc45 : file45;
        const dl916 = (hasPc && pc916) ? pc916 : file916;
        const dl = (fmt, href, label) => href
          ? `<a class="download" data-dl="${fmt}" href="${esc(href)}" download="${esc(fileName(href))}">${label}</a>` : '';
        const dayBtn = (day16 || day45) ? `<button type="button" class="day-tab" data-daynight="night" aria-pressed="false" title="Toggle the daylight variant">\u2600 Daylight</button>` : '';
        const pcBtn = hasPc ? `<button type="button" class="day-tab pc-tab is-active" data-postcard="on" aria-pressed="true" title="Postcard collection">\u{1F4E9} Postcard</button>` : '';
const nightBtn = ((file16 || file45) && (hasPc || day16 || day45)) ? `<button type="button" class="night-tab${hasPc ? '' : ' is-active'}" data-night="on" aria-pressed="${hasPc ? 'false' : 'true'}" title="Show the nighttime view">\u{1F319} Night</button>` : '';
        card.innerHTML = `
          <div class="preview">
            ${thumb}
          </div>
          ${tabs ? `<div class="fmt-tabs" role="group" aria-label="Image size">${tabs}</div>` : ''}
          ${(dayBtn || pcBtn || nightBtn) ? `<div class="day-row">${nightBtn}${dayBtn}${pcBtn}</div>` : ''}
          <div class="card-body">
            <div class="status-row">
              <div class="entry-id">${esc(s.entry_id)}</div>
              <span class="status ${esc((s.approval_status || 'Candidate').toLowerCase())}">${esc(s.approval_status || 'Candidate')}</span>
            </div>
            <h3 class="caption">${esc(s.caption)}</h3>
            <p class="scenario" data-scenario="${esc(s.scenario_label)}">${hasPc ? 'Postcard collection' : `Scenario: ${esc(s.scenario_label)}`}</p>
            <p class="composition">${esc(s.composition)}</p>
            ${s.description ? `<p class="detail">${esc(s.description)}</p>` : ''}
            <div class="actions">
              <a class="badge" href="${esc(s.license_anchor)}">${esc(s.license_badge)}</a>
              ${dl('16x9', dl16, 'Download 16:9')}
              ${dl('4x5', dl45, 'Download 4:5')}
              ${dl('9x16', dl916, 'Download 9:16')}
              ${s.audio ? `<button type="button" class="narrate" data-audio="${esc(s.audio)}" aria-pressed="false" aria-label="Listen to the scene description">🔊 Listen</button>` : ''}
              <button type="button" class="copy-link" aria-label="Copy link to this scene">Copy link</button>
            </div>
          ${relatedHTML(s.entry_id)}</div>`;
        grid.appendChild(card);
      }
    }
    const cardAudio = { el: null, btn: null };
    function stopCardAudio() {
      if (cardAudio.el) { cardAudio.el.pause(); cardAudio.el = null; }
      if (cardAudio.btn) { cardAudio.btn.classList.remove('playing'); cardAudio.btn.setAttribute('aria-pressed','false'); cardAudio.btn.innerHTML = '🔊 Listen'; cardAudio.btn = null; }
    }
    grid.addEventListener('click', (event) => {
      const nbtn = event.target.closest('.narrate');
      if (nbtn) {
        event.preventDefault();
        const src = nbtn.getAttribute('data-audio');
        if (cardAudio.btn === nbtn && cardAudio.el && !cardAudio.el.paused) { stopCardAudio(); return; }
        stopCardAudio();
        const a = new Audio(src);
        cardAudio.el = a; cardAudio.btn = nbtn;
        nbtn.classList.add('playing'); nbtn.setAttribute('aria-pressed','true'); nbtn.innerHTML = '\u23F8\uFE0E Pause';
        a.addEventListener('ended', stopCardAudio);
        a.addEventListener('error', stopCardAudio);
        a.play().catch(stopCardAudio);
        return;
      }
      const ntab = event.target.closest('.night-tab');
      if (ntab) {
        event.preventDefault();
        const ncard = ntab.closest('.card');
        if (!ncard) return;
        ntab.classList.add('is-active');
        ntab.setAttribute('aria-pressed', 'true');
        const nsun = ncard.querySelector('.day-tab:not(.pc-tab)');
        if (nsun) { nsun.classList.remove('is-active'); nsun.setAttribute('aria-pressed', 'false'); nsun.setAttribute('data-daynight', 'night'); }
        const npc = ncard.querySelector('.pc-tab');
        if (npc) { npc.classList.remove('is-active'); npc.setAttribute('aria-pressed', 'false'); npc.setAttribute('data-postcard', 'off'); }
        applyVariant(ncard, 'scene');
        return;
      }
      const ptab = event.target.closest('.pc-tab');
      if (ptab) {
        event.preventDefault();
        const card = ptab.closest('.card');
        if (!card) return;
        const on = !ptab.classList.contains('is-active');
        ptab.classList.toggle('is-active', on);
        ptab.setAttribute('aria-pressed', on ? 'true' : 'false');
        ptab.setAttribute('data-postcard', on ? 'on' : 'off');
        if (on) { const pnt = card.querySelector('.night-tab'); if (pnt) { pnt.classList.remove('is-active'); pnt.setAttribute('aria-pressed', 'false'); } }
        const sun = card.querySelector('.day-tab:not(.pc-tab)');
        if (on && sun) {
          sun.classList.remove('is-active');
          sun.setAttribute('aria-pressed', 'false');
          sun.setAttribute('data-daynight', 'night');
        }
        applyVariant(card, on ? 'postcard' : 'scene');
        return;
      }
      const dtab = event.target.closest('.day-tab');
      if (dtab) {
        event.preventDefault();
        const dcard = dtab.closest('.card');
        if (!dcard) return;
        const isDay = !dtab.classList.contains('is-active');
        dtab.classList.toggle('is-active', isDay);
        dtab.setAttribute('aria-pressed', isDay ? 'true' : 'false');
        dtab.setAttribute('data-daynight', isDay ? 'day' : 'night');
        const pcard = dcard.querySelector('.pc-tab');
        if (isDay && pcard) {
          pcard.classList.remove('is-active');
          pcard.setAttribute('aria-pressed', 'false');
          pcard.setAttribute('data-postcard', 'off');
        }
        const dnt = dcard.querySelector('.night-tab');
        if (dnt) { dnt.classList.remove('is-active'); dnt.setAttribute('aria-pressed', 'false'); }
        if (isDay) preDay916.set(dcard, snapshot916(dcard));
        applyVariant(dcard, isDay ? 'day' : 'scene');
        if (!isDay) restore916(dcard);
        return;
      }
      const tab = event.target.closest('.fmt-tab');
      if (!tab || tab.disabled) return;
      event.preventDefault();
      const card = tab.closest('.card');
      if (!card) return;
      const fmt = tab.getAttribute('data-format');
      card.querySelectorAll('.fmt-tab').forEach((item) => {
        const on = item === tab;
        item.classList.toggle('is-active', on);
        item.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
      const link = card.querySelector('a.thumb');
      const img = link && link.querySelector('img');
      if (!img || !link) return;
      const mode = cardMode(card);
      const next = fmt === "4x5"
        ? (mode === 'postcard' ? img.getAttribute('data-src-45-pc') : mode === 'day' ? (img.getAttribute('data-src-45-day') || img.getAttribute("data-src-45")) : img.getAttribute("data-src-45"))
        : fmt === "9x16"
        ? (mode === 'postcard' ? img.getAttribute('data-src-916-pc') : mode === 'day' ? (img.getAttribute('data-src-916-day') || img.getAttribute('data-src-916')) : img.getAttribute('data-src-916'))
        : (mode === 'postcard' ? img.getAttribute('data-src-16-pc') : mode === 'day' ? (img.getAttribute('data-src-16-day') || img.getAttribute('data-src-16')) : img.getAttribute('data-src-16'));
      if (next) {
        img.src = next;
        link.href = next;
      }
      link.classList.toggle('tall', fmt === '4x5');
      link.classList.toggle('tall916', fmt === '9x16');
    });
    q.addEventListener('input', render);
    region.addEventListener('change', render);
    if (fdn) fdn.addEventListener('change', render);
    if (fmood) fmood.addEventListener('change', render);
    clearBtn.addEventListener('click', () => { q.value = ''; region.value = ''; if (fdn) fdn.value = ''; if (fmood) fmood.value = ''; render(); });
    /* Phase 1: copy-link + related-scene navigation (delegated; cards rebuild on render). */
    grid.addEventListener('click', (event) => {
      const rl = event.target.closest('.related-link');
      if (rl) {
        event.preventDefault();
        const href = rl.getAttribute('href') || '';
        const id = href.charAt(0) === '#' ? href.slice(1) : href;
        q.value = '';
        region.value = '';
        if (fdn) fdn.value = '';
        if (fmood) fmood.value = '';
        render();
        if (id) {
          history.pushState(null, '', '#' + id);
          const el = document.getElementById(id);
          if (el) el.scrollIntoView({block: 'start'});
        }
        return;
      }
      const cb = event.target.closest('.copy-link');
      if (cb) {
        event.preventDefault();
        const card = cb.closest('.card');
        const id = card ? card.id : '';
        const url = location.origin + location.pathname + '#' + id;
        const done = () => { cb.textContent = 'Copied \u2713';
          setTimeout(() => { cb.textContent = 'Copy link'; }, 1600); };
        const fb = () => { const ta = document.createElement('textarea'); ta.value = url;
          ta.style.position = 'fixed'; ta.style.opacity = '0'; document.body.appendChild(ta);
          ta.select(); try { document.execCommand('copy'); done(); } catch (e) {} ta.remove(); };
        if (navigator.clipboard && navigator.clipboard.writeText) {
          navigator.clipboard.writeText(url).then(done, fb);
        } else { fb(); }
      }
    });

    render();
    if (location.hash) {
      let deep = location.hash.slice(1);
      try { deep = decodeURIComponent(deep); } catch (e) {}
      const el = deep && document.getElementById(deep);
      if (el) el.scrollIntoView({block: 'start'});
    }
  </script>
  <noscript><p>Images and download links work without JavaScript. Enable JavaScript for search and the full-screen viewer.</p></noscript>
  <script>
(function(){
    var overlay=document.createElement('div');
    overlay.className='lb';overlay.setAttribute('aria-hidden','true');
    overlay.innerHTML='<button class="lb-close" aria-label="Close">&times;</button>'
      +'<figure><div class="lb-nav"><button class="lb-prev" aria-label="Previous image">&#8249;</button>'
      +'<span class="lb-count"></span>'
      +'<button class="lb-next" aria-label="Next image">&#8250;</button></div>'
      +'<img alt=""><figcaption><span class="lb-cap"></span></figcaption>'
      +'<div class="lb-controls"><button class="lb-play" aria-label="Play slideshow">&#9654;</button><button class="lb-narrate" aria-label="Play scene narration" style="display:none">&#128266;</button></div></figure>';
    document.body.appendChild(overlay);
    var img=overlay.querySelector('img'),cap=overlay.querySelector('.lb-cap'),count=overlay.querySelector('.lb-count');
    var playBtn=overlay.querySelector('.lb-play');
    var narrBtn=overlay.querySelector('.lb-narrate');
    var narrAudio=null;
    function stopNarr(){if(narrAudio){narrAudio.pause();narrAudio=null;}narrBtn.classList.remove('playing');narrBtn.setAttribute('aria-label','Play scene narration');narrBtn.innerHTML='&#128266;';}
    function setNarrState(playing){narrBtn.classList.toggle('playing',playing);narrBtn.setAttribute('aria-label',playing?'Pause scene narration':'Play scene narration');narrBtn.innerHTML=playing?'&#10074;&#10074;':'&#128266;';}
    function toggleNarr(){
      var card=visibleCards()[idx];var src=card?card.getAttribute('data-audio'):'';
      if(!src)return;
      if(narrAudio&&!narrAudio.paused){stopNarr();return;}
      stopNarr();
      narrAudio=new Audio(src);
      narrAudio.addEventListener('ended',stopNarr);
      narrAudio.addEventListener('error',stopNarr);
      setNarrState(true);
      narrAudio.play().catch(stopNarr);
    }
    var items=[],idx=0;
    var playing=false,timer=null;
    var INTERVAL=4000;/* 4s slideshow autoplay, no autostart */
    var lbFormat='16x9';
    var lbDay='night';/* lightbox-session day/night: seeded from the opening card's active day tab; persists across prev/next and slideshow navigation *//* lightbox-session format: seeded from the opening card's active tab; persists across prev/next and slideshow navigation, never reset to 16:9 */
    var lbPost='off';/* lightbox-session postcard: seeded from the opening card; falls back per image when that card has no postcard */
    function visibleCards(){return Array.prototype.filter.call(document.querySelectorAll('.card'),function(c){return c.style.display!=='none';});}
    function show(i){
      items=visibleCards().map(function(c){
        var im=c.querySelector('a.thumb img');var t=c.querySelector('h3.caption');
        var src='';
        var daySrc='';
        var pcSrc='';
        if(im){var nk=lbFormat==='4x5'?'data-src-45':lbFormat==='9x16'?'data-src-916':'data-src-16',dk=lbFormat==='4x5'?'data-src-45-day':lbFormat==='9x16'?'data-src-916-day':'data-src-16-day',pk=lbFormat==='4x5'?'data-src-45-pc':lbFormat==='9x16'?'data-src-916-pc':'data-src-16-pc';pcSrc=(lbPost==='on')?(im.getAttribute(pk)||''):'';if(pcSrc){src=pcSrc;}else{if(lbDay==='day'){daySrc=im.getAttribute(dk)||'';}src=daySrc||im.getAttribute(nk);}}
        if(!src){var a=c.querySelector('a.thumb');src=a?a.href:'';}
        var capT=t?t.textContent:'';if(pcSrc)capT=capT+' \u2014 Postcard collection';else if(daySrc)capT=capT+' \u2014 \u2600 Daylight variant';
        var altT=im&&im.alt?im.alt:'';if(pcSrc&&altT)altT=altT+' \u2014 Postcard collection';else if(daySrc&&altT)altT=altT+' \u2014 \u2600 Daylight variant';
        return{src:src,cap:capT,alt:altT};
      }).filter(function(x){return x.src;});
      if(!items.length)return;
      idx=(i+items.length)%items.length;
      stopNarr();
      img.src=items[idx].src;img.alt=items[idx].alt||items[idx].cap;cap.textContent=items[idx].cap;
      var curCard=visibleCards()[idx];var hasA=!!(curCard&&curCard.getAttribute('data-audio'));
      narrBtn.style.display=hasA?'':'none';
      count.textContent=(idx+1)+' / '+items.length;
      overlay.classList.add('open');overlay.setAttribute('aria-hidden','false');document.body.style.overflow='hidden';
    }
    function setPlaying(on){playing=on;playBtn.classList.toggle('playing',on);playBtn.innerHTML=on?'&#10074;&#10074;':'&#9654;';playBtn.setAttribute('aria-label',on?'Pause slideshow':'Play slideshow');}
    function restartTimer(){if(timer)clearTimeout(timer);timer=setTimeout(tick,INTERVAL);}
    function tick(){if(!playing)return;show(idx+1);restartTimer();}
    /* No autostart, so prefers-reduced-motion needs no special casing; an explicit user press of play is always honoured. */
    function startSlideshow(){if(playing)return;setPlaying(true);restartTimer();}
    function stopSlideshow(){playing=false;if(timer){clearTimeout(timer);timer=null;}setPlaying(false);}
    function togglePlay(){if(playing)stopSlideshow();else startSlideshow();}
    function nav(d){show(idx+d);if(playing)restartTimer();}
    function hide(){stopSlideshow();stopNarr();overlay.classList.remove('open');overlay.setAttribute('aria-hidden','true');document.body.style.overflow='';}
    document.addEventListener('click',function(e){
      var a=e.target.closest?e.target.closest('a.thumb'):null;
      if(a){e.preventDefault();var cards=visibleCards();var card=a.closest('.card');var tab=card.querySelector('.fmt-tab.is-active');lbFormat=(tab&&tab.getAttribute('data-format')==='9x16')?'9x16':(tab&&tab.getAttribute('data-format')==='4x5')?'4x5':'16x9';var ptab=card.querySelector('.pc-tab.is-active');lbPost=ptab?'on':'off';var dtab=card.querySelector('.day-tab:not(.pc-tab).is-active');lbDay=(dtab&&dtab.getAttribute('data-daynight')==='day')?'day':'night';if(lbPost==='on')lbDay='night';show(cards.indexOf(card));return;}
      if(e.target===overlay||(e.target.closest&&e.target.closest('.lb-close')))hide();
      else if(e.target.closest&&e.target.closest('.lb-play'))togglePlay();
      else if(e.target.closest&&e.target.closest('.lb-narrate'))toggleNarr();
      else if(e.target.closest&&e.target.closest('.lb-prev'))nav(-1);
      else if(e.target.closest&&e.target.closest('.lb-next'))nav(1);
    });
    document.addEventListener('keydown',function(e){
      if(!overlay.classList.contains('open'))return;
      if(e.key==='Escape')hide();
      else if(e.key==='ArrowLeft')nav(-1);
      else if(e.key==='ArrowRight')nav(1);
      else if(e.key===' '||e.key==='Spacebar'){
        /* let a focused button's native space activation handle itself */
        if(e.target&&e.target.tagName==='BUTTON')return;
        e.preventDefault();togglePlay();
      }
    });
  })();
</script>
<script>
(function(){
  try{
    var data=JSON.parse(document.getElementById('wotd-data').textContent);
    if(!data||!data.length)return;
    var now=new Date();
    var doy=Math.floor((now-new Date(now.getFullYear(),0,0))/864e5); /* Jan 1 -> 1 */
    var e=data[(doy-1)%data.length];
    var esc=function(s){return String(s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});};
    var h='<span class="word">'+esc(e.word)+'</span>';
    if(e.translit)h+=' <span class="translit">('+esc(e.translit)+')</span>';
    h+=' <span class="gloss">&ldquo;'+esc(e.word_en)+'&rdquo;</span> <span class="sep">&middot;</span> <span class="phrase">&ldquo;'+esc(e.phrase)+'&rdquo;</span>';
    if(e.phrase_translit)h+=' <span class="translit">('+esc(e.phrase_translit)+')</span>';
    h+=' <span class="gloss">&ldquo;'+esc(e.phrase_en)+'&rdquo;</span>';
    document.querySelector('#wotd .wotd-body').innerHTML=h;
    document.getElementById('wotd-day').textContent='Day '+doy+' of 365';
  }catch(err){}
})();
</script>


</body>
</html>"""

MOOD_PATH = Path(__file__).resolve().parent / "denmark_moods.json"
# Signed-off mood strings live in tools/denmark_moods.json. A scene added later
# still receives Coastal / Mountain / Urban / Historic tags from these words
# until that table is extended. Day or night comes from the scenario hour:
# 07:00-16:59 is day; every other hour is night. That split matches the
# published Denmark gallery.
MOOD_KEYWORDS = {
    "coastal": (
        "beach", "coast", "harbour", "harbor", "fjord", "island", "shore",
        "lighthouse", "marina", "quay", "waterfront", "strait", "dune",
        "sea", "ocean", "bay", "inlet", "cliff", "klint",
    ),
    "mountain": (
        "mountain", "glacier", "fjeld", "highland", "peak", "alpine", "valley", "gorge",
    ),
    "urban": (
        "street", "square", "skyline", "old town", "quarter", "avenue",
        "city centre", "city center", "neighbourhood", "neighborhood",
    ),
    "historic": (
        "castle", "cathedral", "church", "palace", "ruin", "museum", "medieval",
        "manor", "abbey", "fortress", "monastery", "kirke", "slot", "historic",
    ),
}


def scenario_period(label: str) -> str:
    import re
    match = re.search(r"(\d{2}):(\d{2})", label or "")
    if not match:
        return "night"
    hour = int(match.group(1))
    return "day" if 7 <= hour <= 16 else "night"


def infer_moods(card: dict) -> str:
    import re
    blob = " ".join(
        str(card.get(key) or "")
        for key in ("caption", "description", "composition", "city", "region")
    ).lower()
    tags = []
    for name, words in MOOD_KEYWORDS.items():
        if any(
            re.search(rf"(?<![a-zæøå]){re.escape(word)}(?![a-zæøå])", blob)
            for word in words
        ):
            tags.append(name)
    return ",".join(tags)


# Gallery pages stay on the preview host. library/ bytes are served from the
# assets repo at the same relative path.
ASSET_BASE = "https://devlij.github.io/jason-ds-vision-denmark-assets/"


def master_exists(rel: str | None) -> bool:
    if not rel:
        return False
    return (ROOT / "library" / "world" / rel).is_file()


def published_library_rel(url_or_rel: str) -> str:
    if url_or_rel.startswith(ASSET_BASE):
        return url_or_rel[len(ASSET_BASE):]
    return url_or_rel


def _library_rel(path: str | None) -> str | None:
    if not path:
        return None
    prefix = "library/world/"
    rel = path[len(prefix):] if path.startswith(prefix) else path
    return rel if master_exists(rel) else None


def gallery_card(data: dict) -> dict:
    """Gallery payload. Image controls are omitted when the master file is absent."""
    card: dict = {}
    for key in (
        "entry_id",
        "approval_status",
        "country",
        "region",
        "city",
        "caption",
        "scenario_label",
        "composition",
        "description",
        "alt_text",
        "license_badge",
        "license_anchor",
    ):
        value = data.get(key)
        if value not in (None, ""):
            card[key] = value
    for key in ("file_16x9", "file_4x5"):
        rel = data.get(key)
        if master_exists(rel):
            card[key] = rel
    variant = data.get("daylight_variant") or {}
    files = variant.get("files") or {}
    day16 = _library_rel(files.get("16x9"))
    day45 = _library_rel(files.get("4x5"))
    if day16 and day45:
        card["file_16x9_day"] = day16
        card["file_4x5_day"] = day45
    night = data.get("file_16x9") or ""
    if night.endswith("-16x9.png"):
        folder = night.rsplit("/", 1)[0] if "/" in night else ""
        stem = Path(night).name[: -len("-16x9.png")]
        for key, suffix in (("file_9x16", "-9x16.png"), ("file_9x16_day", "-daylight-9x16.png")):
            rel = f"{folder}/{stem}{suffix}" if folder else f"{stem}{suffix}"
            if master_exists(rel):
                card[key] = rel
        for key, suffix in (
            ("file_16x9_postcard", "-postcard-16x9.png"),
            ("file_4x5_postcard", "-postcard-4x5.png"),
            ("file_9x16_postcard", "-postcard-9x16.png"),
        ):
            rel = f"{folder}/{stem}{suffix}" if folder else f"{stem}{suffix}"
            if master_exists(rel):
                card[key] = rel
        # The live catalogue publishes no night/day 9:16 tabs. Those masters
        # stay on disk. This rebuild must not turn them on for other scenes.
        # Postcard 9:16 uses file_9x16_postcard and is unaffected.
        card.pop("file_9x16", None)
        card.pop("file_9x16_day", None)
    entry = str(data.get("entry_id") or "")
    audio = ROOT / "audio" / f"{entry.lower()}-narration.mp3"
    if entry and audio.is_file():
        card["audio"] = f"audio/{audio.name}"
    return card


def denmark_meta(cards: list) -> dict:
    moods = {}
    if MOOD_PATH.is_file():
        moods = json.loads(MOOD_PATH.read_text(encoding="utf-8"))
    meta = {}
    for card in cards:
        entry = card["entry_id"]
        rel = card.get("file_16x9") or ""
        thumb = f"{ASSET_BASE}library/world/{rel}" if rel and master_exists(rel) else ""
        mood = moods.get(entry)
        if mood is None:
            mood = infer_moods(card)
        meta[entry] = [
            card.get("region") or "",
            scenario_period(card.get("scenario_label") or ""),
            mood or "",
            thumb,
            card.get("caption") or "",
        ]
    return meta


def write_site(scenes: list) -> None:
    cards = []
    for scene in scenes:
        data = scene.get("_manifest") if isinstance(scene, dict) and scene.get("_manifest") else scene
        cards.append(gallery_card(data))
    cards.sort(key=lambda item: item["entry_id"])
    meta = denmark_meta(cards)
    payload = json.dumps(cards, ensure_ascii=False).replace("<", "\\u003c")
    meta_payload = json.dumps(meta, ensure_ascii=False).replace("<", "\\u003c")
    html = (
        PAGE.replace("DK_SVG", DK_SVG)
        .replace("__ASSET_BASE__", ASSET_BASE)
        .replace("__DENMARK_META__", meta_payload)
        .replace("__SCENES__", payload)
    )
    for eid, row in meta.items():
        thumb = row[3]
        rel = published_library_rel(thumb) if thumb else ""
        if rel and not (ROOT / rel).is_file():
            raise SystemExit(f"related thumb missing master {eid} {thumb}")
    for card in cards:
        for key in ("file_16x9", "file_4x5", "file_16x9_day", "file_4x5_day", "file_9x16", "file_9x16_day", "file_16x9_postcard", "file_4x5_postcard", "file_9x16_postcard"):
            rel = card.get(key)
            if rel and not master_exists(rel):
                raise SystemExit(f"gallery control for missing master {card['entry_id']} {key}")
        audio = card.get("audio")
        if audio and not (ROOT / audio).is_file():
            raise SystemExit(f"missing narration {card['entry_id']} {audio}")
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    import build_image_sitemap

    (ROOT / "robots.txt").write_text(build_image_sitemap.robots_txt(), encoding="utf-8")
    (ROOT / "sitemap.xml").write_text(
        """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://devlij.github.io/jason-ds-vision-denmark-preview/</loc>
  </url>
</urlset>
""",
        encoding="utf-8",
    )
    build_image_sitemap.write_image_sitemap(ROOT)
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    required = [
        "G-PDJ4WSS725",
        "flag-band",
        "https://germany.jdvision.org/",
        "https://italy.jdvision.org/",
        "https://spain.jdvision.org/",
        "https://france.jdvision.org/",
        "https://greece.jdvision.org/",
        "https://devlij.github.io/jason-ds-vision-switzerland-preview/",
        "https://devlij.github.io/jason-ds-vision-norway-preview/",
        "flag-no",
        'id="license"',
        "Our promise to creators",
        "Download 16:9",
        "Download 4:5",
        "h3.caption",
        'id="qc-count"',
        "independently approved",
        "lightbox-session format",
        "s.approval_status",
        "function sceneAlt",
        "SITE_NAME",
        "lb-play",
        "INTERVAL=4000",
        "home-link",
        "Postcard collection",
        "file_16x9_postcard",
        'id="q"',
        'id="region"',
        'id="f-daynight"',
        'id="f-mood"',
        "Coastal",
        "Mountain",
        "Urban",
        "Historic",
        'id="result-count"',
        'aria-label="Clear all filters"',
        "function relatedFor",
        "Copy link",
        "Copied \\u2713",
        "card.id = s.entry_id",
        "related-row",
        "class=\"badge\"",
        "fmt-tab",
        "https://devlij.github.io/jason-ds-vision-denmark-assets/",
        "How our images are made",
        'id="wotd"',
        "ImageGallery",
        "center/45% 22%",
        'getAttribute("data-src-45")',
        "\\u23F8\\uFE0E",
        "🔊 Listen",
    ]
    for item in required:
        if item not in html:
            raise SystemExit(f"gallery missing {item}")
    if "G-FPVHCRLKD2" in html:
        raise SystemExit("stale analytics id")
    if "\\u0001F50A" in html or "\\u0023F8" in html:
        raise SystemExit("broken Listen glyph")
    if "background:#DA291C;position:relative" in html:
        raise SystemExit("switzerland chip missing cross")
    if "__SCENES__" in html or "__DENMARK_META__" in html or "__ASSET_BASE__" in html:
        raise SystemExit("unsubstituted gallery placeholder")
    if html.count("ASSET_BASE + 'library/world/'") != 9:
        raise SystemExit("asset url prefix drift")
    if '"library/world/' in html or "jason-ds-vision-denmark-preview/library/" in html:
        raise SystemExit("gallery asset URL is not on the assets CDN")



def main() -> None:
    if len(SCENES) != 16:
        raise SystemExit(len(SCENES))
    lines = []
    for scene in SCENES:
        label = scenario_label(scene["entry_id"])
        write_outputs(scene, label)
        manifest(scene, label)
        approval(scene, label)
        brief = scene["weather_brief"]
        city = scene["city"]
        entry = scene["entry_id"].lower()
        retrieved = scene["weather_prefix"]
        lines.append(
            f"**{scene['entry_id']} — {scene['caption']}** · Scenario: {label} · "
            f"Weather: {retrieved} {scene['weather_detail']} · "
            f"Masters: `Denmark/{city}/{entry}-16x9.png`, `Denmark/{city}/{entry}-4x5.png` · Gates: 5/5 pass."
        )
        print(lines[-1])
    write_site(SCENES)
    report = ROOT / "approvals" / "BATCH-DK-01-001-016.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("site written", len(SCENES))


if __name__ == "__main__":
    main()
