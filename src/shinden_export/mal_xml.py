"""Build MyAnimeList-compatible XML for AniList import."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.dom import minidom

from shinden_export.models import AnimeEntry


def build_xml(entries: list[AnimeEntry]) -> str:
    root = ET.Element("myanimelist")

    for entry in entries:
        if entry.mal_id is None:
            continue
        anime = ET.SubElement(root, "anime")
        ET.SubElement(anime, "series_animedb_id").text = str(entry.mal_id)
        ET.SubElement(anime, "series_title").text = entry.title
        ET.SubElement(anime, "my_watched_episodes").text = str(entry.episodes_watched)
        ET.SubElement(anime, "my_score").text = str(entry.score)
        ET.SubElement(anime, "my_status").text = str(entry.status)
        ET.SubElement(anime, "update_on_import").text = "1"

    rough = ET.tostring(root, encoding="unicode")
    parsed = minidom.parseString(rough)
    return parsed.toprettyxml(indent="    ", encoding="UTF-8").decode("utf-8")
