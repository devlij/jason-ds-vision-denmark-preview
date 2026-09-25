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
<script async src="https://www.googletagmanager.com/gtag/js?id=G-FPVHCRLKD2"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', 'G-FPVHCRLKD2');
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
<meta property="og:image" content="https://devlij.github.io/jason-ds-vision-denmark-preview/library/world/Denmark/Copenhagen/dk-01-001-16x9.png"/>
<meta property="og:url" content="https://devlij.github.io/jason-ds-vision-denmark-preview/"/>
<meta name="twitter:card" content="summary_large_image"/>
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "WebSite",
      "name": "Jason D’s Vision — Denmark",
      "url": "https://devlij.github.io/jason-ds-vision-denmark-preview/",
      "inLanguage": "en"
    },
    {
      "@type": "Organization",
      "name": "Jason D's Vision",
      "url": "https://jdvision.org/"
    }
  ]
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
      overflow: hidden; display: flex; flex-direction: column;
    }
    .preview { position: relative; }
    .fmt-tabs {
      position: absolute; top: 1.05rem; left: 1.05rem; display: flex; gap: 6px; z-index: 2;
    }
    .fmt-tab {
      background: rgba(23, 32, 42, 0.85); color: var(--text); border: 1px solid var(--line);
      border-radius: 8px; padding: 5px 10px; font: inherit; font-size: 12px; line-height: 1.2; cursor: pointer;
    }
    .fmt-tab:hover { border-color: var(--muted); }
    .fmt-tab.is-active {
      background: var(--accent); border-color: var(--accent); color: var(--bg); font-weight: 700;
    }
    .view-affordance {
      position: absolute; top: 1.05rem; right: 1.05rem; z-index: 2;
      padding: 5px 10px; border: 1px solid rgba(255, 255, 255, 0.35); border-radius: 999px;
      background: rgba(23, 32, 42, 0.72); color: var(--text); font-size: 11px; pointer-events: none;
    }
    .thumb {
      display: block; padding: 0.65rem 0.65rem 0; background: #12151c; line-height: 0;
    }
    .thumb img {
      width: 100%; height: auto; display: block; border-radius: 8px; background: #000;
      aspect-ratio: 16 / 9; object-fit: contain;
    }
    .thumb.tall img { aspect-ratio: 4 / 5; }
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
    .flag-chip.flag-ch{background:#DA291C;position:relative}
    .flag-chip.flag-dk{background:linear-gradient(to bottom,transparent 38%,#fff 38%,#fff 62%,transparent 62%),linear-gradient(to right,transparent 28%,#fff 28%,#fff 44%,transparent 44%),#C8102E}
    .lb{position:fixed;inset:0;z-index:60;display:none;align-items:center;justify-content:center;background:rgba(13,18,24,.93)}
.lb.open{display:flex}
.lb figure{margin:0;max-width:94vw;display:flex;flex-direction:column;align-items:center}
.lb img{max-width:94vw;max-height:72vh;display:block;border-radius:6px}
.lb figcaption{align-self:stretch;color:#f0f3f6;font-size:14px;padding:10px 2px 0}
.lb-nav{display:flex;align-items:center;justify-content:center;gap:20px;margin-bottom:12px}
.lb-count{color:#9fb0c0;white-space:nowrap;font-size:15px;min-width:90px;text-align:center}
.lb-controls{display:flex;justify-content:center;margin-top:12px}
.lb-prev,.lb-next,.lb-play{background:rgba(23,32,42,.85);color:#f0f3f6;border:1px solid #26313d;border-radius:999px;width:46px;height:46px;font-size:20px;cursor:pointer;line-height:1}
.lb-play.playing{background:#e05260;border-color:#e05260;color:#0f1418}
.lb-close{position:absolute;top:14px;right:14px;background:rgba(23,32,42,.85);color:#f0f3f6;border:1px solid #26313d;border-radius:999px;width:46px;height:46px;font-size:20px;cursor:pointer;line-height:1}}
</style>
</head>
<body>
  <div class="flag-band" aria-hidden="true"></div>
  <header>
    <p class="pointer">Every image is free to use — no credit required. See <a href="#license">license</a> below.</p>
    <h1><span class="flag" aria-hidden="true">DK_SVG</span>Jason D’s Vision — Denmark</h1>
    <p class="qc-count" id="qc-count"></p>
    <nav class="country-switch" aria-label="Country galleries">
      <span aria-current="page"><span class="flag-chip" aria-hidden="true">DK_SVG</span>Denmark</span>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://germany.jdvision.org/"><span class="flag-chip flag-de" aria-hidden="true"></span>Germany</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://italy.jdvision.org/"><span class="flag-chip flag-it" aria-hidden="true"></span>Italy</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://devlij.github.io/jason-ds-vision-spain-preview/"><span class="flag-chip flag-es" aria-hidden="true"></span>Spain</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://france.jdvision.org/"><span class="flag-chip flag-fr" aria-hidden="true"></span>France</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://greece.jdvision.org/"><span class="flag-chip flag-gr" aria-hidden="true"></span>Greece</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://devlij.github.io/jason-ds-vision-switzerland-preview/"><span class="flag-chip flag-ch" aria-hidden="true"></span>Switzerland</a>
      <span class="sep" aria-hidden="true">|</span>
      <a href="https://devlij.github.io/jason-ds-vision-netherlands-preview/"><span class="flag-chip flag-nl" aria-hidden="true"></span>Netherlands</a>
    </nav>
    <p class="sub">Denmark, the Faroe Islands and Greenland · Candidate scenes until an independent QC pass</p>
  </header>

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
      <button type="button" id="clear">Clear</button>
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
    <p>AI-generated artistic interpretations · <span class="sig">Jason D’s Vision</span></p>
  </footer>

  <script>
    const SCENES = __SCENES__;

    const grid = document.getElementById('grid');
    const q = document.getElementById('q');
    const region = document.getElementById('region');
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

    function render() {
      const query = q.value.trim().toLowerCase();
      const reg = region.value;
      const filtered = SCENES.filter(s => {
        if (reg && s.region !== reg) return false;
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
        const file16 = 'library/world/' + s.file_16x9;
        const file45 = 'library/world/' + s.file_4x5;
        card.innerHTML = `
          <div class="preview">
            <div class="fmt-tabs" role="group" aria-label="Image size">
              <button type="button" class="fmt-tab is-active" data-format="16x9" aria-pressed="true">16:9</button>
              <button type="button" class="fmt-tab" data-format="4x5" aria-pressed="false">4:5</button>
            </div>
            <a class="thumb" href="${esc(file16)}" target="_blank" rel="noopener">
              <img src="${esc(file16)}" alt="${esc(s.alt_text)}" loading="lazy" data-src-16="${esc(file16)}" data-src-45="${esc(file45)}" />
              <span class="view-affordance">View image</span>
            </a>
          </div>
          <div class="card-body">
            <div class="status-row">
              <div class="entry-id">${esc(s.entry_id)}</div>
              <span class="status ${esc((s.approval_status || 'Candidate').toLowerCase())}">${esc(s.approval_status || 'Candidate')}</span>
            </div>
            <h3 class="caption">${esc(s.caption)}</h3>
            <p class="scenario">Scenario: ${esc(s.scenario_label)}</p>
            <p class="composition">${esc(s.composition)}</p>
            ${s.description ? `<p class="detail">${esc(s.description)}</p>` : ""}
            <div class="actions">
              <a class="badge" href="${esc(s.license_anchor)}">${esc(s.license_badge)}</a>
              <a class="download" href="${esc(file16)}" download="${esc(fileName(file16))}">Download 16:9</a>
              <a class="download" href="${esc(file45)}" download="${esc(fileName(file45))}">Download 4:5</a>
            </div>
          </div>`;
        grid.appendChild(card);
      }
    }
    grid.addEventListener('click', (event) => {
      const tab = event.target.closest('.fmt-tab');
      if (!tab) return;
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
      const next = fmt === "4x5" ? img.getAttribute("data-src-45") : img.getAttribute("data-src-16");
      if (next) {
        img.src = next;
        link.href = next;
      }
      link.classList.toggle('tall', fmt === '4x5');
    });
    q.addEventListener('input', render);
    region.addEventListener('change', render);
    clearBtn.addEventListener('click', () => { q.value = ''; region.value = ''; render(); });
    render();
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
      +'<div class="lb-controls"><button class="lb-play" aria-label="Play slideshow">&#9654;</button></div></figure>';
    document.body.appendChild(overlay);
    var img=overlay.querySelector('img'),cap=overlay.querySelector('.lb-cap'),count=overlay.querySelector('.lb-count');
    var playBtn=overlay.querySelector('.lb-play');
    var items=[],idx=0;
    var playing=false,timer=null;
    var INTERVAL=6000;/* 6s slideshow autoplay, no autostart */
    var lbFormat='16x9';/* lightbox-session format: seeded from the opening card's active tab; persists across prev/next and slideshow navigation, never reset to 16:9 */
    function visibleCards(){return Array.prototype.filter.call(document.querySelectorAll('.card'),function(c){return c.style.display!=='none';});}
    function show(i){
      items=visibleCards().map(function(c){
        var im=c.querySelector('a.thumb img');var t=c.querySelector('h3.caption');
        var src='';
        if(im){src=lbFormat==='4x5'?im.getAttribute('data-src-45'):im.getAttribute('data-src-16');}
        if(!src){var a=c.querySelector('a.thumb');src=a?a.href:'';}
        return{src:src,cap:t?t.textContent:''};
      }).filter(function(x){return x.src;});
      if(!items.length)return;
      idx=(i+items.length)%items.length;
      img.src=items[idx].src;img.alt=items[idx].cap;cap.textContent=items[idx].cap;
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
    function hide(){stopSlideshow();overlay.classList.remove('open');overlay.setAttribute('aria-hidden','true');document.body.style.overflow='';}
    document.addEventListener('click',function(e){
      var a=e.target.closest?e.target.closest('a.thumb'):null;
      if(a){e.preventDefault();var cards=visibleCards();var card=a.closest('.card');var tab=card.querySelector('.fmt-tab.is-active');lbFormat=(tab&&tab.getAttribute('data-format')==='4x5')?'4x5':'16x9';show(cards.indexOf(card));return;}
      if(e.target===overlay||(e.target.closest&&e.target.closest('.lb-close')))hide();
      else if(e.target.closest&&e.target.closest('.lb-play'))togglePlay();
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
</body>
</html>
"""



def write_site(scenes: list) -> None:
    cards = [s["_manifest"] for s in scenes]
    payload = json.dumps(cards, ensure_ascii=False).replace("<", "\\u003c")
    html = PAGE.replace("DK_SVG", DK_SVG).replace("__SCENES__", payload)
    # The title and h1 in the template use a curly apostrophe typed as a unicode char.
    (ROOT / "index.html").write_text(html, encoding="utf-8")
    (ROOT / "robots.txt").write_text(
        "User-agent: *\nAllow: /\n\nSitemap: https://devlij.github.io/jason-ds-vision-denmark-preview/sitemap.xml\n",
        encoding="utf-8",
    )
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
    (ROOT / ".nojekyll").write_text("", encoding="utf-8")
    required = [
        'getAttribute("data-src-45")',
        'getAttribute("data-src-16")',
        "flag-band",
        "G-FPVHCRLKD2",
        "https://germany.jdvision.org/",
        "https://italy.jdvision.org/",
        "https://devlij.github.io/jason-ds-vision-spain-preview/",
        "https://france.jdvision.org/",
        "https://greece.jdvision.org/",
        "https://devlij.github.io/jason-ds-vision-switzerland-preview/",
        "https://devlij.github.io/jason-ds-vision-netherlands-preview/",
        'id="license"',
        "Our promise to creators",
        "Download 16:9",
        "Download 4:5",
        "h3.caption",
        'id="qc-count"',
        "independently approved",
        "lightbox-session format",
        "s.approval_status",
        "lb-play",
        "INTERVAL=6000",
    ]
    for item in required:
        if item not in html:
            raise SystemExit(f"gallery missing {item}")


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
