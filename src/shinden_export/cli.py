"""Command-line interface."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

from shinden_export import __version__
from shinden_export.jikan import search_mal_id_with_delay
from shinden_export.mal_xml import build_xml
from shinden_export.models import AnimeEntry
from shinden_export.shinden import (
    collect_anime_rows,
    mal_status_from_watch_status,
    default_mal_status_for_slug,
    parse_list_url,
)


DEFAULT_OUTPUT = "shinden_export.xml"
DEFAULT_LIST_URL = "https://lista.shinden.pl/animelist/103810-teoroki"


def _prompt_list_url() -> str:
    print("Shinden → MyAnimeList XML exporter")
    print(f"Example: {DEFAULT_LIST_URL}")
    url = input("Paste your public Shinden animelist URL: ").strip()
    if not url:
        raise SystemExit("No URL provided.")
    return url


def _rows_to_entries(rows, default_mal: int) -> list[AnimeEntry]:
    entries: list[AnimeEntry] = []
    for row in rows:
        status = mal_status_from_watch_status(row.watch_status, default_mal)
        score = row.score if row.score is not None else 0
        entries.append(
            AnimeEntry(
                title=row.title,
                status=status,
                episodes_watched=row.episodes_watched,
                score=score,
            )
        )
    return entries


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Export a public Shinden.pl animelist to MAL XML for AniList import.",
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="Public animelist URL (interactive prompt if omitted)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Output XML path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--all-statuses",
        action="store_true",
        help="Export every list section (watching, completed, plan, etc.)",
    )
    parser.add_argument(
        "--no-jikan",
        action="store_true",
        help="Skip Jikan lookups (XML will be empty without mal_id)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    args = parser.parse_args(argv)

    list_url = args.url or _prompt_list_url()
    parse_list_url(list_url)  # validate early

    print(f"Fetching list: {list_url}")
    target, rows = collect_anime_rows(list_url, all_statuses=args.all_statuses)
    if not rows:
        print("No anime entries found.", file=sys.stderr)
        return 1

    default_mal = default_mal_status_for_slug(target.status_slug)
    entries = _rows_to_entries(rows, default_mal)

    skipped: list[str] = []
    if not args.no_jikan:
        session = requests.Session()
        print(f"Looking up {len(entries)} titles on Jikan (1 req/s)...")
        for i, entry in enumerate(entries, start=1):
            print(f"  [{i}/{len(entries)}] {entry.title}")
            try:
                entry.mal_id = search_mal_id_with_delay(entry.title, session)
            except requests.RequestException as exc:
                print(f"    Jikan error: {exc}", file=sys.stderr)
                entry.mal_id = None
            if entry.mal_id is None:
                skipped.append(entry.title)
                print("    No MAL match — skipped", file=sys.stderr)

    xml_text = build_xml(entries)
    out_path = Path(args.output)
    out_path.write_text(xml_text, encoding="utf-8")

    exported = sum(1 for e in entries if e.mal_id is not None)
    print(f"\nWrote {exported} anime to {out_path.resolve()}")
    if skipped:
        print(f"Skipped {len(skipped)} titles without a Jikan match:", file=sys.stderr)
        for title in skipped:
            print(f"  - {title}", file=sys.stderr)
    print("\nImport at: https://anilist.co/settings/import")
    return 0 if exported else 1


def main() -> None:
    raise SystemExit(run())
