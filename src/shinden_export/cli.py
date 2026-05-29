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
    API_STATUSES,
    collect_anime_rows,
    default_mal_status_for_slug,
    mal_status_from_watch_status,
    parse_list_url,
)

EXAMPLE_LIST_URL = "https://lista.shinden.pl/animelist/123456-nickname"

# CLI label -> (filename segment, Shinden API status slugs)
STATUS_CHOICES: dict[str, tuple[str, list[str]]] = {
    "all": ("all", list(API_STATUSES)),
    "watching": ("watching", ["in-progress"]),
    "completed": ("completed", ["completed"]),
    "on-hold": ("on-hold", ["hold"]),
    "dropped": ("dropped", ["dropped"]),
    "plan": ("plan", ["plan"]),
    "skip": ("skip", ["skip"]),
}


def _prompt_list_url() -> str:
    print("Shinden → MyAnimeList XML exporter")
    print(f"Example: {EXAMPLE_LIST_URL}")
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


def _resolve_export_mode(args: argparse.Namespace) -> tuple[str, list[str]]:
    if args.watching:
        return STATUS_CHOICES["watching"]
    if args.completed:
        return STATUS_CHOICES["completed"]
    if args.on_hold:
        return STATUS_CHOICES["on-hold"]
    if args.dropped:
        return STATUS_CHOICES["dropped"]
    if args.plan:
        return STATUS_CHOICES["plan"]
    if args.skip:
        return STATUS_CHOICES["skip"]
    return STATUS_CHOICES["all"]


def _default_output_path(user_id: int, label: str) -> Path:
    return Path(f"{user_id}_{label}_shinden_export.xml")


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
        help="Output XML path (default: {userId}_{status}_shinden_export.xml)",
    )
    status_group = parser.add_mutually_exclusive_group()
    status_group.add_argument(
        "--watching",
        action="store_true",
        help="Export only “Oglądam” / in-progress titles",
    )
    status_group.add_argument(
        "--completed",
        action="store_true",
        help="Export only “Obejrzane” / completed titles",
    )
    status_group.add_argument(
        "--on-hold",
        action="store_true",
        help="Export only “Wstrzymane” / on-hold titles",
    )
    status_group.add_argument(
        "--dropped",
        action="store_true",
        help="Export only “Porzucone” / dropped titles",
    )
    status_group.add_argument(
        "--plan",
        action="store_true",
        help="Export only “Planuję” / plan to watch titles",
    )
    status_group.add_argument(
        "--skip",
        action="store_true",
        help="Export only “Pomijam” / skipped titles",
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
    target = parse_list_url(list_url)

    export_label, status_slugs = _resolve_export_mode(args)
    out_path = Path(args.output) if args.output else _default_output_path(
        target.user_id, export_label
    )

    print(f"Fetching list: {list_url}")
    print(f"Status filter: {export_label}")
    target, rows = collect_anime_rows(list_url, status_slugs=status_slugs)
    if not rows:
        print("No anime entries found.", file=sys.stderr)
        return 1

    default_mal = default_mal_status_for_slug(
        status_slugs[0] if len(status_slugs) == 1 else None
    )
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
