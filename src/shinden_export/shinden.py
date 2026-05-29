"""Fetch and parse public Shinden animelist pages."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

SHINDEN_LIST_URL_RE = re.compile(
    r"^https?://lista\.shinden\.pl/animelist/(?P<user_id>\d+)-(?P<nickname>[^/?#]+)"
    r"(?:/(?P<status>in-progress|completed|hold|dropped|plan|skip|all))?/?$",
    re.IGNORECASE,
)

URL_STATUS_TO_API: dict[str, str] = {
    "in-progress": "in-progress",
    "completed": "completed",
    "hold": "hold",
    "dropped": "dropped",
    "plan": "plan",
    "skip": "skip",
}

# Polish sidebar labels (HTML) and API watchStatus values -> MAL status id
POLISH_STATUS_TO_MAL: dict[str, int] = {
    "obejrzane": 1,
    "completed": 1,
    "oglądam": 2,
    "ogladam": 2,
    "in progress": 2,
    "in-progress": 2,
    "inprogress": 2,
    "wstrzymane": 3,
    "hold": 3,
    "porzucone": 4,
    "dropped": 4,
    "planowane": 6,
    "planuję": 6,
    "planuje": 6,
    "plan": 6,
    "pomijam": 4,  # Shinden "skip" — no MAL equivalent; treat as dropped
    "skip": 4,
}

API_STATUSES = ("in-progress", "completed", "hold", "dropped", "plan", "skip")

LIST_API_BASE = "https://lista.shinden.pl/api/userlist"
USER_AGENT = (
    "Mozilla/5.0 (compatible; shinden-to-anilist/1.0; +https://github.com/)"
)


@dataclass(frozen=True)
class ListTarget:
    user_id: int
    nickname: str
    status_slug: str | None


@dataclass
class RawAnimeRow:
    title: str
    watch_status: str
    episodes_watched: int
    score: int | None


def parse_list_url(url: str) -> ListTarget:
    url = url.strip()
    match = SHINDEN_LIST_URL_RE.match(url)
    if not match:
        raise ValueError(
            "Invalid Shinden list URL. Expected format: "
            "https://lista.shinden.pl/animelist/123456-nickname "
            "or .../animelist/123456-nickname/in-progress"
        )
    return ListTarget(
        user_id=int(match.group("user_id")),
        nickname=match.group("nickname"),
        status_slug=match.group("status"),
    )


def mal_status_from_watch_status(watch_status: str, fallback: int) -> int:
    key = watch_status.strip().lower()
    return POLISH_STATUS_TO_MAL.get(key, fallback)


def mal_status_from_polish_label(label: str, fallback: int) -> int:
    key = label.strip().lower()
    return POLISH_STATUS_TO_MAL.get(key, fallback)


def _session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    return session


def fetch_page_html(url: str, session: requests.Session | None = None) -> str:
    sess = session or _session()
    response = sess.get(url, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def parse_next_data_user(html: str) -> dict | None:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return None
    payload = json.loads(script.string)
    return payload.get("props", {}).get("pageProps", {}).get("user")


def parse_table_rows(html: str, default_status: int) -> list[RawAnimeRow]:
    """Parse anime rows from server-rendered HTML when present."""
    soup = BeautifulSoup(html, "html.parser")
    rows: list[RawAnimeRow] = []

    for row in soup.select('[class*="table-row"], tr[data-title-id], .listMobile > div'):
        title_el = row.select_one("a[href*='/series/'], .title a, [class*='title'] a")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        if not title:
            continue

        status_text = ""
        status_el = row.select_one("[class*='status'], [data-status]")
        if status_el:
            status_text = status_el.get_text(strip=True)

        episodes = 0
        ep_el = row.select_one("[class*='episode'], [class*='progress']")
        if ep_el:
            ep_match = re.search(r"(\d+)", ep_el.get_text())
            if ep_match:
                episodes = int(ep_match.group(1))

        score = None
        score_el = row.select_one("[class*='ratio'], [class*='score'], [class*='rate']")
        if score_el:
            score_match = re.search(r"(\d+(?:[.,]\d+)?)", score_el.get_text())
            if score_match:
                score = int(round(float(score_match.group(1).replace(",", "."))))

        rows.append(
            RawAnimeRow(
                title=title,
                watch_status=status_text or "",
                episodes_watched=episodes,
                score=score,
            )
        )

    if rows:
        for row in rows:
            if not row.watch_status:
                row.watch_status = _mal_to_api_watch_status(default_status)
    return rows


def _mal_to_api_watch_status(mal_status: int) -> str:
    return {
        1: "completed",
        2: "in progress",
        3: "hold",
        4: "dropped",
        6: "plan",
    }.get(mal_status, "in progress")


def default_mal_status_for_slug(slug: str | None) -> int:
    if not slug or slug == "all":
        return 2
    mapping = {
        "in-progress": 2,
        "completed": 1,
        "hold": 3,
        "dropped": 4,
        "plan": 6,
        "skip": 4,
    }
    return mapping.get(slug, 2)


def fetch_api_page(
    user_id: int,
    status_slug: str,
    offset: int,
    limit: int,
    session: requests.Session,
) -> dict:
    url = f"{LIST_API_BASE}/{user_id}/anime/{status_slug}"
    params = {"offset": offset, "limit": limit}
    response = session.get(url, params=params, timeout=30)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("success"):
        raise RuntimeError(payload.get("message", "Shinden API request failed"))
    return payload["result"]


def fetch_list_from_api(
    user_id: int,
    status_slug: str,
    session: requests.Session,
    page_size: int = 100,
) -> list[RawAnimeRow]:
    rows: list[RawAnimeRow] = []
    offset = 0
    default_mal = default_mal_status_for_slug(status_slug)

    while True:
        result = fetch_api_page(user_id, status_slug, offset, page_size, session)
        items = result.get("items") or []
        for item in items:
            score_raw = item.get("rateTotal")
            score: int | None = None
            if score_raw is not None and str(score_raw).strip():
                score = int(round(float(score_raw)))

            watched_raw = item.get("watchedEpisodesCnt", 0)
            try:
                episodes = int(watched_raw)
            except (TypeError, ValueError):
                episodes = 0

            watch_status = item.get("watchStatus") or ""
            rows.append(
                RawAnimeRow(
                    title=item.get("title", "").strip(),
                    watch_status=watch_status,
                    episodes_watched=episodes,
                    score=score,
                )
            )

        total = int(result.get("count") or 0)
        offset += len(items)
        if offset >= total or not items:
            break

    if not rows:
        return rows

    for row in rows:
        if not row.watch_status:
            row.watch_status = _mal_to_api_watch_status(default_mal)
    return rows


def resolve_status_slugs(target: ListTarget, all_statuses: bool) -> list[str]:
    if all_statuses or target.status_slug == "all":
        return list(API_STATUSES)
    if target.status_slug:
        return [URL_STATUS_TO_API.get(target.status_slug, target.status_slug)]
    return ["in-progress"]


def collect_anime_rows(
    list_url: str,
    *,
    all_statuses: bool = False,
    session: requests.Session | None = None,
) -> tuple[ListTarget, list[RawAnimeRow]]:
    target = parse_list_url(list_url)
    sess = session or _session()

    html = fetch_page_html(list_url, sess)
    user_meta = parse_next_data_user(html)
    if user_meta:
        profile = user_meta.get("user") or {}
        if profile.get("userId") and int(profile["userId"]) != target.user_id:
            raise ValueError("URL user id does not match profile data from Shinden.")

    slugs = resolve_status_slugs(target, all_statuses)
    default_for_page = default_mal_status_for_slug(target.status_slug)

    rows = parse_table_rows(html, default_for_page)
    if rows:
        for row in rows:
            mal = mal_status_from_polish_label(row.watch_status, default_for_page)
            if mal == default_for_page and row.watch_status:
                mal = mal_status_from_watch_status(row.watch_status, default_for_page)
            row.watch_status = _mal_to_api_watch_status(mal)
        return target, rows

    combined: list[RawAnimeRow] = []
    for slug in slugs:
        combined.extend(fetch_list_from_api(target.user_id, slug, sess))

    return target, combined
