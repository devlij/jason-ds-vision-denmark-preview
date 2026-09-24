#!/usr/bin/env python3
"""Bake DK-01-017 through DK-01-032 and rebuild the gallery from every manifest."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_denmark as bd

WEATHER = (
    "Model data from Open-Meteo, retrieved 25 September 2026 00:36 Europe/Copenhagen, "
    "valid 25 September 2026 00:00 Europe/Copenhagen \u2014 not a verified on-site observation."
)

SCENES = [
    {
        "entry_id": "DK-01-017",
        "region": "Capital Region",
        "city": "Copenhagen",
        "caption": "Tivoli Gardens, Copenhagen",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 13.9\u00b0C, cloud cover 43%, wind 5.0 km/h, no precipitation.",
        "weather_brief": "mainly clear, 13.9\u00b0C",
        "composition": "Closed garden gate and dark trees on Vesterbrogade \u00b7 AI-generated artistic interpretation",
        "description": "From the Vesterbrogade sidewalk, Tivoli's historic garden gate is shut and the trees behind it are dark. The pavement is empty under ordinary streetlamps. It is a mainly clear night, about 13.9\u00b0C, with no rain. Summer at Tivoli ended on 20 September 2026 and Halloween does not open until 2 October, so this is not a ride night, a flower show, or a Halloween display.",
        "alt_text": "AI-generated artistic interpretation of the closed Tivoli Gardens gate in Copenhagen on a mainly clear night",
        "viewpoint": "Vesterbrogade sidewalk outside the main garden gate, looking at the closed entrance and the trees. Approximate researched point 55.6738, 12.5680, not a surveyed camera.",
        "refs": [
            "https://www.tivoli.dk/en/opening-hours-and-seasons",
            "https://en.wikipedia.org/wiki/Tivoli_Gardens",
        ],
        "anchors": [
            "Historic garden gate shut against the street.",
            "Dark late-September trees inside, with no moving rides.",
            "Empty pavement and streetlamps, no Halloween dressing and no Christmas lights.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:03 Europe/Copenhagen. Cloud cover 43%. A waxing gibbous moon near 97% illumination was computed for 22:15 UTC, not observed on site. The gate is lit by streetlamps.",
        "independent": "Tivoli Gardens is the pleasure garden on Vesterbrogade. On 25 September 2026 it is between the summer season, which the gardens' own page places through 20 September, and Halloween, which opens on 2 October.",
        "ip": "No ride branding is the subject. Any small ornament on the gate is architectural and is not treated as cleared trademark artwork. Internal review only, not a legal certification.",
        "visual": "Pass. Shut gate, dark trees, empty street. An earlier wide frame showed colored ride light inside the closed park and was replaced before publish. No Halloween and no Christmas.",
        "swap": "No location swap. The scene stays Tivoli Gardens. It is depicted closed, because the summer season had ended and Halloween had not opened.",
    },
    {
        "entry_id": "DK-01-018",
        "region": "Capital Region",
        "city": "Copenhagen",
        "caption": "Str\u00f8get, Copenhagen",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 13.9\u00b0C, cloud cover 42%, wind 4.7 km/h, no precipitation.",
        "weather_brief": "mainly clear, 13.9\u00b0C",
        "composition": "Empty pedestrian street at Amagertorv \u00b7 AI-generated artistic interpretation",
        "description": "The view looks along Str\u00f8get at Amagertorv, a wide pedestrian street of historic facades and warm shop windows. The paving is empty at this hour. It is mainly clear, about 13.9\u00b0C, with little wind and no rain. Small lettering in the windows is not treated as real shop signage.",
        "alt_text": "AI-generated artistic interpretation of Str\u00f8get in Copenhagen at night, an empty pedestrian street of historic facades",
        "viewpoint": "On Str\u00f8get at Amagertorv, looking along the pedestrian street. Approximate researched point 55.6786, 12.5790, not a surveyed camera.",
        "refs": [
            "https://www.visitcopenhagen.com/copenhagen/planning/stroget-gdk414471",
            "https://en.wikipedia.org/wiki/Str%C3%B8get",
        ],
        "anchors": [
            "Wide paved pedestrian street with no carriageway.",
            "Historic facades on both sides and warm windows.",
            "Empty midnight paving under streetlamps.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:03 Europe/Copenhagen. Cloud cover 42%. Streetlamps carry the scene.",
        "independent": "Str\u00f8get is the pedestrian sequence from R\u00e5dhuspladsen to Kongens Nytorv. Amagertorv is the square along it with the Stork Fountain.",
        "ip": "Shopfront lettering is not treated as real signage and no brand is the subject. Internal review only, not a legal certification.",
        "visual": "Pass. Pedestrian street, historic facades, empty night. Not Nyhavn.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-019",
        "region": "Capital Region",
        "city": "Copenhagen",
        "caption": "Christiansborg Palace, Copenhagen",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 14.0\u00b0C, cloud cover 41%, wind 5.0 km/h, no precipitation.",
        "weather_brief": "mainly clear, 14.0\u00b0C",
        "composition": "Copper spire and stone wings across the canal \u00b7 AI-generated artistic interpretation",
        "description": "From the canal by the Marble Bridge, Christiansborg's pale stone wings and tall copper-green spire stand over the dark water. A few lamps break on the canal. The night is mainly clear, about 14.0\u00b0C, and the quay is empty. This is the exterior only. Whether a flag was flying was not verified, so no large flag is claimed.",
        "alt_text": "AI-generated artistic interpretation of Christiansborg Palace in Copenhagen at night, seen across the canal",
        "viewpoint": "Canal edge beside Marmorbroen, looking at the palace tower. Approximate researched point 55.6763, 12.5794, not a surveyed camera.",
        "refs": [
            "https://www.visitcopenhagen.com/copenhagen/planning/christiansborg-palace-gdk420896",
            "https://en.wikipedia.org/wiki/Christiansborg_Palace",
        ],
        "anchors": [
            "Pale stone palace wings.",
            "One tall copper-green spire.",
            "Canal water in the foreground and a bridge at the edge.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:03 Europe/Copenhagen. Cloud cover 41%. Facade and quay lamps, not a surveyed lighting plot.",
        "independent": "Christiansborg is the palace on Slotsholmen, recognized from the canal by its stone body and copper tower. The Marble Bridge crosses toward the riding ground.",
        "ip": "No featured commercial logos. Royal emblems, if present, are architectural. Internal review only, not a legal certification.",
        "visual": "Pass. Exterior tower, stone wings, and canal. No interior rooms.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-020",
        "region": "Capital Region",
        "city": "Copenhagen",
        "caption": "Rosenborg Castle, Copenhagen",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 13.6\u00b0C, cloud cover 42%, wind 5.0 km/h, no precipitation.",
        "weather_brief": "mainly clear, 13.6\u00b0C",
        "composition": "Red-brick castle and copper spires across the moat \u00b7 AI-generated artistic interpretation",
        "description": "Across the moat in Kongens Have, Rosenborg is a red-brick Renaissance castle with copper-green spires. The water is dark, and the late-September trees are still mostly green. It is mainly clear, about 13.6\u00b0C, with a few warm windows and an empty path. The portrait is the same single castle, not a row of townhouses.",
        "alt_text": "AI-generated artistic interpretation of Rosenborg Castle in Copenhagen at night, seen across its moat",
        "viewpoint": "Kongens Have side of the moat, the usual exterior of the castle in the water. Address \u00d8ster Voldgade 4A. Approximate researched point 55.6856, 12.5773, not a surveyed camera.",
        "refs": [
            "https://denkongeligesamling.dk/en/rosenborg-castle/",
            "https://en.wikipedia.org/wiki/Rosenborg_Castle",
        ],
        "anchors": [
            "One red-brick castle with several copper-green spires.",
            "Dark moat in the foreground.",
            "Park trees, still mostly green, and an empty path.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:03 Europe/Copenhagen. Cloud cover 42%. A few windows and path lamps.",
        "independent": "Rosenborg is Christian IV's red-brick castle in the King's Garden, surrounded by a moat.",
        "ip": "No featured logos. Internal review only, not a legal certification.",
        "visual": "Pass. Single brick castle, copper spires, and moat. An earlier portrait that read as a row of houses was replaced before publish.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-021",
        "region": "Capital Region",
        "city": "Copenhagen",
        "caption": "Kastellet, Copenhagen",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 13.5\u00b0C, cloud cover 39%, wind 6.1 km/h, no precipitation.",
        "weather_brief": "mainly clear, 13.5\u00b0C",
        "composition": "Red barracks and the rampart windmill \u00b7 AI-generated artistic interpretation",
        "description": "Inside Kastellet, a straight lane of red barracks leads toward the windmill on the rampart, with the moat beside the path. Trees and lamps line the lane. The night is mainly clear, about 13.5\u00b0C, and the paths are empty. The Little Mermaid stands outside the fortress and is not in this frame.",
        "alt_text": "AI-generated artistic interpretation of Kastellet in Copenhagen at night, with red barracks and the rampart windmill",
        "viewpoint": "Inside the star fortress, looking along the barrack lane toward the windmill on the rampart. Approximate researched point 55.6913, 12.5940, not a surveyed camera.",
        "refs": [
            "https://en.wikipedia.org/wiki/Kastellet,_Copenhagen",
            "https://www.openstreetmap.org/#map=17/55.6913/12.5940",
        ],
        "anchors": [
            "Long red barrack buildings with white windows.",
            "A windmill on the green rampart.",
            "Moat water at the side and an empty lane.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:03 Europe/Copenhagen. Cloud cover 39%. Lamps along the lane.",
        "independent": "Kastellet is the star-shaped fortress north of the city center. The red barracks and the windmill on the rampart are the interior view.",
        "ip": "No featured logos. Internal review only, not a legal certification.",
        "visual": "Pass. Barracks, windmill, and moat. Not the Little Mermaid.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-022",
        "region": "Capital Region",
        "city": "Copenhagen",
        "caption": "Christianshavn, Copenhagen",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 14.0\u00b0C, cloud cover 41%, wind 5.0 km/h, no precipitation.",
        "weather_brief": "mainly clear, 14.0\u00b0C",
        "composition": "Canal, houseboats, and low warehouses \u00b7 AI-generated artistic interpretation",
        "description": "From the quay, Christianshavn's canal holds houseboats and low colorful warehouses, with a bridge farther along the water. It is a wider, lower canal than Nyhavn's continuous gabled row. The night is mainly clear, about 14.0\u00b0C, and the cobbles are empty. The spiral church spire is not the subject of this frame.",
        "alt_text": "AI-generated artistic interpretation of a Christianshavn canal in Copenhagen at night, with houseboats and warehouses",
        "viewpoint": "Quay along Christianshavns Kanal, looking along the water and the moored boats. Approximate researched point 55.6742, 12.5918, not a surveyed camera.",
        "refs": [
            "https://en.wikipedia.org/wiki/Christianshavn",
            "https://www.visitcopenhagen.com/copenhagen/planning/travel-info/36-hours-in-copenhagen-a-local-take-on-the-city",
        ],
        "anchors": [
            "Canal water with houseboats and small boats.",
            "Lower colorful warehouses, not Nyhavn's tall gable wall.",
            "A bridge in the distance and an empty cobbled quay.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:03 Europe/Copenhagen. Cloud cover 41%. Lamps on the water.",
        "independent": "Christianshavn is the canal quarter east of the inner harbour. Houseboats and warehouses line Christianshavns Kanal.",
        "ip": "No readable shop names intended. Internal review only, not a legal certification.",
        "visual": "Pass. Houseboats and a lower canal. Distinct from Nyhavn and from the spiral-spire scene.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-023",
        "region": "Capital Region",
        "city": "Copenhagen",
        "caption": "Opera House, Copenhagen",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 13.9\u00b0C, cloud cover 41%, wind 5.0 km/h, no precipitation.",
        "weather_brief": "mainly clear, 13.9\u00b0C",
        "composition": "Flat overhanging roof and glass front across the harbour \u00b7 AI-generated artistic interpretation",
        "description": "From the harbour, the Opera House shows a long glass front under one flat roof that cantilevers over the water. Dark water fills the foreground. It is mainly clear, about 13.9\u00b0C, and the quay is empty. The auditorium is not shown. The roof is a single slab, not a cluster of shells.",
        "alt_text": "AI-generated artistic interpretation of the Copenhagen Opera House at night, seen across the harbour",
        "viewpoint": "Harbour viewpoint from the Ofelia Plads side of the inner harbour, looking across the water at the opera exterior. The building stands on Dok\u00f8en. Approximate researched point 55.6797, 12.5955, not a surveyed camera.",
        "refs": [
            "https://en.wikipedia.org/wiki/Copenhagen_Opera_House",
            "https://www.visitcopenhagen.com/copenhagen/planning/inspiration/72-hours-in-copenhagen",
        ],
        "anchors": [
            "One wide flat roof overhanging the water.",
            "A long glass facade beneath the roof.",
            "Dark harbour water in the foreground.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:03 Europe/Copenhagen. Cloud cover 41%. The glass front is gently lit.",
        "independent": "The Copenhagen Opera House is the harbour building on Dok\u00f8en, seen from across the inner harbour as a glass front under a cantilevered roof.",
        "ip": "Exterior architecture only. No performance imagery and no logos. Internal review only, not a legal certification.",
        "visual": "Pass. Flat roof, glass, and harbour. Not a sail-shell opera house and not an interior.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-024",
        "region": "Capital Region",
        "city": "Copenhagen",
        "caption": "Rundet\u00e5rn, Copenhagen",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 13.9\u00b0C, cloud cover 42%, wind 4.7 km/h, no precipitation.",
        "weather_brief": "mainly clear, 13.9\u00b0C",
        "composition": "Round brick tower and observatory lantern on K\u00f8bmagergade \u00b7 AI-generated artistic interpretation",
        "description": "On K\u00f8bmagergade, Rundet\u00e5rn is a round brick tower beside the church gable, with the observatory lantern and railing at the top. The street is empty under lamps. The night is mainly clear, about 13.9\u00b0C. The golden band on the tower is ornament in this frame, not a readable inscription.",
        "alt_text": "AI-generated artistic interpretation of Rundet\u00e5rn in Copenhagen at night, a round brick tower with an observatory lantern",
        "viewpoint": "K\u00f8bmagergade at the foot of the tower, looking up at the cylinder and the Trinitatis church wall. Address K\u00f8bmagergade 52A. Approximate researched point 55.6813, 12.5758, not a surveyed camera.",
        "refs": [
            "https://en.wikipedia.org/wiki/Rundet%C3%A5rn",
            "https://en.wikipedia.org/wiki/Trinitatis_Church",
        ],
        "anchors": [
            "A cylindrical red-brick tower, not a church spire.",
            "Observatory lantern and railing at the top.",
            "Church gable beside the tower and empty cobbles below.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:03 Europe/Copenhagen. Cloud cover 42%. Streetlamps.",
        "independent": "Rundet\u00e5rn is the round brick observatory tower on K\u00f8bmagergade, built against Trinitatis Church. The golden rebus band circles the upper brick.",
        "ip": "The rebus is not presented as readable text. No logos. Internal review only, not a legal certification.",
        "visual": "Pass. Round tower, lantern, and church wall. Glyptotek was not used.",
        "swap": "Catalogue choice, not a blocked site. The brief allowed Ny Carlsberg Glyptotek or Rundet\u00e5rn and preferred the Round Tower if the museum front felt logo-heavy. This scene is Rundet\u00e5rn.",
    },
    {
        "entry_id": "DK-01-025",
        "region": "Capital Region",
        "city": "Copenhagen",
        "caption": "Church of Our Saviour, Copenhagen",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 14.0\u00b0C, cloud cover 41%, wind 5.0 km/h, no precipitation.",
        "weather_brief": "mainly clear, 14.0\u00b0C",
        "composition": "Gilded external spiral stair on the spire \u00b7 AI-generated artistic interpretation",
        "description": "The exterior spire of the Church of Our Saviour rises over Christianshavn, wrapped in an open gilded spiral stair, with a small figure at the tip. The stair is empty because it is closed at this hour. It is mainly clear, about 14.0\u00b0C. The church interior is not shown.",
        "alt_text": "AI-generated artistic interpretation of the Church of Our Saviour in Copenhagen at night, with its gilded spiral stair",
        "viewpoint": "Street level in Christianshavn, looking up at the exterior helix. The church address is Sankt Ann\u00e6 Gade 29. Approximate researched point 55.6727, 12.5936, not a surveyed camera.",
        "refs": [
            "https://www.vorfrelserskirke.dk/",
            "https://en.wikipedia.org/wiki/Church_of_Our_Saviour,_Copenhagen",
        ],
        "anchors": [
            "An external open spiral staircase wrapping the spire.",
            "Gilded stair against a dark tower.",
            "A small figure at the tip, and no one climbing.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:03 Europe/Copenhagen. Cloud cover 41%. The gilded stair catches ambient light.",
        "independent": "Vor Frelsers Kirke in Christianshavn is known for the external helical stair on its spire and the figure at the top.",
        "ip": "Exterior architecture only. No interior artwork. Internal review only, not a legal certification.",
        "visual": "Pass. External helix and a figure at the tip. An earlier wide frame put an animal ornament on the spire and was replaced before publish.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-026",
        "region": "Capital Region",
        "city": "Copenhagen",
        "caption": "Islands Brygge, Copenhagen",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 14.0\u00b0C, cloud cover 43%, wind 5.0 km/h, no precipitation.",
        "weather_brief": "mainly clear, 14.0\u00b0C",
        "composition": "Empty harbour-bath decks on the public quay \u00b7 AI-generated artistic interpretation",
        "description": "On the public quay at Islands Brygge, the wooden harbour-bath decks are empty over dark water, with promenade lamps and brick buildings along the shore. City lights sit across the harbour. It is mainly clear, about 14.0\u00b0C. The bath's published hours run from 06:00 to 22:00, so there are no swimmers at this hour.",
        "alt_text": "AI-generated artistic interpretation of the Islands Brygge waterfront in Copenhagen at night, with empty harbour-bath decks",
        "viewpoint": "Public promenade beside Havnebadet Islands Brygge, looking across the harbour. Address Islands Brygge 14, 2300 Copenhagen S. Approximate researched point 55.6668, 12.5785, not a surveyed camera.",
        "refs": [
            "https://svoemkbh.kk.dk/en/node/14",
            "https://en.wikipedia.org/wiki/Islands_Brygge",
        ],
        "anchors": [
            "Wooden harbour-bath decks with no swimmers.",
            "Paved public promenade and brick quay buildings.",
            "Dark harbour and distant city lights.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:03 Europe/Copenhagen. Cloud cover 43%. Promenade lamps.",
        "independent": "Islands Brygge is the public harbour quay south of the inner city. The wooden harbour bath stays on the water after the lifeguard season, and its posted hours end at 22:00.",
        "ip": "Public waterfront only. No private interiors and no logos. Internal review only, not a legal certification.",
        "visual": "Pass. Empty decks, quay, and harbour. No swimmers.",
        "swap": "Catalogue choice, not a blocked site. The brief allowed a Christiania public-street exterior or Islands Brygge and preferred the public waterfront. Christiania interiors were not depicted. This scene is Islands Brygge.",
    },
    {
        "entry_id": "DK-01-027",
        "region": "Capital Region",
        "city": "Humleb\u00e6k",
        "caption": "Louisiana Museum, Humleb\u00e6k",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 13.3\u00b0C, cloud cover 35%, wind 8.3 km/h, no precipitation.",
        "weather_brief": "mainly clear, 13.3\u00b0C",
        "composition": "Low white pavilions and the \u00d8resund \u00b7 AI-generated artistic interpretation",
        "description": "From the grounds, Louisiana's low white pavilions and glass step toward a dark lawn and the \u00d8resund. A few windows are lit and the museum is closed for the night. It is mainly clear, about 13.3\u00b0C, with a breeze near 8 km/h. No sculpture from the collection is used as the subject.",
        "alt_text": "AI-generated artistic interpretation of the Louisiana Museum exterior in Humleb\u00e6k at night, with low white buildings and the sea",
        "viewpoint": "Exterior grounds looking across the low wings toward the Sound. Address Gl. Strandvej 13, 3050 Humleb\u00e6k. Approximate researched point 55.9690, 12.5430, not a surveyed camera.",
        "refs": [
            "https://louisiana.dk/en/museum/architecture-and-history/",
            "https://en.wikipedia.org/wiki/Louisiana_Museum_of_Modern_Art",
        ],
        "anchors": [
            "Low horizontal white modernist buildings.",
            "Lawn and trees between the wings and the water.",
            "Dark \u00d8resund horizon, no sculpture as the subject.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:03 Europe/Copenhagen along this coast. Cloud cover 35%. A few window lights.",
        "independent": "Louisiana is the low modernist museum at Humleb\u00e6k, set on the lawn above the \u00d8resund. The town is Humleb\u00e6k, in Fredensborg Municipality.",
        "ip": "Exterior architecture and landscape only. Collection works are not depicted. Third-party rights in those works are not waived. Internal review only, not a legal certification.",
        "visual": "Pass. White pavilions, lawn, and sea. No focal sculpture.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-028",
        "region": "Capital Region",
        "city": "Fredensborg",
        "caption": "Fredensborg Palace, Fredensborg",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 12.2\u00b0C, cloud cover 44%, wind 4.3 km/h, no precipitation.",
        "weather_brief": "mainly clear, 12.2\u00b0C",
        "composition": "Pale baroque palace and one copper dome \u00b7 AI-generated artistic interpretation",
        "description": "From the garden axis, Fredensborg is a pale baroque palace with one central copper dome, low hedges in front, and a dark avenue at the sides. A few windows are lit. The night is mainly clear, about 12.2\u00b0C, and the garden is empty. It does not have Frederiksborg's red-brick lake silhouette.",
        "alt_text": "AI-generated artistic interpretation of Fredensborg Palace at night, a pale baroque building with one copper dome",
        "viewpoint": "Public garden axis toward the palace exterior, the Brede All\u00e9 approach. Approximate researched point 55.9823, 12.3974, not a surveyed camera. Interior rooms are not shown.",
        "refs": [
            "https://www.kongehuset.dk/en/palaces-and-the-royal-yacht/fredensborg-palace/",
            "https://en.wikipedia.org/wiki/Fredensborg_Palace",
        ],
        "anchors": [
            "One symmetrical pale palace.",
            "A single central copper dome, not a cluster of spires.",
            "Formal hedges and a dark avenue, empty at night.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:04 Europe/Copenhagen. Cloud cover 44%. A few lit windows.",
        "independent": "Fredensborg Palace is the baroque palace by Esrum Lake, known from the garden by its pale walls and central dome. The public garden is separate from the summer interior tours.",
        "ip": "Exterior only. No interior artwork. Internal review only, not a legal certification.",
        "visual": "Pass. Pale palace and one dome. Distinct from Frederiksborg Castle in Hiller\u00f8d.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-029",
        "region": "Capital Region",
        "city": "Helsing\u00f8r",
        "caption": "Maritime Museum, Helsing\u00f8r",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 14.8\u00b0C, cloud cover 43%, wind 10.8 km/h, no precipitation.",
        "weather_brief": "mainly clear, 14.8\u00b0C",
        "composition": "Old shipyard dry dock and glass bridges \u00b7 AI-generated artistic interpretation",
        "description": "The old shipyard dry dock in Helsing\u00f8r is an open concrete void crossed by angular glass-and-steel bridges. Lamps pick out the dock walls and the surrounding paving. It is mainly clear, about 14.8\u00b0C, with wind near 11 km/h, and the dock is empty. Kronborg's towers are outside this frame.",
        "alt_text": "AI-generated artistic interpretation of the Maritime Museum dry dock in Helsing\u00f8r at night, with glass bridges",
        "viewpoint": "Edge of the preserved dry dock at the M/S Maritime Museum, looking along the void and the bridges. Address Ny Kronborgvej 1, 3000 Helsing\u00f8r. Approximate researched point 56.0391, 12.6161, not a surveyed camera.",
        "refs": [
            "https://mfs.dk/en/opening-hours-and-prices",
            "https://en.wikipedia.org/wiki/M/S_Maritime_Museum_of_Denmark",
        ],
        "anchors": [
            "A long sunken concrete dry dock open to the sky.",
            "Angular glass-and-steel bridges crossing the void.",
            "Shipyard paving, and no castle spires.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:03 Europe/Copenhagen. Cloud cover 43%. Dock lamps.",
        "independent": "The Maritime Museum sits around the old Helsing\u00f8r shipyard dry dock. The dock was left open and is crossed by bridges. It is a different subject from Kronborg, which is already DK-01-004.",
        "ip": "Exterior of the dock and bridges only. No interior exhibitions and no logos. Internal review only, not a legal certification.",
        "visual": "Pass. Dry dock and glass bridges. Kronborg is not in the frame.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-030",
        "region": "Capital Region",
        "city": "Drag\u00f8r",
        "caption": "Drag\u00f8r Harbour, Drag\u00f8r",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 12.3\u00b0C, cloud cover 35%, wind 6.1 km/h, no precipitation.",
        "weather_brief": "mainly clear, 12.3\u00b0C",
        "composition": "Yellow cottages and the small fishing harbour \u00b7 AI-generated artistic interpretation",
        "description": "Drag\u00f8r's old harbour is a cobbled quay of yellow limewashed cottages with red tile roofs and a few wooden boats. Lamps warm the empty lane. The night is mainly clear, about 12.3\u00b0C. This is the village harbour, not a modern marina, and small lettering is not treated as real signage.",
        "alt_text": "AI-generated artistic interpretation of Drag\u00f8r harbour at night, with yellow cottages and wooden boats",
        "viewpoint": "The old harbour quay among the yellow cottages. Approximate researched point 55.5945, 12.6660, not a surveyed camera.",
        "refs": [
            "https://en.wikipedia.org/wiki/Drag%C3%B8r",
            "https://www.visitcopenhagen.com/files/visitcopenhagen.com/2026-05/dragor_2026_guide_.pdf",
        ],
        "anchors": [
            "Low yellow limewashed cottages with red tile roofs.",
            "A small harbour basin and wooden boats.",
            "Cobbled quay, empty, with no high-rise marina.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:03 Europe/Copenhagen at nearby Copenhagen. Cloud cover 35%. Quay lamps.",
        "independent": "Drag\u00f8r is the old fishing and skipper town on the east side of Amager, with yellow cottages around its harbour.",
        "ip": "No featured logos. Any small lettering is not treated as real signage. Internal review only, not a legal certification.",
        "visual": "Pass. Yellow cottages, cobbles, and a small harbour.",
        "swap": "No site swap. Region note: the kit coverage row lists Drag\u00f8r with Zealand attractions. Drag\u00f8r Municipality is in the Capital Region of Denmark, on Amager, so the gallery region is Capital Region and the city folder is Drag\u00f8r.",
    },
    {
        "entry_id": "DK-01-031",
        "region": "Zealand",
        "city": "K\u00f8ge",
        "caption": "K\u00f8ge Old Town, K\u00f8ge",
        "weather_prefix": WEATHER,
        "weather_detail": "Partly cloudy, 11.6\u00b0C, cloud cover 76%, wind 9.0 km/h, no precipitation.",
        "weather_brief": "partly cloudy, 11.6\u00b0C",
        "composition": "Half-timbered houses around the old square \u00b7 AI-generated artistic interpretation",
        "description": "K\u00f8ge's old-town square is half-timbered houses and red tile roofs around the cobbles. Cloud cover is about 76%, so the sky is dark and the moon is mostly hidden, and the timber is lit by streetlamps. It is about 11.6\u00b0C, with no rain, and the square is empty. Small lettering is not treated as real signage.",
        "alt_text": "AI-generated artistic interpretation of K\u00f8ge old town at night, half-timbered houses under a cloudy sky",
        "viewpoint": "The old-town square, Torvet, looking across the cobbles at the half-timbered fronts. Approximate researched point 55.4582, 12.1824, not a surveyed camera.",
        "refs": [
            "https://en.wikipedia.org/wiki/K%C3%B8ge",
            "https://www.visitkoege.com/",
        ],
        "anchors": [
            "Half-timbered houses with red tile roofs.",
            "A cobbled square.",
            "A dark cloudy sky and streetlamps, with no modern mall.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:05 Europe/Copenhagen. Cloud cover 76%, so lamp light dominates.",
        "independent": "K\u00f8ge's old town is the half-timbered center around Torvet, on the K\u00f8ge Bay coast of Zealand.",
        "ip": "No featured logos. Internal review only, not a legal certification.",
        "visual": "Pass. Half-timbered square under heavy cloud. Not Ribe and not Den Gamle By.",
        "swap": None,
    },
    {
        "entry_id": "DK-01-032",
        "region": "Zealand",
        "city": "Store Heddinge",
        "caption": "Stevns Klint, Store Heddinge",
        "weather_prefix": WEATHER,
        "weather_detail": "Mainly clear, 11.4\u00b0C, cloud cover 37%, wind 6.8 km/h, no precipitation.",
        "weather_brief": "mainly clear, 11.4\u00b0C",
        "composition": "Truncated chalk church on the cliff edge \u00b7 AI-generated artistic interpretation",
        "description": "At H\u00f8jerup, the old chalk church of Stevns Klint stands on the grass at the cliff edge, cut off where the choir fell toward the sea. White chalk drops to the dark Baltic. The night is mainly clear, about 11.4\u00b0C, and the cliff path is empty. This is not the beech-lined cliff at M\u00f8ns Klint, which has no church on the rim.",
        "alt_text": "AI-generated artistic interpretation of Stevns Klint at night, with the truncated church on the chalk cliff",
        "viewpoint": "Cliff-edge path beside H\u00f8jerup old church, looking along the truncated church and the chalk face. Address H\u00f8jerup Bygade 30, 4660 Store Heddinge. Approximate researched point 55.2791, 12.4457, not a surveyed camera.",
        "refs": [
            "https://en.wikipedia.org/wiki/Stevns_Klint",
            "https://xn--hjeruplund-0cb.dk/en/hoejerup-old-church-opening-hours/",
        ],
        "anchors": [
            "A small chalk church with the seaward end missing.",
            "White cliff falling to a dark beach and the Baltic.",
            "Grass cliff top, empty, with no visitor center as the subject.",
        ],
        "solar": "Night. Sunset on 24 September 2026 was 19:04 Europe/Copenhagen. Cloud cover 37%, so some moonlight on the chalk is plausible. Not surveyed on site.",
        "independent": "Stevns Klint is the chalk cliff on the Stevns peninsula. The landmark at the edge is H\u00f8jerup old church, whose choir fell in 1928.",
        "ip": "No logos. Internal review only, not a legal certification.",
        "visual": "Pass. Truncated church and chalk cliff. Distinct from M\u00f8ns Klint.",
        "swap": "City verified, not a site swap. The viewpoint is the hamlet of H\u00f8jerup. The postal town on the church address is 4660 Store Heddinge. Stevns is the municipality, not the town used in the caption. Gallery region is Zealand, matching Region Sj\u00e6lland and the kit coverage row.",
    },
]


def load_all_scenes() -> list:
    scenes = []
    for path in sorted((bd.ROOT / "manifests").glob("DK-01-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        scenes.append({"_manifest": data})
    scenes.sort(key=lambda item: item["_manifest"]["entry_id"])
    return scenes


def main() -> None:
    if len(SCENES) != 16:
        raise SystemExit(len(SCENES))
    lines = []
    for scene in SCENES:
        label = bd.scenario_label(scene["entry_id"])
        bd.write_outputs(scene, label)
        bd.manifest(scene, label)
        bd.approval(scene, label)
        entry = scene["entry_id"].lower()
        city = scene["city"]
        lines.append(
            f"**{scene['entry_id']} \u2014 {scene['caption']}** \u00b7 Scenario: {label} \u00b7 "
            f"Weather: {scene['weather_prefix']} {scene['weather_detail']} \u00b7 "
            f"Masters: `Denmark/{city}/{entry}-16x9.png`, `Denmark/{city}/{entry}-4x5.png` \u00b7 Gates: 5/5 pass."
        )
        print(lines[-1])
    all_scenes = load_all_scenes()
    if len(all_scenes) != 32:
        raise SystemExit(f"expected 32 manifests, got {len(all_scenes)}")
    ids = [item["_manifest"]["entry_id"] for item in all_scenes]
    expected = [f"DK-01-{n:03d}" for n in range(1, 33)]
    if ids != expected:
        raise SystemExit(ids)
    bd.write_site(all_scenes)
    report = bd.ROOT / "approvals" / "BATCH-DK-01-017-032.txt"
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("site written", len(all_scenes))


if __name__ == "__main__":
    main()
