"""MyAnimeList id lookup via Jikan API v4."""

from __future__ import annotations

import time

import requests

JIKAN_SEARCH_URL = "https://api.jikan.moe/v4/anime"
JIKAN_DELAY_SECONDS = 1.0
USER_AGENT = "shinden-to-anilist/1.0"


def search_mal_id(title: str, session: requests.Session | None = None) -> int | None:
    sess = session or requests.Session()
    if not session:
        sess.headers["User-Agent"] = USER_AGENT

    response = sess.get(
        JIKAN_SEARCH_URL,
        params={"q": title, "limit": 1},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json().get("data") or []
    if not data:
        return None
    mal_id = data[0].get("mal_id")
    return int(mal_id) if mal_id is not None else None


def search_mal_id_with_delay(
    title: str,
    session: requests.Session | None = None,
    *,
    delay_seconds: float = JIKAN_DELAY_SECONDS,
) -> int | None:
    mal_id = search_mal_id(title, session)
    time.sleep(delay_seconds)
    return mal_id
